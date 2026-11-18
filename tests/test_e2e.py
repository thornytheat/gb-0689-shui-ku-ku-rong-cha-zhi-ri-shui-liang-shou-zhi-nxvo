from app.pipeline import run
from app.config import SAMPLES
def test_dirty_flow_reconciles(raw,isolate):
    result=run(raw)
    assert len(result["stages"])==7
    assert result["input_count"]==len(result["records"])+len(result["quarantine"])
def test_same_content_is_idempotent(raw,isolate):
    a=run(raw);b=run(raw)
    assert a["manifest"]["run_id"]==b["manifest"]["run_id"]
    assert a["manifest"]["created"]==b["manifest"]["created"]
def test_real_http_modules(client):
    for stage in range(1,8):
        reply=client.get(f"/api/m{stage}")
        assert reply.status_code==200
        assert len(reply.json["stages"])==stage
def test_invalid_csv_is_recoverable(client):
    result=client.post("/api/runs",json={"text":"bad,header\n1,2"})
    assert result.status_code==422
    assert result.json["code"]=="HEADER"
def test_real_pages_and_export(client):
    for stage in range(1,8): assert client.get(f"/m/{stage}").status_code==200
    response=client.get("/api/evidence.csv")
    assert response.status_code==200 and "原因码" in response.text
def test_stale_review_rejected(client):
    r=client.post("/api/runs",json={}).json
    body={"version":r["version"],"decision":"通过"}
    assert client.post("/api/review/"+r["manifest"]["run_id"],json=body).status_code==200
    assert client.post("/api/review/"+r["manifest"]["run_id"],json=body).status_code==409


def test_offset_change_supersedes_old_run(raw, isolate):
    first = run(raw)
    second = run(raw, {'level_offset_m': '-0.01,0.03'})
    assert first['manifest']['run_id'] != second['manifest']['run_id']
    from app import store
    old = store.fetch(first['manifest']['run_id'])
    assert old['stale'] and old['superseded_by'] == second['manifest']['run_id']
    assert old['review'] == '已失效'


def test_rerun_same_batch_adds_nothing(raw, isolate):
    first = run(raw)
    from app import store
    store.review(first['manifest']['run_id'], 1, '通过')
    again = run(raw)
    assert again['manifest']['run_id'] == first['manifest']['run_id']
    assert again['version'] == 2 and again['review'] == '通过'
    assert len(store.history()) == 1


def test_stale_run_cannot_be_reviewed(raw, isolate):
    first = run(raw)
    run(raw, {'level_offset_m': '0.01'})
    reply = __import__('app.main', fromlist=['create_app']).create_app().test_client().post(
        '/api/review/' + first['manifest']['run_id'], json={'version': 1, 'decision': '通过'})
    assert reply.status_code == 409


def test_offset_flows_through_api(client):
    result = client.post('/api/m6', json={'params': {'level_offset_m': '[-0.02,0.02]'}}).json
    assert result['manifest']['params']['level_offset_m'] == '[-0.02,0.02]'
    assert all('residual_low' in row for row in result['review_rows'])
    bad = client.post('/api/m6', json={'params': {'level_offset_m': '0.05,-0.01'}})
    assert bad.status_code == 422 and bad.json['code'] == 'RANGE'


def test_knot_day_not_passed_by_single_value(isolate):
    from app.config import SAMPLES
    raw = (SAMPLES / 'knots.csv').read_bytes()
    single = run(raw, {'level_offset_m': '0'}, stop=6, persist=False)
    assert single['review_rows'][0]['code'] == 'PASS'
    ranged = run(raw, {'level_offset_m': '±0.02'}, stop=6, persist=False)
    row = ranged['review_rows'][0]
    from decimal import Decimal as D
    assert D(row['residual']) == 450
    assert D(row['residual_low']) < 500 < D(row['residual_high'])
    assert row['code'] == 'REVIEW' and row['state'] == '待复核'

import pytest
from decimal import Decimal as D
from app.errors import DomainError
from app.pipeline import run
from app.normalize import instant
from app.modules.m6_review.rules import evaluate

def test_incomplete_priority():
    assert evaluate([{'state':'缺测','residual':D(999)}],D(1))[0]['code']=='GAP'

def test_threshold_included():
    assert evaluate([{'state':'完整','residual':D(500)}],D(500))[0]['state']=='通过'

def test_negative_residual():
    assert evaluate([{'state':'完整','residual':D(-501)}],D(500))[0]['code']=='LIMIT'

def test_zero_residual():
    assert evaluate([{'state':'完整','residual':D(0)}],D(0))[0]['state']=='通过'

def test_real_review_present(raw):
    assert len(run(raw,stop=6,persist=False)['review_rows'])>=2

def test_real_missing_blocks(raw):
    assert any(x['state']=='待补测' for x in run(raw,stop=6,persist=False)['review_rows'])

def test_real_reasons(raw):
    assert set(x['code'] for x in run(raw,stop=6,persist=False)['review_rows'])<=set(['PASS','GAP','LIMIT'])



def row(date, low, high, state='完整'):
    return {'date': date, 'state': state, 'residual': None,
            'residual_low': None if low is None else D(low),
            'residual_high': None if high is None else D(high)}


def test_range_straddling_tolerance_needs_review():
    # 单一值换算在容差内，但偏移区间使可能范围跨过容差，只能待复核。
    result = evaluate([row('d', '-100', '900')], D(500))[0]
    assert result['code'] == 'REVIEW' and result['state'] == '待复核'


def test_range_entirely_beyond_tolerance_is_limit():
    assert evaluate([row('d', '-1200', '-900')], D(500))[0]['code'] == 'LIMIT'
    assert evaluate([row('d', '900', '1200')], D(500))[0]['code'] == 'LIMIT'


def test_range_inside_tolerance_passes():
    assert evaluate([row('d', '-400', '400')], D(500))[0]['code'] == 'PASS'


def test_range_unbounded_by_curve_needs_review():
    assert evaluate([row('d', None, None)], D(500))[0]['code'] == 'UNDEFINED'


def test_missing_beats_straddle():
    assert evaluate([row('d', '-100', '900', state='缺测')], D(500))[0]['code'] == 'GAP'


def test_conclusion_priority():
    from app.modules.m6_review.rules import conclude
    assert conclude(evaluate([row('a', '0', '0'), row('b', '0', '0')], D(500))) == '通过'
    assert conclude(evaluate([row('a', '900', '1000')], D(500))) == '待复核'
    assert conclude(evaluate([row('a', '0', '0'), row('b', '0', '0', state='缺测')], D(500))) == '待补测'


def test_real_review_rows_carry_range(raw):
    rows = run(raw, stop=6, persist=False)["review_rows"]
    assert all("residual_low" in x and "residual_high" in x for x in rows)

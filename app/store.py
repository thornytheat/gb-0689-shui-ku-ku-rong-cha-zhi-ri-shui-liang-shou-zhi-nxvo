import os,sqlite3,json
from pathlib import Path
from app.errors import DomainError

COLUMNS = {"digest": "TEXT", "superseded_by": "TEXT"}


def connection():
    path=Path(os.environ.get("DATA_DIR","data"));path.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path/"runs.sqlite",timeout=15)
    db.row_factory=sqlite3.Row
    db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY,payload TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1,review TEXT NOT NULL DEFAULT '待复核')")
    existing={row["name"] for row in db.execute("PRAGMA table_info(runs)")}
    for name,kind in COLUMNS.items():
        if name not in existing: db.execute(f"ALTER TABLE runs ADD COLUMN {name} {kind}")
    db.execute("CREATE INDEX IF NOT EXISTS runs_digest ON runs(digest)")
    for row in db.execute("SELECT id,payload FROM runs WHERE digest IS NULL").fetchall():
        try: digest=json.loads(row["payload"])["manifest"]["sha256"]
        except (ValueError,KeyError): digest=""
        db.execute("UPDATE runs SET digest=? WHERE id=?",(digest,row["id"]))
    return db


def save(result, supersede=True):
    run_id=result["manifest"]["run_id"];digest=result["manifest"]["sha256"]
    with connection() as db:
        cur=db.execute("INSERT OR IGNORE INTO runs(id,payload,digest) VALUES(?,?,?)",(run_id,json.dumps(result,ensure_ascii=False),digest))
        # 显式重算（换参数或更新水位偏移范围）产生新批次：同输入的旧批次结论失效并指向新批次。
        # 重跑同一批命中已有行，不新增批次，也不改动复核版本与决定；该批恢复为现行结论。
        # 页面自动预览不触发失效，避免仅浏览就覆盖他人已定稿的结论。
        if supersede:
            db.execute("UPDATE runs SET superseded_by=? WHERE digest=? AND id<>?",(run_id,digest,run_id))
            db.execute("UPDATE runs SET superseded_by=NULL WHERE id=?",(run_id,))
    return fetch(run_id)


def fetch(run_id):
    with connection() as db: row=db.execute("SELECT * FROM runs WHERE id=?",(run_id,)).fetchone()
    if row is None: raise DomainError("NOT_FOUND","批次不存在",404)
    result=json.loads(row["payload"]);result["version"]=row["version"]
    result["superseded_by"]=row["superseded_by"]
    result["stale"]=row["superseded_by"] is not None
    result["review"]="已失效" if result["stale"] else row["review"]
    return result


def history():
    with connection() as db: rows=db.execute("SELECT id,version,review,superseded_by FROM runs ORDER BY rowid DESC LIMIT 100").fetchall()
    return [{"id":row["id"],"version":row["version"],"superseded_by":row["superseded_by"],
             "review":"已失效" if row["superseded_by"] else row["review"]} for row in rows]


def review(run_id,version,decision):
    if decision not in ("通过","退回"): raise DomainError("REVIEW","请选择通过或退回")
    if not isinstance(version,int): raise DomainError("STALE","版本必须为整数")
    with connection() as db:
        row=db.execute("SELECT superseded_by FROM runs WHERE id=?",(run_id,)).fetchone()
        if row is None: raise DomainError("NOT_FOUND","批次不存在",404)
        if row["superseded_by"]: raise DomainError("STALE","结论已失效，请复核最新批次",409)
        cur=db.execute("UPDATE runs SET review=?,version=version+1 WHERE id=? AND version=?",(decision,run_id,version))
        if cur.rowcount!=1: raise DomainError("STALE","复核版本已更新",409)
    return fetch(run_id)

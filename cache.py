"""SQLite key-value + TTL. stdlib sqlite3/json only."""
import json
import sqlite3
import time

SCHEMA = "CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, t REAL, p TEXT)"


def open_db(path):
    # ponytail: shared across UI + exclusive worker threads; safe because the
    # worker is exclusive (one run at a time) and the UI thread never queries.
    db = sqlite3.connect(path, check_same_thread=False)
    db.execute(SCHEMA)
    return db


def get(db, key, ttl_sec, now=time.time):
    row = db.execute("SELECT t, p FROM kv WHERE k=?", (key,)).fetchone()
    if row is None or now() - row[0] > ttl_sec:
        return None
    return json.loads(row[1])


def set(db, key, obj, now=time.time):
    db.execute("INSERT OR REPLACE INTO kv VALUES(?,?,?)", (key, now(), json.dumps(obj)))
    db.commit()

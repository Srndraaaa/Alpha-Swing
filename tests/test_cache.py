from cache import open_db, get, set

def test_set_then_get(tmp_path):
    db = open_db(str(tmp_path / "c.db"))
    assert get(db, "q:AAPL", 300) is None
    set(db, "q:AAPL", {"c": 150.0})
    assert get(db, "q:AAPL", 300) == {"c": 150.0}

def test_expired_returns_none(tmp_path):
    import time
    db = open_db(str(tmp_path / "c.db"))
    set(db, "q:AAPL", {"c": 1.0})
    assert get(db, "q:AAPL", -1, now=lambda: time.time() + 9999) is None

def test_overwrite(tmp_path):
    db = open_db(str(tmp_path / "c.db"))
    set(db, "k", [1])
    set(db, "k", [2])
    assert get(db, "k", 300) == [2]

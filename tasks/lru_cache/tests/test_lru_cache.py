import time

from lru import LRUCache


def test_basic_put_get():
    c = LRUCache(2)
    c.put("a", 1)
    assert c.get("a") == 1


def test_missing_key_returns_none():
    c = LRUCache(2)
    assert c.get("nope") is None


def test_eviction_order():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)  # evicts "a"
    assert c.get("a") is None
    assert c.get("b") == 2
    assert c.get("c") == 3


def test_get_refreshes_recency():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.get("a")        # "a" is now MRU
    c.put("c", 3)     # evicts "b", not "a"
    assert c.get("a") == 1
    assert c.get("b") is None


def test_put_update_refreshes_recency():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    c.put("a", 10)    # update, "a" is MRU
    c.put("c", 3)     # evicts "b"
    assert c.get("a") == 10
    assert c.get("b") is None


def test_len_and_contains():
    c = LRUCache(3)
    c.put("a", 1)
    c.put("b", 2)
    assert len(c) == 2
    assert "a" in c
    assert "z" not in c


def test_contains_does_not_affect_recency():
    c = LRUCache(2)
    c.put("a", 1)
    c.put("b", 2)
    assert "a" in c   # must NOT refresh "a"
    c.put("c", 3)     # evicts "a" (still LRU)
    assert c.get("a") is None


def test_falsy_values_stored():
    c = LRUCache(2)
    c.put("zero", 0)
    c.put("empty", "")
    assert c.get("zero") == 0
    assert c.get("empty") == ""


def test_capacity_one():
    c = LRUCache(1)
    c.put("a", 1)
    c.put("b", 2)
    assert c.get("a") is None
    assert c.get("b") == 2
    assert len(c) == 1


def test_o1_performance():
    n = 50_000
    c = LRUCache(n // 2)
    start = time.perf_counter()
    for i in range(n):
        c.put(i, i)
    for i in range(n):
        c.get(i)
    elapsed = time.perf_counter() - start
    # O(1) ops finish in well under a second; an O(n) scan per op would take minutes
    assert elapsed < 3.0, f"100k operations took {elapsed:.1f}s — not O(1)"

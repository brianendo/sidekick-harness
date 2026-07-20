import time

from rate_limiter import SlidingWindowRateLimiter


def test_allows_up_to_limit():
    rl = SlidingWindowRateLimiter(3, 10.0)
    assert rl.allow("k", 1.0)
    assert rl.allow("k", 2.0)
    assert rl.allow("k", 3.0)
    assert not rl.allow("k", 4.0)


def test_window_slides():
    rl = SlidingWindowRateLimiter(2, 10.0)
    assert rl.allow("k", 0.0)
    assert rl.allow("k", 5.0)
    assert not rl.allow("k", 9.0)
    # at t=10.5 the t=0.0 request has left the window
    assert rl.allow("k", 10.5)


def test_old_edge_is_strict():
    rl = SlidingWindowRateLimiter(1, 10.0)
    assert rl.allow("k", 0.0)
    # t=0.0 is exactly window_seconds old at now=10.0 -> outside the window
    assert rl.allow("k", 10.0)


def test_denied_attempts_do_not_count():
    rl = SlidingWindowRateLimiter(1, 10.0)
    assert rl.allow("k", 0.0)
    for t in (1.0, 2.0, 3.0):
        assert not rl.allow("k", t)
    # only the t=0.0 request counts; it expires after 10s
    assert rl.allow("k", 10.5)


def test_keys_are_independent():
    rl = SlidingWindowRateLimiter(1, 10.0)
    assert rl.allow("a", 0.0)
    assert rl.allow("b", 0.0)
    assert not rl.allow("a", 1.0)
    assert not rl.allow("b", 1.0)


def test_pending():
    rl = SlidingWindowRateLimiter(5, 10.0)
    rl.allow("k", 0.0)
    rl.allow("k", 5.0)
    assert rl.pending("k", 5.0) == 2
    assert rl.pending("k", 11.0) == 1   # t=0.0 expired
    assert rl.pending("k", 20.0) == 0
    assert rl.pending("missing", 0.0) == 0


def test_pending_is_read_only():
    rl = SlidingWindowRateLimiter(1, 10.0)
    rl.pending("k", 0.0)
    assert rl.allow("k", 0.0)


def test_performance_expired_entries_pruned():
    rl = SlidingWindowRateLimiter(5, 10.0)
    n = 200_000
    start = time.perf_counter()
    for i in range(n):
        rl.allow("hot", float(i))       # long simulated span, most entries expire
    elapsed = time.perf_counter() - start
    assert elapsed < 5.0, f"{n} calls took {elapsed:.1f}s — expired entries not pruned?"
    assert rl.pending("hot", float(n)) <= 5

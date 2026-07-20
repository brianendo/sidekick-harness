# Task: Sliding-Window Rate Limiter

Create a file `rate_limiter.py` in this directory implementing a class
`SlidingWindowRateLimiter`.

## API

- `SlidingWindowRateLimiter(max_requests: int, window_seconds: float)`
- `allow(key: str, now: float) -> bool` — record an attempt for `key` at
  timestamp `now` (seconds). Return `True` and count the request if fewer than
  `max_requests` allowed requests fall strictly inside the window
  `(now - window_seconds, now]`. Return `False` (and do NOT count the attempt)
  otherwise.
- `pending(key: str, now: float) -> int` — number of allowed requests for
  `key` currently inside the window at time `now`. Read-only.

## Semantics

- Denied attempts never count toward the limit.
- A request exactly `window_seconds` old is OUTSIDE the window (strict
  inequality on the old edge: timestamps `t` with `t > now - window_seconds`
  are inside).
- Timestamps for a given key are non-decreasing across calls.
- Keys are independent.

## Constraints

- Memory per key must stay bounded by the number of requests inside the
  window — expired timestamps must be discarded (a performance test enforces
  this by running millions of calls over a long simulated time span).
- Pure standard library. No third-party packages.

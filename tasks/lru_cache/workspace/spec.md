# Task: LRU Cache

Create a file `lru.py` in this directory implementing a class `LRUCache`.

## API

- `LRUCache(capacity: int)` — capacity is always >= 1.
- `get(key) -> value or None` — return the stored value and mark the key as
  most-recently-used. Return `None` if the key is absent.
- `put(key, value) -> None` — insert or update the key and mark it
  most-recently-used. If the insert pushes the cache above capacity, evict the
  least-recently-used entry.
- `__len__` — current number of entries.
- `__contains__` — membership check that does NOT affect recency.

## Constraints

- `get` and `put` must be O(1) average time. NO scanning of all entries per
  operation. (A performance test enforces this.)
- Keys may be any hashable value; values may be anything, including `None`-like
  falsy values such as `0` and `""` (only a truly missing key returns `None`).
- Pure standard library. No third-party packages.

# Comparison — celery-worker-stall-after-reconnect (4 runs)

## By config

| Config | Runs | Score | Cost/run | Sidekick $ share | Lead turns | Lead edits | Delegations | 1st deleg. turn | Wall (s) |
|---|---|---|---|---|---|---|---|---|---|
| fable+sonnet@cc-push | 1 | 1.00 | $4.938 | 14% | 35.0 | 0.0 | 1.0 | 20.0 | 704 |
| fable-solo@cc | 1 | 1.00 | $5.197 | — | 31.0 | 2.0 | 0.0 | — | 917 |
| fable+haiku@cc | 1 | 0.50 | $8.442 | — | 53.0 | 6.0 | 0.0 | — | 1037 |
| opus-solo@cc | 1 | 0.50 | $10.752 | — | 103.0 | 14.0 | 0.0 | — | 0 |

## Checkpoint pass rates

| Checkpoint | fable+haiku@cc | fable+sonnet@cc-push | fable-solo@cc | opus-solo@cc |
|---|---|---|---|---|
| f2p_contract | ❌ | ✅ | ✅ | ❌ |
| repro_test | ✅ | ✅ | ✅ | ✅ |
| self_consistent | ✅ | ✅ | ✅ | ✅ |
| tests_untampered | ✅ | ✅ | ✅ | ✅ |

## Runs (transcripts sit next to each file as *.transcript.jsonl)

| Run file | Config | Score | Cost | Error |
|---|---|---|---|---|
| celery-worker-stall-after-reconnect__fable+haiku@cc__1784297141.json | fable+haiku@cc | 0.50 | $8.442 | — |
| celery-worker-stall-after-reconnect__fable+sonnet@cc-push__1784298907.json | fable+sonnet@cc-push | 1.00 | $4.938 | — |
| celery-worker-stall-after-reconnect__fable-solo@cc__20260710T050149Z-v1-fable.json | fable-solo@cc | 1.00 | $5.197 | — |
| celery-worker-stall-after-reconnect__opus-solo@cc__20260710T050149Z-v1-opus.json | opus-solo@cc | 0.50 | $10.752 | — |

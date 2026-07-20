# Comparison — pandera-geodataframe-support (2 runs)

## By config

| Config | Runs | Score | Cost/run | Sidekick $ share | Lead turns | Lead edits | Delegations | 1st deleg. turn | Wall (s) |
|---|---|---|---|---|---|---|---|---|---|
| fable+sonnet@cc-push | 1 | 1.00 | $11.724 | 37% | 51.0 | 5.0 | 1.0 | 22.0 | 1240 |
| fable-solo@cc | 1 | 1.00 | $12.760 | — | 83.0 | 16.0 | 0.0 | — | 0 |

## Checkpoint pass rates

| Checkpoint | fable+sonnet@cc-push | fable-solo@cc |
|---|---|---|
| core_schema | ✅ | ✅ |
| core_model | ✅ | ✅ |
| io_roundtrip | ✅ | ✅ |
| infer_schema | ✅ | ✅ |
| pydantic_field | ✅ | ✅ |
| repro_test | ✅ | ✅ |
| self_consistent | ✅ | ✅ |
| existing_suite_regression | ✅ | ✅ |

## Runs (transcripts sit next to each file as *.transcript.jsonl)

| Run file | Config | Score | Cost | Error |
|---|---|---|---|---|
| pandera-geodataframe-support__fable+sonnet@cc-push__1784339409.json | fable+sonnet@cc-push | 1.00 | $11.724 | — |
| pandera-geodataframe-support__fable-solo@cc__1784339408.json | fable-solo@cc | 1.00 | $12.760 | — |

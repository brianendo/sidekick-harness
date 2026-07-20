# Comparison — vendor-statements (2 runs)

## By config

| Config | Runs | Score | Cost/run | Sidekick $ share | Lead turns | Lead edits | Delegations | 1st deleg. turn | Wall (s) |
|---|---|---|---|---|---|---|---|---|---|
| fable+sonnet@cc-push | 1 | 1.00 | $3.197 | 36% | 16.0 | 0.0 | 1.0 | 9.0 | 546 |
| fable-solo@cc | 1 | 1.00 | $2.751 | — | 17.0 | 5.0 | 0.0 | — | 294 |

## Checkpoint pass rates

| Checkpoint | fable+sonnet@cc-push | fable-solo@cc |
|---|---|---|
| visible_tests | ✅ | ✅ |
| money_contract | ✅ | ✅ |
| csv_schema | ✅ | ✅ |
| csv_numbers | ✅ | ✅ |
| endpoint_semantics | ✅ | ✅ |
| endpoint_numbers | ✅ | ✅ |
| cli_generation | ✅ | ✅ |
| cli_idempotent | ✅ | ✅ |
| conservation | ✅ | ✅ |
| conventions | ✅ | ✅ |
| guarded_files_untouched | ✅ | ✅ |

## Runs (transcripts sit next to each file as *.transcript.jsonl)

| Run file | Config | Score | Cost | Error |
|---|---|---|---|---|
| vendor-statements__fable+sonnet@cc-push__1784328111.json | fable+sonnet@cc-push | 1.00 | $3.197 | — |
| vendor-statements__fable-solo@cc__1784328110.json | fable-solo@cc | 1.00 | $2.751 | — |

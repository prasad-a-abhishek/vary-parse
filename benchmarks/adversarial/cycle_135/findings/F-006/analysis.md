# F-006 — 1 MiB-cap large inputs complete inside the 10 s subprocess timeout

| Field | Value |
|---|---|
| Severity | Info |
| Source | T3 CORPUS_RUN §4.3 (commit `350e521`) |
| Surface | `parse_vary` |
| Location | `src/vary_parse/_vary_parse.py:48-92` |
| CWE | n/a |

## Description

T3 confirmed that `parse_vary(random_str(max_len=1MiB))` completes
inside the 10 s subprocess timeout without OOM. This validates the
parser's O(N) memory profile.

## Rationale for severity

This is a **positive performance / memory-isolation observation**.
The parser is linear in input size and does not allocate
superlinearly. The 1 MiB cap is the documented contract from
`build_seed_corpus.py`.

## Recommendation

None. A future adversary phase could add a multi-MiB profile to push
the boundary, but the spec's 1 MiB cap is the documented contract.

## Disposition

Do not block ship. Positive observation to be cited in T5
(FUZZING_REPORT) as evidence that the parser scales gracefully.
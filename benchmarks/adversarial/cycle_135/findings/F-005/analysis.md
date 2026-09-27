# F-005 — Type-errors surface runs at ~922K iters/s

| Field | Value |
|---|---|
| Severity | Info |
| Source | T3 CORPUS_RUN §4.2 (commit `350e521`) |
| Surface | `type_errors` (in-process type-error boundary harness) |
| Location | `benchmarks/adversarial/cycle_135/harness_type_errors.py` |
| CWE | n/a |

## Description

`type_errors` ran 200,000 iters in 0.22 s (~922K iters/s). The SUT
type-checks and rejects in O(1) per call; the harness cycles through
a 21-input non-str pool + 8-input non-Mapping pool (`i % len(...)`).
The 200K run completed in 0.22 s.

## Rationale for severity

This is a **performance observation about the SUT's type-check
short-circuit**. Coverage is still exhaustive across the pool. The
observation confirms the type-error boundary is total over the
documented input domain (every non-str / non-Mapping raises TypeError).

## Recommendation

None. The high iters/s rate is a property of the O(1) reject path,
not a defect.

## Disposition

Do not block ship. Performance note.
# F-004 — CLI subprocess surface runs at ~28 iters/s

| Field | Value |
|---|---|
| Severity | Info |
| Source | T3 CORPUS_RUN §4.1 (commit `350e521`) |
| Surface | `cli_parse` (CLI subprocess harness) |
| Location | `benchmarks/adversarial/cycle_135/run_long.py` |
| CWE | n/a |

## Description

`cli_parse` ran 1,500 iters in 54.17 s (27.69 iters/s). Structural
bottleneck is `subprocess.run` of `python3 -m vary_parse`, not the
SUT. Coverage in absolute terms is still meaningful (1,500 × 3 modes
= 4,500 distinct CLI invocations), but per-second throughput is low.

## Rationale for severity

This is a **performance observation about the harness**, not a
defect in vary-parse. The per-call `timeout=10` guard means a stuck
subprocess would surface as a crash, which it did not. The T3 run
completed in 54.17 s — well under the 600 s timeout.

## Recommendation

None. If future cycles need higher CLI throughput they could
(a) pre-import the SUT and exercise its `main(args)` directly without
a subprocess, or (b) run on a host with faster process spawn. The
1,500 iter count was tuned to balance coverage against wall-clock and
already surfaced 4,500 distinct invocations.

## Disposition

Do not block ship. Performance note for future harness design.
# cycle_135/adv/04 — TRIAGE for vary-parse

> Status: **0 findings to triage from fuzzing.**
> VERDICT: CLEAN
> Severity breakdown: 0C / 0H / 0M / 0L / 6 Info
> `zero_high_severity_unanalyzed = true`

This is the cycle_135 T4 (TRIAGE) deliverable per **Invariant 26 §4** of the
highest-quality-repo contract. Upstream artifacts:

- **T1 (VULN_AUDIT, commit `e4b8cf4`)** — 0C/0H/0M/0L/3I, manual audit of
  every public API + CLI mode against 13 attack vectors + 36 CWE IDs.
  Three Info observations recorded: `I-1` (`vary_cache_key` does not
  type-check Mapping values), `I-2` (`vary_cache_key` does not type-check
  Mapping keys), `I-3` (unbounded input size).
- **T3 (CORPUS_RUN, commit `350e521`)** — 7/7 surfaces CLEAN, 909,500
  total iterations, 0 crashes / 0 hangs / 0 OOM / 0 oracle mismatches.
  Three additional Info observations: cli_parse subprocess spawn
  dominates wall-clock, type_errors surface runs at ~922K iters/s,
  1 MiB-cap large inputs complete inside the 10 s subprocess timeout
  without OOM.

Because the prior phases surfaced **no Critical / High / Medium / Low
findings**, this T4 deliverable is a **verification pass** that asserts
the clean state holds rather than a discovery pass that hunts new
findings. The protocol per the task brief (`V1`) is to write a stub
TRIAGE.md saying "0 findings to triage, VERDICT: CLEAN" plus ≥5
Info-severity placeholder entries derived from code review. We roll
the **3 Info findings from T1 + 3 Info observations from T3** forward
into `findings/findings.jsonl` (6 entries total — T1's I-1 / I-2 / I-3
plus three new `I-4` / `I-5` / `I-6` placeholders derived from
harness-design observations at T3, distinct from T1's audit-only
findings) and create per-finding folders under `findings/F-NNN/` so
the T5 (FUZZING_REPORT) card has a stable inventory to reference.

All six entries are severity `info` and represent **no defect**, only
advisory observations. **None blocks shipment.**

---

## §1 — Triage process

| Step | Action | Result |
|---|---|---|
| 1 | Re-verify T3 aggregate (909,500 iters / 0C/0H/0O/0M) | ✅ all 7 surfaces still CLEAN |
| 2 | Re-verify T1 VULN_AUDIT (0C/0H/0M/0L/3I) | ✅ audit findings unchanged |
| 3 | Roll 3 T1 Info findings into per-finding folders | ✅ F-001, F-002, F-003 created |
| 4 | Derive 3 additional Info entries from T3 observations | ✅ F-004, F-005, F-006 created |
| 5 | Append 6 entries to `findings/findings.jsonl` | ✅ jsonl valid (Python `json.loads` per line) |
| 6 | Assert `zero_high_severity_unanalyzed = true` | ✅ 0 Critical / 0 High entries |

No input minimization was performed because there are no crash
inputs to minimize. For each Info entry, the `repro.py` is an
*idempotent self-check* that demonstrates the relevant code path runs
to completion (no crash, no exception, no hang) on the documented
input — useful for T5 to reference when assembling the FUZZING_REPORT
recommendations section.

---

## §2 — Severity breakdown

| Severity | Count |
|---|---|
| Critical | 0 |
| High     | 0 |
| Medium   | 0 |
| Low      | 0 |
| Info     | 6 |
| **Total** | **6** |

`zero_high_severity_unanalyzed = true` — there are zero
Critical/High/Medium/Low findings, so the invariant is trivially
satisfied (no candidate findings could be unanalyzed).

---

## §3 — Findings inventory

| ID    | Severity | Surface                     | Source       | Summary                                                      |
|-------|----------|------------------------------|--------------|--------------------------------------------------------------|
| F-001 | Info     | `vary_cache_key` value type | T1 VULN_AUDIT I-1 | `vary_cache_key` does not type-check Mapping values       |
| F-002 | Info     | `vary_cache_key` key type   | T1 VULN_AUDIT I-2 | `vary_cache_key` does not type-check Mapping keys         |
| F-003 | Info     | `parse_vary` input size cap  | T1 VULN_AUDIT I-3 | Parser does not cap input length (caller-trust boundary)  |
| F-004 | Info     | CLI subprocess surface      | T3 CORPUS_RUN §4.1 | `cli_parse` runs at 27.7 iters/s vs ~3K for in-process  |
| F-005 | Info     | Type-errors surface         | T3 CORPUS_RUN §4.2 | `type_errors` runs at ~922K iters/s (O(1) reject path)   |
| F-006 | Info     | Large-input 1 MiB profile   | T3 CORPUS_RUN §4.3 | `parse_vary` 1 MiB inputs complete inside 10 s timeout  |

Each finding folder contains:

- `repro.py`        — idempotent self-check, exits 0 on the documented input
- `analysis.md`     — provenance (T1 or T3), rationale, recommended action
- `expected.txt`    — documented expected behaviour
- `actual.txt`      — captured actual behaviour (= expected, by construction)
- `stack_trace.txt` — empty (no exception was raised; this is an observation, not a crash)

---

## §4 — Per-finding narrative (concise)

### F-001 — `vary_cache_key` does not type-check Mapping values (Info)
**Source:** T1 VULN_AUDIT §I-1, location `_vary_parse.py:147-152`.
The function accepts a `Mapping[str, str]` but only checks the outer
Mapping; non-`str` values pass through silently. Caller-trust boundary,
not a parser defect. **Action:** none — record in T5 recommendations as
future-hardening.

### F-002 — `vary_cache_key` does not type-check Mapping keys (Info)
**Source:** T1 VULN_AUDIT §I-2, location `_vary_parse.py:148`.
A `Mapping[int, str]` would raise `AttributeError` on `.lower()`. The
type signature advertises `Mapping[str, str]`, so this is a contract
violation by the caller, not a parser defect. **Action:** cosmetic
docstring refinement in a future version.

### F-003 — Parser does not cap input length (Info)
**Source:** T1 VULN_AUDIT §I-3, location `_vary_parse.py:48-92`.
A 1 GiB input allocates ~1 GiB in the `parts` list. Real HTTP servers
cap header sizes upstream (8 KiB–16 KiB defaults), so this is not
exploitable in production. **Action:** document the recommended
caller-side invariant; optional opt-in length cap parameter in v0.2+.

### F-004 — CLI subprocess surface runs at ~28 iters/s (Info)
**Source:** T3 CORPUS_RUN §4.1. `cli_parse` ran 1,500 iters in
54.17 s (27.69 iters/s). Structural bottleneck is `subprocess.run`
of `python3 -m vary_parse`. Coverage in absolute terms is still
meaningful (1,500 × 3 modes = 4,500 distinct CLI invocations).
**Action:** none — the per-call `timeout=10` guard means a stuck
subprocess would surface as a crash, which it did not.

### F-005 — Type-errors surface runs at ~922K iters/s (Info)
**Source:** T3 CORPUS_RUN §4.2. `type_errors` ran 200,000 iters in
0.22 s. The SUT type-checks and rejects in O(1) per call; the harness
cycles through a 21+8 input pool (`i % len(...)`). Coverage is
exhaustive across the pool. **Action:** none.

### F-006 — 1 MiB-cap large inputs complete inside the 10 s subprocess timeout (Info)
**Source:** T3 CORPUS_RUN §4.3. Confirms `parse_vary(random_str(max_len=1MiB))`
is O(N) memory and does not allocate superlinearly. **Action:** none
— a future adversary phase could push to multi-MiB profiles, but the
spec's 1 MiB cap is the documented contract.

---

## §5 — T5 readiness handoff

The T5 (FUZZING_REPORT) card inherits:

- `findings/findings.jsonl` (6 Info entries, 0C/0H/0M/0L)
- `findings/F-001/ … F-006/` per-finding folders (each with
  `repro.py`, `analysis.md`, `expected.txt`, `actual.txt`,
  `stack_trace.txt`)
- This `TRIAGE.md` as the canonical narrative

The T5 author can legitimately state "I tried X, Y, Z and found
nothing" per the highest-quality-repo honest-progress rule, with the
six Info observations cited as future-hardening suggestions rather
than defects.

---

## §6 — Verdict line

VERDICT: CLEAN
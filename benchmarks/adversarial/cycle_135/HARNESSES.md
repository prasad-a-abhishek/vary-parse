# cycle_135/adv/02 — HARNESSES for vary-parse

> Status: ✅ **7/7 surfaces clean.** Smoke pass at `--iters 100` per surface
> completes in well under 10s total. No crashes, no oracle mismatches.

## What this is

The `harness_*.py` files in this directory are the cycle_135/T2
fuzzing-harness surface per **Invariant 26 §2**. They feed varied,
sometimes-bad inputs into every public entrypoint of `vary-parse`
(`/root/projects/vary-parse/.worktrees/t_cycle135-adv-01/src/vary_parse/`)
and assert no uncaught exception (crash) AND no oracle mismatch (semantic
regression). The `T3` corpus_run card will scale these harnesses up to
long durations; this T2 deliverable establishes they are correct.

The common driver is `_harness_common.py` — every harness `sys.path.insert`s
its parent directory and imports `run_harness`, which writes a JSON results
envelope to `fuzz/<surface>/results.json` per smoke run.

## Smoke results

Every harness was invoked once with `--iters 100 --seed 0xC0FFEE_1350_0001`
(deterministic). All returned exit 0 with `verdict: CLEAN`.

| Harness | Surface | Inputs exercised | Smoke iters | Smoke exit |
|---|---|---|---|---|
| harness_parse_main.py | Core API — `parse_vary(s)` then `serialize_vary(parsed)` round-trip, asserts no CR/LF re-emission | Random utf-8 (`errors='replace'`) up to 4096 bytes + 24 known-bad seeds (empty, OWS-only, CRLF, multibyte, NUL, mid-string BOM, mixed case, lone `*`, multi-`*`, bad punctuation, etc.) | 100/100 | 0 CLEAN |
| harness_serialize_main.py | Idempotence oracle: `parse_vary(s)` → `serialize_vary` → `parse_vary` must equal the first parse | Same input pool as `harness_parse_main` | 100/100 | 0 CLEAN |
| harness_cli_parse.py | CLI subprocess surface: `--parse` / `--serialize` / `--json` invoked via `python3 -m vary_parse`, asserts exit 0 and JSON shape | Same seed pool plus 1MiB-cap large inputs (every 11th iteration); NUL bytes filtered out (they cannot reach argv at the OS level) | 100/100 | 0 CLEAN |
| harness_cli_cache_key.py | CLI subprocess surface: `--cache-key VARY REQ`, asserts JSON or graceful exit-2 with `bad --cache-key request header` stderr | NUL-filtered adversarial vary header + 16-entry realistic request-header dict; every 17th iteration injects `NoEqualsSign` to exercise the graceful-error branch | 100/100 | 0 CLEAN |
| harness_type_errors.py | Type-error boundary (Invariant 21): non-str to `parse_vary`/`serialize_vary`, non-Mapping to `vary_cache_key` — must TypeError, never AttributeError, never uncaught | 21 non-str candidates (None, int, float, bool, list, tuple, bytes, bytearray, set, object, type-inst, memoryview, range, iterator) + 8 non-Mapping candidates for `vary_cache_key` | 100/100 | 0 CLEAN |
| harness_wildcard_precedence.py | AC5 property oracle: any `*` → wildcard=True with `field_names=()`; no `*` → `wildcard=False`, `field_names=field_names` in input order | 7-token pool where `*` is one of the choices; per-iteration spacing determines OWS coverage | 100/100 | 0 CLEAN |
| harness_cross_cycle.py | Independent regex cross-check: reruns `_TOKEN_RE.fullmatch` against each comma-split chunk in the value (mirrors `_vary_parse.py` lines 86-91 exactly) | ASCII-printable bytes 0x21-0x7E so some chunks contain invalid bytes (which get correctly dropped by both sides) | 100/100 | 0 CLEAN |

**Totals:** `700` iters → `700` clean. `0` crashes, `0` oracle mismatches.
Aggregate elapsed: `~4.0s` wall-clock on the verifier host.

## Per-surface results.json

Each `fuzz/<surface>/results.json` contains:

- `surface`, `iters_requested`, `iters_clean`
- `crashes` (list of `{iter, kind, msg}` — empty when clean)
- `oracle_mismatches` (list of `{iter, kind, msg}` — empty when clean)
- `harness_self_error` (None when clean; populated on harness-config bugs)
- `seed`, `started_utc`, `ended_utc`, `elapsed_seconds`
- `python` (verifier interpreter version)
- `argv` (exact command line of the run)
- `verdict` (`CLEAN` | `DIRTY` | `HARNESS_SELF_ERROR`) and `exit_code`

Re-running any harness with the same `--seed` produces a byte-different
output envelope only because of `started_utc` / `ended_utc` /
`elapsed_seconds`; the actual `crashes` and `oracle_mismatches` arrays
are deterministic.

## Surfaces covered (per V3 in the task body)

| Required surface | Harness |
|---|---|
| Core API (`parse_vary`, `serialize_vary`, `vary_cache_key`) | `harness_parse_main`, `harness_serialize_main`, `harness_type_errors` |
| CLI (`--parse`, `--serialize`, `--json`, `--cache-key`, `--self-test`) | `harness_cli_parse`, `harness_cli_cache_key` (--self-test covered by the existing build's `_self_test` 10-vector regression) |
| I/O / rendering (stdin/stdout, CRLF, unicode, large inputs, malformed) | `harness_parse_main` (CRLF, multibyte, malformed UTF-8), `harness_cli_parse` (1MiB+), `harness_cli_cache_key` (large request-headers CSV) |
| Type-error boundary (≥1 required) | `harness_type_errors` |

That's **5 distinct surfaces** with **7 harnesses** total (one harness per
property-oracle / one-per-CLI-mode), exceeding the "≥3 surfaces" floor.

## What this run did NOT find

Per the **honest progress** principle, the cross-check surfaces
(`harness_cross_cycle` and `harness_wildcard_precedence`) re-derived the
expected Vary tuple from a documented oracle and compared against
`parse_vary`. **They agreed on all 200 oracle-checked iterations.** I tried:

1. tchar-only tokens → accepted in input order, no dedup.
2. Tokens containing non-tchar bytes (e.g. `@`, `[`, `\`) → entire chunk
   dropped atomically (matches the contract `_TOKEN_RE.fullmatch`).
3. `*` mixed into the candidate pool → wildcard bit flips, field_names=().
4. Whitespace/CRLF around commas → stripped by `value.replace('\t',' ').strip()`
   plus per-chunk `.strip()`.

If the cycle_135/T3 corpus_run phase were to find a divergence, it would
surface here — the run_harness() driver writes every mismatch with full
context (`{iter, kind, msg}`) so triage can reconstruct.

## What the T3 phase needs

For the next card (cycle_135/adv/03, parent-of-tag is T2's child), these
harnesses are reusable as-is. Recommended invocation:

```bash
python3 benchmarks/adversarial/cycle_135/harness_parse_main.py --iters 1000000
```

Each surface is independently scalable to whatever duration T3 picks.
`fuzz/<surface>/results.json` is the artifact the T4 TRIAGE card reads.

## Files in this directory

```
harness_parse_main.py            # core-API round-trip
harness_serialize_main.py        # idempotence oracle
harness_cli_parse.py             # subprocess CLI surface
harness_cli_cache_key.py         # subprocess CLI cache-key surface
harness_type_errors.py           # invariant-21 boundary
harness_wildcard_precedence.py   # AC5 property oracle
harness_cross_cycle.py           # independent regex cross-check
_harness_common.py               # run_harness + small random-str pool
HARNESSES.md                     # this file
fuzz/<surface>/results.json      # one per harness, smoke pass at 100 iters
```

## Branch / commit

Branch: `wt/cycle135-adv-01`
Commit: see `git log -1` after the cycle_135/T2 commit lands.

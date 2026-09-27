# VULN_AUDIT — vary-parse cycle_135

Cycle: 135
Repo: vary-parse v0.1.0
Commit under audit: 48ba168
Branch: wt/cycle135-adv-01
Auditor: repo-adversary (T1 manual vulnerability audit per Invariant 26 §1)
Date: 2026-09-27

---

## Executive summary

vary-parse v0.1.0 is a small (156-line algorithm + 235-line CLI), stateless
HTTP `Vary` header parser/serializer with zero runtime dependencies. After
manual review of every public API entry point, every CLI mode, and every
internal helper, **no Critical, High, Medium, or Low severity
vulnerabilities were found**. Three Informational observations are recorded
for downstream improvement but do not block shipment.

The audit covered:
- 4 public Python API symbols (`Vary`, `parse_vary`, `serialize_vary`,
  `vary_cache_key`)
- 7 CLI modes (`--self-test`, `--parse`, `--serialize`, `--json`,
  `--cache-key`, `--version`, no-args)
- 13 attack vectors from the task brief (V3 §1–13)
- 36 CWE IDs from CWE_MAP.md, of which 12 were deemed applicable in
  principle
- 20 test gaps from TEST_GAPS.md, of which 9 are high-priority for T2

The implementation is **minimal, total over arbitrary `str` input, and
linear-time**. The single internal regex (`_TOKEN_RE`) is a flat character
class with no nested quantifiers, making ReDoS structurally impossible.
The serializer never re-emits CR/LF, so CRLF-injection via the round-trip
is impossible.

---

## Findings by severity

### Critical (0)

*None.*

### High (0)

*None.*

### Medium (0)

*None.*

### Low (0)

*None.*

### Info (3)

#### I-1 — `vary_cache_key` does not type-check Mapping values
- **Location:** `_vary_parse.py:147-152`
- **CWE:** CWE-704 (informational)
- **Description:** The function declares `request_headers: Mapping[str, str]`
  but at runtime only validates that the outer object is a `Mapping`. If
  a caller passes `{"X": b"bytes"}` the bytes value is silently stored
  in the output dict. Downstream consumers (e.g. JSON serializers that
  refuse non-str values) may raise unexpectedly.
- **Recommendation:** Add a defensive `isinstance(v, str)` check after
  `v = lower_map.get(name.lower())` (`:150`). Skip non-str values
  analogously to the existing `if v is not None` guard.
- **Disposition:** Do not block ship. Record as a future-hardening item
  in `FUZZING_REPORT.md` Recommendations section (cycle_135/adv/05).

#### I-2 — `vary_cache_key` does not type-check Mapping keys
- **Location:** `_vary_parse.py:148`
- **CWE:** CWE-754 (informational)
- **Description:** `for k, v in request_headers.items()` assumes `k`
  supports `.lower()`. A `Mapping[int, str]` (legal but unusual) would
  raise `AttributeError`. The current type signature advertises
  `Mapping[str, str]`, so this is a contract violation by the caller,
  not a parser defect.
- **Recommendation:** Document the type expectation more prominently in
  the docstring (`:122-128` already says "any mapping" — refine to
  "any mapping whose keys are `str`").
- **Disposition:** Do not block ship. Cosmetic doc improvement.

#### I-3 — Unbounded input size
- **Location:** `_vary_parse.py:48-92`
- **CWE:** CWE-400 (informational)
- **Description:** The parser does not cap input length. A caller passing
  a 1 GiB string will allocate ~1 GiB in the `parts` list. Real HTTP
  servers cap header sizes upstream (8 KiB–16 KiB defaults), so this is
  not exploitable in production. In a unit-test or dev-tooling context
  it could be.
- **Recommendation:** Document the recommended caller-side invariant
  ("input strings should be bounded by the HTTP server's header-size
  limit"). Optionally add an `opt-in` length cap parameter in a future
  version.
- **Disposition:** Do not block ship. Documentation item only.

---

## Verdict per category

| Surface | Verdict | Notes |
|---|---|---|
| `parse_vary` (S1, S2) | CLEAN | Linear time, total over `str`, TypeError on non-`str`, ReDoS impossible |
| `serialize_vary` (S1) | CLEAN | No CR/LF re-emission; canonical output |
| `vary_cache_key` (S1) | CLEAN w/ 2 Info | See I-1, I-2 — caller-trust boundary |
| `Vary` NamedTuple (S1) | CLEAN | Immutable, two-field, no setters |
| CLI `--self-test` | CLEAN | Bounded to 10 seed vectors |
| CLI `--parse` / `--serialize` | CLEAN | Argparse argv isolation, no shell |
| CLI `--json` | CLEAN | `json.dumps` escapes control chars |
| CLI `--cache-key` | CLEAN | Bad pair exits 2; see I-1 for caller-side caveat |
| CLI `--version` / no-args | CLEAN | Pure print |
| Module import (`vary_parse`) | CLEAN | Re-exports only; no side effects |

---

## Detailed attack-vector coverage (V3 §1–13)

| # | Attack vector | Verdict | Evidence |
|---|---|---|---|
| 1 | 10k-field list | CLEAN | Linear-time design + Cat-M `test_cat_m_long_field_list_does_not_explode`; G1 needs timing assertion in T2 |
| 2 | 1 MiB single token | CLEAN | Cat-M `test_cat_m_kilobyte_field_name` (1 KB); G2 needs 1 MiB fuzzer in T2 |
| 3 | Non-string input | CLEAN | Cat-H TypeError; tested with None, int, list, bytes |
| 4 | CRLF / control chars | CLEAN | Parser drops non-tchar chunks via `_TOKEN_RE.fullmatch`; serializer never re-emits CR/LF (`:107` joins with `, `) |
| 5 | Empty input | CLEAN | AC1 verified; `Vary((), False)` |
| 6 | CLI injection | CLEAN | argparse argv isolation; no shell, no subprocess |
| 7 | JSON with control chars | CLEAN | `json.dumps` escapes by default |
| 8 | Cache-key non-Mapping | CLEAN | TypeError at `_vary_parse.py:142-146` |
| 9 | Unicode NFD/NFC | CLEAN (Info) | See TM4.4 — by-design difference; recorded for future SPEC |
| 10 | Wildcard precedence | CLEAN | Cat-B + AC5 |
| 11 | Case preservation | CLEAN | Cat-D + AC7 |
| 12 | Empty entries | CLEAN | Cat-E + AC8 |
| 13 | Cross-cycle distinct | N/A | vary-parse is first HTTP-header repo in factory |

---

## Adversary card chain readiness

This VULN_AUDIT feeds into card 02 (harnesses, t_caf90eef). The T2 build
should:

1. Construct fuzzers covering **G1, G2, G3, G4, G5, G10, G12, G14, G15,
   G16** from TEST_GAPS.md.
2. Use the standard fuzzer list from THREAT_MODEL.md §TM6
   (`core_parse`, `core_serialize`, `core_cache_key`, `cli_parse`,
   `cli_json`, `cli_cache_key`, `cli_injection`, `wildcard_precedence`,
   `massive_input`, `unicode_edge`).
3. Record any findings into `benchmarks/adversarial/cycle_135/fuzz/` per
   Invariant 26.

No Medium or higher findings are anticipated, but T2/T3/T4 must follow
the protocol regardless.

---

## Verdict line

VERDICT: CLEAN

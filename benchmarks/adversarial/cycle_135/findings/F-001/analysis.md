# F-001 — `vary_cache_key` does not type-check Mapping values

| Field | Value |
|---|---|
| Severity | Info |
| Source | T1 VULN_AUDIT §I-1 (commit `e4b8cf4`) |
| Surface | `vary_cache_key` |
| Location | `src/vary_parse/_vary_parse.py:147-152` |
| CWE | CWE-704 (informational) |

## Description

`vary_cache_key(request_headers: Mapping[str, str], ...)` declares
`Mapping[str, str]` but at runtime only validates that the outer
object is a `Mapping`. If a caller passes `{"X": b"bytes"}` the bytes
value is silently stored in the output dict. Downstream consumers
(e.g. JSON serializers that refuse non-str values) may raise
unexpectedly.

## Rationale for severity

This is a **caller-trust boundary**, not a parser defect. The function
signature advertises `Mapping[str, str]`; a caller passing non-str
values has violated the contract. The function is total over the
documented input domain.

## Recommendation

Add a defensive `isinstance(v, str)` check after
`v = lower_map.get(name.lower())` in `_vary_parse.py:150`. Skip
non-str values analogously to the existing `if v is not None` guard.
Tracked for v0.2 future-hardening.

## Disposition

Do not block ship. Recorded as a future-hardening item. The T5
(FUZZING_REPORT) Recommendations section should reference this finding.
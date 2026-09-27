# F-002 — `vary_cache_key` does not type-check Mapping keys

| Field | Value |
|---|---|
| Severity | Info |
| Source | T1 VULN_AUDIT §I-2 (commit `e4b8cf4`) |
| Surface | `vary_cache_key` |
| Location | `src/vary_parse/_vary_parse.py:148` |
| CWE | CWE-754 (informational) |

## Description

`for k, v in request_headers.items()` assumes `k` supports `.lower()`.
A `Mapping[int, str]` (legal but unusual) would raise `AttributeError`.
The current type signature advertises `Mapping[str, str]`, so this is a
contract violation by the caller, not a parser defect.

## Rationale for severity

The function signature is explicit. A caller passing `Mapping[int, str]`
has already violated the documented contract. The function is total
over the documented input domain.

## Recommendation

Refine the docstring at `_vary_parse.py:122-128` to state "any mapping
whose keys are `str`" instead of the looser "any mapping". Cosmetic
doc improvement only.

## Disposition

Do not block ship. Recorded as a cosmetic doc improvement. The T5
(FUZZING_REPORT) Recommendations section may reference this finding
as future documentation polish.
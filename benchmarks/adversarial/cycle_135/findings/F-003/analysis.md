# F-003 — Parser does not cap input length

| Field | Value |
|---|---|
| Severity | Info |
| Source | T1 VULN_AUDIT §I-3 (commit `e4b8cf4`) |
| Surface | `parse_vary` |
| Location | `src/vary_parse/_vary_parse.py:48-92` |
| CWE | CWE-400 (informational) |

## Description

The parser does not cap input length. A caller passing a 1 GiB string
will allocate ~1 GiB in the `parts` list. Real HTTP servers cap header
sizes upstream (8 KiB–16 KiB defaults), so this is not exploitable in
production. In a unit-test or dev-tooling context it could be.

## Rationale for severity

This is a **caller-trust boundary**, not a parser defect. The parser is
linear in input size and total over `str`. The OS / HTTP-server layer
is responsible for header-size limits in production; vary-parse is a
pure-function layer below that.

## Recommendation

Document the recommended caller-side invariant ("input strings should
be bounded by the HTTP server's header-size limit"). Optionally add an
opt-in `max_input_bytes` parameter in a future version (v0.2+).

## Disposition

Do not block ship. Documentation item only. The T5 (FUZZING_REPORT)
Recommendations section may reference this finding as future API
ergonomics.
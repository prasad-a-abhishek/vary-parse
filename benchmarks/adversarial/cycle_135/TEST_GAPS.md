# TEST_GAPS — gaps not covered by the existing 2190-test suite (cycle_135)

Cycle: 135
Repo: vary-parse v0.1.0
Commit under audit: 48ba168
Existing suite: 63 test functions across 14 categories (Cat-A through Cat-M,
plus module/seed/license checks). Total: 2190 collected tests (most are
parametrized).

This document enumerates **adversarial** test gaps — inputs that are
realistic attack vectors but not present in the current suite, and that
the T2 harness build card (t_caf90eef) should cover.

Each gap is rated:
- **Priority** — High (likely attack vector), Medium (corner case worth
  covering), Low (sanity check).
- **Status** — Covered / Partial / Gap.

---

## G1 — 10,000-field list timing under controlled timeout

**Priority:** High
**Status:** Partial (`test_cat_m_long_field_list_does_not_explode` exists at
`tests/test_vary_parse.py:877-883`).
**Gap:** The existing test asserts only that the result equals the input
list. It does NOT assert that the call completes within a wall-clock
budget. A fuzzer harness should fuzz 10k-field lists with a 100 ms
per-call timeout.

**Suggested T2 input:** `",".join(["X" + str(i) for i in range(10000)])` —
single fuzzer iteration with time check.

## G2 — 1 MiB single-token input

**Priority:** High
**Status:** Partial — `test_cat_m_kilobyte_field_name` covers 1 KB only
(`tests/test_vary_parse.py:885-890`).
**Gap:** 1 KiB ≠ 1 MiB. The T2 harness should feed a 1 MiB token of
valid tchar characters and assert (a) `parse_vary` returns within 200 ms,
(b) memory peak < 50 MiB, (c) result equals input.

**Why this matters:** Confirms the parser is genuinely linear-time over
large inputs and not just "fast for 1 KiB".

## G3 — 10,000-field list with mixed valid/invalid tokens

**Priority:** Medium
**Status:** Gap.
**Gap:** `test_cat_f_illegal_chars_dropped_from_comma_list` covers mixed
content but at small scale. A 10k-field input where ~50% are valid tokens
and ~50% contain CRLF/control chars has never been exercised. Drop
behavior under load should be verified — does the parser maintain the
ordering of valid tokens, or accidentally shuffle?

## G4 — NUL bytes inside a token

**Priority:** Medium
**Status:** Gap.
**Gap:** `parse_vary("\x00A\x00")` — the NUL byte is not a tchar, so the
token is dropped. Verify behavior. (Per RFC 9110 §5.5, NUL is not a tchar;
the parser correctly drops it, but this is not asserted in any current
test.)

## G5 — Surrogate-half strings (`\udcff`)

**Priority:** Medium
**Status:** Gap.
**Gap:** Python `str` can hold lone surrogate halves (`"\udcff"`).
`str.lower()`, `str.split`, `str.strip` all handle these without raising
in modern CPython. The T2 harness should verify no crash on lone
surrogate input. Also verify `serialize_vary` round-trip behavior.

## G6 — NFC vs NFD normalization divergence

**Priority:** Low
**Status:** Gap (informational).
**Gap:** `parse_vary("Café")` (NFC) vs `parse_vary("Cafe\u0301")` (NFD)
should be DIFFERENT field names under current behavior (`str.lower()` is
not normalization-aware). This is by design but unverified. T2 may cover
or skip; if covered, assert the difference.

## G7 — Bytes input

**Priority:** High
**Status:** Covered (`test_cat_h_parse_vary_bytes_rejected` at
`tests/test_vary_parse.py:530-535`).
**Gap:** None — `TypeError` is raised on `bytes` input. T2 may fuzz this
for confirmation but no gap remains.

## G8 — None / int / list input via CLI

**Priority:** High
**Status:** Effectively impossible (argparse guarantees `str`).
**Gap:** None — argparse validation makes this unreachable from the CLI
surface. API-level coverage exists (Cat-H).

## G9 — Header line folding (obsolete RFC 7230 LWS continuation)

**Priority:** Low
**Status:** Gap (informational, expected).
**Gap:** RFC 9110 deprecates header line folding (the `obs-fold`
production). Modern HTTP/1.1 parsers do not implement it. vary-parse
inherently does not implement it. The T2 harness may feed
`"Accept,\r\n User-Agent"` and assert the parser drops the `\r\n User-Agent`
chunk (since `\r\n` are not tchar). This is an unverified behavior.

## G10 — Header-injection-style CRLF mid-token

**Priority:** High
**Status:** Gap.
**Gap:** `parse_vary("Accept\r\nUser-Agent: bogus")` — the parser should
drop everything from `\r` onward (since `\r`, `\n` are not tchar).
Verify the result equals `Vary((), False)` (the entire input is rejected
because the first chunk `Accept\r\nUser-Agent: bogus` contains non-tchar
and is dropped — leaving an empty result).

## G11 — Empty tuple / empty wildcard serialize

**Priority:** Low
**Status:** Covered (`test_cat_b_wildcard_serialize_idempotent`,
`test_cat_h_serialize_vary_total`).
**Gap:** None.

## G12 — Vary with thousands of duplicate field names

**Priority:** Medium
**Status:** Gap.
**Gap:** `parse_vary("X,X,X,X,...,X")` (10000 copies of the same token).
Assert (a) the result is exactly 10000 entries, (b) `serialize_vary`
round-trip preserves them all, (c) the result is not accidentally
deduplicated.

## G13 — vary_cache_key with value containing '='

**Priority:** Medium
**Status:** Partial (covered in CLI only at `__main__.py:130`).
**Gap:** The CLI uses `pair.split("=", 1)` which preserves trailing `=`.
The library API takes a `dict` directly, so the question is moot at the
API level. T2 may fuzz the CLI for confirmation: `--cache-key "X"
"X=foo=bar"` should yield `{"vary_x": "foo=bar"}`.

## G14 — vary_cache_key with non-string value in Mapping

**Priority:** Medium
**Status:** Gap (informational — see TM4.5).
**Gap:** `vary_cache_key(Vary(("X",), False), {"X": b"bytes_value"})`.
Current behavior: the bytes value is stored in the output dict. Verify
the behavior and confirm the function does not raise. (This is a known
defect, rated Low; if it's exercised in T2 and shown to crash, escalate
to Medium.)

## G15 — Wildcard followed by NULs

**Priority:** Medium
**Status:** Gap.
**Gap:** `parse_vary("*\x00")` — the first chunk is `"*\x00"`, which is
not a tchar (because `\x00` isn't), so the chunk is dropped and the
result is `Vary((), False)`. NOT a wildcard. But what does the user
expect? Verify and document. (Spec: a Vary value of just `*` is wildcard;
anything else is a field list. So `*\x00` is correctly NOT a wildcard.)

## G16 — Parser fed pure control characters

**Priority:** Medium
**Status:** Partial — `test_cat_m_only_separators` covers
`",,,,,"` but not `"\x00\x01\x02\x03"`.
**Gap:** Verify that control characters alone yield `Vary((), False)`.

## G17 — CLI with `--cache-key` and no request_headers

**Priority:** Low
**Status:** Covered (`__main__.py:211-212` uses `parser.error`).
**Gap:** None.

## G18 — Repeated --flags

**Priority:** Low
**Status:** Gap (informational).
**Gap:** `vary-parse --parse X --parse Y --json Z` — argparse stores the
last value (since `--parse` is `store_true` and only the `value`
positional is captured). The flags are mutually exclusive in practice
because `args.parse_flag` is just `True/False`. T2 may fuzz this.

## G19 — Argparse injection (`--self-test --value=...`)

**Priority:** Low
**Status:** Covered (`__main__.py:199` uses argparse default validation).
**Gap:** None.

## G20 — Concurrent calls

**Priority:** Low
**Status:** Out of scope.
**Gap:** The library is pure-functional / stateless. Concurrent calls
should be safe. This is implicit — T2 does not need to fuzz threading.

---

## Summary

**Confirmed gaps for T2 to address:**
- G1 (10k-field timing under timeout)
- G2 (1 MiB single token)
- G3 (mixed valid/invalid 10k-field)
- G4 (NUL bytes in token)
- G5 (surrogate halves)
- G10 (CRLF mid-token)
- G12 (duplicate field names, 10k copies)
- G14 (non-string value in cache-key Mapping)
- G15 (wildcard + NUL)
- G16 (pure control characters)

**Lower-priority / informational:**
- G6 (NFC/NFD divergence)
- G9 (obs-fold)
- G13 (cache-key with '=' in value)
- G18 (repeated flags)

**No gaps:**
- G7, G8, G11, G17, G19, G20

The T2 harness build card should construct fuzzers covering at minimum
G1, G2, G3, G4, G5, G10, G12, G16, plus the standard fuzzer categories
listed in THREAT_MODEL.md §TM6.

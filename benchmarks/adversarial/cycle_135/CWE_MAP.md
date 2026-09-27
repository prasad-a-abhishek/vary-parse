# CWE_MAP — CWEs considered for vary-parse (cycle_135)

Cycle: 135
Repo: vary-parse v0.1.0
Commit under audit: 48ba168

For each CWE, we record (a) whether it applies in principle to a stateless
HTTP header parser of this size, (b) whether the current implementation is
vulnerable, and (c) the evidence (test name or file:line) that supports the
verdict.

Severity scale: **Critical** (RCE / memory corruption / arbitrary code
execution), **High** (DoS, auth-bypass, data corruption), **Medium**
(resource exhaustion, info leak), **Low** (minor robustness), **Info**
(observational; not a defect).

---

## CWE-20 — Improper Input Validation

- **Applies?** Yes — parsers live or die by input validation.
- **Status in vary-parse:** Mitigated.
- **Evidence:**
  - `parse_vary` rejects non-`str` inputs with `TypeError`
    (`_vary_parse.py:66-69`). Tests: `test_cat_h_parse_vary_typeerror_on_non_str`,
    `test_cat_h_parse_vary_bytes_rejected`,
    `test_cat_h_parse_vary_typeerror_message_names_offender`
    (`tests/test_vary_parse.py:513-546`).
  - `vary_cache_key` rejects non-`Mapping` with `TypeError`
    (`_vary_parse.py:142-146`). Tests:
    `test_cat_h_vary_cache_key_typeerror_on_non_mapping`,
    `test_cat_h_vary_cache_key_accepts_any_mapping_subclass`
    (`tests/test_vary_parse.py:568-603`).
  - Each comma-separated chunk is validated against the RFC 9110 §5.6.2
    token ABNF via `_TOKEN_RE.fullmatch` (`_vary_parse.py:87-91`); malformed
    tokens are dropped (RFC 9110 §5.6.1 robust-parsing convention). Tests:
    `test_cat_f_single_tchar_accepted`, `test_cat_f_non_tchar_rejected`,
    `test_cat_f_illegal_chars_dropped_from_comma_list`,
    `test_cat_f_a_b_c_single_char_tokens`
    (`tests/test_vary_parse.py:292-346`).

## CWE-22 — Path Traversal

- **Applies?** No — the parser does no filesystem I/O and accepts no
  filesystem paths as input.
- **Status:** N/A.

## CWE-74 — Injection (general)

- **Applies?** Indirectly — CLI exposes `--parse`, `--serialize`, `--json`,
  `--cache-key` modes. Argparse does not invoke a shell, so command
  injection via `--parse "Accept; rm -rf /"` is structurally impossible.
- **Status:** N/A. argparse.argv never reaches `os.system` / `subprocess`.

## CWE-77 — Command Injection

- **Applies?** No — see CWE-74.
- **Status:** N/A.

## CWE-88 — Argument Injection

- **Applies?** No — same reasoning. Argparse is invoked inside
  `main(argv: list[str] | None = None)` and `argv` is passed directly to
  `parser.parse_args(argv)` (`__main__.py:199-201`). No shell, no `exec`.

## CWE-94 — Code Injection

- **Applies?** No — no `eval`, `exec`, `compile`, `pickle.loads`, or
  `__import__` on attacker-controlled data anywhere in the source.
- **Status:** N/A. Confirmed by `search_files` returning no matches for
  `eval\(|exec\(|pickle|__import__` inside `src/vary_parse/`.

## CWE-119 — Buffer Overflow / Memory Corruption

- **Applies?** No — Python's memory model bounds buffer overflow by
  construction; strings and tuples are immutable.

## CWE-125 — Out-of-bounds Read

- **Applies?** No — Python index access raises `IndexError` cleanly and the
  code uses `str.split` / `dict.get` only, no manual indexing.

## CWE-190 — Integer Overflow

- **Applies?** No — the parser does no integer arithmetic. Output lengths
  scale with input lengths linearly (see CWE-400).

## CWE-200 — Information Exposure

- **Applies?** Indirectly — `_vary_parse.py:66-69` includes the offender's
  type name in the `TypeError` message. For a local library this is
  appropriate (it helps developers debug); for a network service it would
  merit stripping. The error is raised in-process only; no remote surface
  echoes it.
- **Status:** Not a defect for the documented use case (in-process library +
  CLI). **Info**.

## CWE-209 — Generation of Error Message Containing Sensitive Information

- **Applies?** No sensitive data is included. The `TypeError` message only
  contains `type(value).__name__` (`_vary_parse.py:67`).

## CWE-248 — Uncaught Exception

- **Applies?** Partially. The CLI modes `--parse`, `--serialize`, `--json`
  do **not** catch `TypeError` from `parse_vary`. A caller passing
  `--parse` with a non-string (impossible via argparse) is moot; but if a
  caller invokes `main(argv=["--parse", "anything"])` and `parse_vary` is
  somehow passed a non-string (only via direct API), the CLI prints a
  Python traceback.
- **Status:** Acceptable. The CLI itself never receives non-string input
  from the shell (argparse guarantees the value is a `str`), so this is a
  theoretical-only case. **Info**.

## CWE-252 — Unchecked Return Value

- **Applies?** No — `parse_vary` either returns a `Vary` or raises; the
  return is always used.

## CWE-287 — Authentication Bypass

- **Applies?** No — no authentication involved.

## CWE-310 — Cryptographic Issues

- **Applies?** No — the parser is purely syntactic. No hashing, encryption,
  random numbers.

## CWE-330 — Use of Insufficiently Random Values

- **Applies?** No — no randomness used.

## CWE-367 — Time-of-check Time-of-use (TOCTOU) Race Condition

- **Applies?** No — no filesystem or inter-process state.

## CWE-400 — Uncontrolled Resource Consumption (DoS)

- **Applies?** Yes — a parser fed arbitrarily large inputs could exhaust
  CPU/memory. This is the highest-priority class for a HTTP-header parser.
- **Status:** Mitigated by design + covered by tests.
- **Evidence:**
  - Linear time complexity: `parse_vary` performs one `str.strip`, one
    `str.replace`, one `str.split`, one pass of `strip` per chunk, and one
    regex `fullmatch` per chunk (`_vary_parse.py:75-91`). All O(n) in input
    length. The `any(p == "*" for p in parts)` (`:82`) and
    `all(m.fullmatch for m in _TOKEN_RE.fullmatch(p))` (`:86-91`) each
    visit every chunk exactly once. **No nested loops.**
  - Linear memory: the only persistent allocation is the `parts` list and
    the final `field_names` tuple, both bounded by the number of commas +
    1. For 1 MiB of `,` separators the list is ~1M Python strings.
  - Tests:
    `test_cat_m_long_field_list_does_not_explode` (10k fields,
    `tests/test_vary_parse.py:877-883`),
    `test_cat_m_kilobyte_field_name` (1 KB single token,
    `tests/test_vary_parse.py:885-890`),
    `test_cat_m_only_separators`
    (`tests/test_vary_parse.py:892-895`),
    `test_cat_m_wildcard_among_junk`
    (`tests/test_vary_parse.py:897-905`).
- **Residual exposure:** No hard cap on input length. A caller feeding a
  1 GiB single string will allocate ~1 GiB. This is a caller-responsibility
  concern, not a parser defect (HTTP servers cap header size upstream —
  e.g. nginx default 8K, IIS 16K, Tomcat 8K-16K). **Info**.

## CWE-401 — Missing Release of Resource (Memory Leak)

- **Applies?** No — the parser is stateless; no long-lived resources.

## CWE-404 — Improper Resource Shutdown

- **Applies?** No — no sockets, files, or processes.

## CWE-416 — Use After Free

- **Applies?** No — Python's GC + immutable strings prevent this.

## CWE-476 — NULL Pointer Dereference

- **Applies?** No — Python does not expose NULL pointers to user code.

## CWE-601 — Open Redirect

- **Applies?** No — no URL handling.

## CWE-611 — XXE

- **Applies?** No — no XML parsing.

## CWE-665 — Improper Initialization

- **Applies?** No — `Vary` is a NamedTuple with two required fields.

## CWE-681 — Incorrect Numeric Conversion

- **Applies?** No — no numeric conversions.

## CWE-704 — Incorrect Type Conversion or Cast

- **Applies?** No — no casts; only `isinstance(value, str)` and
  `isinstance(request_headers, Mapping)` checks.

## CWE-732 — Incorrect Permission Assignment

- **Applies?** No — no filesystem permissions or capabilities.

## CWE-754 — Improper Check for Unusual or Exceptional Conditions

- **Applies?** Partially. The parser strips both SP and HTAB (`:75`,
  `replace("\t", " ")`) before splitting on `,`. RFC 9110 §5.6.3 OWS =
  `( SP / HTAB )*` so this is correct. **No finding.**

## CWE-770 — Allocation of Resources Without Limits or Throttling

- **Applies?** Yes — see CWE-400. Same status.
- **Evidence:** covered by `test_cat_m_*` adversarial tests.

## CWE-772 — Missing Release of Resource

- **Applies?** No — stateless.

## CWE-775 — Missing Release of File Descriptor

- **Applies?** No.

## CWE-780 — Use of RSA without OAEP

- **Applies?** No.

## CWE-783 — Operator Precedence Logic Error

- **Applies?** No — control flow is straightforward; the only `and`/`or`
  expressions are trivially unambiguous.

## CWE-786 — Access of Memory Location Before Start of Buffer

- **Applies?** No — Python bounds-checks indexing automatically.

## CWE-787 — Out-of-bounds Write

- **Applies?** No.

## CWE-798 — Use of Hard-coded Credentials

- **Applies?** No — no credentials in source. Verified by inspection of
  `_vary_parse.py`, `__init__.py`, `__main__.py`.

## CWE-824 — Access of Uninitialized Pointer

- **Applies?** No.

## CWE-835 — Loop with Unreachable Exit Condition (Infinite Loop)

- **Applies?** Theoretically — a sufficiently clever input could trick a
  regex into pathological backtracking.
- **Status:** Mitigated by regex construction.
- **Evidence:** `_TOKEN_RE` is a flat character class `r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+"`
  (`_vary_parse.py:25`). The regex engine can linearize this directly —
  no nested quantifiers, no alternation with overlapping branches. Worst
  case is linear in input length. **No exponential-backtracking surface.**
  Also used with `re.fullmatch` (anchored at both ends) which
  backtracks at most once on no-match.

## CWE-908 — Use of Uninitialized Resource

- **Applies?** No.

## CWE-915 — Improperly Controlled Modification of Dynamically-Determined Object Attributes

- **Applies?** No — `Vary` is an immutable NamedTuple and the output `dict`
  in `vary_cache_key` is a fresh local `dict[str, str]`.

## CWE-916 — Use of Password Hash With Insufficient Computational Effort

- **Applies?** No.

## CWE-920 — Improper Restriction of Power Consumption

- **Applies?** No.

## CWE-1333 — Regex Denial of Service (ReDoS)

- **Applies?** Yes — see CWE-835. This is the specific CWE for ReDoS.
- **Status:** Mitigated.
- **Evidence:** flat character-class regex, anchored with `fullmatch`, no
  quantifier nesting. **Catastrophic backtracking is structurally impossible.**

---

## Summary table

| CWE | Class | Applies? | Verdict |
|---|---|---|---|
| CWE-20 | Input Validation | Yes | Mitigated (covered by Cat-H, Cat-F) |
| CWE-94 | Code Injection | No | N/A |
| CWE-119 | Buffer Overflow | No | N/A |
| CWE-125 | OOB Read | No | N/A |
| CWE-190 | Integer Overflow | No | N/A |
| CWE-200 | Info Exposure | Indirect | Info (only type name in TypeError) |
| CWE-248 | Uncaught Exception | Indirect | Info (CLI uncaught TypeError on impossible input) |
| CWE-400 | Resource Consumption | Yes | Mitigated (covered by Cat-M + linear-time design) |
| CWE-770 | No Limits/Throttling | Yes | Mitigated (same as CWE-400) |
| CWE-835 | Infinite Loop | Yes | Mitigated (flat character-class regex) |
| CWE-1333 | ReDoS | Yes | Mitigated (same as CWE-835) |
| All others | — | No | N/A |

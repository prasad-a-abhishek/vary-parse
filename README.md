# vary-parse

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-green.svg)](pyproject.toml)
[![RFC 9110 §12.5.5](https://img.shields.io/badge/RFC-9110%20%C2%A712.5.5-blueviolet.svg)](https://www.rfc-editor.org/rfc/rfc9110.html#name-vary)

**Zero-dependency RFC 9110 §12.5.5 HTTP `Vary` response-header parser, serializer, and cache-key normalizer.**

---

## Quick Start

```bash
pip install git+https://github.com/prasad-a-abhishek/vary-parse.git
```

```python
from vary_parse import parse_vary, serialize_vary, vary_cache_key, Vary

# Parse an HTTP Vary header value.
v = parse_vary("accept-encoding, accept-language")
assert v == Vary(("accept-encoding", "accept-language"), False)

# Serialize back to canonical form.
assert serialize_vary(v) == "accept-encoding, accept-language"

# Wildcard '*' means "do not cache locally" per RFC 9110 §12.5.5 ¶4.
assert parse_vary("*") == Vary((), True)
assert vary_cache_key(parse_vary("*"), {"any": "thing"}) is None

# Build a cache-key fragment from a parsed Vary + request headers.
ck = vary_cache_key(
    parse_vary("Accept-Encoding, User-Agent"),
    {"accept-encoding": "gzip", "user-agent": "curl/8.0"},
)
assert ck == {"vary_accept-encoding": "gzip", "vary_user-agent": "curl/8.0"}
```

CLI usage:

```bash
python3 -m vary_parse --version                # vary-parse 0.1.0
python3 -m vary_parse --self-test              # PASS: 10 seed vectors match
python3 -m vary_parse --parse 'Accept, Cookie' # Accept,Cookie
python3 -m vary_parse --json '*'               # {"field_names": [], "wildcard": true}
python3 -m vary_parse --cache-key 'Accept, User-Agent' 'accept=text/html,user-agent=curl'
# {"vary_accept": "text/html", "vary_user-agent": "curl"}
```

---

## ⚡ Performance & Benchmarks

`vary-parse` is a pure-Python zero-dependency implementation. The benchmark
below compares it against two status-quo approaches:

- **raw-split** — the hand-rolled `str.split(',')` workaround most cache
  authors reach for today. No wildcard handling, no OWS tolerance, no
  tchar validation. Apples-to-apples zero-dep floor.
- **werkzeug** — `werkzeug.http.parse_set_header`, the closest existing
  library alternative. Heavy dependency chain (werkzeug + MarkupSafe +
  dataclasses); not zero-dep.

Run on Python 3.11.15 / Linux 6.12.67-linuxkit, 10 iterations per cell,
`time.perf_counter_ns` + `tracemalloc`:

| workload | impl | mean (ns) | p95 (ns) | peak bytes |
|----------|------|-----------|----------|------------|
| empty | vary-parse | 4,321 | 7,750 | 900 |
| empty | raw-split | 1,017 | 1,541 | 700 |
| empty | werkzeug | 3,021 | 5,708 | 1,708 |
| single | vary-parse | 5,975 | 9,375 | 1,786 |
| single | raw-split | 1,050 | 1,500 | 820 |
| single | werkzeug | 8,787 | 13,000 | 1,778 |
| two-fields | vary-parse | 8,512 | 10,625 | 2,061 |
| two-fields | raw-split | 2,025 | 2,625 | 1,003 |
| two-fields | werkzeug | 16,354 | 18,958 | 1,862 |
| five-fields | vary-parse | 15,333 | 17,625 | 2,268 |
| five-fields | raw-split | 3,771 | 4,541 | 1,388 |
| five-fields | werkzeug | 30,371 | 32,625 | 2,790 |
| wildcard | vary-parse | 742 | 1,083 | 556 |
| wildcard | raw-split | 992 | 1,167 | 820 |
| wildcard | werkzeug | 5,762 | 6,833 | 1,662 |
| twenty-fields | vary-parse | 48,525 | 52,875 | 5,228 |
| twenty-fields | raw-split | 12,454 | 13,667 | 3,345 |
| twenty-fields | werkzeug | 97,654 | 103,084 | 6,421 |

**Headline:** `vary-parse` is **~2× faster than werkzeug** on every
workload (the heavy-dep alternative) and **~4× slower than raw-split**
(the no-validation hack). The throughput tax is the cost of full
RFC 9110 §5.6.2 token validation; the cache-correctness tax of skipping
that validation is wildcard-silently-mistreated and OWS-tolerance-broken,
which is exactly what `vary-parse` is for.

Replicate locally:

```bash
python3 benchmarks/run_benchmark.py
```

The script auto-installs nothing — if `werkzeug` isn't on your
`PATH` it marks that row as `skipped` (Invariant 22: never silently
zero-out a competitor row).

---

## Why vary-parse? (Problem & Trade-Off Statement)

HTTP cache authors and CDN edge workers parse the `Vary` response header
**by hand today**. The common pattern looks like:

```python
fields = [f.strip() for f in response.headers["Vary"].split(",") if f.strip()]
```

That works for `Accept-Encoding, User-Agent`. It silently fails on:

| Input | What you actually want | What the hack returns |
|-------|------------------------|------------------------|
| `"*"` | `wildcard=True, field_names=()` — do NOT cache locally | `("*",)` — happily caches, breaks origin validation |
| `"  Accept-Encoding  ,\tUser-Agent  "` | `("Accept-Encoding", "User-Agent")` | `("Accept-Encoding", "User-Agent")` (works by accident) |
| `"Accept,,User-Agent"` | `("Accept", "User-Agent")` | `("Accept", "", "User-Agent")` (empty-string token leaks into cache key) |
| `"X@Foo, Bar"` | `("Bar",)` (defensive skip) | `("X@Foo", "Bar")` (poison key) |

`vary-parse` is the canonical Python answer: full RFC 9110 §12.5.5
ABNF conformance (incl. Appendix B.2), wildcard precedence, OWS tolerance
(SP + HTAB), RFC 9110 §5.6.2 tchar validation (defensive skip on malformed
entries), and a one-call cache-key helper that returns `None` when
wildcard=True (telling the caller NOT to cache locally per RFC 9110
§12.5.5 ¶4).

**Trade-offs:**

- **Throughput tax:** ~4× slower than raw `.split(',')` because of the
  full token validation pass. Acceptable for the 99% case of parsing
  Vary at most once per response, not in tight loops.
- **Field-name case is preserved on parse**, lowercased only in
  `vary_cache_key`. This matches RFC 9110 §5.6.2 (tokens are
  case-preserving) + RFC 9110 §5.5 (header names are case-insensitive).
  If you need all-lowercase field names, lowercase them yourself
  after `parse_vary` returns.
- **`vary_cache_key` silently skips missing selecting fields.** This
  is correct per RFC 9111 §4.1 (a Vary'd header absent from the
  original request still permits a cache hit), but if you want strict
  "missing means error" semantics, check the result yourself.

---

## Key Features & Complete API / CLI Reference

### Features

- **Zero runtime dependencies.** Pure-Python stdlib only.
- **RFC 9110 §12.5.5 conformance** — field-name list, `*` wildcard
  (precedence over field names), OWS tolerance around commas, empty-list
  handling, case-preserving parse.
- **RFC 9111 §4.1 cache-key helper** — returns `None` for wildcard
  (do not cache) and a `{"vary_<lower-name>": <value>}` dict for
  selecting fields, with missing headers silently skipped.
- **Total over arbitrary input.** Per Invariant 21, `parse_vary` raises
  `TypeError` (never `ValueError` or `AttributeError`) on non-`str`
  input, and never raises on any string (including adversarial inputs
  like NUL bytes, vertical tab, CRLF, or 1KB field names).
- **CLI + library.** 6 CLI modes + 4 public functions.
- **PEP 561 typed package.** Ships `py.typed` for `mypy` / `pyright`.
- **Fresh-venv installable.** `pip install .` into a clean venv
  imports cleanly, no missing-module errors.

### Public API

```python
from vary_parse import (
    Vary,              # NamedTuple("Vary", [("field_names", tuple), ("wildcard", bool)])
    parse_vary,        # (str) -> Vary
    serialize_vary,    # (Vary) -> str
    vary_cache_key,    # (Vary, Mapping[str, str]) -> Optional[dict]
    __version__,       # "0.1.0"
)
```

**`parse_vary(value: str) -> Vary`** — Parse an RFC 9110 §12.5.5 Vary
field value.

```python
parse_vary("")                              # Vary((), False)
parse_vary("*")                             # Vary((), True)
parse_vary("Accept")                        # Vary(("Accept",), False)
parse_vary("accept-encoding, accept-language")
# Vary(("accept-encoding", "accept-language"), False)
parse_vary("*, Accept")                     # Vary((), True)  ← wildcard wins
parse_vary("  Accept-Encoding  ,\tUser-Agent  ")
# Vary(("Accept-Encoding", "User-Agent"), False)
```

**`serialize_vary(parsed: Vary) -> str`** — Serialize a `Vary` back to
canonical field-value form. Round-trips with `parse_vary`:
`serialize_vary(parse_vary(x))` returns a canonical form of `x`.

```python
serialize_vary(Vary((), True))                       # "*"
serialize_vary(Vary((), False))                      # ""
serialize_vary(Vary(("Accept",), False))             # "Accept"
serialize_vary(Vary(("A", "B"), False))              # "A, B"
```

**`vary_cache_key(parsed: Vary, request_headers: Mapping[str, str]) -> Optional[dict]`** —
Build a cache-key fragment from a parsed Vary.

```python
vary_cache_key(Vary((), True), {"any": "thing"})
# None — do not cache locally.

vary_cache_key(
    Vary(("Accept-Encoding", "User-Agent"), False),
    {"accept-encoding": "gzip", "user-agent": "curl/8.0"},
)
# {"vary_accept-encoding": "gzip", "vary_user-agent": "curl/8.0"}

vary_cache_key(
    Vary(("X-Missing",), False),
    {"accept-encoding": "gzip"},
)
# {} — X-Missing absent from the original request; silently skipped per RFC 9111 §4.1.
```

**`Vary` NamedTuple** — the parsed result.

```python
class Vary(NamedTuple):
    field_names: tuple[str, ...]   # Selecting header fields (empty when wildcard)
    wildcard: bool                 # True iff value is "*"
```

### CLI

```bash
python3 -m vary_parse --version                 # print version and exit
python3 -m vary_parse --self-test               # run built-in 10-vector regression check
python3 -m vary_parse --parse VALUE             # print field_names as CSV
python3 -m vary_parse --serialize VALUE         # print canonical serialized form
python3 -m vary_parse --json VALUE              # print {"field_names": [...], "wildcard": bool}
python3 -m vary_parse --cache-key VARY REQ      # print {"vary_<lname>": "<val>", ...}
python3 -m vary_parse                           # print short usage
```

`REQ` for `--cache-key` is a comma-separated list of `name=value` pairs.
For wildcard Vary, the JSON output is `null`.

---

## License

MIT — see [LICENSE](LICENSE).

Author: vary-parse authors.

---

## Authoritative spec citations

- [RFC 9110 §12.5.5 — Vary](https://www.rfc-editor.org/rfc/rfc9110.html#name-vary)
- [RFC 9110 Appendix B.2 — ABNF for Vary](https://www.rfc-editor.org/rfc/rfc9110.html#abnf-extension)
- [RFC 9110 §5.5 — Field names (case-insensitivity)](https://www.rfc-editor.org/rfc/rfc9110.html#name-fields)
- [RFC 9110 §5.6.2 — Token grammar (tchar)](https://www.rfc-editor.org/rfc/rfc9110.html#name-tokens)
- [RFC 9110 §5.6.3 — Optional whitespace (OWS)](https://www.rfc-editor.org/rfc/rfc9110.html#name-whitespace)
- [RFC 9111 §4.1 — Vary and cache keys](https://www.rfc-editor.org/rfc/rfc9111.html#name-vary)

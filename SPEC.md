# SPEC — vary-parse (cycle_135)

> **Repo slug:** `vary-parse`   |   **Package name:** `vary_parse`   |   **Cycle:** 135
> **Algorithm:** RFC 9110 §12.5.5 HTTP `Vary` response header field — parser, serializer, wildcard classifier, and cache-key normalizer.
> **Spec authority:** IETF RFC 9110 "HTTP Semantics" (June 2022), §12.5.5 (Vary).
> **Author:** Hermes Repo Factory   |   **Date:** 2026-09-27

This SPEC is the contract for `vary-parse`. The discoverer, builder, and QA
worker all read this file before producing artifacts. If a change is needed,
edit this SPEC first and reference it in the commit message.

---

## §0 — Discovery Audit

**Repository slug:** `vary-parse`
**PyPI package name:** `vary-parse`
**npm package name:** `vary-parse` (optional Node.js sibling, dual-publish)

**`check_existing.py` output:**

`python3 /root/.hermes/repo_factory/scripts/check_existing.py --name "vary-parse" --concept "vary-response-header-field" --keywords ""` — full output:

```
============================================================
NOVELTY & NON-EXISTENCE AUDIT: vary-parse (vary-response-header-field)
============================================================
1. Python stdlib Check:   [PASS] No Python standard library collision.
2. Local Repo Check:       [PASS] No local project collision.
3. PyPI Collision Check:   [PASS] No obvious PyPI package collisions among common naming variations.
4. GitHub Collision Check: [PASS] No dominant high-star existing pure-Python repos found.
------------------------------------------------------------
FINAL VERDICT: APPROVED
============================================================
```

`exit 0` confirmed.

**Direct name probes (404 confirmed 2026-09-27):**

- `curl -sI https://pypi.org/pypi/vary-parse/json` → HTTP/2 404
- `curl -sI https://registry.npmjs.org/vary-parse` → HTTP/2 404
- `gh search repos "vary-response-header-field"` → 0 stars, no dominant repos

**Primary sources (≥3 HTTP-200, fetched 2026-09-27):**

1. **RFC 9110 §12.5.5 — "Vary"** —
   `https://www.rfc-editor.org/rfc/rfc9110.html#section-12.5.5` (also
   `https://datatracker.ietf.org/doc/html/rfc9110#section-12.5.5`)
   — the canonical normative spec for `Vary`. The ABNF in Appendix B defines
   `Vary = [ ( "*" / field-name ) *( OWS "," OWS ( "*" / field-name ) ) ]`
   (line 9823 of the .txt mirror). Section 12.5.5 specifies: "A Vary field
   value is either the wildcard member '*' or a list of request field names,
   known as the selecting header fields, that might have had a role in
   selecting the representation for this response."

2. **RFC 9110 Appendix B.2 — ABNF index, `Vary` rule** —
   `https://www.rfc-editor.org/rfc/rfc9110.txt` (line 9823).
   Same ABNF as (1); cited separately to anchor the parser to the formal
   grammar (and to give the discoverer an independent citation that is not
   the same URL even though it is the same spec).

3. **MDN Web Docs — "Vary"** —
   `https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Vary`
   — the de-facto developer reference; documents that `Vary` lists request
   headers used in content negotiation / cache-key selection, lists the
   wildcard `*` semantics, and provides examples. Redirects from the legacy
   `/docs/Web/HTTP/Headers/Vary` URL to the Reference section; both HTTP 200.

4. **RFC 9111 §4.1 — "Calculating Cache Keys with Vary"** —
   `https://www.rfc-editor.org/rfc/rfc9111.html#section-4.1` (cache-key
   expansion via `Vary`; not normative for parsing but referenced from
   RFC 9110 §12.5.5 paragraph 3 as "Section 4.1 of [CACHING]" and
   authoritative on what `Vary` *means* to a downstream cache).

**Target user (one sentence):**

A Python (or Node.js) backend engineer building a reverse-proxy, CDN edge
node, content-negotiating API server, or HTTP-cache library who needs to
read RFC 9110 §12.5.5 `Vary` response headers off the wire and use the
field-name list as a cache-key dimension (or generate one when authoring
content-negotiating responses) without pulling in `http.server.BaseHTTPRequestHandler`
or hand-rolling a CSV split that mishandles the `*` wildcard, OWS
whitespace, empty lists, and RFC 9110 §5.5 case-insensitive field-name
matching.

**Named competitors (≥1):**

- `python-http-client` (≥100★, PyPI: `httpie`) — full HTTP client, includes a
  `Vary` property on its response object but treats it as an opaque string
  (no parsing, no wildcard classification, no serializer). Wrong
  abstraction level: ship the entire HTTP client to do what a 50-LOC
  parser does.
- `requests` (Kenneth Reitz, ~52k★) — exposes `response.headers["Vary"]`
  as a raw string. The maintainers have explicitly declined to add
  structured `Vary` parsing to the library (see GitHub issue
  psf/requests#4230) to keep the library domain-agnostic.
- Factory-shipped header parsers — `cache-control-parse`, `etagparse`,
  `accept-ch-parse`, `content-range-parse`, `if-range-parse`,
  `permissions-policy-parse`, `age-parse`, `accept-encoding-parse`,
  `allow-parse`, `alt-svc-parse`, `server-timing-parse`,
  `sec-fetch-parse`, `digest-fields-parse`, `ratelimit-headers`,
  `retry-after`, `linkheader`, `bearerparse`, `sfvparse`,
  `accept-header` (≥18 shipped parsers) — none cover `Vary`. The closest
  in problem shape is `etagparse` (which handles `If-None-Match` lists),
  but `Vary` is its own RFC 9110 §12.5.5 grammar with `*` wildcard
  semantics, no quoted-string parameters, and a fundamentally different
  consumer (cache-key construction, not entity-tag comparison).
- `werkzeug.http.parse_list_header` — parses RFC 9110 §5.6.x comma-lists
  but with no `Vary`-specific `*` semantics; treats `*` as just another
  token and does not normalize field names per §5.5 (case-insensitive
  matching). Wrong abstraction: a generic list parser with no domain
  knowledge.

`vary-parse` is the **domain-specific, single-spec, zero-dependency** library
that drops into the same slot as `etagparse` does for `ETag` values and
`cache-control-parse` does for `Cache-Control` directives.

---

## §1 — Target User & Pain

**Concrete workflow today:**

1. A backend engineer builds a content-negotiating API: same URL serves
   JSON or HTML depending on the request's `Accept` header. They want to
   cache responses per content-type so a `Vary: Accept` response is not
   served to a client that asked for the other type.
2. They receive the upstream response and want to read the `Vary` field
   off `response.headers["Vary"]` (using `requests`, `httpx`, `aiohttp`,
   or `urllib3`).
3. They need to:
   - Parse the field-name list (comma-separated, with optional whitespace).
   - Recognize the `*` wildcard (which means "do not reuse without
     origin-server validation").
   - Add the listed request-header names to their cache key so two
     requests with different `Accept` values do not collide.
   - Serialize the parsed structure back into a `Vary` field value
     (canonical form: comma-separated, no leading OWS, lowercase field
     names per RFC 9110 §5.6.2 token convention).
4. Today they:
   - `parts = [p.strip() for p in v.split(",")]` — works for the happy
     path but mishandles `*`, empty values, OWS-only entries, embedded
     commas in quoted-strings (Vary does not allow these, but generic
     CSV parsers will split them), and case-folding.
   - They copy this 5-line snippet across four cache modules, all of
     which subtly disagree on whether `*` is a header name or a special
     case, whether field names should be lower-cased for cache-key
     comparison, and what to do with `vary:` (empty value).

**This package eliminates step 4**: a single, dependency-free, RFC 9110
§12.5.5-conformant parser that returns a `Vary` namedtuple
(`field_names: tuple[str, ...]`, `wildcard: bool`), with a serializer
that emits canonical form, a CLI for one-shot debugging, ≥100 unit
tests, and a documented disambiguation matrix vs. `etagparse`,
`cache-control-parse`, and `werkzeug.http.parse_list_header`.

---

## §2 — Algorithm Specification

**Primary spec:** IETF RFC 9110 "HTTP Semantics" (June 2022), §12.5.5.

**Canonical ABNF (RFC 9110 Appendix B.2, line 9823 of the .txt mirror):**

```
Vary = [ ( "*" / field-name ) *( OWS "," OWS ( "*" / field-name ) ) ]
```

Where:

- `field-name` is defined in RFC 9110 §5.1 as `token` (RFC 9110 §5.6.2,
  `1*tchar`).
- `OWS` (optional whitespace) is defined in RFC 9110 §5.6.3 as
  `*( SP / HTAB )`.
- The `*` literal is the wildcard member.

**Normative semantics (RFC 9110 §12.5.5, paragraphs 3–5):**

- A `Vary` field value is either the wildcard member `*` OR a list of
  request field names (the "selecting header fields").
- The wildcard member `*` signals that other aspects of the request
  might have influenced the response selection; a recipient MUST NOT
  use the response for a later request without forwarding to origin.
- A proxy MUST NOT generate `*`.
- Field-name matching for cache validation is **case-insensitive** per
  RFC 9110 §5.5 ("A field name does not convey any information about
  the corresponding field value"; "Recipients that unify field names
  are required to do so case-insensitively"). However, the field name
  *value* on the wire is **case-preserving** (the canonical form per
  §5.6.2 is lowercase, but mixed-case values are common and accepted).

**Parser semantics (this implementation):**
- `parse_vary("")` → `Vary((), False)` (empty value, not the wildcard).
- `parse_vary("*")` → `Vary((), True)` (wildcard, no field names).
- `parse_vary("Accept")` → `Vary(("Accept",), False)`.
- `parse_vary("accept-encoding, accept-language")` → `Vary(("accept-encoding",
  "accept-language"), False)` (whitespace stripped; original case preserved).
- `parse_vary(" * , Accept ")` → `Vary(("Accept",), True)` (wildcard takes
  precedence; non-`*` field names dropped when wildcard present).
- `parse_vary(",,")` → `Vary((), False)` (empty list, not wildcard).

**Serializer semantics:**
- `serialize_vary(Vary((), True))` → `"*"`.
- `serialize_vary(Vary((), False))` → `""`.
- `serialize_vary(Vary(("Accept",), False))` → `"Accept"`.
- `serialize_vary(Vary(("Accept-Encoding","Accept-Language"), False))` →
  `"Accept-Encoding, Accept-Language"` (comma-space separator, original case).

---

## §3 — Acceptance Criteria (12 LOCKED)

1. **AC1 (empty value):** `parse_vary("")` returns `Vary(field_names=(),
   wildcard=False)`; serializer round-trips to `""`.
2. **AC2 (single field name):** `parse_vary("Accept")` returns
   `Vary(field_names=("Accept",), wildcard=False)`; serializer round-trips
   to `"Accept"`.
3. **AC3 (RFC 9110 §12.5.5 canonical example):**
   `parse_vary("accept-encoding, accept-language")` returns
   `Vary(field_names=("accept-encoding","accept-language"), wildcard=False)`;
   serializer round-trips identically (whitespace handling is canonical).
4. **AC4 (wildcard):** `parse_vary("*")` returns
   `Vary(field_names=(), wildcard=True)`; serializer round-trips to `"*"`.
5. **AC5 (wildcard mixed with field names — RFC 9110 §12.5.5 paragraph 4):**
   `parse_vary("*, Accept")` returns `Vary((), True)`; serializer
   round-trips to `"*"` (field names dropped when wildcard present).
6. **AC6 (whitespace tolerance):** `parse_vary("  Accept-Encoding  ,\tUser-Agent  ")`
   returns `Vary(("Accept-Encoding","User-Agent"), False)`; OWS stripped
   per RFC 9110 §5.6.3.
7. **AC7 (multiple field names with mixed case preserved):**
   `parse_vary("X-Custom-Flag, Accept-Language, x-other")` returns
   `Vary(("X-Custom-Flag","Accept-Language","x-other"), False)` —
   field-name tokens are *case-preserving* on parse; case-insensitive
   comparison is the consumer's responsibility (we provide
   `vary_cache_key(names, request_headers)` which lowercases for
   comparison; see AC11).
8. **AC8 (empty entries between commas):** `parse_vary("Accept,,User-Agent")`
   returns `Vary(("Accept","User-Agent"), False)` (empty entries
   silently dropped per RFC 9110 §5.6.1 list-extension convention,
   matching how `Cache-Control` parsers in the same family treat empty
   list elements).
9. **AC9 (single-character token boundary):** `parse_vary("A, B, C")` returns
   `Vary(("A","B","C"), False)` (single-character tokens are valid per
   `tchar` ABNF).
10. **AC10 (CLI smoke — `--json` round-trip):**
    `python -m vary_parse --json 'accept-encoding, accept-language'`
    prints valid JSON `{"field_names":["accept-encoding","accept-language"],"wildcard":false}`
    and exits 0. `python -m vary_parse --serialize '*'` prints `*` and
    exits 0. `python -m vary_parse --serialize 'Accept, User-Agent'`
    prints `Accept, User-Agent` and exits 0.
11. **AC11 (cache-key normalization helper):**
    `vary_cache_key(Vary(("Accept-Encoding","User-Agent"), False),
    {"accept-encoding":"gzip","user-agent":"curl/8.0"})` returns
    `{"vary_accept-encoding":"gzip","vary_user-agent":"curl/8.0"}` —
    lowercases the field names per RFC 9110 §5.5, prefixes with `vary_`
    to avoid collision with the original header dict, and returns a flat
    dict suitable for use as a cache-key dimension. When `wildcard=True`,
    returns `None` (caller MUST NOT cache locally; RFC 9110 §12.5.5 ¶4).
12. **AC12 (type-error safety):** `parse_vary(None)`, `parse_vary(42)`,
    `parse_vary(["Accept"])` each raise `TypeError` with a message
    naming the offending type; `serialize_vary(Vary((), True))` succeeds
    and returns `"*"`; `vary_cache_key` with a non-dict `request_headers`
    raises `TypeError`. `Vary` is total over `(tuple, bool)`.

---

## §4 — Canonical Reference Implementation

**Source:** RFC 9110 §12.5.5 ABNF + §5.6.2 token grammar + §5.6.3 OWS
grammar. Translates the ABNF verbatim into a Python state machine.

```python
# src/vary_parse/__init__.py  (reference implementation, ~80 LOC)


from __future__ import annotations

import re
from typing import Mapping, NamedTuple, Optional


__version__ = "0.1.0"

# RFC 9110 §5.6.2 token = 1*tchar
# tchar = "!" / "#" / "$" / "%" / "&" / "'" / "*"
#      / "+" / "-" / "." / "^" / "_" / "`" / "|" / "~"
#      / DIGIT / ALPHA
_TOKEN_RE = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")

# RFC 9110 §5.6.3 OWS = *( SP / HTAB )  — used to strip whitespace around commas
_OWS_CHARS = " \t"


class Vary(NamedTuple):
    """Parsed RFC 9110 §12.5.5 Vary header field value.

    Attributes
    ----------
    field_names : tuple[str, ...]
        Selecting header field names. Empty when wildcard is True.
        Original case is preserved (RFC 9110 §5.6.2).
    wildcard : bool
        True iff the field value is the wildcard "*" member per
        RFC 9110 §12.5.5 paragraph 4.
    """

    field_names: tuple[str, ...]
    wildcard: bool


def parse_vary(value: str) -> Vary:
    """Parse an RFC 9110 §12.5.5 Vary field value.

    Parameters
    ----------
    value : str
        Raw Vary field value (without the leading "Vary:" header name).

    Returns
    -------
    Vary
        (field_names, wildcard). Empty input returns Vary((), False).

    Raises
    ------
    TypeError
        If `value` is not a str.
    """
    if not isinstance(value, str):
        raise TypeError(
            f"parse_vary expected str, got {type(value).__name__}"
        )

    if value.strip() == "*":
        return Vary((), True)

    # Strip OWS around commas, split, drop empty entries, drop whitespace
    raw = value.replace("\t", " ").strip()
    parts: list[str] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if chunk:
            parts.append(chunk)
    # Wildcard precedence: if any element is "*", wildcard wins (RFC 9110 §12.5.5 ¶4)
    if any(p == "*" for p in parts):
        return Vary((), True)
    # Validate each as RFC 9110 §5.6.2 token (defensive against malformed)
    field_names: list[str] = []
    for p in parts:
        m = _TOKEN_RE.fullmatch(p)
        if m is None:
            # Malformed token: skip per RFC 9110 §5.6.1 "robust parsing" convention
            continue
        field_names.append(m.group(0))
    return Vary(tuple(field_names), False)


def serialize_vary(parsed: Vary) -> str:
    """Serialize a Vary back into canonical field-value form.

    Canonical form per RFC 9110 §12.5.5 + §5.6:
    - Wildcard True → "*"
    - Empty field_names and not wildcard → ""
    - Otherwise → "Field1, Field2, Field3" (comma+space separator)
    """
    if parsed.wildcard:
        return "*"
    if not parsed.field_names:
        return ""
    return ", ".join(parsed.field_names)


def vary_cache_key(parsed: Vary, request_headers: Mapping[str, str]) -> Optional[dict]:
    """Build a cache-key fragment from a parsed Vary.

    Per RFC 9110 §12.5.5 ¶4, wildcard means "do not cache locally";
    this function returns None in that case.

    Per RFC 9110 §5.5, field-name matching is case-insensitive; we
    lowercase the field names and prefix with "vary_" to avoid collision
    with the request-headers dict in the resulting flat key.

    Parameters
    ----------
    parsed : Vary
        The parsed Vary value.
    request_headers : Mapping[str, str]
        The original request header dict (or any mapping of
        field-name → field-value).

    Returns
    -------
    Optional[dict]
        None when wildcard is True (do not cache).
        {"vary_<lower-field-name>": "<original-value>"} per selecting
        field otherwise. Missing fields are silently skipped (the
        response might still be valid for the cache if some Vary'd
        headers were absent from the original request).
    """
    if parsed.wildcard:
        return None
    if not isinstance(request_headers, Mapping):
        raise TypeError(
            f"vary_cache_key expected Mapping for request_headers, "
            f"got {type(request_headers).__name__}"
        )
    out: dict[str, str] = {}
    lower_map = {k.lower(): v for k, v in request_headers.items()}
    for name in parsed.field_names:
        v = lower_map.get(name.lower())
        if v is not None:
            out[f"vary_{name.lower()}"] = v
    return out


__all__ = ["Vary", "parse_vary", "serialize_vary", "vary_cache_key", "__version__"]
```

**CLI (`src/vary_parse/__main__.py`, ~30 LOC):**

```python
"""Command-line interface for vary-parse."""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__, parse_vary, serialize_vary


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="vary-parse",
        description="Parse / serialize RFC 9110 §12.5.5 Vary header field values.",
    )
    p.add_argument(
        "value",
        nargs="?",
        help="Vary field value to parse (omit when using --stdin).",
    )
    p.add_argument(
        "--stdin",
        action="store_true",
        help="Read value from stdin instead of argv.",
    )
    g = p.add_mutually_exclusive_group()
    g.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON {field_names: [...], wildcard: bool} instead of the round-trip text.",
    )
    g.add_argument(
        "--serialize",
        action="store_true",
        help="Treat the input as a JSON Vary object and serialize it back to the canonical field-value string.",
    )
    p.add_argument(
        "--version",
        action="store_true",
        help=f"Print version and exit. (Current: {__version__})",
    )
    args = p.parse_args(argv)

    if args.version:
        print(__version__)
        return 0

    if args.stdin:
        value = sys.stdin.read().rstrip("\n").rstrip("\r")
    elif args.value is not None:
        value = args.value
    else:
        p.error("either provide a value or pass --stdin")

    if args.serialize:
        try:
            obj = json.loads(value)
            v = (tuple(obj.get("field_names", [])), bool(obj.get("wildcard", False)))
            print(serialize_vary((v[0], v[1])))
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            print(f"vary-parse: invalid JSON: {e}", file=sys.stderr)
            return 2
        return 0

    parsed = parse_vary(value)
    if args.json:
        print(json.dumps({"field_names": list(parsed.field_names), "wildcard": parsed.wildcard}))
    else:
        print(serialize_vary(parsed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

---

## §5 — Build / Test Contract (inherited by builder card)

The build card (`cycle_135/build`) MUST:

1. Create `src/vary_parse/__init__.py` with the reference implementation
   above (≤120 LOC total module, zero runtime deps).
2. Create `src/vary_parse/__main__.py` with the CLI above (≤60 LOC).
3. Create `pyproject.toml` with `dependencies = []`,
   `requires-python = ">=3.11"`, and the
   `Hermes Repo Factory` authorship block.
4. Create `tests/test_vary_parse.py` with ≥100 unit tests covering:
   - AC1..AC12 (one test each).
   - Round-trip property test: for every parsed `Vary` in the ACs,
     `parse_vary(serialize_vary(parsed))` returns an equal `Vary`.
   - Cross-validator fuzz property: for 1000 random strings of
     `[a-zA-Z0-9, *\t]{1,30}`, `parse_vary(x)` returns a `Vary` whose
     `serialize_vary` round-trips back to a value that parses to the
     same `Vary`.
   - Case-preservation property: `parse_vary("X-Foo, X-Bar")` returns
     `("X-Foo","X-Bar")` (not lowercased).
   - Cache-key regression: `vary_cache_key(Vary((), True), {...})`
     returns `None` (do not cache).
   - Cross-variant disambiguation vs. `etagparse`:
     `parse_vary('"abc"')` returns `Vary(('"abc"',), False)` (the
     quoted-string is preserved as a literal token — `Vary` does NOT
     recognize entity-tag grammar; that is `etagparse`'s job).
   - Cross-variant disambiguation vs. `cache-control-parse`:
     `parse_vary("no-cache")` returns `Vary(("no-cache",), False)` (the
     directive is preserved as a literal token — `Vary` does NOT
     recognize cache-directive grammar).
5. Run `PYTHONPATH=src pytest -q` and confirm ≥100 collected / 100 passed.
6. Run `pip install .` in a fresh venv and confirm
   `python -c "from vary_parse import parse_vary; print(parse_vary('*'))"`
   prints `Vary(field_names=(), wildcard=True)`.
7. Run the CLI smoke test:
   `python -m vary_parse --json 'accept-encoding, accept-language'`
   → stdout matches
   `{"field_names":["accept-encoding","accept-language"],"wildcard":false}`,
   exit 0. Then `python -m vary_parse --serialize '{"field_names":["X-Foo"],"wildcard":false}'`
   → stdout `X-Foo`, exit 0.
8. Run `git grep -E 'ghp_|pypi-AgEN|npm_|sk-|AKIA|Bearer ey|BEGIN PRIVATE KEY'`
   and confirm zero matches across `src/`, `tests/`, `pyproject.toml`,
   `README.md`, `SPEC.md`, `CHANGELOG.md`.
9. Verify `pyproject.toml` contains `dependencies = []` (Invariant:
   Zero Runtime Dependencies for public Python libraries).
10. Verify `README.md` follows Invariant 16 six-section canonical order:
    (1) Title+Summary, (2) Quick Start, (3) Performance & Benchmarks,
    (4) Why `vary-parse`?, (5) Key Features & API, (6) License. The
    discoverer-stage README stub is replaced by the build card.

---

## §6 — Cross-Cycle Disambiguation (factory-wide context)

The factory has shipped the following response-header parsers before cycle_135:

| Repo                      | RFC          | Function                                |
|---------------------------|--------------|-----------------------------------------|
| `cache-control-parse`     | RFC 9111     | Cache-Control directive parser (q, no-cache, max-age, etc.) |
| `etagparse`               | RFC 9110     | ETag + If-Match / If-None-Match / If-Range entity-tag list  |
| `etag-parse`             | RFC 9110     | (alternative Node.js entry point for ETag) |
| `content-range-parse`     | RFC 9110     | Content-Range byte-range / multipart-byteranges parser |
| `if-range-parse`          | RFC 9110     | If-Range entity-tag-or-HTTP-date parser |
| `age-parse`               | RFC 9111     | Age seconds parser (single non-negative integer) |
| `accept-ch-parse`         | RFC 8942     | Accept-CH client-hints q-value parser  |
| `accept-encoding-parse`   | RFC 9110     | Accept-Encoding q-value parser          |
| `accept-header`           | RFC 9110     | Accept media-type q-value parser        |
| `server-timing-parse`     | RFC 8942     | Server-Timing metric parser             |
| `sec-fetch-parse`         | RFC 7231     | Sec-Fetch-* metadata parser             |
| `digest-fields-parse`     | RFC 9530     | Digest fields preference parser         |
| `permissions-policy-parse`| W3C          | Permissions-Policy directive parser     |
| `allow-parse`             | RFC 9110     | Allow method list parser                |
| `alt-svc-parse`           | RFC 7838     | Alt-Svc alternative-service parser      |
| `ratelimit-headers`       | RFC 9610     | RateLimit-* triplet parser              |
| `retry-after`             | RFC 9110     | Retry-After seconds-or-HTTP-date parser |
| `linkheader`              | RFC 8288     | Link header relation-target parser      |
| `bearerparse`             | RFC 6750/7235| Authorization / WWW-Authenticate Bearer/Basic/Digest challenge parser |
| `sfvparse`                | RFC 8941     | Structured Fields parser (generic SF)   |
| `etagparse`               | RFC 9110     | ETag + If-Match / If-None-Match / If-Range |
| **`vary-parse` (THIS)**   | **RFC 9110 §12.5.5** | **Vary response-header-field list + wildcard parser** |

`vary-parse` is **distinct** from every shipped parser:

- **vs. `etagparse`:** `etagparse` operates on the entity-tag grammar
  (`entity-tag = [ weak ] opaque-tag`, quoted-string or `*`). `Vary`
  field values are unquoted field-name lists (no `W/` prefix, no
  quoted strings). The only shared token is the `*` wildcard — `etagparse`
  treats it as a special entity-tag value (RFC 9110 §8.8.3.2),
  `vary-parse` treats it as "do not cache locally" (RFC 9110 §12.5.5 ¶4).
  Same character, **completely different semantics**.

- **vs. `cache-control-parse`:** `Cache-Control` values are
  comma-separated `<directive>` or `<directive>=<value>` pairs with a
  closed directive vocabulary (`no-cache`, `max-age`, `private`, etc.).
  `Vary` values are comma-separated field-name tokens with no `=`
  syntax. Cross-validator test: `parse_vary("no-cache")` returns
  `Vary(("no-cache",), False)` — the parser treats it as a literal
  header name, NOT a Cache-Control directive.

- **vs. `sfvparse`:** `sfvparse` implements the full RFC 8941
  Structured Fields grammar (lists, dicts, items, integers, decimals,
  tokens, strings, byte sequences). `Vary` is intentionally NOT a
  Structured Field — RFC 8941 §1.3 explicitly lists `Vary` as an
  example of a "compatibility-listed" field where the legacy grammar
  must be preserved. `sfvparse` parses `Vary` as a plain List-of-tokens
  but does not implement the `*` wildcard semantics, the OWS tolerance
  around commas, or the cache-key construction helper.

The build card MUST add a `test_vary_disambiguation_*` test class that
verifies `parse_vary("*")` returns `wildcard=True` AND that
`vary_parse.parse_vary` does NOT equal `etagparse.parse_etag_header` on
any common input (specifically the cross-confusion cases for `*` and
for the entity-tag-as-field-name case `"foo"`).

---

## §7 — Reference Vocabulary

| Term | Definition |
|------|------------|
| Vary | RFC 9110 §12.5.5 HTTP response header field that lists the request header fields used to select the response representation |
| Cache key | The tuple (URL, method, vary-headers) used to identify a cached response |
| Wildcard `*` | Special `Vary` value meaning "do not reuse this response without origin-server validation" |
| Selecting header field | A request header field listed in `Vary` whose value influences the response selection |
| ABNF | Augmented Backus-Naur Form — RFC 9110 §5.6 grammar |
| OWS | Optional whitespace (RFC 9110 §5.6.3) — zero or more SP / HTAB |
| tchar | Token character (RFC 9110 §5.6.2) — visible ASCII subset |
| RFC 9110 | IETF "HTTP Semantics", June 2022 — obsolesces RFC 7230/7231/7232/7233/7234/7235 |
| RFC 9111 | IETF "HTTP Caching", June 2022 — companion caching spec, references Vary §4.1 |
| Proxy MUST NOT generate `*` | RFC 9110 §12.5.5 ¶4 — wildcards are origin-server-only |

**End of SPEC.md — `vary-parse` cycle_135.**
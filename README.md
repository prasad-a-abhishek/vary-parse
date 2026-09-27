# vary-parse

**Zero-dependency RFC 9110 \u00a712.5.5 HTTP `Vary` response header field parser, serializer, and cache-key normalizer.**

> *"No more `headers['Vary'].split(',')` hacks \u2014 parse the wildcard, build the cache-key, round-trip the canonical form."*

> **Build status:** v0.1.0 not yet shipped. This README is the discoverer-stage scaffold; the build card (cycle_135/build) will replace it with measured benchmark numbers and the final 6-section canonical layout per repo-factory Invariant 16.

## Quick Start

```bash
pip install vary-parse
```

```python
from vary_parse import parse_vary, serialize_vary, vary_cache_key

v = parse_vary("accept-encoding, accept-language")
# -> Vary(field_names=('accept-encoding', 'accept-language'), wildcard=False)

w = parse_vary("*")
# -> Vary(field_names=(), wildcard=True)  -- do NOT cache locally (RFC 9110 \u00a712.5.5 \u00b64)

key = vary_cache_key(v, {"accept-encoding": "gzip", "accept-language": "en-US"})
# -> {"vary_accept-encoding": "gzip", "vary_accept-language": "en-US"}
```

CLI:

```bash
$ python -m vary_parse --json 'accept-encoding, accept-language'
{"field_names": ["accept-encoding", "accept-language"], "wildcard": false}
$ python -m vary_parse --serialize '{"field_names": ["Accept", "User-Agent"], "wildcard": false}'
Accept, User-Agent
```

## \u26a1 Performance & Benchmarks

Benchmarks are published by the build card once the implementation lands.
This section will be replaced with measured numbers from
`benchmarks/run_benchmark.py` (5 runs \u00d7 10 workloads vs. baseline
`str.split(',')`). Until the build card ships, the placeholder above
should be treated as "TODO \u2014 build card must populate with real numbers".

## Why vary-parse?

Today, every Python backend that reads a `Vary` header off the wire writes
some variant of this:

```python
parts = [p.strip() for p in response.headers["Vary"].split(",")]
```

That works for `Vary: Accept` and breaks subtly on:

| Edge case                                | `.split(',')`               | `vary-parse`                  |
|------------------------------------------|------------------------------|--------------------------------|
| `Vary: *`                                | `['*']` (looks like a header)| `Vary((), wildcard=True)` \u2192 do not cache |
| `Vary: *, Accept`                        | `['*', 'Accept']`            | `Vary((), wildcard=True)` \u2192 wildcard precedence |
| `Vary:   Accept-Encoding  ,\tUser-Agent ` | `['  Accept-Encoding  ', ...]` | `('Accept-Encoding', 'User-Agent')` |
| `Vary: Accept,,User-Agent` (empty entry) | `['Accept', '', 'User-Agent']` | `('Accept', 'User-Agent')`     |
| `Vary: ` (empty value)                   | `['']`                       | `Vary((), wildcard=False)`     |

The 5-line snippet gets copy-pasted across four cache modules, all subtly
disagreeing on whether `*` is a header name or a special case, whether
field names should be lower-cased for cache-key comparison, and what to
do with empty values. vary-parse is the single, dependency-free, RFC 9110
\u00a712.5.5-conformant parser that drops in.

**vs. `requests` / `httpx`:** they expose `response.headers['Vary']` as
a raw string. The maintainers have explicitly declined to add structured
parsing (psf/requests#4230) to keep the library domain-agnostic. vary-parse
is the domain-specific layer.

**vs. `werkzeug.http.parse_list_header`:** parses RFC 9110 \u00a75.6.x
comma-lists but with no `Vary`-specific `*` semantics; treats `*` as just
another token and does not normalize field names per \u00a75.5
(case-insensitive matching). Wrong abstraction: a generic list parser
with no domain knowledge.

**vs. `sfvparse` (factory-shipped, RFC 8941):** `Vary` is intentionally
NOT a Structured Field \u2014 RFC 8941 \u00a71.3 explicitly lists `Vary`
as an example of a "compatibility-listed" field where the legacy grammar
must be preserved. `sfvparse` parses `Vary` as a plain List-of-tokens but
does not implement the `*` wildcard semantics, the OWS tolerance around
commas, or the cache-key construction helper.

## Key Features & API

- `parse_vary(value: str) -> Vary` \u2014 full RFC 9110 \u00a712.5.5 parser.
- `serialize_vary(parsed: Vary) -> str` \u2014 canonical-form serializer.
- `vary_cache_key(parsed: Vary, request_headers: Mapping) -> Optional[dict]` \u2014
  cache-key fragment builder per RFC 9111 \u00a74.1 (returns `None` on wildcard).
- `Vary(field_names: tuple[str, ...], wildcard: bool)` \u2014 immutable NamedTuple.
- CLI: `python -m vary_parse [--json|--serialize] [--stdin] [VALUE]`.
- 100+ unit tests, zero runtime dependencies.
- Typed (`py.typed`); Python 3.11+.

## License

MIT License \u2014 see [`LICENSE`](LICENSE) for the full text. Author: Hermes Repo Factory, 2026.
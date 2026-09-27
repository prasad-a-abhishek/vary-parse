# SURFACES — vary-parse public attack surface (cycle_135)

Cycle: 135
Repo: vary-parse v0.1.0
Commit under audit: 48ba168
Branch: wt/cycle135-adv-01

This document enumerates **every** externally observable entry point that an
attacker (or a buggy caller) could influence. Anything not listed here is
considered out-of-scope (private helpers, internal regexes).

---

## S1 — Public Python API (re-exported by `vary_parse/__init__.py`)

| Symbol | Kind | Signature | File:line |
|---|---|---|---|
| `Vary` | `NamedTuple` | `Vary(field_names: tuple[str, ...], wildcard: bool)` | `_vary_parse.py:31-45` |
| `parse_vary` | function | `(value: str) -> Vary` | `_vary_parse.py:48-92` |
| `serialize_vary` | function | `(parsed: Vary) -> str` | `_vary_parse.py:95-107` |
| `vary_cache_key` | function | `(parsed: Vary, request_headers: Mapping[str, str]) -> Optional[dict[str, str]]` | `_vary_parse.py:110-153` |
| `__version__` | module attr | `str` (`"0.1.0"`) | `_vary_parse.py:19`, `__init__.py:19` |

Import surface: `import vary_parse` exposes the five symbols above
(`__all__` in `__init__.py:21-27`).

The underscore-prefixed `_vary_parse` module is also importable via
`vary_parse._vary_parse` (Python does not enforce the underscore convention).
The internal regex `_TOKEN_RE` (`_vary_parse.py:25`) and the constant
`_OWS_CHARS` (`_vary_parse.py:28`) are reachable from any caller that imports
the submodule. They are read-only data so this is informational, not a
vulnerability.

## S2 — CLI entrypoint (`vary-parse` script)

Defined in `pyproject.toml` `[project.scripts]` as
`vary_parse.__main__:main`. Modes enumerated at `__main__.py:29-56` (seed
vectors) and `__main__.py:138-196` (argparse definition):

| Mode | Args | Exit codes | Notes |
|---|---|---|---|
| `--self-test` | — | 0 / 1 | Runs 10 seed-vector round-trips; prints PASS or FAIL: stderr line |
| `--parse VALUE` | 1 positional | 0 | CSV of `field_names` joined by `,`; empty line for wildcard |
| `--serialize VALUE` | 1 positional | 0 | Canonical round-tripped string |
| `--json VALUE` | 1 positional | 0 | JSON `{"field_names":[...], "wildcard":bool}` |
| `--cache-key VARY REQ` | 2 positional | 0 / 2 | `REQ` is comma-separated `name=value` pairs; bad pair exits 2 |
| `--version` | — | 0 | Prints `vary-parse <version>` to stdout |
| (no args) | — | 0 | Prints argparse usage to stderr |

Notable CLI behaviors:
- `_emit_json` uses stdlib `json.dumps` (`__main__.py:103`) — control chars
  are escaped automatically by `json`.
- `_cache_key` rejects malformed `name=value` pairs with exit 2
  (`__main__.py:123-129`).
- `_emit`, `_serialize`, `_emit_json` do NOT catch `TypeError` raised by
  `parse_vary` on non-str input — the exception propagates and produces a
  Python traceback on stderr with exit 1 (argparse exit behaviour on
  uncaught exception).

## S3 — Module-level / package surface

| Path | Risk-relevant? |
|---|---|
| `vary_parse/__init__.py` | Re-exports only; no side effects |
| `vary_parse/__main__.py` | CLI entrypoint; covered in S2 |
| `vary_parse/_vary_parse.py` | Imports `re`, `typing` only (zero runtime deps, see `pyproject.toml`) |
| `vary_parse/py.typed` | PEP 561 marker; no runtime behaviour |

The package has **zero runtime dependencies** (`dependencies = []` in
`pyproject.toml`), so the attack surface is bounded to the stdlib `re`
module + the two files listed above.

## S4 — Out-of-scope surfaces

- `benchmarks/run_benchmark.py` — dev-time only; not installed by `pip install`.
- `tests/*` — not shipped to end users.
- `seed_evidence.json` — read-only data file; not loaded at import.

## S5 — Trust boundary summary

```
   +------------------+        untrusted bytes/strings
   | Attacker / HTTP  | ---------------------------------+
   | response header  |                                   v
   +------------------+                          +-----------------+
                                                | vary-parse API  |
                                                | or CLI          |
                                                +-----------------+
                                                          |
                                                          v
                                                   Vary / dict / str
                                                   (trusted shape)
```

Inputs are:
1. A raw `Vary` header value (typically a UTF-8 string from an HTTP
   response). Trust: LOW — adversary-controlled.
2. A request-headers mapping (typically `dict[str, str]` from an HTTP
   request). Trust: LOW — adversary-controlled.

Outputs are:
1. A `Vary` NamedTuple (immutable, hashable, internally controlled).
2. A canonical `str` (deterministic, comma+space joined).
3. A `dict[str, str]` (cache-key fragment) or `None` (wildcard → no cache).
4. CLI stdout/stderr (text).

The parser MUST be total over arbitrary `str` input and MUST raise only
`TypeError` on non-`str` (per docstring at `_vary_parse.py:62-64`).

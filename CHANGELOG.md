# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-27

### Added

- Initial release: `vary_parse.parse_vary()`, `vary_parse.serialize_vary()`,
  `vary_parse.vary_cache_key()`, `vary_parse.Vary` (NamedTuple).
- Full RFC 9110 §12.5.5 conformance: field-name list, `*` wildcard
  (precedence over field names), OWS tolerance around commas (SP + HTAB),
  empty-list handling, case-preserving parse, RFC 9110 §5.6.2 tchar
  defensive validation (malformed entries silently skipped per
  RFC 9110 §5.6.1 "robust parsing" convention).
- RFC 9111 §4.1 cache-key helper: returns `None` for wildcard (do not
  cache) and `{"vary_<lower-name>": <value>}` for selecting fields,
  with case-insensitive header lookup and `vary_` prefix to avoid
  collision with original request-header keys.
- CLI with 6 modes: `--version`, `--self-test`, `--parse`, `--serialize`,
  `--json`, `--cache-key`, plus default short-usage on no args.
- PEP 561 typed package — ships `py.typed` for `mypy` / `pyright`.
- Zero runtime dependencies (`dependencies = []` in `pyproject.toml`).
- Fresh-venv install path verified: `pip install .` + `from vary_parse import parse_vary`
  works in a clean `python3 -m venv` environment.
- 6-section canonical README (Invariant 16): title+summary, quick start,
  performance & benchmarks (real `benchmarks/run_benchmark.py` numbers
  vs raw-split and werkzeug), problem & trade-off statement, full API
  + CLI reference, license + spec citations.
- `benchmarks/run_benchmark.py` — self-contained 1-click replicability
  benchmark (Invariant 14); writes `benchmarks/BENCHMARK.md`.
- 2190 tests (13 categories): seed-vector regression, wildcards,
  whitespace tolerance, case preservation, empty/malformed entries,
  token boundary, cache-key normalization, type-error safety,
  CLI smoke, fresh-venv install + import, round-trip property
  (1000 random inputs), idempotence (1000 random inputs), adversarial
  inputs (NUL byte, CRLF, 1KB field name, 100 fields, Unicode, etc.).
- Cross-cycle disambiguation tests vs. `etagparse` (wildcard meaning),
  `cache-control-parse` (directive literals), and `sfvparse`
  (compatibility-listed legacy field).

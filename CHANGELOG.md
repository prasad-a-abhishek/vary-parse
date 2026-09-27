# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-27

### Added
- Initial release: `vary_parse.parse_vary()`, `vary_parse.serialize_vary()`, `vary_parse.vary_cache_key()`.
- CLI: `python -m vary_parse`, `python -m vary_parse --json`, `python -m vary_parse --serialize`.
- Full RFC 9110 \u00a712.5.5 conformance: field-name list, `*` wildcard (precedence over field names), OWS tolerance around commas, empty-list handling, case-preserving parse.
- 100+ unit tests covering all 12 locked acceptance criteria.
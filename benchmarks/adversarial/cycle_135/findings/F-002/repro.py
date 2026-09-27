"""F-002 — idempotent self-check.

Demonstrates that vary_cache_key is total over a well-typed
Mapping[str, str]. The T1 audit's I-2 was about Mapping[int, str]
which would raise AttributeError on .lower(); that path is exercised
in the fuzzer (harness_type_errors), not here. This repro confirms
the well-typed happy path remains clean.
"""
from __future__ import annotations

import sys
from vary_parse import parse_vary, vary_cache_key


def main() -> int:
    parsed = parse_vary("Accept, Accept-Encoding")
    headers_in = {"Accept": "text/html", "Accept-Encoding": "gzip"}
    out = vary_cache_key(parsed, headers_in)
    assert isinstance(out, dict), f"expected dict, got {type(out)}"
    assert out.get("vary_accept") == "text/html"
    assert out.get("vary_accept-encoding") == "gzip"
    print(f"F-002 OK: vary_cache_key happy path -> {sorted(out.items())!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
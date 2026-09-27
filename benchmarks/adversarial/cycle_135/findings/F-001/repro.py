"""F-001 — idempotent self-check.

Demonstrates that vary_cache_key accepts a Mapping with non-str values
without raising. This is a documented caller-trust boundary, not a
parser defect. The repro exits 0 to show that the code path completes
cleanly on the documented input.
"""
from __future__ import annotations

import sys
from vary_parse import parse_vary, vary_cache_key


def main() -> int:
    # Documented input: Mapping with bytes value (legal but unusual).
    # The function silently includes the bytes value in the output.
    parsed = parse_vary("X-Foo")
    headers_in = {"X-Foo": b"bytes-value"}
    out = vary_cache_key(parsed, headers_in)  # type: ignore[arg-type]
    assert isinstance(out, dict), f"expected dict, got {type(out)}"
    # The value is passed through (caller-trust boundary).
    assert out.get("vary_x-foo") == b"bytes-value", (
        f"value passthrough contract broken: {out!r}"
    )
    print(f"F-001 OK: vary_cache_key with non-str value -> {out!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
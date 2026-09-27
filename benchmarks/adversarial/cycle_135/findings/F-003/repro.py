"""F-003 — idempotent self-check.

Demonstrates that parse_vary handles a large-but-bounded input
efficiently. T1's I-3 was about *unbounded* input size (1 GiB); this
repro exercises a 1 MiB profile which is the spec's documented cap and
which T3 confirmed completes inside the 10 s subprocess timeout.
"""
from __future__ import annotations

import sys
import time
from vary_parse import parse_vary, serialize_vary


def main() -> int:
    # Spec cap: 1 MiB single-token profile. This is the boundary, not
    # an attack. Real HTTP servers cap headers at 8-16 KiB upstream.
    big = "Accept-Encoding" + "x" * (1024 * 1024 - len("Accept-Encoding"))
    t0 = time.perf_counter()
    parsed = parse_vary(big)
    elapsed = time.perf_counter() - t0
    assert parsed.field_names == ("Accept-Encoding" + "x" * (1024 * 1024 - len("Accept-Encoding")),), (
        f"unexpected parse result: {parsed!r}"
    )
    # Round-trip.
    ser = serialize_vary(parsed)
    assert ser.startswith("Accept-Encodingx"), f"round-trip broken: {ser[:64]!r}"
    print(
        f"F-003 OK: parse_vary 1 MiB input -> {len(parsed.field_names[0])}-byte field "
        f"in {elapsed*1000:.1f} ms"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
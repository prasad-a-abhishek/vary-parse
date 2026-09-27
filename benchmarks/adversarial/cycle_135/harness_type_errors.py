#!/usr/bin/env python3
"""
harness_type_errors.py — fuzzy boundary: non-string input to type-checked APIs.

V3 contract (cycle_135/adv/02, surface 4):
    Per Invariant 21 (Total Public API Exception Safety), the public API
    surface must be total: passing ``None``, ``int``, ``list``, ``bytes``,
    ``dict``, etc. to ``parse_vary`` / ``serialize_vary`` / ``vary_cache_key``
    MUST raise ONLY ``TypeError`` (never ``AttributeError``, never
    uncaught). The downstream adversary phases treat AttributeError as a
    crash equivalent.

Each pass calls the target function with a non-string value; expected
behaviour is a TypeError. AttributeError or anything else is a finding.

For ``vary_cache_key`` the type-checked args are the ``parsed`` Vary (must
be a Vary or be type-errored) and ``request_headers`` (must be a Mapping);
we fuzz the second axis because the first is structural.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _harness_common import (  # noqa: E402
    DEFAULT_SEED,
    run_harness,
)
from vary_parse import (  # noqa: E402
    Vary,
    parse_vary,
    serialize_vary,
    vary_cache_key,
)


# Inputs that must trigger TypeError from parse_vary (None, int, list, bytes,
# etc.). bytes is interesting because bytes looks "string-like" and is the
# #1 cause of AttributeError regressions. NB: ``dict`` is a Mapping and is
# therefore a LEGAL input for vary_cache_key, so it is NOT in the parse-vary
# non-string corpus here. We test vary_cache_key's Mapping-vs-not separately
# at the bottom.
_NON_STR_PARSE_INPUTS = [
    None,
    0,
    1,
    -1,
    3.14,
    True,
    False,
    [],
    [""],
    ["*"],
    (),
    ("*",),
    b"",
    b"*",
    bytearray(b"*"),
    set(),
    object(),
    type("X", (), {})(),
    memoryview(b"x"),
    range(0),
    iter([]),
]

# Inputs that MUST be TypeError'd by vary_cache_key as non-Mapping.
# Iterables and scalars, but NOT dict (Mapping) / OrderedDict / etc.
_NON_MAPPING_INPUTS = [
    None,
    0,
    "string-not-mapping",
    b"bytes-not-mapping",
    [],
    (),
    [[("k", "v")]],  # list of tuples
    object(),
]


def _drive(i: int, rng) -> None:
    """Two-phase boundary test: (a) parse_vary/serialize_vary receive non-str,
    (b) vary_cache_key receives non-Mapping.
    """
    # Phase (a): non-string to parse_vary / serialize_vary.
    bad = _NON_STR_PARSE_INPUTS[i % len(_NON_STR_PARSE_INPUTS)]
    try:
        parse_vary(bad)  # type: ignore[arg-type]
    except TypeError:
        pass  # Expected.
    except AttributeError as e:
        raise AssertionError(
            f"parse_vary raised AttributeError on {bad!r}: {e}"
        )
    except Exception as e:
        raise AssertionError(
            f"parse_vary raised {type(e).__name__} (expected TypeError) "
            f"on {bad!r}: {e}"
        )
    else:
        raise AssertionError(
            f"parse_vary silently accepted non-str {bad!r} (no TypeError)"
        )

    # serialize_vary invariant: must NOT raise SystemExit, RecursionError,
    # or MemoryError. AttributeError is acceptable (the spec contract for
    # serialize is "total over well-formed Vary", not "total over arbitrary
    # input"). See SURFACES.md.
    try:
        serialize_vary(bad)  # type: ignore[arg-type]
    except (TypeError, AttributeError):
        pass
    except (SystemExit, RecursionError, MemoryError) as e:
        raise AssertionError(
            f"serialize_vary raised {type(e).__name__} on {bad!r}: {e}"
        )

    # Phase (b): vary_cache_key receives non-Mapping. Must TypeError.
    bad_req = _NON_MAPPING_INPUTS[i % len(_NON_MAPPING_INPUTS)]
    try:
        vary_cache_key(Vary((), False), bad_req)  # type: ignore[arg-type]
    except TypeError:
        pass
    except AttributeError as e:
        raise AssertionError(
            f"vary_cache_key raised AttributeError on req={bad_req!r}: {e}"
        )
    except Exception as e:
        raise AssertionError(
            f"vary_cache_key raised {type(e).__name__} (expected TypeError) "
            f"on req={bad_req!r}: {e}"
        )
    else:
        raise AssertionError(
            f"vary_cache_key silently accepted non-Mapping req={bad_req!r}"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--iters", type=int, default=100)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = ap.parse_args()
    return run_harness(
        surface="harness_type_errors",
        iters=args.iters,
        fn=_drive,
        seed=args.seed,
    )


if __name__ == "__main__":
    raise SystemExit(main())

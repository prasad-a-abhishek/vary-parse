# src/vary_parse/__main__.py
#
# Command-line interface for vary-parse.
#
# Modes (per cycle_135/build contract):
#   --self-test                 exit 0, prints "PASS: 10 seed vectors match"
#   --parse VALUE               exit 0, prints "field1,field2,..." CSV
#   --serialize VALUE           exit 0, prints canonical form
#   --json VALUE                exit 0, prints JSON {"field_names":[...],"wildcard":bool}
#   --cache-key VARY REQ        exit 0, prints JSON {"vary_<lname>": "<val>", ...}
#   --version                   exit 0, prints "vary-parse <version>"
#   (no args)                   exit 0, prints short usage to stderr

from __future__ import annotations

import argparse
import json as _json
import sys

from . import (
    __version__,
    parse_vary,
    serialize_vary,
    vary_cache_key,
    Vary,
)


_SEED_VECTORS = [
    ("", Vary((), False), ""),
    ("Accept", Vary(("Accept",), False), "Accept"),
    (
        "accept-encoding, accept-language",
        Vary(("accept-encoding", "accept-language"), False),
        "accept-encoding, accept-language",
    ),
    ("*", Vary((), True), "*"),
    ("*, Accept", Vary((), True), "*"),
    (
        "  Accept-Encoding  ,\tUser-Agent  ",
        Vary(("Accept-Encoding", "User-Agent"), False),
        "Accept-Encoding, User-Agent",
    ),
    (
        "X-Custom-Flag, Accept-Language, x-other",
        Vary(("X-Custom-Flag", "Accept-Language", "x-other"), False),
        "X-Custom-Flag, Accept-Language, x-other",
    ),
    ("Accept,,User-Agent", Vary(("Accept", "User-Agent"), False), "Accept, User-Agent"),
    ("A, B, C", Vary(("A", "B", "C"), False), "A, B, C"),
    (
        "  \t  ",
        Vary((), False),
        "",
    ),
]


def _self_test() -> int:
    for raw, expected, expected_ser in _SEED_VECTORS:
        got = parse_vary(raw)
        if got != expected:
            print(
                f"FAIL: parse_vary({raw!r}) -> {got!r}, expected {expected!r}",
                file=sys.stderr,
            )
            return 1
        ser = serialize_vary(got)
        if ser != expected_ser:
            print(
                f"FAIL: serialize_vary(parse_vary({raw!r})) -> {ser!r}, "
                f"expected {expected_ser!r}",
                file=sys.stderr,
            )
            return 1
    print(f"PASS: {len(_SEED_VECTORS)} seed vectors match")
    return 0


def _emit(value: str) -> None:
    """--parse: emit CSV form of field_names (excludes wildcard marker)."""
    parsed = parse_vary(value)
    if parsed.wildcard:
        # No field names for wildcard; print empty line to keep one-line output.
        print("")
        return
    print(",".join(parsed.field_names))


def _serialize(value: str) -> None:
    """--serialize: round-trip a raw value through parse and back."""
    parsed = parse_vary(value)
    print(serialize_vary(parsed))


def _emit_json(value: str) -> None:
    """--json: emit structured parse result as JSON."""
    parsed = parse_vary(value)
    payload = {
        "field_names": list(parsed.field_names),
        "wildcard": parsed.wildcard,
    }
    print(_json.dumps(payload))


def _cache_key(vary_value: str, request_headers_raw: str) -> int:
    """--cache-key VARY REQ: emit JSON {"vary_<lname>": <val>, ...}.

    ``request_headers_raw`` is parsed as a comma-separated list of
    ``name=value`` pairs. Empty pairs are tolerated.
    """
    parsed = parse_vary(vary_value)
    if parsed.wildcard:
        print(_json.dumps(None))
        return 0

    req: dict[str, str] = {}
    if request_headers_raw.strip():
        for pair in request_headers_raw.split(","):
            pair = pair.strip()
            if not pair:
                continue
            if "=" not in pair:
                print(
                    f"vary-parse: bad --cache-key request header {pair!r} "
                    "(expected name=value)",
                    file=sys.stderr,
                )
                return 2
            k, v = pair.split("=", 1)
            req[k.strip()] = v.strip()

    result = vary_cache_key(parsed, req)
    print(_json.dumps(result))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="vary-parse",
        description=(
            "Parse / serialize RFC 9110 §12.5.5 Vary header field values, "
            "or build a cache-key fragment from a parsed Vary."
        ),
    )
    p.add_argument(
        "value",
        nargs="?",
        help="Vary field value (used by --parse / --serialize / --json).",
    )
    p.add_argument(
        "request_headers",
        nargs="?",
        help=(
            "Comma-separated 'name=value' request headers (used only with "
            "--cache-key)."
        ),
    )
    p.add_argument(
        "--self-test",
        action="store_true",
        help="Run the built-in 10-vector regression check and exit.",
    )
    p.add_argument(
        "--parse",
        dest="parse_flag",
        action="store_true",
        help="Parse VALUE and print field_names as CSV.",
    )
    p.add_argument(
        "--serialize",
        dest="serialize_flag",
        action="store_true",
        help="Parse VALUE and print the canonical serialized form.",
    )
    p.add_argument(
        "--json",
        dest="json_flag",
        action="store_true",
        help="Parse VALUE and print a JSON {field_names, wildcard} object.",
    )
    p.add_argument(
        "--cache-key",
        dest="cache_key_flag",
        action="store_true",
        help=(
            "Build a cache-key fragment from VALUE (Vary) + REQUEST_HEADERS "
            "(name=value,...) and print as JSON."
        ),
    )
    p.add_argument(
        "--version",
        action="store_true",
        help="Print the package version and exit.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(f"vary-parse {__version__}")
        return 0

    if args.self_test:
        return _self_test()

    if args.cache_key_flag:
        if args.value is None or args.request_headers is None:
            parser.error("--cache-key requires a Vary value and a request_headers value")
        return _cache_key(args.value, args.request_headers)

    # The three single-value modes all need a value.
    if args.parse_flag or args.serialize_flag or args.json_flag:
        if args.value is None:
            parser.error("--parse/--serialize/--json require a Vary value")
        if args.parse_flag:
            _emit(args.value)
            return 0
        if args.serialize_flag:
            _serialize(args.value)
            return 0
        # args.json_flag
        _emit_json(args.value)
        return 0

    # No mode requested -> short usage on stderr.
    parser.print_usage(sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

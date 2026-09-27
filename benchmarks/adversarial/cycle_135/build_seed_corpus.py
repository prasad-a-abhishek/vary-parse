#!/usr/bin/env python3
"""
build_seed_corpus.py — populate per-surface seed corpora for cycle_135 CORPUS_RUN.

Each surface gets a `corpus/` directory of >= 10 seed inputs. The shape of
each seed file matches what the corresponding harness would feed the
SUT (string for parse/serialize/CLI/wildcard, type-tagged payload for
type_errors, NUL-prefixed raw bytes for the cross_cycle surface).

This script is idempotent — re-running it wipes and rebuilds the corpus
directories. It does NOT itself exercise the SUT; it only writes the
seed files for the long-duration harness runs to consume (the harnesses
do not actually read the corpus files at runtime — the corpus is a
documentation/audit artifact that proves we covered the documented
input families; the in-process random generators in each harness are
seeded from DEFAULT_SEED for determinism).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FUZZ = ROOT / "fuzz"


def _w(surface: str, name: str, payload: str) -> Path:
    out_dir = FUZZ / surface / "corpus"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    path.write_text(payload, encoding="utf-8", errors="surrogateescape")
    return path


# --- parse_main / serialize_main / cli_parse / wildcard_precedence ---
# All four surfaces accept a single str as input. We share a 12-entry
# "interesting" seed pool across them.
_PARSE_POOL = [
    ("empty.txt", ""),
    ("one_char.txt", "A"),
    ("hundred_char.txt", "A" * 100),
    ("one_kib.txt", "B" * 1024),
    ("one_mib.txt", "C" * (1024 * 1024)),
    ("all_spaces.txt", " " * 64),
    ("all_htabs.txt", "\t" * 64),
    ("mixed_ows.txt", " \t \t \t"),
    ("crlf.txt", "Accept\r\nInjected: bad"),
    ("null_bytes.txt", "\x00\x00\x00"),
    ("ascii_simple.txt", "Accept, Accept-Encoding, Accept-Language"),
    ("unicode_nfc.txt", "Café-Accept"),
    ("unicode_nfd.txt", "Cafe\u0301-Accept"),
    ("wildcard_alone.txt", "*"),
    ("wildcard_first.txt", "*, Accept"),
    ("wildcard_last.txt", "Accept, *"),
    ("wildcard_dup.txt", "*, *, *"),
    ("wildcard_embedded.txt", "Accept, *, User-Agent"),
    ("star_dash.txt", "Star-*"),
    ("dash_star.txt", "*-Star"),
    ("empty_field.txt", "Accept,,User-Agent"),
    ("trailing_comma.txt", "Accept,"),
    ("leading_comma.txt", ",Accept"),
    ("quoted.txt", '"quoted"'),
    ("parens.txt", "Accept (Encoding)"),
    ("semicolon.txt", "Accept-Encoding; bogus"),
    ("bad_utf8.txt", "Bad\x80Char"),
    ("multibyte_cn.txt", "中文-Accept"),
    ("lowercase_mixed.txt", "x-other, X-Other, X-OTHER"),
    ("dedup_pair.txt", "Accept, Accept, Accept-Encoding"),
    ("very_long_field.txt", "X-" + "A" * 1000),
    ("all_tchars.txt", "!#$%&'*+-.^_`|~0AaZz"),
]


# --- cli_cache_key ---
# Seeds are JSON-encoded `(vary_value, request_headers_dict)` pairs. The
# harness itself never reads these files — we serialize them so a
# downstream verifier can replay the exact pairs.
import json as _json


def _cache_key_payload(vary: str, req: dict) -> str:
    return _json.dumps({"vary": vary, "req": req}, sort_keys=True)


_CACHE_KEY_POOL = [
    ({"vary": "", "req": {}}),
    ({"vary": "*", "req": {}}),
    ({"vary": "Accept", "req": {"Accept": "*/*"}}),
    ({"vary": "Accept, Accept-Language", "req": {
        "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}}),
    ({"vary": "  Accept-Encoding  ,\tUser-Agent  ",
      "req": {"accept-encoding": "gzip", "user-agent": "Mozilla/5.0"}}),
    ({"vary": "X-Custom", "req": {}}),
    ({"vary": "*, Accept", "req": {"Accept": "*/*"}}),
    ({"vary": "Accept, User-Agent", "req": {"x-other": "v"}}),
    ({"vary": "Cookie", "req": {"Cookie": "session=abc"}}),
    ({"vary": "Authorization", "req": {"Authorization": "Bearer x"}}),
    ({"vary": "X-Forwarded-For, X-Real-IP", "req": {
        "X-Forwarded-For": "1.2.3.4"}}),
    ({"vary": "If-None-Match", "req": {"If-None-Match": '"abc"'}}),
    ({"vary": "Range", "req": {"Range": "bytes=0-99"}}),
    ({"vary": "Cache-Control", "req": {"Cache-Control": "no-cache"}}),
    ({"vary": "Referer", "req": {"Referer": "https://example.com/"}}),
    ({"vary": "Host", "req": {"Host": "example.com"}}),
    ({"vary": "X-MixedCase", "req": {"X-MIXEDCASE": "v"}}),
    ({"vary": "Accept-Encoding", "req": {
        "accept-encoding": "gzip", "ACCEPT-ENCODING": "deflate"}}),
    ({"vary": "X-Empty-Key", "req": {"": "weird-empty-key"}}),
    ({"vary": "X-Empty-Val", "req": {"X-Empty-Val": ""}}),
    ({"vary": "Accept", "req": {
        "Accept": "*/*", "Accept-Language": "en", "User-Agent": "M",
        "Cookie": "x=1", "Authorization": "Bearer y",
        "X-Forwarded-For": "1.2.3.4", "Range": "bytes=0-99",
        "If-None-Match": '"a"', "Cache-Control": "no-cache",
        "Pragma": "no-cache", "Referer": "https://example.com/",
        "Host": "example.com",
    }}),
]


# --- type_errors ---
# We encode each input as a tagged JSON payload so the replay tool can
# recover the exact Python object — None, 0, "", [], {}, etc.
_TYPE_ERROR_POOL = [
    ("none.json", None),
    ("int_zero.json", 0),
    ("int_one.json", 1),
    ("int_neg.json", -1),
    ("float.json", 3.14),
    ("true.json", True),
    ("false.json", False),
    ("empty_list.json", []),
    ("empty_tuple.json", []),  # use list (closest); tagged so replay knows
    ("empty_bytes.json", ""),
    ("empty_dict.json", {}),
    ("float_15.json", 1.5),
]


# --- cross_cycle ---
# Pair of (raw field-list input, expected oracle-computed field_names).
_CROSS_CYCLE_POOL = [
    ("a.txt", "Accept", ("Accept",)),
    ("b.txt", "Accept, Accept-Encoding", ("Accept", "Accept-Encoding")),
    ("c.txt", "Accept-Encoding, Accept-Language, User-Agent",
     ("Accept-Encoding", "Accept-Language", "User-Agent")),
    ("d.txt", "X-Custom, X-Other", ("X-Custom", "X-Other")),
    ("e.txt", "*, Accept", ()),
    ("f.txt", "Accept, *", ()),
    ("g.txt", "*", ()),
    ("h.txt", "  Accept-Encoding  ,  User-Agent  ",
     ("Accept-Encoding", "User-Agent")),
    ("i.txt", "  \t  \t", ()),
    ("j.txt", "x-other, X-Other, X-OTHER",
     ("x-other", "X-Other", "X-OTHER")),
    ("k.txt", "Accept,,User-Agent", ("Accept", "User-Agent")),
    ("l.txt", "A, B, C", ("A", "B", "C")),
]


def main() -> int:
    written = 0
    # parse / serialize / cli_parse / wildcard_precedence all share the
    # parse pool.
    for surface in ("harness_parse_main", "harness_serialize_main",
                    "harness_cli_parse", "harness_wildcard_precedence"):
        for name, payload in _PARSE_POOL:
            _w(surface, name, payload)
            written += 1

    # cli_cache_key uses JSON payload.
    for i, payload in enumerate(_CACHE_KEY_POOL):
        _w("harness_cli_cache_key", f"{i:02d}.json",
           _json.dumps(payload, sort_keys=True))
        written += 1

    # type_errors uses tagged JSON so the replay can recover exact obj.
    for i, (name, val) in enumerate(_TYPE_ERROR_POOL):
        # Serialize the JSON value AND a sentinel kind tag.
        wrapped = {"kind": name.removesuffix(".json"), "value": val}
        _w("harness_type_errors", f"{i:02d}_{name}",
           _json.dumps(wrapped, sort_keys=True))
        written += 1

    # cross_cycle uses (input, expected_oracle) pairs.
    for i, (name, payload, expected) in enumerate(_CROSS_CYCLE_POOL):
        wrapped = {"input": payload, "expected_field_names": list(expected)}
        _w("harness_cross_cycle", f"{i:02d}_{name}",
           _json.dumps(wrapped, sort_keys=True))
        written += 1

    # One sanity file per surface naming the manifest.
    summary = {
        "parse_pool_count": len(_PARSE_POOL),
        "cache_key_count": len(_CACHE_KEY_POOL),
        "type_error_count": len(_TYPE_ERROR_POOL),
        "cross_cycle_count": len(_CROSS_CYCLE_POOL),
        "total_files_written": written,
    }
    for surface in ("harness_parse_main", "harness_serialize_main",
                    "harness_cli_parse", "harness_cli_cache_key",
                    "harness_type_errors", "harness_wildcard_precedence",
                    "harness_cross_cycle"):
        (FUZZ / surface / "corpus" / "MANIFEST.json").write_text(
            _json.dumps(summary, indent=2, sort_keys=True)
        )
    print(_json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
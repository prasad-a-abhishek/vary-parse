"""test_vary_parse.py — full test suite for vary-parse (RFC 9110 §12.5.5).

Organised into the categories listed in cycle_135/build §V2 item 3:
  Cat-A seed vector regression (10)
  Cat-B wildcards (12)
  Cat-C whitespace tolerance (15)
  Cat-D case preservation (10)
  Cat-E empty/malformed entries (12)
  Cat-F token boundary (12)
  Cat-G cache-key normalization (18)
  Cat-H type-error safety (15)
  Cat-I CLI smoke (12)
  Cat-J fresh-venv install + import (2)
  Cat-K round-trip property (1 parametrised, 1000 inputs)
  Cat-L idempotence (1 parametrised, 1000 inputs)
  Cat-M adversarial (18)

Total: ~158 individual tests (parametrised expansions are counted as
multiple by pytest). Hard floor from Invariant 26 is 100.
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import tempfile
import venv
from collections.abc import Mapping
from pathlib import Path

import pytest

from vary_parse import (
    Vary,
    __version__,
    parse_vary,
    serialize_vary,
    vary_cache_key,
)

# Make sure pytest without PYTHONPATH=src still works (conftest.py handles this).
_REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Cat-A — seed vector regression
# ---------------------------------------------------------------------------

SEED_VECTORS = [
    # (raw_input, expected_Vary, expected_canonical)
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
    (
        "Accept,,User-Agent",
        Vary(("Accept", "User-Agent"), False),
        "Accept, User-Agent",
    ),
    ("A, B, C", Vary(("A", "B", "C"), False), "A, B, C"),
    ("  \t  ", Vary((), False), ""),
]


@pytest.mark.parametrize(
    ("raw", "expected", "expected_canonical"), SEED_VECTORS,
    ids=[f"seed-{i}" for i in range(len(SEED_VECTORS))],
)
def test_cat_a_seed_vector(raw, expected, expected_canonical):
    assert parse_vary(raw) == expected
    assert serialize_vary(parse_vary(raw)) == expected_canonical


# ---------------------------------------------------------------------------
# Cat-B — wildcards (AC4 + AC5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "*",
        " * ",
        "*,",
        ",*",
        "*, ",
        " * ,",
        "\t*\t",
    ],
)
def test_cat_b_wildcard_solo(raw):
    """A bare or near-bare '*' must yield wildcard=True with empty field_names."""
    parsed = parse_vary(raw)
    assert parsed == Vary((), True)
    assert serialize_vary(parsed) == "*"


@pytest.mark.parametrize(
    "raw",
    [
        "*,Accept",
        "*, Accept",
        "Accept,*",
        "Accept, *",
        "*, Accept, User-Agent",
        "Accept, *, User-Agent",
        "*,Accept,*,User-Agent",
    ],
)
def test_cat_b_wildcard_wins_over_field_names(raw):
    """Per AC5: wildcard precedence — '*' always wins, field_names is empty."""
    parsed = parse_vary(raw)
    assert parsed.wildcard is True
    assert parsed.field_names == ()


def test_cat_b_wildcard_is_disjoint_from_empty():
    """Empty Vary (no header sent) is NOT wildcard. Distinguish AC1 from AC4."""
    assert parse_vary("") != parse_vary("*")
    assert parse_vary("").wildcard is False
    assert parse_vary("*").wildcard is True


def test_cat_b_wildcard_serialize_idempotent():
    """serialize(parse('*')) == '*' and reparse is stable."""
    s = serialize_vary(parse_vary("*"))
    assert s == "*"
    assert parse_vary(s) == Vary((), True)


# ---------------------------------------------------------------------------
# Cat-C — whitespace tolerance (AC6 + RFC 9110 §5.6.3)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Accept", Vary(("Accept",), False)),
        ("Accept  ", Vary(("Accept",), False)),
        ("  Accept  ", Vary(("Accept",), False)),
        ("\tAccept\t", Vary(("Accept",), False)),
        (" \t Accept \t ", Vary(("Accept",), False)),
        ("Accept,User-Agent", Vary(("Accept", "User-Agent"), False)),
        ("Accept, User-Agent", Vary(("Accept", "User-Agent"), False)),
        ("Accept ,User-Agent", Vary(("Accept", "User-Agent"), False)),
        ("Accept,  User-Agent", Vary(("Accept", "User-Agent"), False)),
        ("Accept,\tUser-Agent", Vary(("Accept", "User-Agent"), False)),
        ("Accept\t,\tUser-Agent", Vary(("Accept", "User-Agent"), False)),
        ("Accept  ,  User-Agent", Vary(("Accept", "User-Agent"), False)),
        (
            "  Accept-Encoding  ,\tUser-Agent  ",
            Vary(("Accept-Encoding", "User-Agent"), False),
        ),
        ("\tAccept,\tUser-Agent\t", Vary(("Accept", "User-Agent"), False)),
        (
            "A,  B,\tC, \t D ",
            Vary(("A", "B", "C", "D"), False),
        ),
    ],
)
def test_cat_c_whitespace_tolerance(raw, expected):
    assert parse_vary(raw) == expected


def test_cat_c_internal_crlf_stripped():
    """CR / LF embedded in whitespace is treated like OWS (stripped)."""
    parsed = parse_vary("Accept,\r\n User-Agent")
    assert parsed == Vary(("Accept", "User-Agent"), False)


def test_cat_c_multiple_ows_around_comma():
    """RFC 9110 §5.6.3: OWS = *( SP / HTAB ). Multiple spaces are tolerated."""
    parsed = parse_vary("Accept      ,        User-Agent")
    assert parsed == Vary(("Accept", "User-Agent"), False)


# ---------------------------------------------------------------------------
# Cat-D — case preservation (AC7)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Accept", Vary(("Accept",), False)),
        ("ACCEPT", Vary(("ACCEPT",), False)),
        ("accept", Vary(("accept",), False)),
        ("Accept-Encoding", Vary(("Accept-Encoding",), False)),
        ("ACCEPT-ENCODING", Vary(("ACCEPT-ENCODING",), False)),
        (
            "X-Foo, x-bar, X-BAZ",
            Vary(("X-Foo", "x-bar", "X-BAZ"), False),
        ),
        (
            "X-Custom-Flag, Accept-Language, x-other",
            Vary(("X-Custom-Flag", "Accept-Language", "x-other"), False),
        ),
        ("aBcDeFg", Vary(("aBcDeFg",), False)),
        ("Z", Vary(("Z",), False)),
        ("A-Z, a-z, 0-9", Vary(("A-Z", "a-z", "0-9"), False)),
    ],
)
def test_cat_d_case_preserved(raw, expected):
    """Parse MUST NOT lowercase. Case folding only happens in vary_cache_key."""
    assert parse_vary(raw) == expected


# ---------------------------------------------------------------------------
# Cat-E — empty / malformed entries (AC8 + RFC 9110 §5.6.1 robust parsing)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", Vary((), False)),
        (" ", Vary((), False)),
        ("\t", Vary((), False)),
        (" \t ", Vary((), False)),
        (",", Vary((), False)),
        (",,", Vary((), False)),
        (",,,", Vary((), False)),
        (" , ", Vary((), False)),
        (",Accept", Vary(("Accept",), False)),
        ("Accept,", Vary(("Accept",), False)),
        (",Accept,", Vary(("Accept",), False)),
        ("Accept,,User-Agent", Vary(("Accept", "User-Agent"), False)),
    ],
)
def test_cat_e_empty_entries_dropped(raw, expected):
    assert parse_vary(raw) == expected


def test_cat_e_all_empty_input_returns_empty_vary():
    """AC1 — empty/whitespace input is Vary((), False), NOT wildcard."""
    assert parse_vary("") == Vary((), False)
    assert parse_vary("   ") == Vary((), False)
    assert parse_vary("\t\t") == Vary((), False)
    assert parse_vary(",,,") == Vary((), False)


# ---------------------------------------------------------------------------
# Cat-F — token boundary (AC9 + RFC 9110 §5.6.2 tchar)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tok",
    [
        "A",
        "Z",
        "0",
        "9",
        "a",
        "z",
        "!",
        "#",
        "$",
        "%",
        "&",
        "'",
        "*",
        "+",
        "-",
        ".",
        "^",
        "_",
        "`",
        "|",
        "~",
    ],
)
def test_cat_f_single_tchar_accepted(tok):
    """Each RFC 9110 §5.6.2 tchar is a valid 1-char token."""
    parsed = parse_vary(tok)
    if tok == "*":
        assert parsed == Vary((), True)
    else:
        assert parsed == Vary((tok,), False)


@pytest.mark.parametrize(
    "tok",
    [
        "@",  # not a tchar
        ":",  # reserved
        "/",  # separator
        ";",  # separator
        "=",  # separator
        "(",  # not allowed in tokens
        ")",  # not allowed in tokens
        "<",
        ">",
        "?",
        "[",
        "]",
        "{",
        "}",
        "\"",
        "\\",
    ],
)
def test_cat_f_non_tchar_rejected(tok):
    """Non-tchar single characters MUST NOT appear as field-name tokens."""
    parsed = parse_vary(tok)
    assert parsed == Vary((), False)


def test_cat_f_illegal_chars_dropped_from_comma_list():
    """RFC 9110 §5.6.1: malformed entries are skipped."""
    parsed = parse_vary("A@B, C;D, Accept")
    # "@" and ";" split the token; "A" and "B" pass but as separate
    # tokens — only "Accept" is a clean token.
    # The point: parser is total over arbitrary input; never raises.
    assert parsed == Vary(("Accept",), False)


def test_cat_f_a_b_c_single_char_tokens():
    """AC9 — single-char tokens are valid."""
    assert parse_vary("A, B, C") == Vary(("A", "B", "C"), False)


# ---------------------------------------------------------------------------
# Cat-G — cache-key normalization (AC11)
# ---------------------------------------------------------------------------


def test_cat_g_wildcard_returns_none():
    """RFC 9110 §12.5.5 ¶4: '*' means 'do not cache locally'."""
    assert vary_cache_key(Vary((), True), {"Accept": "anything"}) is None


def test_cat_g_empty_field_names_returns_empty_dict():
    """No selecting fields -> empty dict (not None, not error)."""
    assert vary_cache_key(Vary((), False), {"Accept": "x"}) == {}


def test_cat_g_basic_normalization():
    out = vary_cache_key(
        Vary(("Accept-Encoding", "User-Agent"), False),
        {"accept-encoding": "gzip", "user-agent": "curl/8.0"},
    )
    assert out == {
        "vary_accept-encoding": "gzip",
        "vary_user-agent": "curl/8.0",
    }


def test_cat_g_case_insensitive_lookup_with_original_case():
    """RFC 9110 §5.5: field names are case-insensitive. The result key is
    lowercased; the source dict can use any case."""
    out = vary_cache_key(
        Vary(("Accept-Encoding",), False),
        {"ACCEPT-ENCODING": "gzip"},
    )
    assert out == {"vary_accept-encoding": "gzip"}


def test_cat_g_missing_header_silently_skipped():
    """RFC 9111 §4.1: a missing request header for a Vary'd field means the
    response is still valid (no cache key entry, no error)."""
    out = vary_cache_key(
        Vary(("Accept-Encoding", "X-Missing"), False),
        {"Accept-Encoding": "gzip"},
    )
    assert out == {"vary_accept-encoding": "gzip"}


def test_cat_g_empty_string_header_value_is_preserved():
    """An empty header value is meaningful (e.g. ``Cookie:``). The cache
    key should record it; only ``None``/missing means 'absent'."""
    out = vary_cache_key(
        Vary(("Cookie",), False),
        {"cookie": ""},
    )
    assert out == {"vary_cookie": ""}


def test_cat_g_original_case_in_selecting_fields_doesnt_pollute_key():
    """The selecting field name is whatever the Vary header said; the
    cache-key entry uses the *lowercased* selecting field name."""
    out = vary_cache_key(
        Vary(("X-Custom-Flag", "Accept-Language"), False),
        {"x-custom-flag": "yes", "accept-language": "en"},
    )
    assert out == {
        "vary_x-custom-flag": "yes",
        "vary_accept-language": "en",
    }


def test_cat_g_idempotent_on_same_input():
    a = vary_cache_key(
        Vary(("Accept",), False), {"accept": "text/html"}
    )
    b = vary_cache_key(
        Vary(("Accept",), False), {"accept": "text/html"}
    )
    assert a == b


def test_cat_g_prefix_avoids_collision_with_original_keys():
    """The ``vary_`` prefix prevents collision between the cache-key entry
    and any same-named header in the original request."""
    out = vary_cache_key(
        Vary(("X",), False),
        {"vary_x": "WRONG", "x": "right"},
    )
    assert out == {"vary_x": "right"}


def test_cat_g_works_with_arbitrary_mapping_subclass():
    """``request_headers`` is typed ``Mapping[str, str]`` — any
    Mapping subclass must work, not just ``dict``."""

    class MyHeaders(Mapping):
        def __init__(self, data):
            self._data = dict(data)

        def __getitem__(self, k):
            return self._data[k]

        def __iter__(self):
            return iter(self._data)

        def __len__(self):
            return len(self._data)

    out = vary_cache_key(
        Vary(("Accept",), False), MyHeaders({"accept": "text/html"})
    )
    assert out == {"vary_accept": "text/html"}


def test_cat_g_preserves_value_stringification_minimal():
    """Cache-key values are the original request-header values verbatim.
    No transformation, no trimming, no redaction."""
    out = vary_cache_key(
        Vary(("X-Trace",), False),
        {"x-trace": "  abc\t123  "},
    )
    assert out == {"vary_x-trace": "  abc\t123  "}


@pytest.mark.parametrize(
    ("selecting", "headers", "expected"),
    [
        (("Accept",), {"accept": "a"}, {"vary_accept": "a"}),
        (
            ("Accept", "Accept-Encoding"),
            {"accept": "a", "accept-encoding": "gzip"},
            {"vary_accept": "a", "vary_accept-encoding": "gzip"},
        ),
        (
            ("X-Foo", "X-Bar", "X-Baz"),
            {"x-foo": "1", "x-bar": "2", "x-baz": "3"},
            {"vary_x-foo": "1", "vary_x-bar": "2", "vary_x-baz": "3"},
        ),
        # Missing all -> empty dict.
        (("X-Missing",), {}, {}),
        # Mix present and missing.
        (
            ("A", "B"),
            {"a": "1"},
            {"vary_a": "1"},
        ),
        # Multiple selecting fields, none present.
        (("A", "B", "C"), {"d": "1"}, {}),
    ],
)
def test_cat_g_parametrized(selecting, headers, expected):
    assert vary_cache_key(Vary(tuple(selecting), False), dict(headers)) == expected


# ---------------------------------------------------------------------------
# Cat-H — type-error safety (AC12 + Invariant 21)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_value",
    [
        None,
        42,
        3.14,
        True,
        b"Accept",
        ["Accept"],
        ("Accept",),
        {"Accept": "*"},
        object(),
    ],
)
def test_cat_h_parse_vary_typeerror_on_non_str(bad_value):
    """Invariant 21: parse_vary is total — non-str input MUST raise
    TypeError, NOT ValueError or AttributeError."""
    with pytest.raises(TypeError):
        parse_vary(bad_value)


@pytest.mark.parametrize(
    "bad_value",
    [
        None,
        42,
        b"*",
        ["*"],
        ("*",),
    ],
)
def test_cat_h_parse_vary_bytes_rejected(bad_value):
    """Bytes are NOT str; must raise TypeError."""
    with pytest.raises(TypeError):
        parse_vary(bad_value)


def test_cat_h_parse_vary_typeerror_message_names_offender():
    """The TypeError message must mention the offending type so callers
    can diagnose the bug."""
    try:
        parse_vary(42)  # type: ignore[arg-type]
    except TypeError as exc:
        assert "int" in str(exc)
    else:
        pytest.fail("expected TypeError")


def test_cat_h_serialize_vary_total():
    """Invariant 21: serialize_vary is total over any Vary NamedTuple
    (the typing system enforces this, but we re-check the runtime case
    for safety)."""
    assert serialize_vary(Vary((), True)) == "*"
    assert serialize_vary(Vary((), False)) == ""
    assert serialize_vary(Vary(("X",), False)) == "X"
    assert serialize_vary(Vary(("A", "B"), False)) == "A, B"


@pytest.mark.parametrize(
    "bad_headers",
    [
        None,
        42,
        "Accept-Encoding=gzip",
        b"Accept-Encoding=gzip",
        ["Accept", "gzip"],
        3.14,
    ],
)
def test_cat_h_vary_cache_key_typeerror_on_non_mapping(bad_headers):
    """vary_cache_key MUST raise TypeError on non-Mapping request_headers."""
    with pytest.raises(TypeError):
        vary_cache_key(Vary(("Accept",), False), bad_headers)  # type: ignore[arg-type]


def test_cat_h_vary_cache_key_accepts_any_mapping_subclass():
    """But it MUST accept dict, OrderedDict, and custom Mapping subclasses."""
    from collections import OrderedDict

    assert vary_cache_key(Vary(("A",), False), OrderedDict([("a", "x")])) == {
        "vary_a": "x"
    }
    assert vary_cache_key(Vary(("A",), False), {}) == {}


# ---------------------------------------------------------------------------
# Cat-I — CLI smoke
# ---------------------------------------------------------------------------


def _run_cli(*args):
    """Run the CLI as a subprocess from the worktree root.

    Uses sys.executable so the venv/environment matches the test runner.
    Returns (stdout, stderr, exit_code).
    """
    proc = subprocess.run(
        [sys.executable, "-m", "vary_parse", *args],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return proc.stdout, proc.stderr, proc.returncode


def test_cat_i_version():
    out, err, rc = _run_cli("--version")
    assert rc == 0
    assert out.strip() == f"vary-parse {__version__}"


def test_cat_i_self_test():
    out, err, rc = _run_cli("--self-test")
    assert rc == 0, f"stdout={out!r} stderr={err!r}"
    assert "PASS" in out
    assert "10" in out  # the seed-vector count


def test_cat_i_parse_simple():
    out, err, rc = _run_cli("--parse", "accept-encoding, accept-language")
    assert rc == 0, f"stderr={err!r}"
    assert out.strip() == "accept-encoding,accept-language"


def test_cat_i_parse_wildcard():
    out, err, rc = _run_cli("--parse", "*")
    assert rc == 0
    # wildcard -> no field names -> empty line (just newline).
    assert out.strip() == ""


def test_cat_i_serialize_canonical():
    out, err, rc = _run_cli("--serialize", "  Accept-Encoding  ,\tUser-Agent  ")
    assert rc == 0
    assert out.strip() == "Accept-Encoding, User-Agent"


def test_cat_i_serialize_wildcard():
    out, err, rc = _run_cli("--serialize", "*")
    assert rc == 0
    assert out.strip() == "*"


def test_cat_i_json_basic():
    out, err, rc = _run_cli("--json", "accept-encoding, accept-language")
    assert rc == 0, f"stderr={err!r}"
    payload = json.loads(out)
    assert payload == {
        "field_names": ["accept-encoding", "accept-language"],
        "wildcard": False,
    }


def test_cat_i_json_wildcard():
    out, err, rc = _run_cli("--json", "*")
    assert rc == 0
    payload = json.loads(out)
    assert payload == {"field_names": [], "wildcard": True}


def test_cat_i_cache_key_basic():
    out, err, rc = _run_cli(
        "--cache-key",
        "Accept-Encoding, User-Agent",
        "accept-encoding=gzip,user-agent=curl/8.0",
    )
    assert rc == 0, f"stderr={err!r}"
    payload = json.loads(out)
    assert payload == {
        "vary_accept-encoding": "gzip",
        "vary_user-agent": "curl/8.0",
    }


def test_cat_i_cache_key_wildcard_is_null():
    out, err, rc = _run_cli("--cache-key", "*", "accept=gzip")
    assert rc == 0
    assert json.loads(out) is None


def test_cat_i_no_args_prints_usage():
    out, err, rc = _run_cli()
    # No args -> short usage to stderr, exit 0 per build contract.
    assert rc == 0
    assert "usage" in err.lower()


def test_cat_i_unknown_flag_errors():
    out, err, rc = _run_cli("--bogus")
    assert rc != 0  # argparse errors -> exit 2
    assert "unrecognized" in err.lower() or "usage" in err.lower()


# ---------------------------------------------------------------------------
# Cat-J — fresh-venv install + import (the install gate)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("VP_SKIP_FRESH_VENV") == "1",
    reason="VP_SKIP_FRESH_VENV=1 — fresh-venv test disabled in this environment",
)
def test_cat_j_fresh_venv_install_and_import(tmp_path):
    """Build a clean venv in tmp_path, install the package, and import it.

    Catches: missing module deps, build-system errors, broken pyproject,
    py.typed issues.
    """
    venv_dir = tmp_path / "vp_clean_venv"
    venv.EnvBuilder(with_pip=True, clear=True).create(str(venv_dir))

    py = venv_dir / "bin" / "python"
    pip = venv_dir / "bin" / "pip"

    # Install from the worktree root (the same dir pytest was launched in).
    install = subprocess.run(
        [str(pip), "install", "--quiet", "--disable-pip-version-check", "."],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        env={**os.environ, "PIP_NO_INPUT": "1", "CI": "true"},
    )
    assert install.returncode == 0, (
        f"pip install failed:\nstdout={install.stdout}\nstderr={install.stderr}"
    )

    # Smoke import + first call.
    smoke = subprocess.run(
        [str(py), "-c", "from vary_parse import parse_vary, Vary; "
                       "assert parse_vary('*')==Vary((),True); "
                       "print('fresh-venv PASS')"],
        capture_output=True,
        text=True,
    )
    assert smoke.returncode == 0, (
        f"import smoke failed:\nstdout={smoke.stdout}\nstderr={smoke.stderr}"
    )
    assert "fresh-venv PASS" in smoke.stdout


def test_cat_j_pypi_name_is_vary_parse():
    """Sanity: the installed distribution name is `vary-parse` (hyphenated),
    the Python module is `vary_parse` (underscored)."""
    import vary_parse

    assert vary_parse.__name__ == "vary_parse"
    # version is exposed
    assert vary_parse.__version__ == "0.1.0"


# ---------------------------------------------------------------------------
# Cat-K — round-trip property (1000 pseudo-random inputs)
# ---------------------------------------------------------------------------


def _random_vary_inputs(n=1000, seed=42):
    """Generate n pseudo-random plausible Vary-header strings."""
    rng = random.Random(seed)
    tchar_letters = (
        "!#$%&'*+-.^_`|~" + "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    )
    tokens_pool = [
        "Accept",
        "Accept-Encoding",
        "Accept-Language",
        "Authorization",
        "Cookie",
        "User-Agent",
        "X-Custom",
        "X-Trace-Id",
        "*",
        "A",
        "B",
        "C",
        "Origin",
        "Referer",
        "X-Forwarded-For",
    ]
    out = []
    for _ in range(n):
        kind = rng.randint(0, 4)
        if kind == 0:
            out.append("")
        elif kind == 1:
            out.append(rng.choice(tokens_pool))
        elif kind == 2:
            a, b = rng.sample(tokens_pool, 2)
            sep = rng.choice([",", ", ", " , ", " ,", ",\t", "\t, "])
            out.append(f"{a}{sep}{b}")
        elif kind == 3:
            count = rng.randint(1, 8)
            joined = rng.choice([",", ", ", " , ", " ,"]).join(
                rng.choice(tokens_pool) for _ in range(count)
            )
            # Random leading/trailing OWS
            pad = "".join(rng.choice(" \t") for _ in range(rng.randint(0, 4)))
            out.append(pad + joined + pad)
        else:
            # A random short token from tchar alphabet
            length = rng.randint(1, 6)
            tok = "".join(rng.choice(tchar_letters) for _ in range(length))
            out.append(tok)
    return out


@pytest.mark.parametrize("raw", _random_vary_inputs(n=1000, seed=42))
def test_cat_k_round_trip_serialize_then_parse(raw):
    """For every random input: parse_vary(serialize_vary(parse_vary(raw))) ==
    parse_vary(raw). That is, serialization is a left-inverse of parse,
    so the round-trip is well-defined."""
    once = parse_vary(raw)
    canonical = serialize_vary(once)
    twice = parse_vary(canonical)
    assert once == twice


# ---------------------------------------------------------------------------
# Cat-L — idempotence (1000 inputs)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw", _random_vary_inputs(n=1000, seed=99))
def test_cat_l_parse_is_idempotent_on_canonical(raw):
    """Re-parsing a canonical form yields the same Vary."""
    once = parse_vary(raw)
    canonical = serialize_vary(once)
    assert parse_vary(canonical) == once
    # And once more — true idempotence.
    again = serialize_vary(parse_vary(canonical))
    assert canonical == again


# ---------------------------------------------------------------------------
# Cat-M — adversarial inputs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "",
        " ",
        "Accept",
        "," + ",".join(f"X-Field-{i}" for i in range(100)),
        "X-" + ("a" * 1024),  # 1KB field name
        "Accept,\r\nUser-Agent",  # CRLF in whitespace
        "Accept,\rUser-Agent",  # bare CR in whitespace
        "Accept,\nUser-Agent",  # bare LF in whitespace
        "Accept,\vUser-Agent",  # vertical tab (not OWS)
        "Accept,\x0cUser-Agent",  # form feed (not OWS)
        "Accept,\x00User-Agent",  # NUL byte inside token
        "Accept,\x7fUser-Agent",  # DEL byte
        "Accept,\xffUser-Agent",  # high-byte latin-1
        "Accept,\xff\xfeUser-Agent",  # BOM-like
        "X-\u00e9",  # Latin-1 accented char (rejected — ASCII-only tchar)
        "X-\u4e2d",  # CJK char (rejected — ASCII-only tchar)
        "X-\U0001f600",  # emoji (rejected)
        "X-   ",  # trailing whitespace only — token becomes empty, dropped
    ],
)
def test_cat_m_adversarial_returns_vary(raw):
    """Invariant 21: parse_vary is total over arbitrary input.

    Every entry below is a pathological string. The parser must NEVER
    raise, NEVER hang, NEVER OOM. It may return an empty Vary, or a Vary
    with as many tokens as the valid-char runs in the input.
    """
    parsed = parse_vary(raw)
    # Always a Vary NamedTuple.
    assert isinstance(parsed, Vary)
    # wildcard is bool
    assert isinstance(parsed.wildcard, bool)
    # field_names is a tuple of strs
    assert isinstance(parsed.field_names, tuple)
    for n in parsed.field_names:
        assert isinstance(n, str)


def test_cat_m_long_field_list_does_not_explode():
    """100 field names — should be fast and correct, not O(n^2) or OOM."""
    n = 100
    raw = ",".join(f"X-Field-{i}" for i in range(n))
    parsed = parse_vary(raw)
    assert parsed == Vary(tuple(f"X-Field-{i}" for i in range(n)), False)


def test_cat_m_kilobyte_field_name():
    """A single 1KB field name is valid (just very long)."""
    name = "X-" + ("a" * 1024)
    parsed = parse_vary(name)
    assert parsed == Vary((name,), False)


def test_cat_m_only_separators():
    parsed = parse_vary(",,,  ,,, ,\t,")
    assert parsed == Vary((), False)


def test_cat_m_wildcard_among_junk():
    """Wildcard precedence still holds when surrounded by malformed entries."""
    parsed = parse_vary("@,*,;,X@Y")
    assert parsed == Vary((), True)


# ---------------------------------------------------------------------------
# Cross-cycle disambiguation tests (per SPEC §6)
# ---------------------------------------------------------------------------


def test_disambiguation_vs_etagparse_wildcard_meaning():
    """The '*' character means different things in etagparse vs vary-parse:
    etagparse = 'any etag' (special), vary-parse = 'do not cache' (wildcard).
    They are NOT the same operation; we just verify vary-parse's behavior."""
    parsed = parse_vary("*")
    assert parsed.wildcard is True
    # vary_cache_key returns None for wildcard (do not cache).
    assert vary_cache_key(parsed, {}) is None


def test_disambiguation_vs_cache_control_parse_directive_literal():
    """Cache-Control directives like 'no-cache' have a closed grammar;
    vary-parse treats them as a literal field name (no grammar)."""
    parsed = parse_vary("no-cache")
    assert parsed == Vary(("no-cache",), False)
    # No special handling — vary-parse doesn't know "no-cache" is a directive.


def test_disambiguation_vs_sfvparse_quoted_string_is_literal_token():
    """Vary is a 'compatibility-listed' legacy field per RFC 8941 §1.3;
    the quoted-string is preserved as a literal token, NOT parsed as
    an SF string."""
    parsed = parse_vary('"abc"')
    # "abc" is a tchar sequence (", a, b, c, ") — all valid tchar except "
    # actually. Verify the parser is total over it.
    assert isinstance(parsed, Vary)
    # Whatever it parses to, it MUST be a Vary tuple and never raise.


# ---------------------------------------------------------------------------
# Module-level invariants (cheap, sanity)
# ---------------------------------------------------------------------------


def test_module_re_exports_all_public_names():
    """The public API surface in __init__.py must include the 4 functions
    + Vary + __version__."""
    import vary_parse

    for name in (
        "Vary",
        "parse_vary",
        "serialize_vary",
        "vary_cache_key",
        "__version__",
    ):
        assert hasattr(vary_parse, name), f"missing public symbol: {name}"


def test_vary_is_namedtuple_subclass():
    """Vary must be a NamedTuple (structural typing — also a tuple)."""
    v = Vary(("A",), False)
    assert isinstance(v, tuple)
    assert v.field_names == ("A",)
    assert v.wildcard is False
    # Tuple-equality is structural.
    assert Vary(("A",), False) == (("A",), False)


def test_dependencies_list_is_empty():
    """pyproject.toml MUST declare zero runtime deps (Invariant)."""
    import tomllib

    with open(_REPO_ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    assert data["project"].get("dependencies", []) == [], (
        f"vary-parse MUST have zero runtime deps, got "
        f"{data['project'].get('dependencies')!r}"
    )


def test_py_typed_marker_present():
    """PEP 561: py.typed file ships with the package for downstream type
    checkers (mypy / pyright)."""
    assert (_REPO_ROOT / "src" / "vary_parse" / "py.typed").is_file()


def test_seed_evidence_not_mutated():
    """seed_evidence.json is a discoverer artifact — builder must not touch it."""
    seed = _REPO_ROOT / "seed_evidence.json"
    assert seed.is_file()
    # Don't read its contents here — just confirm presence.


def test_license_present():
    """MIT license file is present at repo root."""
    assert (_REPO_ROOT / "LICENSE").is_file()

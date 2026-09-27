# src/vary_parse/_vary_parse.py
#
# Reference implementation of the RFC 9110 §12.5.5 Vary response-header
# parser, serializer, and cache-key normalizer. Translates the ABNF
# verbatim into a Python state machine. Zero runtime dependencies.
#
# This file is the algorithm body. The public re-exports live in
# ``vary_parse.__init__`` so that ``from vary_parse import parse_vary``
# works as documented in the README. Do NOT modify the algorithm in
# cycle_135/build; any change is a follow-up fix-card, not a build
# concern.

from __future__ import annotations

import re
from typing import Mapping, NamedTuple, Optional


__version__ = "0.1.0"

# RFC 9110 §5.6.2 token = 1*tchar
# tchar = "!" / "#" / "$" / "%" / "&" / "'" / "*"
#      / "+" / "-" / "." / "^" / "_" / "`" / "|" / "~"
#      / DIGIT / ALPHA
_TOKEN_RE = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")

# RFC 9110 §5.6.3 OWS = *( SP / HTAB )  — used to strip whitespace around commas
_OWS_CHARS = " \t"


class Vary(NamedTuple):
    """Parsed RFC 9110 §12.5.5 Vary header field value.

    Attributes
    ----------
    field_names : tuple[str, ...]
        Selecting header field names. Empty when wildcard is True.
        Original case is preserved (RFC 9110 §5.6.2).
    wildcard : bool
        True iff the field value is the wildcard "*" member per
        RFC 9110 §12.5.5 paragraph 4.
    """

    field_names: tuple[str, ...]
    wildcard: bool


def parse_vary(value: str) -> Vary:
    """Parse an RFC 9110 §12.5.5 Vary field value.

    Parameters
    ----------
    value : str
        Raw Vary field value (without the leading "Vary:" header name).

    Returns
    -------
    Vary
        (field_names, wildcard). Empty input returns Vary((), False).

    Raises
    ------
    TypeError
        If ``value`` is not a ``str``.
    """
    if not isinstance(value, str):
        raise TypeError(
            f"parse_vary expected str, got {type(value).__name__}"
        )

    if value.strip() == "*":
        return Vary((), True)

    # Strip OWS around commas, split, drop empty entries, drop whitespace
    raw = value.replace("\t", " ").strip()
    parts: list[str] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if chunk:
            parts.append(chunk)
    # Wildcard precedence: if any element is "*", wildcard wins (RFC 9110 §12.5.5 ¶4)
    if any(p == "*" for p in parts):
        return Vary((), True)
    # Validate each as RFC 9110 §5.6.2 token (defensive against malformed)
    field_names: list[str] = []
    for p in parts:
        m = _TOKEN_RE.fullmatch(p)
        if m is None:
            # Malformed token: skip per RFC 9110 §5.6.1 "robust parsing" convention
            continue
        field_names.append(m.group(0))
    return Vary(tuple(field_names), False)


def serialize_vary(parsed: Vary) -> str:
    """Serialize a Vary back into canonical field-value form.

    Canonical form per RFC 9110 §12.5.5 + §5.6:
    - Wildcard True -> "*"
    - Empty field_names and not wildcard -> ""
    - Otherwise -> "Field1, Field2, Field3" (comma+space separator)
    """
    if parsed.wildcard:
        return "*"
    if not parsed.field_names:
        return ""
    return ", ".join(parsed.field_names)


def vary_cache_key(
    parsed: Vary, request_headers: Mapping[str, str]
) -> Optional[dict]:
    """Build a cache-key fragment from a parsed Vary.

    Per RFC 9110 §12.5.5 ¶4, wildcard means "do not cache locally";
    this function returns None in that case.

    Per RFC 9110 §5.5, field-name matching is case-insensitive; we
    lowercase the field names and prefix with ``vary_`` to avoid
    collision with the request-headers dict in the resulting flat key.

    Parameters
    ----------
    parsed : Vary
        The parsed Vary value.
    request_headers : Mapping[str, str]
        The original request header dict (or any mapping of
        field-name -> field-value).

    Returns
    -------
    Optional[dict]
        None when wildcard is True (do not cache).
        ``{"vary_<lower-field-name>": "<original-value>"}`` per
        selecting field otherwise. Missing fields are silently
        skipped (the response might still be valid for the cache
        if some Vary'd headers were absent from the original
        request).
    """
    if parsed.wildcard:
        return None
    if not isinstance(request_headers, Mapping):
        raise TypeError(
            f"vary_cache_key expected Mapping for request_headers, "
            f"got {type(request_headers).__name__}"
        )
    out: dict[str, str] = {}
    lower_map = {k.lower(): v for k, v in request_headers.items()}
    for name in parsed.field_names:
        v = lower_map.get(name.lower())
        if v is not None:
            out[f"vary_{name.lower()}"] = v
    return out


__all__ = ["Vary", "parse_vary", "serialize_vary", "vary_cache_key"]

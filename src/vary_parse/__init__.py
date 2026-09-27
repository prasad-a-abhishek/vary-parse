# src/vary_parse/__init__.py
#
# Public API surface for vary-parse. Re-exports the algorithm body
# (defined in ``_vary_parse.py``) so callers can write
# ``from vary_parse import parse_vary, Vary`` etc.
#
# The actual parsing/serializing/cache-key logic lives in
# ``_vary_parse.py`` to keep this module a thin facade.

from __future__ import annotations

from ._vary_parse import (
    Vary,
    parse_vary,
    serialize_vary,
    vary_cache_key,
)

__version__ = "0.1.0"

__all__ = [
    "Vary",
    "parse_vary",
    "serialize_vary",
    "vary_cache_key",
    "__version__",
]

"""conftest.py — ensures `src/` is on sys.path for `pytest` invocations
that don't set ``PYTHONPATH=src`` explicitly.

The build contract runs pytest both ways:
- ``PYTHONPATH=src pytest -q`` (preferred for hermetic test runs)
- ``pytest -q`` (for the canonical `python -m pytest` style)

This file makes both work without forcing every test file to
``import vary_parse._bootstrap_path_hack``.
"""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

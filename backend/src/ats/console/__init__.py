"""Operator console surface: research workbench and market data distribution.

This package is deliberately separate from :mod:`ats.api`. The A05 read-only
control surface is constitution-pinned to a fixed, minimal operation set; the
console is the operator workbench and is governed by a different invariant --
it must expose **no financial authority** (see
``tests/contract/api/test_console_boundary.py``).
"""

from .app import create_console_app

__all__ = ["create_console_app"]

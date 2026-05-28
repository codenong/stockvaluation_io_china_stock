"""Source-tree import shim for the flat valuation-agent package."""

from __future__ import annotations

from pathlib import Path

# Installed builds map the import package name to this directory through
# package_dir. A checkout with PYTHONPATH=valuation-agent loads this shim first.
__path__ = [str(Path(__file__).resolve().parent)]
__version__ = "0.1.0"

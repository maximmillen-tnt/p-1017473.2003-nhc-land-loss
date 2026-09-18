"""Readers and writers for the datasets the landloss models are built from.

:data:`ASSETS_DIR` is the one place the packaged data files are located from, so
a module elsewhere in the package reads them by importing it rather than by
counting ``parents[N]`` levels back to here -- a count that silently breaks the
moment that module moves into a submodule.

:data:`REPO_ROOT` anchors default on-disk caches (see ``readers.py`` and
``elevation.py``) so they always land in one place regardless of the current
working directory a script happens to be run from.
"""

from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent / "assets"
REPO_ROOT = Path(__file__).resolve().parents[3]

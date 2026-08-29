"""The Voynich Transliteration Tool (TVTT).

A workbench for building, testing and stress-testing substitution mappings
for the Voynich Manuscript.

The public entry point is the command line interface::

    python -m tvtt --help

Everything optional lives in :mod:`tvtt.plugins` and is switched on or off
from ``plugins.json``.  The core package has no required third-party
dependencies; optional extras (numpy, matplotlib, plotly, ...) are detected
at run time and features degrade gracefully when they are missing.
"""

__version__ = "2.0.0"
__author__ = "Krymorn (cmarbel on voynich.ninja)"

VERSION = __version__

__all__ = ["__version__", "__author__", "VERSION"]

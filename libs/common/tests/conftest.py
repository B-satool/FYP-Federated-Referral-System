"""Unit checks of the shared library, run on the host without the stack:
    .venv\\Scripts\\python -m pytest libs/common/tests -q
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

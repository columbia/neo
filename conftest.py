"""Pytest bootstrap: put ``src/`` on the path so ``import common.*`` etc. work."""
import sys
from pathlib import Path

SRC = Path(__file__).parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

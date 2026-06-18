import os
import sys

# Make sure banter package is importable from src/
_here = os.path.dirname(os.path.abspath(__file__))
_src = os.path.join(_here, "src")
for _p in (_src, "/app/src"):
    if _p not in sys.path:
        sys.path.insert(0, _p)

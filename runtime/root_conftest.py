import os
import sys

# Support both Docker (/app/src) and CI (runtime/src relative to repo root)
_src_candidates = [
    "/app/src",
    os.path.join(os.path.dirname(__file__), "src"),
]
for _p in _src_candidates:
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

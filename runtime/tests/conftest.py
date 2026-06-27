import os
import sys

# Add src/ to path so `from banter.<module> import ...` resolves to src/banter/
_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
for _candidate in ("/app/src", _src):
    if _candidate not in sys.path:
        sys.path.insert(0, _candidate)

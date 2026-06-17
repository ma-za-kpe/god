import os
import sys

# Add src/ to path so `from banter.<module> import ...` resolves to src/banter/
_src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if _src not in sys.path:
    sys.path.insert(0, _src)
# Also support absolute container path for Docker execution
if "/app/src" not in sys.path:
    sys.path.insert(0, "/app/src")

import sys
import os

# 1. Get the absolute path to the 'backend' folder
# This goes: Current File -> Up one level (tests/) -> Up one level (root) -> Down to 'backend'
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend'))

# 2. Add it to the front of the Python Path
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

print(f"Added to path: {backend_path}")
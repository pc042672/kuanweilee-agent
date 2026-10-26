# Required for ADK web to discover the agent
import sys
from pathlib import Path

# Add 'backend' directory to Python path for imports
# This must happen before importing agent which imports tools
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from . import agent

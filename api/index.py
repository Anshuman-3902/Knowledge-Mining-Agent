import sys
from pathlib import Path

# Ensure the root project directory is in the sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import app

# Vercel looks for the WSGI app instance
app = app

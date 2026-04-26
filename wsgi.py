"""
wsgi.py — Production entry point for gunicorn.

gunicorn command:
    gunicorn wsgi:application --workers 2 --threads 4 --timeout 120 --bind 0.0.0.0:$PORT
"""

import os
import sys
from pathlib import Path

# Ensure the project root is on the path
sys.path.insert(0, str(Path(__file__).parent))

# Set matplotlib to non-interactive backend BEFORE any imports touch it
os.environ.setdefault("MPLBACKEND", "Agg")

from app import app as application  # noqa: F401  — gunicorn looks for 'application'

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    application.run(host="0.0.0.0", port=port)

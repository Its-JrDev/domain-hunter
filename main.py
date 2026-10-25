#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "textual>=0.70.0",
#     "httpx>=0.27.0",
#     "dnspython>=2.6.0",
#     "rich>=13.0.0",
# ]
# ///
"""Lanzador de Domain Hunter con soporte de metadatos inline PEP 723."""

import sys
from pathlib import Path

# Añadir directorio actual al sys.path para imports de domain_hunter
CURRENT_DIR = Path(__file__).parent.resolve()
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from domain_hunter.main import main

if __name__ == "__main__":
    main()

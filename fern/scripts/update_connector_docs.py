#!/usr/bin/env python3
"""
Script to generate documentation for connectors based on codebase introspection.
"""

import sys
from pathlib import Path

# Add the parent directory to sys.path
script_dir = Path(__file__).parent
sys.path.append(str(script_dir))

# Now import from the module
from update_connector_docs.__main__ import main

if __name__ == "__main__":
    main()

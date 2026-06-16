"""Точка входа: ``python -m fbschema [-c path/to/config.env] [имена...]``."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv))

"""Main entrypoint for running `python -m walle`."""

import sys
from walle.cli import main

if __name__ == "__main__":
    sys.exit(main())

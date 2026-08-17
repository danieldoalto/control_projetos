"""Permite a execução direta via `python -m ctrl_prj` ou `python -m ctrl_prj.cli`."""

import sys
from ctrl_prj.cli import main

if __name__ == "__main__":
    sys.exit(main())

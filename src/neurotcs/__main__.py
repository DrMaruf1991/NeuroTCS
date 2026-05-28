"""Enable `python -m neurotcs` to invoke the CLI (mirrors the console script)."""
from neurotcs.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
"""Entry point so `python -m neurotcs.audit_core ...` works."""

from neurotcs.audit_core.cli import main

if __name__ == "__main__":
    raise SystemExit(main())

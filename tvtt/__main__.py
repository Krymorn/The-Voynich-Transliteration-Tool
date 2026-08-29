"""Allow ``python -m tvtt``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())

"""Pre-commit hook: fail if any staged file is larger than 1 MB (data belongs in data/)."""

from __future__ import annotations

import os
import sys

MAX_BYTES = 1_000_000


def main(paths: list[str]) -> int:
    too_big = [p for p in paths if os.path.isfile(p) and os.path.getsize(p) > MAX_BYTES]
    for path in too_big:
        print(f"{path}: {os.path.getsize(path) / 1e6:.1f} MB > 1 MB")
    return 1 if too_big else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

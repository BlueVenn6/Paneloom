import os
import sys

from desktop import launcher


def run() -> int:
    exit_code = launcher.main()
    if launcher._HARD_EXIT_REQUIRED:
        if sys.stdout:
            sys.stdout.flush()
        if sys.stderr:
            sys.stderr.flush()
        os._exit(exit_code)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(run())

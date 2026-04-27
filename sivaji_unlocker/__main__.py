"""Allow `python -m sivaji_unlocker` to launch the lock screen."""
import sys
from .ui import run_lock_app

if __name__ == "__main__":
    sys.exit(run_lock_app())

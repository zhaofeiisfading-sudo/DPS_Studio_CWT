"""Fresh interpreter entry point; inherited repository cache environment required."""

import json
import sys
from pathlib import Path

from .storage import worker

if __name__ == "__main__":
    print(json.dumps(worker(Path(sys.argv[1])), allow_nan=False))

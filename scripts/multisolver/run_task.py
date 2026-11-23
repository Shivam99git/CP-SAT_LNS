"""Execute one benchmark task (JSON on argv[1]) in a fresh interpreter and
print its record as one JSON line. Used by run_benchmark.py."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from campaign_lib import execute  # noqa: E402

if __name__ == "__main__":
    task = json.loads(sys.argv[1])
    print("@@RECORD@@" + json.dumps(execute(task)), flush=True)

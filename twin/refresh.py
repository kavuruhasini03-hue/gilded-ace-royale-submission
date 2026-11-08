"""Run the bundle's Databricks job, copy its Gold JSON and build the backup."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="DEFAULT")
    parser.add_argument("--warehouse-id", help="Override the bundle SQL warehouse for a new workspace")
    parser.add_argument("--run-id", type=int, help="Reuse a completed export job run")
    args = parser.parse_args()

    def databricks(*command, capture=False):
        return subprocess.run(["databricks", *command, "-p", args.profile],
                              cwd=ROOT, check=True, text=True,
                              stdout=subprocess.PIPE if capture else None,
                              stderr=subprocess.STDOUT if capture else None).stdout

    run_id = args.run_id
    if run_id is None:
        subprocess.run([sys.executable, "twin/build.py", "notebook"], cwd=ROOT, check=True)
        warehouse = ["--var", f"warehouse_id={args.warehouse_id}"] if args.warehouse_id else []
        databricks("bundle", "deploy", *warehouse)
        result = databricks("bundle", "run", "royale_twin_export", "--no-wait", *warehouse, capture=True)
        print(result.strip(), flush=True)
        match = re.search(r"/runs/(\d+)\b", result)
        if not match:
            raise RuntimeError("Could not find the Databricks export run ID")
        run_id = int(match[1])
    deadline = time.monotonic() + 600
    while True:
        run = json.loads(databricks("jobs", "get-run", str(run_id), "-o", "json", capture=True))
        if run["state"]["life_cycle_state"] in {"TERMINATED", "SKIPPED", "INTERNAL_ERROR"}:
            break
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Gold export {run_id} is still running; use --run-id to resume.")
        time.sleep(5)
    if run["state"].get("result_state") != "SUCCESS":
        raise RuntimeError(f"Gold export {run_id} did not succeed")
    databricks("fs", "cp", f"dbfs:/Volumes/workspace/royale/exports/twin-{run_id}.json",
               "embed/.gold-export.json", "--overwrite")
    subprocess.run([sys.executable, "twin/build.py", "build"], cwd=ROOT, check=True)


if __name__ == "__main__":
    main()

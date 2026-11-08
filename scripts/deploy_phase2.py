"""Upload the release parquet files, deploy the metrics, and verify them in SQL."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
TARGET = "workspace.royale"
VOLUME = "/Volumes/workspace/royale/raw"


def cli(profile, *args):
    return subprocess.check_output(
        ["databricks", *args, "--profile", profile, "--output", "json"],
        cwd=ROOT,
        text=True,
    )


def execute_sql(profile, warehouse, statement):
    payload = {"warehouse_id": warehouse, "statement": statement, "wait_timeout": "30s"}
    endpoint = "/api/2.0/sql/statements"
    result = json.loads(cli(profile, "api", "post", endpoint, "--json", json.dumps(payload)))
    deadline = time.monotonic() + 300
    while result["status"]["state"] in {"PENDING", "RUNNING"}:
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Check SQL statement {result['statement_id']} before retrying")
        time.sleep(2)
        result = json.loads(cli(profile, "api", "get", f"{endpoint}/{result['statement_id']}"))
    if result["status"]["state"] != "SUCCEEDED":
        raise RuntimeError(f"{statement}\n{result['status']}")
    return result.get("result", {}).get("data_array", [])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="DEFAULT")
    parser.add_argument("--warehouse-id", required=True)
    parser.add_argument("--skip-bronze", action="store_true")
    args = parser.parse_args()

    manifest = json.loads((ROOT / "data/manifest.json").read_text())
    parquet = [entry for entry in manifest["files"] if entry["path"].endswith(".parquet")]

    def sql(statement):
        return execute_sql(args.profile, args.warehouse_id, statement)

    def upload(entry):
        path = Path(entry["path"])
        cli(args.profile, "fs", "cp", f"data/{path}", f"dbfs:{VOLUME}/{path.name}", "--overwrite")

    def deploy(path):
        for statement in (ROOT / "databricks" / path).read_text().split(";"):
            if statement.strip():
                sql(statement)
        print(f"Applied {path}", flush=True)

    if not args.skip_bronze:
        sql("CREATE SCHEMA IF NOT EXISTS workspace.royale")
        sql("CREATE VOLUME IF NOT EXISTS workspace.royale.raw")
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(upload, parquet))
        print(f"Uploaded {len(parquet)} parquet files", flush=True)

        deploy("bronze/load.sql")
        for entry in parquet:
            path = Path(entry["path"])
            actual = int(sql(f"SELECT COUNT(*) FROM {TARGET}.{path.stem}")[0][0])
            if actual != entry["rows"]:
                raise ValueError(f"{path.stem}: expected {entry['rows']} rows, got {actual}")
            print(f"{path.stem}: {actual} rows verified", flush=True)

    deploy("silver/align_events.sql")
    for name in ("gold_lorenz", "gold_concentration", "gold_comp_week", "machine_day", "machine_verdict",
                 "supporting", "competing_explanations", "quality_gates",
                 "phase3_demand_downtime", "phase3_players", "phase3_comps", "phase3_quality",
                 "demand_recheck", "comp_recheck", "forecast", "forecast_quality",
                 "comp_control", "demand_mechanisms", "tech_shift_economics",
                 "action_voi", "action_plan", "action_quality", "evidence_vault"):
        deploy(f"gold/{name}.sql")
    print(sql(f"SELECT * FROM {TARGET}.gold_concentration ORDER BY top_percent"), flush=True)
    print(sql(f"SELECT COUNT(*), SUM(gaming_days), SUM(comp_cost_usd), "
              f"SUM(tracked_theo_usd), SUM(floor_theo_usd) FROM {TARGET}.gold_comp_week"), flush=True)


if __name__ == "__main__":
    main()

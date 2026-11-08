"""Log the frozen Databricks forecast comparison to MLflow."""
import argparse
import hashlib
import json
import time

from deploy_phase2 import ROOT, TARGET, cli, execute_sql


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--warehouse-id", required=True)
    parser.add_argument("--profile", default="DEFAULT")
    parser.add_argument("--experiment", default="/Shared/Dashboard Royale Forecast")
    args = parser.parse_args()

    def experiment(command, *options):
        return json.loads(cli(args.profile, "experiments", command, *options) or "{}")

    def sql(statement):
        return execute_sql(args.profile, args.warehouse_id, statement)

    if "'" in args.experiment:
        parser.error("The experiment path cannot contain a single quote.")
    existing = experiment("search-experiments", "--filter", f"name = '{args.experiment}'")
    experiments = existing.get("experiments", []) if isinstance(existing, dict) else existing
    experiment_id = (
        experiments[0]["experiment_id"] if experiments else
        experiment("create-experiment", args.experiment)["experiment_id"]
    )

    score_rows = sql(f"SELECT * FROM {TARGET}.gold_forecast_holdout_metrics ORDER BY model")
    parameters = sql(f"SELECT local_weekday, weekday_usd, event_effect_usd, holiday_effect_usd, "
                     f"baseline_usd FROM {TARGET}.gold_forecast_parameters ORDER BY local_weekday")
    source_sha = hashlib.sha256((ROOT / "databricks/gold/forecast.sql").read_bytes()).hexdigest()
    for model, scored_days, mae, mape in score_rows:
        now = int(time.time() * 1000)
        run = experiment("create-run", "--experiment-id", experiment_id,
                         "--run-name", model, "--start-time", str(now))
        run_id = run["run"]["info"]["run_id"]
        params = {
            "train_start": "2025-01-01", "train_end": "2025-04-30",
            "holdout_start": "2025-05-01", "holdout_end": "2025-06-30",
            "prediction_table": f"{TARGET}.gold_forecast_day",
            "sql_sha256": source_sha,
        }
        if model == "constant_baseline":
            params["constant_usd"] = parameters[0][4]
        else:
            params.update({f"weekday_{row[0]}_usd": row[1] for row in parameters})
            params.update(event_effect_usd=parameters[0][2], holiday_effect_usd=parameters[0][3],
                          flag_ridge_penalty="1.0", event_gate="announced_date < gaming_date")
        payload = {
            "run_id": run_id,
            "params": [{"key": k, "value": str(v)} for k, v in params.items()],
            "metrics": [{"key": key, "value": float(value), "timestamp": now, "step": 0}
                        for key, value in {"holdout_mae_usd": mae, "holdout_mape_pct": mape,
                                           "holdout_scored_days": scored_days}.items()],
        }
        try:
            experiment("log-batch", "--json", json.dumps(payload))
        except Exception:
            experiment("update-run", "--run-id", run_id, "--status", "FAILED")
            raise
        experiment("update-run", "--run-id", run_id, "--status", "FINISHED",
                   "--end-time", str(int(time.time() * 1000)))
        print(f"{model}: experiment {experiment_id}, run {run_id}", flush=True)


if __name__ == "__main__":
    main()

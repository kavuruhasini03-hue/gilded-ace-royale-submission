"""Fit one predeclared trend model and score a frozen forecast on the holdout."""
import csv
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
import tempfile

import numpy as np

from deploy_phase2 import execute_sql

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "twin/forecast-review.json"
FROZEN = ROOT / "twin/.secondary-frozen.json"
WAREHOUSE = "46ae4ab074f3051d"
MODEL = "weekday_ridge_linear_trend"
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def query(sql):
    return execute_sql("DEFAULT", WAREHOUSE, sql)


def matrix(rows, trend):
    return np.array([[float(weekday == name) for name in DAYS] + [float(event), float(holiday)]
                     + ([(date.fromisoformat(day) - date(2025, 1, 1)).days / 7] if trend else [])
                     for day, weekday, event, holiday, *_ in rows])


def fit(rows, trend):
    x = matrix(rows, trend)
    y = np.array([float(row[4]) for row in rows])
    penalty = np.zeros(x.shape[1])
    penalty[7:9] = 1.0
    return np.linalg.solve(x.T @ x + np.diag(penalty), x.T @ y)


def features(start, end, cutoff):
    return query(f"""SELECT CAST(f.gaming_date AS STRING), f.local_weekday, CAST(EXISTS(
        SELECT 1 FROM workspace.royale.events e
        WHERE f.gaming_date BETWEEN e.start_date AND e.end_date
        AND e.announced_date <= DATE '{cutoff}') AS INT), f.holiday_flag
        FROM workspace.royale.gold_forecast_features_day f
        WHERE f.gaming_date BETWEEN DATE '{start}' AND DATE '{end}' ORDER BY 1""")


def score(actual, prediction):
    residual = np.asarray(actual) - np.asarray(prediction)
    return {"mae": float(np.mean(abs(residual))), "mape": float(100 * np.mean(abs(residual) / actual))}


def mean_forecast(train, dates, seasonal):
    means = {day: np.mean([float(row[4]) for row in train if not seasonal or row[1] == day])
             for day in DAYS}
    return [float(means[row[1]]) for row in dates]


def main():
    if OUT.exists() or FROZEN.exists():
        raise SystemExit("Review outputs already exist. Preserve them rather than rescoring the holdout.")
    train = query("""SELECT CAST(gaming_date AS STRING),local_weekday,event_flag,holiday_flag,actual_usd
        FROM workspace.royale.gold_forecast_day WHERE gaming_date <= DATE '2025-04-30' ORDER BY 1""")
    jan_mar = train[:90]
    april = features("2025-04-01", "2025-04-30", "2025-03-31")
    april_actual = np.array([float(row[4]) for row in train[90:]])
    assert len(train) == 120 and len(april) == 30
    current_april = score(april_actual, matrix(april, False) @ fit(jan_mar, False))
    variant_april = score(april_actual, matrix(april, True) @ fit(jan_mar, True))
    baselines = {"Constant baseline": False, "Seasonal (weekday mean) baseline": True}
    april_baselines = {name: score(april_actual, mean_forecast(jan_mar, april, seasonal))
                       for name, seasonal in baselines.items()}
    ridge = fit(train, False)
    trend = fit(train, True)
    future = features("2025-05-01", "2025-06-30", "2025-04-30")
    assert len(future) == 61
    predicted = matrix(future, True) @ trend
    seasonal_prediction = mean_forecast(train, future, True)
    FROZEN.write_text(json.dumps({"origin":"2025-04-30","april_mae":variant_april["mae"],
        "predictions":dict(zip([r[0] for r in future],map(float,predicted)))},indent=2)+"\n")
    digest = hashlib.sha256(FROZEN.read_bytes()).hexdigest()

    # Read the holdout actuals only after the prediction table is frozen.
    holdout = query("""SELECT CAST(gaming_date AS STRING),local_weekday,actual_usd,
        baseline_usd,forecast_usd,event_flag FROM workspace.royale.gold_forecast_day
        WHERE split='holdout' ORDER BY 1""")
    assert [r[0] for r in future] == [r[0] for r in holdout]
    actual = np.array([float(row[2]) for row in holdout])
    origin_flag_differences = sum(int(float(old[5])) != int(new[2]) for old,new in zip(holdout,future))
    primary_origin = matrix(future, False) @ ridge
    series = {"Constant baseline": [float(r[3]) for r in holdout],
              "Current ridge": [float(r[4]) for r in holdout], "Ridge with a trend": predicted,
              "Seasonal (weekday mean) baseline": seasonal_prediction}
    results = {label:score(actual,values) for label,values in series.items()}
    origin_ridge = score(actual,primary_origin)
    bias = {day: {label:float(np.mean([actual[i]-values[i] for i,row in enumerate(holdout) if row[1]==day]))
                  for label,values in series.items()} for day in DAYS}

    # July sensitivity: reprice each covered date with the non-event daily forecast ratio.
    # Also bound recoverable value with the highest ratio at 100% recovery.
    july = [(day.isoformat(), DAYS[day.weekday()], 0, int(day.day == 4))
            for day in (date(2025,7,1)+timedelta(days=i) for i in range(30))]
    factors = matrix(july, True) @ trend / (matrix(july, False) @ ridge)
    snap = json.loads((ROOT/"embed/.gold-export.json").read_text())
    def rows(name):
        item=snap[name]
        return [dict(zip(item["columns"],r)) for r in item["rows"]]
    actions=[r for r in rows("actions") if r["action_type_id"]=="A-TECH-SHIFT"]
    sensitivity=[]
    for row in rows("tech"):
        action=next(r for r in actions if r["target_id"]==row["target"])
        weights=[factor for day,factor in zip(july,factors)
                 if date.fromisoformat(day[0]).day>action["lead_days"]
                 and (row["target"]!="Saturday evening" or day[1]=="Sat")]
        assert len(weights)==row["funded_shifts"] and min(weights)>0
        sensitivity.append({"shift":row["target"],"cost":row["package_cost_usd"],
            "original_recovery":action["mid_uplift_usd"],
            "repriced_recovery":float(action["mid_uplift_usd"]*np.mean(weights)),
            "maximum_recovery":float(row["full_recovery_theo_per_shift"]*len(weights)*max(weights))})
    result={"april":{"current":current_april,"trend":variant_april,**april_baselines},"holdout":results,"bias":bias,
        "strict_origin_ridge":origin_ridge,"origin_flag_differences":origin_flag_differences,
        "trend_usd_per_week":float(trend[-1]),"frozen_sha256":digest,"tech":sensitivity,
        "promote":variant_april["mae"]<current_april["mae"] and results["Ridge with a trend"]["mae"]<origin_ridge["mae"]
                  and results["Ridge with a trend"]["mae"]<results["Current ridge"]["mae"]}
    import mlflow
    mlflow.set_tracking_uri("databricks")
    with tempfile.TemporaryDirectory() as temp:
        table=Path(temp)/"predictions.csv"
        with table.open("w",newline="") as stream:
            writer=csv.writer(stream)
            writer.writerow(["gaming_date","weekday","actual_usd","constant_usd","current_ridge_usd","origin_ridge_usd","trend_usd"])
            for i,row in enumerate(holdout):
                writer.writerow([row[0],row[1],actual[i],series["Constant baseline"][i],
                                 series["Current ridge"][i],primary_origin[i],predicted[i]])
        with mlflow.start_run(experiment_id="2633256274998390",run_name=MODEL,tags={"model_role":"secondary"}) as run:
            mlflow.log_params({"model_role":"secondary","train_end":"2025-04-30","validation_origin":"2025-03-31",
                "event_gate":"announced_date <= origin","flag_ridge_penalty":1,"trend_usd_per_week":float(trend[-1]),
                "prediction_sha256":digest,"coefficients":json.dumps(trend.tolist())})
            mlflow.log_metrics({"april_mae_usd":variant_april["mae"],"april_mape_pct":variant_april["mape"],
                "holdout_mae_usd":results["Ridge with a trend"]["mae"],
                "holdout_mape_pct":results["Ridge with a trend"]["mape"],
                "holdout_scored_days":61,**{f"bias_{day}_usd":bias[day]["Ridge with a trend"] for day in DAYS}})
            mlflow.log_artifact(str(table))
            mlflow.log_artifact(str(FROZEN),artifact_path="frozen")
            result["mlflow_run_id"]=run.info.run_id
    OUT.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))


if __name__ == "__main__":
    main()

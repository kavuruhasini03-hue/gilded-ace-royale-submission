CREATE OR REPLACE VIEW workspace.royale.gold_forecast_features_day AS
SELECT c.gaming_date, c.local_weekday, c.is_weekend,
       CAST(c.federal_holiday IS NOT NULL AND TRIM(c.federal_holiday) <> '' AS DOUBLE) AS holiday_flag,
       CAST(EXISTS (
           SELECT 1 FROM workspace.royale.events e
           WHERE c.gaming_date BETWEEN e.start_date AND e.end_date
             AND e.announced_date < c.gaming_date
             AND e.announced_date <= DATE '2025-04-30'
       ) AS DOUBLE) AS event_flag
FROM workspace.royale.calendar_day c
WHERE c.gaming_date BETWEEN DATE '2025-01-01' AND DATE '2025-06-30';

CREATE OR REPLACE TABLE workspace.royale.gold_forecast_parameters USING DELTA AS
WITH train AS (
    SELECT f.*, CAST(g.coin_in_usd AS DOUBLE) AS y
    FROM workspace.royale.gold_forecast_features_day f
    JOIN workspace.royale.gold_floor_day g USING (gaming_date)
    WHERE f.gaming_date < DATE '2025-05-01'
), weekdays AS (
    SELECT local_weekday, AVG(y) AS y_bar, AVG(event_flag) AS e_bar, AVG(holiday_flag) AS h_bar
    FROM train GROUP BY local_weekday
), centered AS (
    SELECT t.y - w.y_bar AS y, t.event_flag - w.e_bar AS e, t.holiday_flag - w.h_bar AS h
    FROM train t JOIN weekdays w USING (local_weekday)
), normal_equations AS (
    SELECT SUM(e * e) + 1.0 AS ee, SUM(h * h) + 1.0 AS hh, SUM(e * h) AS eh,
           SUM(e * y) AS ey, SUM(h * y) AS hy
    FROM centered
), effects AS (
    SELECT (hh * ey - eh * hy) / (ee * hh - eh * eh) AS event_effect_usd,
           (ee * hy - eh * ey) / (ee * hh - eh * eh) AS holiday_effect_usd
    FROM normal_equations
), baseline AS (
    SELECT COUNT(*) AS training_days, MAX(gaming_date) AS trained_through, AVG(y) AS baseline_usd
    FROM train
)
SELECT w.local_weekday, w.y_bar - w.e_bar * e.event_effect_usd - w.h_bar * e.holiday_effect_usd AS weekday_usd,
       e.event_effect_usd, e.holiday_effect_usd, b.*, 1.0 AS flag_ridge_penalty
FROM weekdays w CROSS JOIN effects e CROSS JOIN baseline b;

CREATE OR REPLACE TABLE workspace.royale.gold_forecast_frozen USING DELTA AS
SELECT f.*, p.trained_through, p.baseline_usd,
       p.weekday_usd + f.event_flag * p.event_effect_usd + f.holiday_flag * p.holiday_effect_usd AS forecast_usd
FROM workspace.royale.gold_forecast_features_day f
JOIN workspace.royale.gold_forecast_parameters p USING (local_weekday);

CREATE OR REPLACE TABLE workspace.royale.gold_forecast_day USING DELTA AS
SELECT f.*, CASE WHEN f.gaming_date > f.trained_through THEN 'holdout' ELSE 'train' END AS split,
       g.coin_in_usd AS actual_usd,
       g.coin_in_usd - f.baseline_usd AS baseline_residual_usd,
       g.coin_in_usd - f.forecast_usd AS model_residual_usd
FROM workspace.royale.gold_forecast_frozen f
JOIN workspace.royale.gold_floor_day g USING (gaming_date);

CREATE OR REPLACE VIEW workspace.royale.gold_forecast_holdout_metrics AS
WITH predictions AS (
    SELECT actual_usd, 'constant_baseline' AS model, baseline_residual_usd AS residual
    FROM workspace.royale.gold_forecast_day WHERE split = 'holdout'
    UNION ALL
    SELECT actual_usd, 'weekday_event_holiday' AS model, model_residual_usd AS residual
    FROM workspace.royale.gold_forecast_day WHERE split = 'holdout'
)
SELECT model, COUNT(*) AS scored_days, AVG(ABS(residual)) AS mae_usd,
       100 * AVG(ABS(residual) / NULLIF(actual_usd, 0)) AS mape_pct
FROM predictions GROUP BY model;

CREATE OR REPLACE VIEW workspace.royale.gold_forecast_weekday_residual AS
SELECT local_weekday, COUNT(*) AS scored_days,
       AVG(baseline_residual_usd) AS baseline_mean_residual_usd,
       AVG(model_residual_usd) AS model_mean_residual_usd,
       AVG(ABS(model_residual_usd)) AS model_mae_usd
FROM workspace.royale.gold_forecast_day WHERE split = 'holdout' GROUP BY local_weekday;

CREATE OR REPLACE VIEW workspace.royale.gold_forecast_tech_timing AS
WITH historical_hours AS (
    SELECT c.local_weekday, PMOD(h.local_hour - 6, 24) AS gaming_hour,
           COUNT(DISTINCT h.gaming_date) AS observations,
           SUM(h.available_seconds) / 3600.0 AS available_hours,
           SUM(h.coin_in_cents * (1 - d.configured_rtp)) / 100.00 AS theo_usd
    FROM workspace.royale.machine_hour h
    JOIN workspace.royale.gold_machine_day d USING (machine_id, gaming_date)
    JOIN workspace.royale.calendar_day c USING (gaming_date)
    WHERE h.active AND h.location_id IS NOT NULL AND h.gaming_date < DATE '2025-05-01'
    GROUP BY 1, 2
)
SELECT h.*, h.theo_usd / NULLIF(h.available_hours, 0) AS theo_per_available_machine_hour,
       h.theo_usd / h.observations AS theo_per_typical_hour,
       p.weekday_usd AS non_event_daily_forecast_usd
FROM historical_hours h JOIN workspace.royale.gold_forecast_parameters p USING (local_weekday);

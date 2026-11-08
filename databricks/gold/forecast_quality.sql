WITH inputs AS (
    SELECT d.*, CAST(EXISTS (
        SELECT 1 FROM workspace.royale.events e
        WHERE d.gaming_date BETWEEN e.start_date AND e.end_date
          AND e.announced_date <= d.trained_through
    ) AS DOUBLE) AS known_event_at_origin
    FROM workspace.royale.gold_forecast_day d
), checks AS (
    SELECT COUNT(*) = 181 AND COUNT(DISTINCT gaming_date) = 181 AS daily_keys,
           COUNT_IF(split = 'train') = 120 AND COUNT_IF(split = 'holdout') = 61
               AND MIN(trained_through) = DATE '2025-04-30' AND MAX(trained_through) = DATE '2025-04-30' AS split_frozen,
           COUNT_IF(actual_usd <= 0 OR actual_usd IS NULL OR forecast_usd IS NULL OR baseline_usd IS NULL) = 0 AS valid_scores,
           COUNT_IF(split = 'holdout' AND NOT (event_flag <=> known_event_at_origin)) = 0 AS forecast_origin_ok
    FROM inputs
)
SELECT *, ASSERT_TRUE(daily_keys AND split_frozen AND valid_scores AND forecast_origin_ok,
                      'Forecast reconciliation failed') AS quality_gate
FROM checks;

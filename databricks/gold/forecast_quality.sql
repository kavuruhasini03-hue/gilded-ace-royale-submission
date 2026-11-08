WITH checks AS (
    SELECT COUNT(*) = 181 AND COUNT(DISTINCT gaming_date) = 181 AS daily_keys,
           COUNT_IF(split = 'train') = 120 AND COUNT_IF(split = 'holdout') = 61
               AND MIN(trained_through) = DATE '2025-04-30' AND MAX(trained_through) = DATE '2025-04-30' AS split_frozen,
           COUNT_IF(actual_usd <= 0 OR actual_usd IS NULL OR forecast_usd IS NULL OR baseline_usd IS NULL) = 0
               AS valid_scores
    FROM workspace.royale.gold_forecast_day
)
SELECT *, ASSERT_TRUE(daily_keys AND split_frozen AND valid_scores, 'Forecast reconciliation failed') AS quality_gate
FROM checks;

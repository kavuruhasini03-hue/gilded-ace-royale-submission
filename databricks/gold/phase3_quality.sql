WITH checks AS (
    SELECT
        (SELECT COUNT(*) FROM workspace.royale.gold_demand_context_day) =
            (SELECT COUNT(*) FROM workspace.royale.calendar_day) AS demand_calendar_matches,
        ABS((SELECT SUM(lost_theo_usd) FROM workspace.royale.gold_downtime_month_hour) -
            (SELECT SUM(leak_usd) FROM workspace.royale.gold_machine_day)) < 0.01 AS downtime_dollars_match,
        (SELECT SUM(player_net_usd) FROM workspace.royale.gold_player_outcome_window) =
            (SELECT SUM(player_net_usd) FROM workspace.royale.gold_player_decile_month) AS player_net_matches,
        (SELECT SUM(cost_usd) FROM workspace.royale.gold_comp_period WHERE grain = 'month') =
            (SELECT SUM(comp_cost_usd) FROM workspace.royale.gold_comp_week) AS comp_cost_matches,
        (SELECT COUNT(*) FROM workspace.royale.gold_adjusted_bottom10 WHERE floor_days >= 60) = 10 AS adjusted_exposure_matches,
        (SELECT COUNT(*) FROM workspace.royale.gold_machine_verdict
            WHERE verdict_chip IS NULL OR verdict_chip = 'MONITOR' OR
                  (verdict_chip = '♠ REPLACE (long-term candidate)' AND
                   (NOT replacement_material OR floor_days < 60 OR ci90_upper_usd >= 0))) = 0 AS verdict_rules_match
)
SELECT *, ASSERT_TRUE(demand_calendar_matches AND downtime_dollars_match AND player_net_matches
    AND comp_cost_matches AND adjusted_exposure_matches AND verdict_rules_match,
    'Phase 3 or verdict reconciliation failed') AS quality_gate
FROM checks;

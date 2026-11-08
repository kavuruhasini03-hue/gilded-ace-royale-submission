CREATE SCHEMA IF NOT EXISTS workspace.royale_export;

CREATE OR REPLACE VIEW workspace.royale_export.gold_guest_group_day AS
WITH cohort AS (
    SELECT p.player_id, p.period_month, COALESCE(p.tier_end, 'Unknown') AS tier_end,
           COALESCE(p.home_region, 'Unknown') AS home_region, COALESCE(p.age_band, 'Unknown') AS age_band,
           o.theo_decile
    FROM workspace.royale.player_period p
    JOIN workspace.royale.gold_player_outcome_window o USING (player_id)
), play AS (
    SELECT gaming_date, player_id, SUM(coin_in_cents) AS coin, SUM(payout_cents) AS payout,
           SUM(theo_cents) AS theo, 0 AS redemptions, 0 AS points, 0 AS face, 0 AS cost
    FROM workspace.royale.sessions WHERE gaming_date IS NOT NULL GROUP BY gaming_date, player_id
), rewards AS (
    SELECT gaming_date, player_id, 0 AS coin, 0 AS payout, 0 AS theo,
           COUNT(*) AS redemptions, SUM(-points_delta) AS points,
           SUM(face_value_cents) AS face, SUM(economic_cost_cents) AS cost
    FROM workspace.royale.silver_loyalty_ledger
    WHERE gaming_date IS NOT NULL AND event_type = 'redeem' GROUP BY gaming_date, player_id
), activity AS (
    SELECT * FROM play UNION ALL SELECT * FROM rewards
)
SELECT a.gaming_date, c.tier_end, c.home_region, c.age_band, c.theo_decile,
       SUM(coin)/100.0 AS coin_in_usd, SUM(payout)/100.0 AS payout_usd,
       SUM(payout-coin)/100.0 AS player_net_usd, SUM(theo)/100.0 AS theo_usd,
       SUM(payout-coin+theo)/100.0 AS player_luck_usd, SUM(redemptions) AS redemptions,
       SUM(points) AS points, SUM(face)/100.0 AS face_usd, SUM(cost)/100.0 AS cost_usd
FROM activity a JOIN cohort c ON a.player_id=c.player_id AND DATE_FORMAT(a.gaming_date, 'yyyy-MM')=c.period_month
GROUP BY a.gaming_date, c.tier_end, c.home_region, c.age_band, c.theo_decile;

CREATE OR REPLACE VIEW workspace.royale_export.gold_demand_bridge_day AS
WITH inputs AS (
    SELECT d.gaming_date, d.local_weekday, d.coin_in_usd AS actual_usd,
           COALESCE(w.machine_days * e.did_usd_per_machine_day, 0) AS walkway_usd,
           EXISTS(SELECT 1 FROM workspace.royale.events a
                  WHERE d.gaming_date BETWEEN a.start_date AND a.end_date) AS event_day
    FROM workspace.royale.gold_demand_context_day d
    LEFT JOIN workspace.royale.gold_walkway_daily w
      ON w.gaming_date = d.gaming_date AND w.back_forty AND w.phase = 'closure'
    LEFT JOIN workspace.royale.gold_walkway_did e ON e.phase = w.phase
), rates AS (
    SELECT local_weekday, SUM(actual_usd - walkway_usd) / COUNT(*) AS calendar_usd
    FROM inputs WHERE NOT event_day GROUP BY local_weekday
), components AS (
    SELECT i.*, r.calendar_usd, IF(i.event_day, i.actual_usd - i.walkway_usd - r.calendar_usd, 0) AS event_usd
    FROM inputs i JOIN rates r USING (local_weekday)
)
SELECT gaming_date, actual_usd, calendar_usd, event_usd, walkway_usd,
       actual_usd-calendar_usd-event_usd-walkway_usd AS other_usd
FROM components;

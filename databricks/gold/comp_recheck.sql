CREATE OR REPLACE VIEW workspace.royale.gold_comp_behavior_blocks AS
WITH days AS (
    SELECT c.change_date, d.gaming_date,
           CAST(FLOOR((DATEDIFF(d.gaming_date, c.change_date) + 28) / 7) AS INT) AS block_id
    FROM workspace.royale.calendar_day d CROSS JOIN workspace.royale.gold_comp_change_date c
    WHERE d.gaming_date >= DATE_SUB(c.change_date, 28) AND d.gaming_date < DATE_ADD(c.change_date, 28)
), play AS (
    SELECT d.block_id, COUNT(DISTINCT s.player_id) AS active_players,
           SUM(s.theo_cents) / 100.00 AS tracked_theo_usd, SUM(s.coin_in_cents) / 100.00 AS tracked_coin_in_usd
    FROM days d JOIN workspace.royale.sessions s USING (gaming_date)
    WHERE s.coin_in_cents > 0 GROUP BY d.block_id
), visits AS (
    SELECT d.block_id, COUNT(*) AS visits, COUNT_IF(t.observation_complete) AS complete_visits
    FROM days d JOIN workspace.royale.calendar_day c USING (gaming_date)
    JOIN workspace.royale.trips t
      ON t.first_observed_at_utc >= c.gaming_day_start_utc AND t.first_observed_at_utc < c.gaming_day_end_utc
    GROUP BY d.block_id
), ledger AS (
    SELECT d.block_id, COUNT_IF(l.event_type = 'redeem') AS redemptions,
           SUM(CASE WHEN l.event_type = 'award' THEN l.points_delta ELSE 0 END) AS points_earned
    FROM days d JOIN workspace.royale.silver_loyalty_ledger l USING (gaming_date)
    GROUP BY d.block_id
)
SELECT p.*, p.block_id >= 4 AS after_change, v.visits, v.complete_visits, l.redemptions, l.points_earned
FROM play p JOIN visits v USING (block_id) JOIN ledger l USING (block_id);

CREATE OR REPLACE VIEW workspace.royale.gold_comp_behavior_effect AS
WITH samples AS (
    SELECT r.id AS replicate, phase.id AS phase,
           phase.id * 4 + PMOD(XXHASH64(r.id, phase.id, draw.id, 20250102), 4) AS block_id
    FROM RANGE(2000) r CROSS JOIN RANGE(2) phase CROSS JOIN RANGE(4) draw
    UNION ALL SELECT -1, CAST(block_id >= 4 AS INT), block_id
    FROM workspace.royale.gold_comp_behavior_blocks
), totals AS (
    SELECT s.replicate, s.phase, SUM(b.visits) / COUNT(*) AS visits_per_week,
           SUM(b.redemptions) / NULLIF(SUM(b.active_players), 0) AS redemptions_per_active,
           SUM(b.tracked_theo_usd) / NULLIF(SUM(b.active_players), 0) AS theo_per_active_usd,
           SUM(b.points_earned) / NULLIF(SUM(b.tracked_coin_in_usd), 0) AS points_earned_per_coin_in_usd,
           SUM(b.points_earned) / NULLIF(SUM(b.tracked_theo_usd), 0) AS points_earned_per_theo_usd
    FROM samples s JOIN workspace.royale.gold_comp_behavior_blocks b USING (block_id)
    GROUP BY s.replicate, s.phase
), measures AS (
    SELECT replicate, phase, metric, value FROM totals
    UNPIVOT (value FOR metric IN (visits_per_week, redemptions_per_active, theo_per_active_usd,
                                  points_earned_per_coin_in_usd, points_earned_per_theo_usd))
), deltas AS (
    SELECT replicate, metric, MAX(IF(phase = 0, value, NULL)) AS before_value,
           MAX(IF(phase = 1, value, NULL)) AS after_value
    FROM measures GROUP BY replicate, metric
)
SELECT metric, MAX(IF(replicate = -1, before_value, NULL)) AS before_value,
       MAX(IF(replicate = -1, after_value, NULL)) AS after_value,
       MAX(IF(replicate = -1, after_value - before_value, NULL)) AS change_value,
       PERCENTILE(IF(replicate >= 0, after_value - before_value, NULL), 0.05) AS change_ci90_lower,
       PERCENTILE(IF(replicate >= 0, after_value - before_value, NULL), 0.95) AS change_ci90_upper
FROM deltas GROUP BY metric;

CREATE OR REPLACE VIEW workspace.royale.gold_points_liability_day AS
WITH flows AS (
    SELECT gaming_date,
           SUM(IF(event_type = 'award', points_delta, 0)) AS points_awarded,
           -SUM(IF(event_type = 'redeem', points_delta, 0)) AS points_redeemed,
           SUM(points_delta) AS net_points
    FROM workspace.royale.silver_loyalty_ledger
    WHERE gaming_date IS NOT NULL
    GROUP BY gaming_date
)
SELECT *, SUM(net_points) OVER (ORDER BY gaming_date ROWS UNBOUNDED PRECEDING) AS outstanding_points
FROM flows;

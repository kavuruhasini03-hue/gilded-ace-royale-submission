CREATE OR REPLACE VIEW workspace.royale.gold_comp_period AS
WITH redemption_days AS (
    SELECT gaming_date, COUNT(*) AS redemptions, SUM(-points_delta) AS points,
           SUM(face_value_cents) / 100.00 AS face_usd, SUM(economic_cost_cents) / 100.00 AS cost_usd
    FROM workspace.royale.silver_loyalty_ledger
    WHERE event_type = 'redeem' AND gaming_date IS NOT NULL
    GROUP BY gaming_date
), periods AS (
    SELECT gaming_date, 'week' AS grain, CAST(DATE_TRUNC('week', gaming_date) AS DATE) AS period_start
    FROM workspace.royale.calendar_day
    UNION ALL
    SELECT gaming_date, 'month', CAST(DATE_TRUNC('month', gaming_date) AS DATE)
    FROM workspace.royale.calendar_day
), activity AS (
    SELECT p.grain, p.period_start, COUNT(DISTINCT s.player_id) AS active_players
    FROM periods p JOIN workspace.royale.sessions s USING (gaming_date)
    WHERE s.coin_in_cents > 0
    GROUP BY p.grain, p.period_start
), metrics AS (
    SELECT p.grain, p.period_start, COUNT(*) AS gaming_days, SUM(r.redemptions) AS redemptions,
           SUM(r.points) AS points, SUM(r.face_usd) AS face_usd, SUM(r.cost_usd) AS cost_usd,
           SUM(k.tracked_theo_usd) AS tracked_theo_usd, SUM(k.theo_usd) AS floor_theo_usd
    FROM periods p LEFT JOIN redemption_days r USING (gaming_date)
    JOIN workspace.royale.gold_kpi_header k USING (gaming_date)
    GROUP BY p.grain, p.period_start
)
SELECT m.*, a.active_players, points / NULLIF(face_usd, 0) AS points_per_face_usd,
       cost_usd / NULLIF(tracked_theo_usd, 0) AS reinvestment_tracked,
       cost_usd / NULLIF(floor_theo_usd, 0) AS reinvestment_floor,
       redemptions / NULLIF(a.active_players, 0) AS redemptions_per_active_player
FROM metrics m LEFT JOIN activity a USING (grain, period_start);

CREATE OR REPLACE VIEW workspace.royale.gold_comp_tier_day AS
SELECT l.gaming_date, COALESCE(l.tier_before, 'unknown') AS tier,
       COALESCE(p.home_region, 'unknown') AS region,
       COUNT(*) AS redemptions, SUM(-l.points_delta) AS points,
       SUM(l.face_value_cents) / 100.00 AS face_usd, SUM(l.economic_cost_cents) / 100.00 AS cost_usd
FROM workspace.royale.silver_loyalty_ledger l
LEFT JOIN workspace.royale.players p USING (player_id)
WHERE l.event_type = 'redeem' AND l.gaming_date IS NOT NULL
GROUP BY 1, 2, 3;

CREATE OR REPLACE VIEW workspace.royale.gold_comp_change_date AS
WITH daily AS (
    SELECT gaming_date, SUM(points) AS points, SUM(face_usd) AS face_usd
    FROM workspace.royale.gold_comp_tier_day GROUP BY gaming_date
), candidates AS (
    SELECT c.gaming_date AS change_date, d.gaming_date >= c.gaming_date AS after_change,
           SUM(d.points) AS points, SUM(d.face_usd) AS face_usd,
           SUM(POW(d.points, 2) / NULLIF(d.face_usd, 0)) AS squared_term, COUNT(*) AS days
    FROM daily c CROSS JOIN daily d GROUP BY 1, 2
), scores AS (
    SELECT change_date, SUM(squared_term - POW(points, 2) / NULLIF(face_usd, 0)) AS weighted_error
    FROM candidates GROUP BY change_date HAVING MIN(days) >= 28 AND COUNT(*) = 2
)
SELECT * FROM scores ORDER BY weighted_error, change_date LIMIT 1;

CREATE OR REPLACE VIEW workspace.royale.gold_comp_before_after AS
WITH cohorts AS (
    SELECT gaming_date, 'floor' AS dimension, 'all' AS cohort, redemptions, points, face_usd, cost_usd
    FROM workspace.royale.gold_comp_tier_day
    UNION ALL SELECT gaming_date, 'tier', tier, redemptions, points, face_usd, cost_usd
    FROM workspace.royale.gold_comp_tier_day
    UNION ALL SELECT gaming_date, 'region', region, redemptions, points, face_usd, cost_usd
    FROM workspace.royale.gold_comp_tier_day
), sums AS (
    SELECT change_date, dimension, cohort, gaming_date >= change_date AS after_change,
           SUM(redemptions) AS redemptions, SUM(points) AS points, SUM(face_usd) AS face_usd,
           SUM(cost_usd) AS cost_usd
    FROM cohorts CROSS JOIN workspace.royale.gold_comp_change_date
    WHERE gaming_date >= DATE_SUB(change_date, 28) AND gaming_date < DATE_ADD(change_date, 28)
    GROUP BY 1, 2, 3, 4
)
SELECT *, points / NULLIF(face_usd, 0) AS points_per_face_usd
FROM sums;

CREATE OR REPLACE VIEW workspace.royale.gold_comp_change_uncertainty AS
WITH blocks AS (
    SELECT c.change_date, FLOOR((DATEDIFF(d.gaming_date, c.change_date) + 28) / 7) AS block_id,
           SUM(d.points) AS points, SUM(d.face_usd) AS face_usd
    FROM workspace.royale.gold_comp_tier_day d CROSS JOIN workspace.royale.gold_comp_change_date c
    WHERE d.gaming_date >= DATE_SUB(c.change_date, 28) AND d.gaming_date < DATE_ADD(c.change_date, 28)
    GROUP BY 1, 2
), samples AS (
    SELECT r.id AS replicate, phase.id AS phase,
           phase.id * 4 + PMOD(XXHASH64(r.id, phase.id, draw.id, 20250102), 4) AS block_id
    FROM RANGE(1000) r CROSS JOIN RANGE(2) phase CROSS JOIN RANGE(4) draw
), rates AS (
    SELECT b.change_date, s.replicate, s.phase, SUM(b.points) / NULLIF(SUM(b.face_usd), 0) AS rate
    FROM samples s JOIN blocks b USING (block_id) GROUP BY 1, 2, 3
), deltas AS (
    SELECT change_date, replicate, MAX(CASE WHEN phase = 1 THEN rate END)
            - MAX(CASE WHEN phase = 0 THEN rate END) AS change_points_per_face_usd
    FROM rates GROUP BY 1, 2
)
SELECT change_date, PERCENTILE(change_points_per_face_usd, 0.05) AS ci90_lower,
       PERCENTILE(change_points_per_face_usd, 0.95) AS ci90_upper
FROM deltas GROUP BY change_date;

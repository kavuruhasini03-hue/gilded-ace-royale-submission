CREATE OR REPLACE VIEW workspace.royale.gold_points_liability_bridge AS
WITH snapshots AS (
    SELECT MAX(IF(v.gaming_date = DATE_SUB(c.change_date, 29), outstanding_points, NULL)) AS opening_points,
           MAX(IF(v.gaming_date = DATE_SUB(c.change_date, 1), outstanding_points, NULL)) AS pre_points,
           MAX(IF(v.gaming_date = DATE_ADD(c.change_date, 27), outstanding_points, NULL)) AS post_points,
           MAX(IF(v.gaming_date = DATE_SUB(c.change_date, 1), face_usd_per_point, NULL)) AS pre_face_rate,
           MAX(IF(v.gaming_date = DATE_ADD(c.change_date, 27), face_usd_per_point, NULL)) AS post_face_rate,
           MAX(IF(v.gaming_date = DATE_SUB(c.change_date, 1), cost_usd_per_point, NULL)) AS pre_cost_rate,
           MAX(IF(v.gaming_date = DATE_ADD(c.change_date, 27), cost_usd_per_point, NULL)) AS post_cost_rate
    FROM workspace.royale.gold_points_redemption_value_day v CROSS JOIN workspace.royale.gold_comp_change_date c
), rates AS (
    SELECT 'face' AS valuation, opening_points, pre_points, post_points, pre_face_rate AS pre_usd_per_point,
           post_face_rate AS post_usd_per_point FROM snapshots
    UNION ALL
    SELECT 'economic', opening_points, pre_points, post_points, pre_cost_rate, post_cost_rate FROM snapshots
)
SELECT *, pre_points - opening_points AS normal_28d_accrual, post_points - pre_points AS post_28d_accrual,
       post_points - 2 * pre_points + opening_points AS excess_points,
       pre_points * pre_usd_per_point AS apr30_usd, post_points * post_usd_per_point AS may28_usd,
       (pre_points - opening_points) * pre_usd_per_point AS normal_accrual_usd,
       (post_points - 2 * pre_points + opening_points) * pre_usd_per_point AS excess_accrual_usd,
       post_points * (post_usd_per_point - pre_usd_per_point) AS repricing_usd,
       post_points * post_usd_per_point - (2 * pre_points - opening_points) * pre_usd_per_point
           AS excess_valuation_usd
FROM rates;

CREATE OR REPLACE VIEW workspace.royale.gold_comp_control_week AS
WITH daily AS (
    SELECT m.gaming_date,
           SUM(m.carded_coin_in_cents) / 100.0 AS carded_coin_in,
           SUM(m.coin_in_cents - m.carded_coin_in_cents) / 100.0 AS uncarded_coin_in,
           SUM(m.carded_theo_cents) / 100.0 AS carded_theo,
           SUM(m.theo_cents - m.carded_theo_cents) / 100.0 AS uncarded_theo
    FROM workspace.royale.machine_day m
    WHERE m.active AND m.location_id IS NOT NULL GROUP BY m.gaming_date
), weeks AS (
    SELECT CAST(FLOOR(DATEDIFF(gaming_date, change_date) / 7) AS INT) AS relative_week,
           MIN(gaming_date) AS week_start, COUNT(*) AS gaming_days,
           SUM(carded_coin_in) AS carded_coin_in, SUM(uncarded_coin_in) AS uncarded_coin_in,
           SUM(carded_theo) AS carded_theo, SUM(uncarded_theo) AS uncarded_theo
    FROM daily CROSS JOIN workspace.royale.gold_comp_change_date GROUP BY 1
)
SELECT *, carded_coin_in / NULLIF(carded_coin_in + uncarded_coin_in, 0) AS carded_share
FROM weeks;

CREATE OR REPLACE VIEW workspace.royale.gold_comp_control_effect AS
WITH samples AS (
    SELECT r.id AS replicate, phase.id AS phase,
           phase.id * 4 - 4 + PMOD(XXHASH64(r.id, phase.id, draw.id, 20250102), 4) AS relative_week
    FROM RANGE(2000) r CROSS JOIN RANGE(2) phase CROSS JOIN RANGE(4) draw
    UNION ALL SELECT -1, CAST(relative_week >= 0 AS INT), relative_week
    FROM workspace.royale.gold_comp_control_week WHERE relative_week BETWEEN -4 AND 3
), phases AS (
    SELECT s.replicate, s.phase, SUM(w.carded_coin_in) / COUNT(*) AS carded_per_week,
           SUM(w.uncarded_coin_in) / COUNT(*) AS uncarded_per_week,
           SUM(w.uncarded_theo) / COUNT(*) AS uncarded_theo_per_week,
           SUM(w.carded_coin_in) / SUM(w.carded_coin_in + w.uncarded_coin_in) AS share,
           SUM(b.tracked_theo_usd) / SUM(b.active_players) AS tracked_theo_per_player
    FROM samples s JOIN workspace.royale.gold_comp_control_week w USING (relative_week)
    JOIN workspace.royale.gold_comp_behavior_blocks b ON b.block_id = s.relative_week + 4
    GROUP BY s.replicate, s.phase
), deltas AS (
    SELECT a.replicate,
           100 * (a.carded_per_week / p.carded_per_week / (a.uncarded_per_week / p.uncarded_per_week) - 1) AS relative_coin_in_pct,
           a.carded_per_week - p.carded_per_week * a.uncarded_per_week / p.uncarded_per_week AS relative_coin_in_usd_week,
           100 * (a.share - p.share) AS carded_share_pp,
           a.tracked_theo_per_player - p.tracked_theo_per_player AS tracked_theo_per_player_raw_usd,
           a.tracked_theo_per_player - p.tracked_theo_per_player * a.uncarded_theo_per_week / p.uncarded_theo_per_week
               AS tracked_theo_per_player_control_adjusted_usd
    FROM phases a JOIN phases p USING (replicate) WHERE a.phase = 1 AND p.phase = 0
), measures AS (
    SELECT replicate, metric, value FROM deltas
    UNPIVOT (value FOR metric IN (relative_coin_in_pct, relative_coin_in_usd_week, carded_share_pp,
        tracked_theo_per_player_raw_usd, tracked_theo_per_player_control_adjusted_usd))
)
SELECT metric, MAX(IF(replicate = -1, value, NULL)) AS estimate,
       PERCENTILE(IF(replicate >= 0, value, NULL), 0.05) AS ci90_lower,
       PERCENTILE(IF(replicate >= 0, value, NULL), 0.95) AS ci90_upper
FROM measures GROUP BY metric;

CREATE OR REPLACE VIEW workspace.royale.gold_comp_control_pretrend AS
WITH pre AS (
    SELECT relative_week, LOG(carded_coin_in / uncarded_coin_in) AS log_ratio,
           carded_share * 100 AS share_pp
    FROM workspace.royale.gold_comp_control_week WHERE relative_week < 0 AND gaming_days = 7
), stats AS (
    SELECT COUNT(*) AS weeks, REGR_SLOPE(log_ratio, relative_week) AS log_ratio_slope,
           REGR_R2(log_ratio, relative_week) AS ratio_r2, REGR_SYY(log_ratio, relative_week) AS ratio_syy,
           REGR_SLOPE(share_pp, relative_week) AS share_pp_slope,
           REGR_R2(share_pp, relative_week) AS share_r2, REGR_SYY(share_pp, relative_week) AS share_syy,
           REGR_SXX(log_ratio, relative_week) AS sxx
    FROM pre
)
SELECT weeks, log_ratio_slope, SQRT((1-ratio_r2)*ratio_syy/((weeks-2)*sxx)) AS log_ratio_slope_se,
       share_pp_slope, SQRT((1-share_r2)*share_syy/((weeks-2)*sxx)) AS share_pp_slope_se
FROM stats;

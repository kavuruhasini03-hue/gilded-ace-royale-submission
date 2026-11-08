CREATE OR REPLACE VIEW workspace.royale.gold_action_cost AS
SELECT a.*, h.horizon_days, GREATEST(0, h.horizon_days - a.lead_days) AS operating_days,
       (a.unit_cost_cents + a.recurring_cost_cents_per_day * GREATEST(0, h.horizon_days - a.lead_days))
         / 100.00 AS cost_per_unit_usd
FROM workspace.royale.action_catalog a
CROSS JOIN (SELECT 30 AS horizon_days UNION ALL SELECT 365) h;

CREATE OR REPLACE TABLE workspace.royale.gold_machine_verdict USING DELTA AS
WITH machine AS (
    SELECT machine_id, MAX_BY(zone_name, gaming_date) AS last_zone, MAX(manufacturer) AS manufacturer,
           MAX_BY(zone_id, gaming_date) AS last_zone_id,
           MAX_BY(bank_id, gaming_date) AS last_bank_id,
           MAX_BY(bank_name, gaming_date) AS last_bank_name,
           MAX_BY(config_id, gaming_date) AS last_config_id,
           COUNT(DISTINCT bank_id) AS banks_observed,
           SUM(potential_theo_usd) AS potential_theo_usd,
           COUNT(*) AS floor_days, SUM(available_hours) AS available_hours,
           SUM(available_seconds) / NULLIF(SUM(scheduled_seconds), 0) AS availability,
           SUM(faults_opened) AS faults,
           SUM(house_win_usd) AS house_win_usd, SUM(theo_usd) AS theo_usd,
           SUM(luck_residual_usd) AS luck_usd, SQRT(SUM(luck_variance_usd2)) AS luck_sigma_usd,
           SUM(machine_specific_usd) AS machine_specific_usd, SUM(leak_usd) AS leak_usd,
           SUM(location_usd) AS location_usd, SUM(lineup_usd) AS lineup_usd,
           SUM(config_peer_rate * available_seconds) / NULLIF(SUM(available_seconds), 0) AS config_peer_rate
    FROM workspace.royale.gold_machine_day GROUP BY machine_id
), ordered_days AS (
    SELECT machine_id, machine_specific_usd,
           ROW_NUMBER() OVER (PARTITION BY machine_id ORDER BY gaming_date) AS day_idx
    FROM workspace.royale.gold_machine_day
), samples AS (
    SELECT m.machine_id, r.id AS replicate,
           PMOD(XXHASH64(m.machine_id, r.id, draw, 20250102), m.floor_days) + 1 AS day_idx
    FROM machine m
    CROSS JOIN RANGE(400) r
    LATERAL VIEW EXPLODE(SEQUENCE(1L, m.floor_days)) draws AS draw
), bootstrap AS (
    SELECT s.machine_id, s.replicate, SUM(d.machine_specific_usd) AS effect_usd
    FROM samples s JOIN ordered_days d USING (machine_id, day_idx)
    GROUP BY s.machine_id, s.replicate
), ci AS (
    SELECT machine_id, PERCENTILE(effect_usd, 0.05) AS ci90_lower_usd,
           PERCENTILE(effect_usd, 0.95) AS ci90_upper_usd
    FROM bootstrap GROUP BY machine_id
), exposure_window AS (
    SELECT COUNT(*) AS window_days FROM workspace.royale.calendar_day
), ranks AS (
    SELECT m.*, ci.ci90_lower_usd, ci.ci90_upper_usd,
           -CAST(m.machine_specific_usd AS DOUBLE) / w.window_days AS uplift_per_day,
           -ci.ci90_upper_usd / w.window_days AS uplift_per_day_lower,
           -ci.ci90_lower_usd / w.window_days AS uplift_per_day_upper,
           m.luck_usd / NULLIF(m.luck_sigma_usd, 0) AS luck_z,
           ROW_NUMBER() OVER (ORDER BY m.house_win_usd, m.machine_id) AS gm_rank,
           CASE WHEN floor_days >= 60 THEN ROW_NUMBER() OVER (
               ORDER BY CASE WHEN floor_days >= 60 THEN 0 ELSE 1 END, ci.ci90_upper_usd, m.machine_id
           ) END AS adjusted_rank
    FROM machine m JOIN ci USING (machine_id)
    CROSS JOIN exposure_window w
), options AS (
    SELECT r.machine_id, a.action_type_id, a.horizon_days, a.cost_per_unit_usd,
           a.operating_days * r.uplift_per_day AS uplift_usd,
           a.operating_days * r.uplift_per_day - a.cost_per_unit_usd AS net_benefit_usd,
           a.operating_days * r.uplift_per_day_lower - a.cost_per_unit_usd AS net_ci90_lower_usd,
           a.operating_days * r.uplift_per_day_upper - a.cost_per_unit_usd AS net_ci90_upper_usd,
           CASE WHEN r.uplift_per_day > a.recurring_cost_cents_per_day / 100.00
                THEN a.lead_days + a.unit_cost_cents / 100.00
                    / (r.uplift_per_day - a.recurring_cost_cents_per_day / 100.00) END AS payback_days
    FROM ranks r CROSS JOIN workspace.royale.gold_action_cost a
    WHERE a.action_type_id IN ('A-REPLACE-LEASE', 'A-REPLACE-BUY')
), best_annual AS (
    SELECT * FROM options WHERE horizon_days = 365
    QUALIFY ROW_NUMBER() OVER (PARTITION BY machine_id ORDER BY net_benefit_usd DESC, action_type_id) = 1
), eligibility AS (
    SELECT r.*, july.uplift_usd AS uplift_30d_usd, july.cost_per_unit_usd AS replacement_cost_30d_usd,
           y.action_type_id AS replacement_action_12m, y.uplift_usd AS uplift_12m_usd,
           y.cost_per_unit_usd AS replacement_cost_12m_usd, y.net_benefit_usd AS net_benefit_12m_usd,
           y.net_ci90_lower_usd, y.net_ci90_upper_usd,
           CAST(CEIL(y.payback_days * 12 / 365) AS BIGINT) AS payback_month,
           y.net_benefit_usd > 0 AND y.payback_days <= 365 AS replacement_material,
           LEAST(location_usd, -leak_usd, lineup_usd, luck_usd, 0) AS worst_non_machine_usd
    FROM ranks r JOIN best_annual y USING (machine_id)
    JOIN options july ON r.machine_id = july.machine_id
         AND july.horizon_days = 30 AND july.action_type_id = 'A-REPLACE-LEASE'
), decisions AS (
    SELECT *,
           ci90_upper_usd < 0 AND NOT replacement_material AS weaker_than_peers_but_immaterial,
           CASE
             WHEN worst_non_machine_usd < 0 AND location_usd = worst_non_machine_usd THEN '♣ LOCATION'
             WHEN worst_non_machine_usd < 0 AND -leak_usd = worst_non_machine_usd THEN '♥ LEAK'
             WHEN worst_non_machine_usd < 0 AND lineup_usd = worst_non_machine_usd THEN '⚙ LINEUP'
             ELSE '♦ LUCK'
           END AS dominant_non_machine_chip
    FROM eligibility
)
SELECT *,
       floor_days >= 60 AND ci90_upper_usd < 0 AND replacement_material AS long_term_candidate,
       CASE
         WHEN ABS(luck_z) >= 3 THEN '🔍 INSPECT'
         WHEN floor_days >= 60 AND ci90_upper_usd < 0 AND replacement_material
           THEN '♠ REPLACE (long-term candidate)'
         ELSE dominant_non_machine_chip
       END AS verdict_chip
FROM decisions;

CREATE OR REPLACE VIEW workspace.royale.gold_walkway_daily AS
WITH closure AS (
    SELECT c.gaming_date,
           CASE WHEN c.gaming_day_end_utc <= w.closed_from_utc THEN 'pre'
                WHEN c.gaming_day_start_utc >= w.closed_to_utc THEN 'post'
                ELSE 'closure' END AS phase
    FROM workspace.royale.calendar_day c
    CROSS JOIN workspace.royale.floor_walkways w
    WHERE w.walkway_id = 'W-ENT-B40'
)
SELECT d.gaming_date, c.phase, d.zone_id = 'Z-B40' AS back_forty,
       SUM(d.coin_in_usd) AS coin_in_usd, COUNT(*) AS machine_days,
       SUM(d.available_seconds) AS available_seconds
FROM workspace.royale.gold_machine_day d JOIN closure c USING (gaming_date)
GROUP BY d.gaming_date, c.phase, d.zone_id = 'Z-B40';

CREATE OR REPLACE VIEW workspace.royale.gold_walkway_traffic_week AS
WITH phases AS (
    SELECT DISTINCT gaming_date, phase FROM workspace.royale.gold_walkway_daily
), weekly AS (
    SELECT CAST(DATE_TRUNC('week', t.gaming_date) AS DATE) AS week_start, p.phase,
           t.zone_id = 'Z-B40' AS back_forty,
           SUM(CASE WHEN t.coverage_minutes > 0 THEN t.entries_count END) AS entries,
           SUM(CASE WHEN t.entries_count IS NOT NULL AND t.coverage_minutes > 0
                    THEN t.coverage_minutes ELSE 0 END) AS covered_minutes,
           COUNT(*) * 60 AS reported_sensor_minutes
    FROM workspace.royale.silver_zone_traffic_hourly t
    JOIN phases p USING (gaming_date)
    GROUP BY 1, 2, 3
)
SELECT *, 60.0 * entries / NULLIF(covered_minutes, 0) AS entries_per_covered_hour,
       covered_minutes / NULLIF(reported_sensor_minutes, 0) AS coverage_share
FROM weekly;

CREATE OR REPLACE VIEW workspace.royale.gold_walkway_did AS
WITH rates AS (
    SELECT phase, back_forty, SUM(coin_in_usd) / SUM(machine_days) AS coin_in_per_machine_day
    FROM workspace.royale.gold_walkway_daily GROUP BY phase, back_forty
), gaps AS (
    SELECT phase, MAX(CASE WHEN back_forty THEN coin_in_per_machine_day END) AS back_forty_rate,
           MAX(CASE WHEN NOT back_forty THEN coin_in_per_machine_day END) AS control_rate
    FROM rates GROUP BY phase
), traffic AS (
    SELECT phase,
           60.0 * SUM(CASE WHEN back_forty THEN entries END)
             / NULLIF(SUM(CASE WHEN back_forty THEN covered_minutes END), 0) AS back_forty_entries_per_covered_hour,
           60.0 * SUM(CASE WHEN NOT back_forty THEN entries END)
             / NULLIF(SUM(CASE WHEN NOT back_forty THEN covered_minutes END), 0) AS control_entries_per_covered_hour
    FROM workspace.royale.gold_walkway_traffic_week GROUP BY phase
), pre_daily AS (
    SELECT DATEDIFF(gaming_date, DATE '2025-01-01') AS day_index,
           MAX(CASE WHEN back_forty THEN coin_in_usd / machine_days END) -
           MAX(CASE WHEN NOT back_forty THEN coin_in_usd / machine_days END) AS daily_gap
    FROM workspace.royale.gold_walkway_daily
    WHERE phase = 'pre'
    GROUP BY gaming_date
), prefit AS (
    SELECT COUNT(*) AS pre_days, REGR_SLOPE(daily_gap, day_index) AS pre_slope,
           REGR_R2(daily_gap, day_index) AS pre_r2,
           REGR_SXX(daily_gap, day_index) AS pre_sxx, REGR_SYY(daily_gap, day_index) AS pre_syy
    FROM pre_daily
)
SELECT g.phase, g.back_forty_rate, g.control_rate,
       g.back_forty_rate - g.control_rate - p.back_forty_rate + p.control_rate AS did_usd_per_machine_day,
       100 * g.back_forty_rate / p.back_forty_rate AS back_forty_index,
       100 * g.control_rate / p.control_rate AS control_index,
       t.back_forty_entries_per_covered_hour, t.control_entries_per_covered_hour,
       f.pre_days, f.pre_slope,
       SQRT(GREATEST(0, (1 - f.pre_r2) * f.pre_syy) / NULLIF((f.pre_days - 2) * f.pre_sxx, 0)) AS pre_slope_se
FROM gaps g JOIN traffic t USING (phase) CROSS JOIN prefit f CROSS JOIN (SELECT * FROM gaps WHERE phase = 'pre') p;

CREATE OR REPLACE VIEW workspace.royale.gold_bottom10_mean_reversion AS
WITH halves AS (
    SELECT machine_id, gaming_date < DATE '2025-04-01' AS first_half,
           SUM(house_win_usd) / NULLIF(SUM(available_seconds) / 3600.0, 0) AS house_win_per_available_hour
    FROM workspace.royale.gold_machine_day GROUP BY machine_id, gaming_date < DATE '2025-04-01'
), ranks AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY first_half ORDER BY house_win_per_available_hour NULLS LAST, machine_id
    ) AS half_rank, COUNT(*) OVER (PARTITION BY first_half) AS half_population
    FROM halves
)
SELECT v.machine_id, v.gm_rank, v.verdict_chip, v.luck_z,
       h1.half_rank AS jan_mar_rank, h1.half_population AS jan_mar_population,
       h2.half_rank AS apr_jun_rank, h2.half_population AS apr_jun_population,
       h1.house_win_per_available_hour AS jan_mar_rate, h2.house_win_per_available_hour AS apr_jun_rate
FROM workspace.royale.gold_machine_verdict v
LEFT JOIN ranks h1 ON v.machine_id = h1.machine_id AND h1.first_half
LEFT JOIN ranks h2 ON v.machine_id = h2.machine_id AND NOT h2.first_half
WHERE v.gm_rank <= 10 OR h1.half_rank <= 10;

CREATE OR REPLACE VIEW workspace.royale.gold_fault_clusters AS
WITH faults AS (
    SELECT * FROM workspace.royale.gold_downtime_ticket WHERE event_type = 'fault_repair'
), mfr_exposure AS (
    SELECT manufacturer AS cohort, SUM(scheduled_seconds) / 3600.0 AS exposure_hours
    FROM workspace.royale.gold_machine_day GROUP BY manufacturer
), hour_exposure AS (
    SELECT CAST(gaming_hour AS STRING) AS cohort, COUNT(*) AS exposure_hours
    FROM workspace.royale.gold_machine_hour_leak GROUP BY gaming_hour
), shift_exposure AS (
    SELECT shift AS cohort,
           SUM(TIMESTAMPDIFF(SECOND, start_utc, end_utc)) / 3600.0 AS exposure_hours
    FROM workspace.royale.shift_roster WHERE role = 'slot_tech' AND zone_id IS NULL GROUP BY shift
), grouped AS (
    SELECT 'manufacturer' AS dimension, manufacturer AS cohort,
           COUNT(*) AS faults, SUM(wait_seconds) AS wait_seconds, SUM(work_seconds) AS work_seconds,
           COUNT(wait_seconds) AS wait_observations, COUNT(work_seconds) AS work_observations
    FROM faults GROUP BY manufacturer
    UNION ALL
    SELECT 'gaming_hour', CAST(gaming_hour AS STRING), COUNT(*), SUM(wait_seconds), SUM(work_seconds),
           COUNT(wait_seconds), COUNT(work_seconds)
    FROM faults GROUP BY gaming_hour
    UNION ALL
    SELECT 'technician_shift', COALESCE(technician_shift, 'unrostered'), COUNT(*), SUM(wait_seconds),
           SUM(work_seconds), COUNT(wait_seconds), COUNT(work_seconds)
    FROM faults GROUP BY COALESCE(technician_shift, 'unrostered')
), exposure AS (
    SELECT 'manufacturer' AS dimension, * FROM mfr_exposure
    UNION ALL SELECT 'gaming_hour', * FROM hour_exposure
    UNION ALL SELECT 'technician_shift', * FROM shift_exposure
)
SELECT g.*, e.exposure_hours, 1000 * g.faults / NULLIF(e.exposure_hours, 0) AS faults_per_1000_exposure_hours,
       g.wait_seconds / 3600.0 / NULLIF(g.wait_observations, 0) AS mean_wait_hours,
       g.work_seconds / 3600.0 / NULLIF(g.work_observations, 0) AS mean_work_hours
FROM grouped g LEFT JOIN exposure e USING (dimension, cohort);

CREATE OR REPLACE VIEW workspace.royale.gold_verdict_sensitivity AS
WITH z_thresholds AS (
    SELECT 2.5 AS inspection_z UNION ALL SELECT 3.0 UNION ALL SELECT 3.5
), exposure_thresholds AS (
    SELECT 45 AS min_days UNION ALL SELECT 60 UNION ALL SELECT 90
)
SELECT z.inspection_z, d.min_days,
       COUNT_IF(ABS(v.luck_z) >= z.inspection_z) AS inspections,
       COUNT_IF(ABS(v.luck_z) < z.inspection_z AND v.floor_days >= d.min_days
                AND v.ci90_upper_usd < 0 AND v.replacement_material) AS replacement_candidates,
       COUNT_IF(ABS(v.luck_z) < z.inspection_z AND v.floor_days >= d.min_days
                AND v.ci90_upper_usd < 0 AND v.replacement_material AND v.gm_rank <= 10) AS gm_bottom10_replacement_candidates
FROM workspace.royale.gold_machine_verdict v
CROSS JOIN z_thresholds z CROSS JOIN exposure_thresholds d
GROUP BY z.inspection_z, d.min_days;

CREATE OR REPLACE VIEW workspace.royale.gold_claims_evidence_core AS
SELECT 'Raw and adjusted bottom tens differ' AS claim,
       'Tribunal' AS widget, 'gold_machine_verdict / machine_verdict.sql' AS evidence,
       CONCAT(COUNT_IF(adjusted_rank <= 10 AND gm_rank <= 10), ' machines appear in both lists') AS result,
       'Availability-adjusted peer comparison and day bootstrap' AS alternative_tested,
       'Peer benchmarks are fixed to the six-month release' AS limitation
FROM workspace.royale.gold_machine_verdict
UNION ALL
SELECT 'Walkway closure coincides with weaker Back Forty exposure',
       'Floor Radar', 'gold_walkway_did / competing_explanations.sql',
       CONCAT(ROUND(did_usd_per_machine_day, 2), ' USD per installed machine-day relative to control'),
       CONCAT('Counter entries per covered sensor-hour during closure: ',
              ROUND(back_forty_entries_per_covered_hour, 2), ' Back Forty vs ',
              ROUND(control_entries_per_covered_hour, 2), ' control. See gold_walkway_traffic_week.'),
       'Descriptive comparison. Simultaneous events and control spillovers can affect it.'
FROM workspace.royale.gold_walkway_did WHERE phase = 'closure'
UNION ALL
SELECT 'Tracked play is concentrated', 'High-Roller Ladder', 'gold_concentration / gold_concentration.sql',
       CONCAT('Top ', top_percent, '% earned ', ROUND(100 * tracked_theo_share, 2), '% of tracked theo'),
       'Coin-in share and player net for the same ranked cohort',
       'Carded play only'
FROM workspace.royale.gold_concentration
UNION ALL
SELECT 'Tracked theo is the comp reinvestment denominator', 'High-Roller Ladder',
       'gold_comp_week / gold_comp_week.sql',
       CONCAT(ROUND(100 * SUM(comp_cost_usd) / SUM(tracked_theo_usd), 2), '% of tracked theo'),
       CONCAT(ROUND(100 * SUM(comp_cost_usd) / SUM(floor_theo_usd), 2), '% of floor theo'),
       'Economic redemption cost on gaming dates in the release'
FROM workspace.royale.gold_comp_week;

CREATE OR REPLACE VIEW workspace.royale.gold_gm_bottom10_bridge AS
SELECT gm_rank, machine_id, last_zone, last_bank_name, last_config_id, verdict_chip,
       weaker_than_peers_but_immaterial, potential_theo_usd, leak_usd, location_usd,
       lineup_usd, machine_specific_usd, theo_usd, luck_usd, house_win_usd,
       uplift_30d_usd, replacement_cost_30d_usd, uplift_12m_usd, replacement_cost_12m_usd, replacement_action_12m,
       net_benefit_12m_usd, net_ci90_lower_usd, net_ci90_upper_usd, payback_month, long_term_candidate
FROM workspace.royale.gold_machine_verdict WHERE gm_rank <= 10;

CREATE OR REPLACE VIEW workspace.royale.gold_adjusted_bottom10 AS
SELECT adjusted_rank, machine_id, last_zone, last_bank_name, last_config_id, manufacturer,
       floor_days, availability, banks_observed, ci90_lower_usd, ci90_upper_usd,
       verdict_chip, weaker_than_peers_but_immaterial, replacement_action_12m,
       net_benefit_12m_usd, net_ci90_lower_usd, net_ci90_upper_usd, payback_month, long_term_candidate
FROM workspace.royale.gold_machine_verdict WHERE adjusted_rank <= 10;

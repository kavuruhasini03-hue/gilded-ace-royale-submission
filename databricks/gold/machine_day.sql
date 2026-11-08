CREATE OR REPLACE TABLE workspace.royale.gold_machine_hour_leak USING DELTA AS
WITH hours AS (
    SELECT h.machine_id, h.gaming_date, h.location_id, h.hour_start_utc,
           PMOD(h.local_hour - 6, 24) AS gaming_hour,
           h.available_seconds, h.occupied_seconds
    FROM workspace.royale.machine_hour h
    WHERE h.active AND h.location_id IS NOT NULL
), profile AS (
    SELECT gaming_hour,
           SUM(occupied_seconds) / NULLIF(SUM(available_seconds), 0) AS occupancy
    FROM hours GROUP BY gaming_hour
), floor_profile AS (
    SELECT SUM(occupied_seconds) / NULLIF(SUM(available_seconds), 0) AS occupancy
    FROM hours
), weighted AS (
    SELECT h.*,
           GREATEST(0, 3600 - h.available_seconds) AS unavailable_seconds,
           COALESCE(p.occupancy / NULLIF(f.occupancy, 0), 1.0) AS weight
    FROM hours h
    JOIN profile p USING (gaming_hour)
    CROSS JOIN floor_profile f
), totals AS (
    SELECT *, SUM(unavailable_seconds) OVER (PARTITION BY machine_id, gaming_date) AS day_unavailable_seconds
    FROM weighted
)
SELECT t.machine_id, t.gaming_date, t.location_id, t.hour_start_utc, t.gaming_hour,
       t.available_seconds / 3600.0 AS available_hours,
       CASE WHEN t.day_unavailable_seconds > 0 THEN
           (m.scheduled_seconds - m.available_seconds) / 3600.0
           * t.unavailable_seconds / t.day_unavailable_seconds ELSE 0 END AS downtime_hours,
       weight
FROM totals t
JOIN workspace.royale.machine_day m USING (machine_id, gaming_date)
WHERE m.active AND m.location_id IS NOT NULL;

CREATE OR REPLACE TABLE workspace.royale.gold_machine_day USING DELTA AS
WITH base AS (
    SELECT d.*, CONCAT(d.zone_name, ' · Bank ', REGEXP_EXTRACT(d.bank_id, '[0-9]+$', 0)) AS bank_name,
           m.scheduled_seconds, m.available_seconds, m.sum_bet_squared,
           g.payout_multiplier_variance AS payout_var, f.x_m, f.y_m
    FROM workspace.royale.prepared_daily_view d
    JOIN workspace.royale.machine_day m USING (machine_id, gaming_date)
    JOIN workspace.royale.game_math g ON d.config_id = g.config_id
    JOIN workspace.royale.floor_locations f ON d.location_id=f.location_id
    WHERE d.active AND d.location_id IS NOT NULL
), machine_config AS (
    SELECT machine_id, config_id, 3600.0 * SUM(theo_usd) / SUM(available_seconds) AS theo_rate
    FROM base GROUP BY machine_id, config_id HAVING SUM(available_seconds) > 0
), floor_machines AS (
    SELECT machine_id, 3600.0 * SUM(theo_usd) / SUM(available_seconds) AS theo_rate
    FROM base GROUP BY machine_id HAVING SUM(available_seconds) > 0
), config_peer AS (
    SELECT config_id, MEDIAN(theo_rate) AS config_peer_rate FROM machine_config GROUP BY config_id
), machine_zone_config AS (
    SELECT machine_id, zone_id, config_id, 3600.0 * SUM(theo_usd) / SUM(available_seconds) AS theo_rate
    FROM base GROUP BY machine_id, zone_id, config_id HAVING SUM(available_seconds) > 0
), machine_zone AS (
    SELECT m.machine_id, m.zone_id, MEDIAN(m.theo_rate / NULLIF(c.config_peer_rate, 0)) AS ratio
    FROM machine_zone_config m JOIN config_peer c USING (config_id)
    GROUP BY m.machine_id, m.zone_id
), zones AS (
    SELECT zone_id, MEDIAN(ratio) AS zone_factor FROM machine_zone GROUP BY zone_id
), floor_peer AS (
    SELECT MEDIAN(theo_rate) AS floor_peer_rate FROM floor_machines
), best_zone AS (
    SELECT MAX(zone_factor) AS best_zone_factor FROM zones
), weighted AS (
    SELECT machine_id, gaming_date, SUM(downtime_hours * weight) AS weighted_downtime_hours
    FROM workspace.royale.gold_machine_hour_leak GROUP BY machine_id, gaming_date
), rates AS (
    SELECT b.*, c.config_peer_rate, f.floor_peer_rate,
           COALESCE(z.zone_factor, 1.0) AS zone_factor, best.best_zone_factor,
           b.scheduled_seconds / 3600.0 AS scheduled_hours,
           (b.scheduled_seconds - b.available_seconds) / 3600.0 AS downtime_hours,
           b.sum_bet_squared * b.payout_var / 10000.0 AS luck_variance_usd2,
           COALESCE(w.weighted_downtime_hours, 0) AS weighted_downtime_hours
    FROM base b
    JOIN config_peer c USING (config_id)
    LEFT JOIN zones z USING (zone_id)
    LEFT JOIN weighted w USING (machine_id, gaming_date)
    CROSS JOIN floor_peer f
    CROSS JOIN best_zone best
), components AS (
    SELECT *,
           CAST(ROUND(floor_peer_rate * available_seconds / 3600.0, 4) AS DECIMAL(22,4)) AS floor_expected_usd,
           CAST(ROUND((config_peer_rate - floor_peer_rate) * available_seconds / 3600.0, 4) AS DECIMAL(22,4)) AS lineup_usd,
           CAST(ROUND((zone_factor - 1) * config_peer_rate * available_seconds / 3600.0, 4) AS DECIMAL(22,4)) AS location_usd,
           CAST(ROUND(zone_factor * config_peer_rate * weighted_downtime_hours, 4) AS DECIMAL(22,4)) AS leak_usd,
           CAST(ROUND(GREATEST(0, best_zone_factor - zone_factor) * config_peer_rate
                      * available_seconds / 3600.0, 4) AS DECIMAL(22,4)) AS location_opportunity_usd
    FROM rates
)
SELECT *,
       CAST(floor_expected_usd + leak_usd AS DECIMAL(22,4)) AS potential_theo_usd,
       CAST(theo_usd - floor_expected_usd - lineup_usd - location_usd AS DECIMAL(22,4)) AS machine_specific_usd
FROM components;

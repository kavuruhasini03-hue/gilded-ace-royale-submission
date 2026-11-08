CREATE OR REPLACE VIEW workspace.royale.gold_zone_month_demand AS
WITH days AS (
    SELECT CAST(DATE_TRUNC('month', gaming_date) AS DATE) AS month_start, COUNT(*) AS calendar_days
    FROM workspace.royale.calendar_day GROUP BY 1
), zone_days AS (
    SELECT CAST(DATE_TRUNC('month', gaming_date) AS DATE) AS month_start, zone_id, MAX(zone_name) AS zone_name,
           COUNT(DISTINCT gaming_date) AS observed_zone_days, COUNT(*) AS machine_days,
           SUM(coin_in_usd) AS coin_in_usd, SUM(theo_usd) AS theo_usd,
           SUM(available_seconds) / 3600.0 AS available_hours, SUM(occupied_hours) AS occupied_hours,
           SUM(scheduled_seconds) / 3600.0 AS scheduled_hours, SUM(paid_spins) AS spins
    FROM workspace.royale.gold_machine_day GROUP BY 1, 2
)
SELECT z.*, d.calendar_days, coin_in_usd / d.calendar_days AS coin_in_per_day_usd,
       theo_usd / d.calendar_days AS theo_per_day_usd,
       coin_in_usd / machine_days AS coin_in_per_machine_day_usd,
       theo_usd / machine_days AS theo_per_machine_day_usd,
       scheduled_hours / machine_days AS scheduled_hours_per_machine_day,
       available_hours / NULLIF(scheduled_hours, 0) AS availability,
       occupied_hours / NULLIF(available_hours, 0) AS occupancy,
       spins / NULLIF(occupied_hours, 0) AS spins_per_occupied_hour,
       coin_in_usd / NULLIF(spins, 0) AS mean_bet_usd
FROM zone_days z JOIN days d USING (month_start);

CREATE OR REPLACE VIEW workspace.royale.gold_floor_month_demand AS
SELECT month_start, MAX(calendar_days) AS calendar_days,
       SUM(coin_in_usd) AS coin_in_usd, SUM(theo_usd) AS theo_usd,
       SUM(coin_in_usd) / MAX(calendar_days) AS coin_in_per_day_usd,
       SUM(theo_usd) / MAX(calendar_days) AS theo_per_day_usd
FROM workspace.royale.gold_zone_month_demand GROUP BY month_start;

CREATE OR REPLACE VIEW workspace.royale.gold_month_demand_bridge AS
WITH inputs AS (
    SELECT d.*, COALESCE(w.machine_days * e.did_usd_per_machine_day, 0) AS walkway_coin_in,
           COALESCE(w.machine_days * e.did_usd_per_machine_day * d.theo_usd / NULLIF(d.coin_in_usd, 0), 0) AS walkway_theo,
           EXISTS(SELECT 1 FROM workspace.royale.events a
                  WHERE d.gaming_date BETWEEN a.start_date AND a.end_date) AS event_day
    FROM workspace.royale.gold_demand_context_day d
    LEFT JOIN workspace.royale.gold_walkway_daily w
      ON w.gaming_date = d.gaming_date AND w.back_forty AND w.phase = 'closure'
    LEFT JOIN workspace.royale.gold_walkway_did e ON e.phase = w.phase
), measures AS (
    SELECT gaming_date, local_weekday, event_day, 'coin-in' AS metric,
           CAST(coin_in_usd AS DOUBLE) AS actual_usd, CAST(walkway_coin_in AS DOUBLE) AS walkway_usd
    FROM inputs
    UNION ALL
    SELECT gaming_date, local_weekday, event_day, 'theo', CAST(theo_usd AS DOUBLE), CAST(walkway_theo AS DOUBLE)
    FROM inputs
), rates AS (
    SELECT metric, local_weekday, SUM(actual_usd - walkway_usd) / COUNT(*) AS weekday_reference
    FROM measures WHERE NOT event_day GROUP BY metric, local_weekday
), components AS (
    SELECT CAST(DATE_TRUNC('month', gaming_date) AS DATE) AS month_start, m.metric,
           m.actual_usd, m.walkway_usd, r.weekday_reference,
           CASE WHEN m.event_day THEN m.actual_usd - m.walkway_usd - r.weekday_reference
                ELSE 0 END AS event_usd
    FROM measures m JOIN rates r USING (metric, local_weekday)
)
SELECT month_start, metric, COUNT(*) AS days, SUM(actual_usd) AS actual_usd,
       SUM(weekday_reference) AS calendar_weekday_usd, SUM(event_usd) AS event_usd,
       SUM(walkway_usd) AS walkway_usd,
       SUM(actual_usd - weekday_reference - event_usd - walkway_usd) AS other_usd
FROM components GROUP BY month_start, metric;

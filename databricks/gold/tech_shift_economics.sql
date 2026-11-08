CREATE OR REPLACE VIEW workspace.royale.gold_tech_shift_economics AS
WITH historical_shifts AS (
    SELECT 'Grave' AS target, gaming_date, start_utc, end_utc
    FROM workspace.royale.shift_roster WHERE role = 'slot_tech' AND shift = 'grave' AND zone_id IS NULL
    UNION ALL
    SELECT 'Saturday evening', gaming_date, start_utc, start_utc + INTERVAL 8 HOURS
    FROM (
        SELECT gaming_date, TO_UTC_TIMESTAMP(CAST(CONCAT(gaming_date, ' 18:00:00') AS TIMESTAMP),
                                              'America/Los_Angeles') AS start_utc
        FROM workspace.royale.calendar_day WHERE local_weekday = 'Sat'
    )
), opened AS (
    SELECT h.target, h.gaming_date, t.operation_id, t.opened_at_utc,
           LEAST(h.end_utc, t.work_started_at_utc) AS wait_end_utc
    FROM historical_shifts h
    JOIN workspace.royale.gold_downtime_ticket t
      ON t.opened_at_utc >= h.start_utc AND t.opened_at_utc < h.end_utc
    WHERE t.event_type = 'fault_repair' AND t.work_started_at_utc IS NOT NULL
), wait_hours AS (
    SELECT target, operation_id, opened_at_utc, wait_end_utc,
           EXPLODE(SEQUENCE(DATE_TRUNC('hour', opened_at_utc), DATE_TRUNC('hour', wait_end_utc),
                            INTERVAL 1 HOUR)) AS hour_utc
    FROM opened WHERE wait_end_utc > opened_at_utc
), priced_hours AS (
    SELECT w.target,
           TIMESTAMPDIFF(SECOND, GREATEST(w.hour_utc, w.opened_at_utc),
                        LEAST(w.hour_utc + INTERVAL 1 HOUR, w.wait_end_utc)) / 3600.0 AS waiting_hours,
           p.theo_per_available_machine_hour AS hourly_rate
    FROM wait_hours w
    JOIN workspace.royale.calendar_day c
      ON w.hour_utc >= c.gaming_day_start_utc AND w.hour_utc < c.gaming_day_end_utc
    JOIN workspace.royale.gold_forecast_tech_timing p
      ON p.local_weekday = c.local_weekday
     AND p.gaming_hour = PMOD(HOUR(FROM_UTC_TIMESTAMP(w.hour_utc, 'America/Los_Angeles')) - 6, 24)
), exposure AS (
    SELECT target, COUNT(*) AS observed_shifts FROM historical_shifts GROUP BY target
), faults AS (
    SELECT target, COUNT(*) AS faults FROM opened GROUP BY target
), recovery AS (
    SELECT target, SUM(waiting_hours) AS waiting_hours,
           SUM(waiting_hours * hourly_rate) AS waiting_theo_usd
    FROM priced_hours GROUP BY target
), calendar AS (
    SELECT h.horizon_days, h.operating_days, EXPLODE(SEQUENCE(
        DATE_ADD(DATE '2025-07-01', h.lead_days), DATE_ADD(DATE '2025-07-01', h.horizon_days-1))) AS work_day
    FROM workspace.royale.gold_action_cost h WHERE h.action_type_id='A-TECH-SHIFT'
), eligible AS (
    SELECT horizon_days, COUNT(*) AS grave_shifts, COUNT_IF(DAYOFWEEK(work_day) = 7) AS saturday_shifts
    FROM calendar GROUP BY horizon_days
)
SELECT e.target, a.horizon_days, e.observed_shifts, f.faults, f.faults / e.observed_shifts AS faults_per_shift,
       r.waiting_hours / f.faults AS reducible_wait_hours_per_fault,
       r.waiting_theo_usd / NULLIF(r.waiting_hours, 0) AS wait_weighted_theo_per_machine_hour,
       r.waiting_theo_usd / e.observed_shifts AS full_recovery_theo_per_shift,
       CASE WHEN e.target='Grave' THEN s.grave_shifts ELSE s.saturday_shifts END AS funded_shifts,
       a.cost_per_unit_usd * CEIL(a.operating_days / 30.0) AS package_cost_usd
FROM exposure e JOIN faults f USING (target) JOIN recovery r USING (target)
CROSS JOIN eligible s JOIN workspace.royale.gold_action_cost a
  ON a.action_type_id = 'A-TECH-SHIFT' AND a.horizon_days=s.horizon_days;

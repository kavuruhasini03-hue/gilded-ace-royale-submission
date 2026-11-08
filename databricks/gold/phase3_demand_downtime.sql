CREATE OR REPLACE VIEW workspace.royale.gold_demand_context_day AS
SELECT g.gaming_date, c.local_weekday, c.is_weekend, c.federal_holiday,
       g.coin_in_usd, g.theo_usd, p.events_active, e.phase AS walkway_phase,
       w.source_date AS weather_calendar_date, w.tmax_c, w.prcp_mm, w.tmax_qflag, w.prcp_qflag,
       c.month AS visitation_month, v.visitor_volume, v.visitor_yoy_ratio
FROM workspace.royale.gold_floor_day g
JOIN workspace.royale.calendar_day c USING (gaming_date)
JOIN workspace.royale.property_day p USING (gaming_date)
LEFT JOIN (SELECT DISTINCT gaming_date, phase FROM workspace.royale.gold_walkway_daily) e USING (gaming_date)
LEFT JOIN workspace.royale.weather_daily w ON w.source_date = g.gaming_date
LEFT JOIN workspace.royale.city_visitation_monthly v ON v.month = c.month;

CREATE OR REPLACE VIEW workspace.royale.gold_event_demand AS
WITH event_days AS (
    SELECT e.event_id, e.name, e.event_type, d.gaming_date, d.coin_in_usd, d.theo_usd,
           d.local_weekday, d.visitation_month
    FROM workspace.royale.events e
    JOIN workspace.royale.gold_demand_context_day d ON d.gaming_date BETWEEN e.start_date AND e.end_date
), baseline AS (
    SELECT visitation_month, local_weekday,
           SUM(coin_in_usd) / COUNT(*) AS coin_in_usd, SUM(theo_usd) / COUNT(*) AS theo_usd
    FROM workspace.royale.gold_demand_context_day d
    WHERE NOT EXISTS (
        SELECT 1 FROM workspace.royale.events e WHERE d.gaming_date BETWEEN e.start_date AND e.end_date
    )
    GROUP BY visitation_month, local_weekday
)
SELECT e.event_id, e.name, e.event_type, COUNT(*) AS event_days, COUNT(b.coin_in_usd) AS matched_days,
       SUM(CASE WHEN b.coin_in_usd IS NOT NULL THEN e.coin_in_usd END) AS matched_coin_in_usd,
       SUM(e.coin_in_usd - b.coin_in_usd) AS matched_coin_in_gap_usd,
       SUM(e.theo_usd - b.theo_usd) AS matched_theo_gap_usd
FROM event_days e LEFT JOIN baseline b USING (visitation_month, local_weekday)
GROUP BY e.event_id, e.name, e.event_type;

CREATE OR REPLACE VIEW workspace.royale.gold_downtime_exposure_day_hour AS
WITH hourly AS (
    SELECT *, SUM(downtime_hours * weight) OVER (PARTITION BY machine_id, gaming_date) AS daily_weight
    FROM workspace.royale.gold_machine_hour_leak
)
SELECT h.gaming_date, h.gaming_hour, d.zone_id, d.manufacturer,
       SUM(h.available_hours) AS available_hours, SUM(h.downtime_hours) AS downtime_hours,
       SUM(COALESCE(d.leak_usd * h.downtime_hours * h.weight / NULLIF(h.daily_weight, 0), 0)) AS lost_theo_usd
FROM hourly h JOIN workspace.royale.gold_machine_day d USING (machine_id, gaming_date)
GROUP BY h.gaming_date, h.gaming_hour, d.zone_id, d.manufacturer;

CREATE OR REPLACE VIEW workspace.royale.gold_downtime_month_hour AS
SELECT CAST(DATE_TRUNC('month', gaming_date) AS DATE) AS month_start, gaming_hour, zone_id, manufacturer,
       SUM(available_hours) AS available_hours, SUM(downtime_hours) AS downtime_hours,
       SUM(lost_theo_usd) AS lost_theo_usd
FROM workspace.royale.gold_downtime_exposure_day_hour GROUP BY 1, 2, 3, 4;

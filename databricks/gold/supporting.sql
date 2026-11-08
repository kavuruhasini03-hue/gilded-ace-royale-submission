CREATE OR REPLACE VIEW workspace.royale.gold_floor_day AS
SELECT gaming_date, COUNT(*) AS active_machines,
       SUM(coin_in_usd) AS coin_in_usd, SUM(payout_usd) AS payout_usd,
       SUM(house_win_usd) AS house_win_usd, SUM(theo_usd) AS theo_usd,
       SUM(luck_residual_usd) AS luck_usd, SUM(luck_variance_usd2) AS luck_variance_usd2,
       SUM(scheduled_seconds) AS scheduled_seconds, SUM(available_seconds) AS available_seconds,
       SUM(potential_theo_usd) AS potential_theo_usd, SUM(leak_usd) AS leak_usd,
       SUM(lineup_usd) AS lineup_usd, SUM(location_usd) AS location_usd,
       SUM(machine_specific_usd) AS machine_specific_usd,
       SUM(location_opportunity_usd) AS location_opportunity_usd
FROM workspace.royale.gold_machine_day GROUP BY gaming_date;

CREATE OR REPLACE VIEW workspace.royale.gold_kpi_header AS
SELECT g.*, p.comp_cost_usd, p.pos_cash_usd, p.pos_cogs_usd, p.events_active,
       g.theo_usd + g.leak_usd + g.location_opportunity_usd AS health_potential_usd,
       COALESCE(t.tracked_theo_usd, 0) AS tracked_theo_usd
FROM workspace.royale.gold_floor_day g
JOIN workspace.royale.property_day p USING (gaming_date)
LEFT JOIN (
    SELECT gaming_date, SUM(carded_theo_cents) / 100.00 AS tracked_theo_usd
    FROM workspace.royale.silver_session_day GROUP BY gaming_date
) t USING (gaming_date);

CREATE OR REPLACE VIEW workspace.royale.gold_zone_gaming_hour AS
WITH traffic AS (
    SELECT gaming_date, zone_id, gaming_hour,
           SUM(entries_count) AS entries, SUM(coverage_minutes) AS coverage_minutes
    FROM workspace.royale.silver_zone_traffic_hourly
    WHERE gaming_date IS NOT NULL
    GROUP BY gaming_date, zone_id, gaming_hour
), machines AS (
    SELECT h.gaming_date, d.zone_id, h.gaming_hour,
           SUM(h.available_hours) AS available_machine_hours,
           SUM(h.downtime_hours) AS downtime_hours,
           SUM(h.downtime_hours * h.weight * d.config_peer_rate * d.zone_factor) AS lost_theo_usd
    FROM workspace.royale.gold_machine_hour_leak h
    JOIN workspace.royale.gold_machine_day d USING (machine_id, gaming_date)
    GROUP BY h.gaming_date, d.zone_id, h.gaming_hour
)
SELECT * FROM traffic FULL JOIN machines USING (gaming_date, zone_id, gaming_hour);

CREATE OR REPLACE VIEW workspace.royale.gold_downtime_ticket AS
SELECT o.*, m.manufacturer, d.zone_id, r.shift AS technician_shift,
       r.actual_headcount AS slot_tech_headcount
FROM workspace.royale.silver_operations o
LEFT JOIN workspace.royale.machines m USING (machine_id)
LEFT JOIN workspace.royale.gold_machine_day d
  ON o.machine_id = d.machine_id AND o.gaming_date = d.gaming_date
LEFT JOIN workspace.royale.shift_roster r
  ON r.role = 'slot_tech' AND r.zone_id IS NULL
 AND o.opened_at_utc >= r.start_utc AND o.opened_at_utc < r.end_utc
WHERE o.gaming_date IS NOT NULL;

CREATE OR REPLACE VIEW workspace.royale.gold_player_segment_month AS
SELECT period_month, tier_end, home_region, age_band,
       COUNT(*) AS players,
       SUM(tracked_coin_in_usd) AS tracked_coin_in_usd,
       SUM(tracked_payout_usd) AS tracked_payout_usd,
       SUM(tracked_net_usd) AS tracked_net_usd,
       SUM(theo_usd) AS tracked_theo_usd,
       SUM(luck_residual_usd) AS luck_usd,
       SUM(comp_cost_usd) AS comp_cost_usd,
       SUM(tracked_contribution_usd) AS tracked_contribution_usd
FROM workspace.royale.player_period GROUP BY period_month, tier_end, home_region, age_band;

CREATE OR REPLACE VIEW workspace.royale.gold_funnel_bounds AS
SELECT machine_id, luck_sigma_usd,
       -3 * luck_sigma_usd AS lower_3sigma_usd, -2 * luck_sigma_usd AS lower_2sigma_usd,
       2 * luck_sigma_usd AS upper_2sigma_usd, 3 * luck_sigma_usd AS upper_3sigma_usd
FROM workspace.royale.gold_machine_verdict;

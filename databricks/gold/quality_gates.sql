WITH ranges AS (
    SELECT 'window' AS label, DATE '2025-01-01' AS start_day, DATE '2025-06-30' AS end_day
    UNION ALL SELECT 'closure', DATE '2025-03-03', DATE '2025-04-06'
    UNION ALL SELECT 'holdout', DATE '2025-05-01', DATE '2025-06-30'
), floor_check AS (
    SELECT r.label
    FROM ranges r
    LEFT JOIN workspace.royale.property_day p ON p.gaming_date BETWEEN r.start_day AND r.end_day
    LEFT JOIN workspace.royale.gold_floor_day g ON g.gaming_date = p.gaming_date
    GROUP BY r.label, r.start_day, r.end_day
    HAVING COUNT(g.gaming_date) <> DATEDIFF(r.end_day, r.start_day) + 1
        OR SUM(ABS(g.active_machines - p.active_machines)) <> 0
        OR SUM(g.coin_in_usd - p.coin_in_usd) <> 0
        OR SUM(g.payout_usd - p.payout_usd) <> 0
        OR SUM(g.house_win_usd - p.house_win_usd) <> 0
        OR ROUND(SUM(g.theo_usd), 2) <> ROUND(SUM(p.theo_usd), 2)
), bridge_day AS (
    SELECT gaming_date, machine_id,
           potential_theo_usd - leak_usd + location_usd + lineup_usd
             + machine_specific_usd - theo_usd AS theo_error,
           theo_usd + luck_residual_usd - house_win_usd AS win_error
    FROM workspace.royale.gold_machine_day
), bridge_ranges AS (
    SELECT r.label, b.machine_id, SUM(theo_error) AS theo_error, SUM(win_error) AS win_error
    FROM ranges r JOIN bridge_day b ON b.gaming_date BETWEEN r.start_day AND r.end_day
    GROUP BY GROUPING SETS ((r.label, b.machine_id), (r.label))
), carded_check AS (
    SELECT COALESCE(m.machine_id, s.machine_id) AS machine_id
    FROM workspace.royale.machine_day m
    FULL OUTER JOIN workspace.royale.silver_session_day s USING (machine_id, gaming_date)
    WHERE COALESCE(m.carded_coin_in_cents, 0) <> COALESCE(s.carded_coin_in_cents, 0)
       OR COALESCE(m.carded_payout_cents, 0) <> COALESCE(s.carded_payout_cents, 0)
       OR COALESCE(m.carded_spins, 0) <> COALESCE(s.carded_spins, 0)
       OR ABS(COALESCE(m.carded_theo_cents, 0) - COALESCE(s.carded_theo_cents, 0)) >= 0.5
), hourly_downtime AS (
    SELECT machine_id, gaming_date, SUM(downtime_hours) AS downtime_hours
    FROM workspace.royale.gold_machine_hour_leak GROUP BY machine_id, gaming_date
), checks AS (
    SELECT (SELECT COUNT(*) FROM floor_check) AS floor_failures,
           (SELECT COUNT(*) FROM bridge_day WHERE theo_error <> 0 OR win_error <> 0) AS day_bridge_failures,
           (SELECT COUNT(*) FROM bridge_ranges WHERE theo_error <> 0 OR win_error <> 0) AS range_bridge_failures,
           (SELECT COUNT(*) FROM carded_check) AS carded_failures,
           (SELECT COUNT(*) FROM workspace.royale.gold_machine_day d
            LEFT JOIN hourly_downtime h USING (machine_id, gaming_date)
            WHERE ABS(d.downtime_hours - COALESCE(h.downtime_hours, 0)) > 0.0001) AS hourly_downtime_failures,
           (SELECT COUNT(*) FROM workspace.royale.sessions s
            LEFT JOIN workspace.royale.calendar_day c
              ON s.gaming_date = c.gaming_date
             AND s.start_utc >= c.gaming_day_start_utc AND s.start_utc < c.gaming_day_end_utc
            WHERE c.gaming_date IS NULL) AS session_date_failures
)
SELECT *, ASSERT_TRUE(floor_failures + day_bridge_failures + range_bridge_failures + carded_failures
    + hourly_downtime_failures + session_date_failures = 0,
    'Floor, bridge, or carded reconciliation failed') AS quality_gate
FROM checks;

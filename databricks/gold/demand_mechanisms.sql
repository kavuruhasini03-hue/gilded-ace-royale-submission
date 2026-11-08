CREATE OR REPLACE VIEW workspace.royale.gold_zone_other_bridge AS
WITH zone_day AS (
    SELECT gaming_date, zone_id, MAX(zone_name) AS zone_name, COUNT(*) AS machine_days,
           SUM(coin_in_usd) AS coin, SUM(occupied_hours) AS occupied, SUM(paid_spins) AS spins
    FROM workspace.royale.gold_machine_day GROUP BY gaming_date, zone_id
), inputs AS (
    SELECT z.*, d.local_weekday,
           EXISTS(SELECT 1 FROM workspace.royale.events a
                  WHERE z.gaming_date BETWEEN a.start_date AND a.end_date) AS event_day,
           CASE WHEN z.zone_id = 'Z-B40' AND d.walkway_phase = 'closure'
                THEN CAST(z.machine_days * e.did_usd_per_machine_day AS DOUBLE) ELSE 0.0 END AS closure_coin
    FROM zone_day z JOIN workspace.royale.gold_demand_context_day d USING (gaming_date)
    CROSS JOIN (SELECT did_usd_per_machine_day FROM workspace.royale.gold_walkway_did WHERE phase = 'closure') e
), reference AS (
    SELECT zone_id, local_weekday, AVG(coin - closure_coin) AS ref_coin,
           AVG(occupied - closure_coin * occupied / NULLIF(coin, 0)) AS ref_hours,
           AVG(spins - closure_coin * spins / NULLIF(coin, 0)) AS ref_spins
    FROM inputs WHERE NOT event_day GROUP BY zone_id, local_weekday
), common AS (
    SELECT zone_id, AVG(ref_coin) AS common_coin, AVG(ref_hours) AS common_hours,
           AVG(ref_spins) AS common_spins
    FROM reference GROUP BY zone_id
), levels AS (
    SELECT z.zone_id, MAX(z.zone_name) AS zone_name,
           z.gaming_date >= DATE '2025-06-01' AS june,
           AVG(coin) AS raw_coin_per_day, AVG(occupied) AS raw_occupied_per_day,
           SUM(coin) / SUM(spins) AS raw_bet, SUM(spins) / SUM(occupied) AS raw_spins_per_hour,
           AVG(IF(event_day, 0, coin - closure_coin - ref_coin)) AS other_coin,
           AVG(IF(event_day, 0, occupied - closure_coin * occupied / NULLIF(coin, 0) - ref_hours)) AS other_hours,
           AVG(IF(event_day, 0, spins - closure_coin * spins / NULLIF(coin, 0) - ref_spins)) AS other_spins
    FROM inputs z JOIN reference r USING (zone_id, local_weekday)
    WHERE z.gaming_date < DATE '2025-02-01' OR z.gaming_date >= DATE '2025-06-01'
    GROUP BY z.zone_id, z.gaming_date >= DATE '2025-06-01'
), standardized AS (
    SELECT l.*, c.common_coin + other_coin AS coin,
           c.common_hours + other_hours AS hours,
           (c.common_coin + other_coin) / (c.common_spins + other_spins) AS bet,
           (c.common_spins + other_spins) / (c.common_hours + other_hours) AS pace
    FROM levels l JOIN common c USING (zone_id)
), paired AS (
    SELECT a.zone_id, a.zone_name, b.other_coin - a.other_coin AS other_change_usd_per_day,
           b.raw_coin_per_day - a.raw_coin_per_day AS raw_change_usd_per_day,
           a.raw_occupied_per_day AS january_raw_occupied_hours_per_day,
           b.raw_occupied_per_day AS june_raw_occupied_hours_per_day,
           a.raw_bet AS january_raw_bet, b.raw_bet AS june_raw_bet,
           a.raw_spins_per_hour AS january_raw_spins_per_hour, b.raw_spins_per_hour AS june_raw_spins_per_hour,
           CASE WHEN b.coin = a.coin THEN a.coin ELSE (b.coin - a.coin) / LOG(b.coin / a.coin) END AS log_mean,
           LOG(b.hours / a.hours) AS hours_change, LOG(b.bet / a.bet) AS bet_change,
           LOG(b.pace / a.pace) AS pace_change
    FROM standardized a JOIN standardized b USING (zone_id) WHERE NOT a.june AND b.june
)
SELECT *, log_mean * hours_change AS occupied_hours_effect_usd_per_day,
       log_mean * bet_change AS bet_effect_usd_per_day,
       log_mean * pace_change AS spins_per_hour_effect_usd_per_day
FROM paired;

CREATE OR REPLACE VIEW workspace.royale.gold_back_forty_lasting_gap AS
WITH cohorts AS (
    SELECT back_forty, IF(gaming_date < DATE '2025-02-01', 'January', 'Post-closure') AS period,
           SUM(coin_in_usd) / COUNT(*) AS coin_in_per_day_usd,
           SUM(coin_in_usd) / SUM(machine_days) AS coin_in_per_machine_day_usd
    FROM workspace.royale.gold_walkway_daily
    WHERE gaming_date < DATE '2025-02-01' OR phase = 'post'
    GROUP BY 1, 2
), deltas AS (
    SELECT back_forty, MAX(IF(period='January', coin_in_per_day_usd, NULL)) AS jan_per_day,
           MAX(IF(period='Post-closure', coin_in_per_day_usd, NULL)) AS post_per_day,
           MAX(IF(period='January', coin_in_per_machine_day_usd, NULL)) AS jan_per_machine_day,
           MAX(IF(period='Post-closure', coin_in_per_machine_day_usd, NULL)) AS post_per_machine_day
    FROM cohorts GROUP BY back_forty
)
SELECT 'Lasting gap after the closure (descriptive)' AS label, b.* EXCEPT (back_forty),
       b.post_per_day - b.jan_per_day AS lasting_gap_usd_per_day,
       b.post_per_machine_day - b.jan_per_machine_day AS lasting_gap_usd_per_machine_day,
       (b.post_per_machine_day - b.jan_per_machine_day) - (r.post_per_machine_day - r.jan_per_machine_day)
           AS gap_relative_to_rest_usd_per_machine_day
FROM deltas b CROSS JOIN deltas r WHERE b.back_forty AND NOT r.back_forty;

CREATE OR REPLACE VIEW workspace.royale.gold_high_limit_visit_day AS
WITH frozen_players AS (
    SELECT player_id, NTILE(10) OVER (ORDER BY SUM(theo_usd) DESC, player_id) AS decile
    FROM workspace.royale.player_period WHERE period_month BETWEEN '2025-01' AND '2025-04'
    GROUP BY player_id HAVING SUM(tracked_coin_in_usd) > 0
), activity AS (
    SELECT s.gaming_date, s.observed_visit_id, COALESCE(p.decile = 1, FALSE) AS top_decile,
           TIMESTAMPDIFF(SECOND, s.start_utc, s.end_utc) / 3600.0 AS duration_hours
    FROM workspace.royale.sessions s
    JOIN workspace.royale.floor_locations f USING (location_id)
    LEFT JOIN frozen_players p USING (player_id)
    WHERE f.zone_id = 'Z-HL' AND s.coin_in_cents > 0
), first_visit AS (
    SELECT observed_visit_id, MIN(gaming_date) AS gaming_date, BOOL_OR(top_decile) AS top_decile
    FROM activity WHERE observed_visit_id IS NOT NULL GROUP BY observed_visit_id
), visits AS (
    SELECT gaming_date, COUNT_IF(top_decile) AS top_visits, COUNT_IF(NOT top_decile) AS other_tracked_visits
    FROM first_visit GROUP BY gaming_date
), hours AS (
    SELECT gaming_date, SUM(IF(top_decile, duration_hours, 0)) AS top_session_hours,
           SUM(IF(NOT top_decile, duration_hours, 0)) AS other_tracked_session_hours
    FROM activity GROUP BY gaming_date
), floor AS (
    SELECT gaming_date, SUM(occupied_hours) AS total_occupied_hours,
           SUM(available_seconds)/3600.0 AS available_hours, SUM(coin_in_usd) AS coin_in_usd,
           COUNT(*) AS machine_days
    FROM workspace.royale.gold_machine_day WHERE zone_id = 'Z-HL' GROUP BY gaming_date
)
SELECT f.*, COALESCE(v.top_visits, 0) AS top_visits, COALESCE(v.other_tracked_visits, 0) AS other_tracked_visits,
       COALESCE(h.top_session_hours, 0) AS top_session_hours,
       COALESCE(h.other_tracked_session_hours, 0) AS other_tracked_session_hours
FROM floor f LEFT JOIN visits v USING (gaming_date) LEFT JOIN hours h USING (gaming_date);

CREATE OR REPLACE VIEW workspace.royale.gold_high_limit_visit_test AS
WITH blocks AS (
    SELECT IF(gaming_date < DATE '2025-05-01', 0, 1) AS phase,
           CAST(FLOOR(DATEDIFF(gaming_date, IF(gaming_date < DATE '2025-05-01',
                   DATE '2025-01-01', DATE '2025-06-01')) / 7) AS INT) AS week,
           COUNT(*) AS days, SUM(top_visits) AS visits, SUM(top_session_hours) AS top_hours,
           SUM(other_tracked_session_hours) AS other_hours, SUM(total_occupied_hours) AS occupied,
           SUM(available_hours) AS available, SUM(coin_in_usd) AS coin_in, SUM(machine_days) AS machine_days
    FROM workspace.royale.gold_high_limit_visit_day
    WHERE gaming_date < DATE '2025-05-01' OR gaming_date >= DATE '2025-06-01'
    GROUP BY 1, 2
), sizes AS (
    SELECT phase, COUNT(*) AS n FROM blocks GROUP BY phase
), samples AS (
    SELECT r.id AS replicate, s.phase, PMOD(XXHASH64(r.id, s.phase, draw, 20250102), s.n) AS week
    FROM sizes s CROSS JOIN RANGE(2000) r LATERAL VIEW EXPLODE(SEQUENCE(1L, s.n)) draws AS draw
    UNION ALL SELECT -1, phase, week FROM blocks
), rates AS (
    SELECT replicate, phase, SUM(visits) / SUM(days) AS top_visits_per_day,
           SUM(top_hours) / SUM(days) AS top_session_hours_per_day,
           SUM(other_hours) / SUM(days) AS other_tracked_hours_per_day,
           SUM(occupied) / SUM(days) AS occupied_hours_per_day,
           100 * SUM(occupied) / SUM(available) AS occupancy_pct,
           SUM(coin_in) / SUM(machine_days) AS coin_in_per_machine_day
    FROM samples s JOIN blocks b USING (phase, week) GROUP BY replicate, phase
), measures AS (
    SELECT replicate, phase, metric, value FROM rates
    UNPIVOT (value FOR metric IN (top_visits_per_day, top_session_hours_per_day,
            other_tracked_hours_per_day, occupied_hours_per_day, occupancy_pct, coin_in_per_machine_day))
), deltas AS (
    SELECT replicate, metric, MAX(IF(phase = 0, value, NULL)) AS baseline, MAX(IF(phase = 1, value, NULL)) AS june
    FROM measures GROUP BY replicate, metric
)
SELECT metric, MAX(IF(replicate = -1, baseline, NULL)) AS jan_apr, MAX(IF(replicate = -1, june, NULL)) AS june,
       MAX(IF(replicate = -1, june-baseline, NULL)) AS change_value,
       PERCENTILE(IF(replicate >= 0, june-baseline, NULL), 0.05) AS ci90_lower,
       PERCENTILE(IF(replicate >= 0, june-baseline, NULL), 0.95) AS ci90_upper
FROM deltas GROUP BY metric;

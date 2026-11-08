CREATE OR REPLACE TABLE workspace.royale.silver_operations USING DELTA AS
SELECT o.*, c.gaming_date,
       PMOD(HOUR(o.opened_at_local) - 6, 24) AS gaming_hour,
       TIMESTAMPDIFF(SECOND, o.opened_at_utc, o.work_started_at_utc) AS wait_seconds,
       TIMESTAMPDIFF(SECOND, o.work_started_at_utc, o.available_at_utc) AS work_seconds
FROM workspace.royale.operations o
LEFT JOIN workspace.royale.calendar_day c
  ON o.opened_at_utc >= c.gaming_day_start_utc
 AND o.opened_at_utc < c.gaming_day_end_utc;

CREATE OR REPLACE TABLE workspace.royale.silver_zone_traffic_hourly USING DELTA AS
SELECT t.*, c.gaming_date, PMOD(t.local_hour - 6, 24) AS gaming_hour
FROM workspace.royale.zone_traffic_hourly t
LEFT JOIN workspace.royale.calendar_day c
  ON t.hour_start_utc >= c.gaming_day_start_utc
 AND t.hour_start_utc < c.gaming_day_end_utc;

CREATE OR REPLACE TABLE workspace.royale.silver_loyalty_ledger USING DELTA AS
SELECT l.*, c.gaming_date
FROM workspace.royale.loyalty_ledger l
LEFT JOIN workspace.royale.calendar_day c
  ON l.event_at_utc >= c.gaming_day_start_utc
 AND l.event_at_utc < c.gaming_day_end_utc;

CREATE OR REPLACE TABLE workspace.royale.silver_session_start_hour USING DELTA AS
SELECT machine_id, gaming_date, DATE_TRUNC('hour', start_utc) AS hour_start_utc,
       COUNT(*) AS segment_count,
       SUM(paid_spins) AS carded_spins,
       SUM(coin_in_cents) AS carded_coin_in_cents,
       SUM(payout_cents) AS carded_payout_cents,
       SUM(theo_cents) AS carded_theo_cents,
       SUM(sum_bet_squared) AS carded_sum_bet_squared
FROM workspace.royale.sessions
GROUP BY machine_id, gaming_date, DATE_TRUNC('hour', start_utc);

CREATE OR REPLACE TABLE workspace.royale.silver_session_day USING DELTA AS
SELECT machine_id, gaming_date, SUM(segment_count) AS segment_count,
       SUM(carded_spins) AS carded_spins,
       SUM(carded_coin_in_cents) AS carded_coin_in_cents,
       SUM(carded_payout_cents) AS carded_payout_cents,
       SUM(carded_theo_cents) AS carded_theo_cents,
       SUM(carded_sum_bet_squared) AS carded_sum_bet_squared
FROM workspace.royale.silver_session_start_hour
GROUP BY machine_id, gaming_date;

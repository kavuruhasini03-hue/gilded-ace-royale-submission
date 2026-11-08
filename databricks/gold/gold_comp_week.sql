CREATE OR REPLACE VIEW workspace.royale.gold_points_redemption_value_day AS
WITH daily AS (
    SELECT c.gaming_date, COALESCE(SUM(l.points_delta), 0) AS net_points,
           COALESCE(SUM(IF(l.event_type = 'redeem', -l.points_delta, 0)), 0) AS points_redeemed,
           COALESCE(SUM(IF(l.event_type = 'redeem', l.face_value_cents, 0)), 0) AS face_cents,
           COALESCE(SUM(IF(l.event_type = 'redeem', l.economic_cost_cents, 0)), 0) AS cost_cents
    FROM workspace.royale.calendar_day c
    LEFT JOIN workspace.royale.silver_loyalty_ledger l USING (gaming_date)
    GROUP BY c.gaming_date
), rolling AS (
    SELECT gaming_date, SUM(net_points) OVER (ORDER BY gaming_date ROWS UNBOUNDED PRECEDING) AS outstanding_points,
           SUM(face_cents) OVER trailing AS face_cents_28d,
           SUM(cost_cents) OVER trailing AS cost_cents_28d,
           SUM(points_redeemed) OVER trailing AS points_redeemed_28d,
           COUNT(*) OVER trailing AS valuation_days
    FROM daily WINDOW trailing AS (ORDER BY gaming_date ROWS BETWEEN 27 PRECEDING AND CURRENT ROW)
), rates AS (
    SELECT *, face_cents_28d / 100.0 / NULLIF(points_redeemed_28d, 0) AS face_usd_per_point,
           cost_cents_28d / 100.0 / NULLIF(points_redeemed_28d, 0) AS cost_usd_per_point
    FROM rolling
)
SELECT *, outstanding_points * face_usd_per_point AS outstanding_face_usd,
       outstanding_points * cost_usd_per_point AS outstanding_economic_usd
FROM rates;

CREATE OR REPLACE VIEW workspace.royale.gold_comp_week AS
WITH calendar AS (
    SELECT *, CAST(DATE_TRUNC('week', gaming_date) AS DATE) AS week_start
    FROM workspace.royale.calendar_day
    WHERE gaming_date BETWEEN DATE '2025-01-01' AND DATE '2025-06-30'
), weeks AS (
    SELECT week_start, COUNT(*) AS gaming_days FROM calendar GROUP BY week_start
), comp AS (
    SELECT c.week_start,
           COUNT(*) AS redemptions,
           -SUM(l.points_delta) AS points_redeemed,
           SUM(l.face_value_cents) / 100.00 AS comp_face_usd,
           SUM(l.economic_cost_cents) / 100.00 AS comp_cost_usd
    FROM workspace.royale.silver_loyalty_ledger l
    JOIN calendar c
      ON l.gaming_date = c.gaming_date
    WHERE l.event_type = 'redeem'
    GROUP BY c.week_start
), tracked AS (
    SELECT c.week_start, SUM(s.carded_theo_cents) / 100.00 AS tracked_theo_usd
    FROM workspace.royale.silver_session_day s
    JOIN calendar c ON c.gaming_date = s.gaming_date
    GROUP BY c.week_start
), liability AS (
    SELECT c.week_start, MAX(c.gaming_date) AS valuation_date,
           MAX_BY(v.valuation_days, c.gaming_date) AS valuation_days,
           MAX_BY(v.outstanding_points, c.gaming_date) AS outstanding_points,
           MAX_BY(v.face_usd_per_point, c.gaming_date) AS face_usd_per_point,
           MAX_BY(v.cost_usd_per_point, c.gaming_date) AS cost_usd_per_point,
           MAX_BY(v.outstanding_face_usd, c.gaming_date) AS outstanding_face_usd,
           MAX_BY(v.outstanding_economic_usd, c.gaming_date) AS outstanding_economic_usd
    FROM calendar c JOIN workspace.royale.gold_points_redemption_value_day v USING (gaming_date)
    GROUP BY c.week_start
), floor AS (
    SELECT c.week_start, SUM(d.theo_usd) AS floor_theo_usd
    FROM workspace.royale.prepared_daily_view d
    JOIN calendar c ON c.gaming_date = d.gaming_date
    WHERE d.location_id IS NOT NULL
    GROUP BY c.week_start
)
SELECT w.week_start, w.gaming_days,
       COALESCE(c.redemptions, 0) AS redemptions,
       COALESCE(c.points_redeemed, 0) AS points_redeemed,
       COALESCE(c.comp_face_usd, 0) AS comp_face_usd,
       COALESCE(c.comp_cost_usd, 0) AS comp_cost_usd,
       c.points_redeemed / NULLIF(c.comp_face_usd, 0) AS points_per_face_usd,
       t.tracked_theo_usd, f.floor_theo_usd,
       COALESCE(c.comp_cost_usd, 0) / NULLIF(t.tracked_theo_usd, 0) AS reinvestment_tracked,
       COALESCE(c.comp_cost_usd, 0) / NULLIF(f.floor_theo_usd, 0) AS reinvestment_floor,
       l.valuation_date, l.valuation_days, l.outstanding_points, l.face_usd_per_point,
       l.cost_usd_per_point, l.outstanding_face_usd, l.outstanding_economic_usd
FROM weeks w
LEFT JOIN comp c USING (week_start)
LEFT JOIN tracked t USING (week_start)
LEFT JOIN floor f USING (week_start)
LEFT JOIN liability l USING (week_start);

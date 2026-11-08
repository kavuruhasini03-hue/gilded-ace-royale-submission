CREATE OR REPLACE VIEW workspace.royale.gold_inspect_voi AS
WITH universe AS (
    SELECT COUNT_IF(luck_z IS NOT NULL) AS tested_machines FROM workspace.royale.gold_machine_verdict
), data AS (
    SELECT machine_id, luck_z, floor_days, GREATEST(0, theo_usd-house_win_usd) / floor_days AS loss_per_day_usd,
           tested_machines, 1 / (1 + 0.2316419 * ABS(luck_z)) AS t,
           EXP(0.4 * luck_z * luck_z) / SQRT(5.0) AS bayes_factor
    FROM workspace.royale.gold_machine_verdict CROSS JOIN universe WHERE ABS(luck_z) >= 3
), adjusted AS (
    SELECT *, LEAST(1.0, tested_machines * 2 * EXP(-0.5*luck_z*luck_z) / SQRT(2*PI())
       * (0.319381530*t - 0.356563782*POW(t,2) + 1.781477937*POW(t,3)
          - 1.821255978*POW(t,4) + 1.330274429*POW(t,5))) AS bonferroni_p,
       (tested_machines-1) / (tested_machines-1+bayes_factor) AS p_luck_base
    FROM data
)
SELECT *, 0.15 * bayes_factor / (4*tested_machines-1+bayes_factor) AS p_actionable_low,
          0.40 * (1-p_luck_base) AS p_actionable_mid,
          0.65 * 2*bayes_factor / (tested_machines-2+2*bayes_factor) AS p_actionable_high
FROM adjusted;

CREATE OR REPLACE VIEW workspace.royale.gold_action_voi AS
WITH pilot_design AS (
WITH enrollment AS (
    SELECT COUNT(*) AS june_active_players FROM workspace.royale.player_period
    WHERE period_month='2025-06' AND tracked_coin_in_usd>0
), pre AS (
    SELECT player_id, CAST(theo_usd AS DOUBLE) AS pre_theo
    FROM workspace.royale.player_period WHERE period_month='2025-04' AND tracked_coin_in_usd>0
), gaming AS (
    SELECT player_id, SUM(IF(gaming_date<DATE '2025-05-31',theo_cents,0))/100.0 AS theo30,
           SUM(theo_cents)/100.0 AS theo60
    FROM workspace.royale.sessions WHERE gaming_date BETWEEN DATE '2025-05-01' AND DATE '2025-06-29'
    GROUP BY player_id
), comps AS (
    SELECT player_id, SUM(IF(gaming_date<DATE '2025-05-31',economic_cost_cents,0))/100.0 AS cost30,
           SUM(economic_cost_cents)/100.0 AS cost60
    FROM workspace.royale.silver_loyalty_ledger
    WHERE event_type='redeem' AND gaming_date BETWEEN DATE '2025-05-01' AND DATE '2025-06-29'
    GROUP BY player_id
), outcomes AS (
    SELECT pre_theo, CAST(COALESCE(theo30,0)-COALESCE(cost30,0) AS DOUBLE) AS net30,
           CAST(COALESCE(theo60,0)-COALESCE(cost60,0) AS DOUBLE) AS net60
    FROM pre LEFT JOIN gaming USING (player_id) LEFT JOIN comps USING (player_id)
), activity AS (
    SELECT COUNT(*) AS backtest_players, AVG(net30) AS mean30, AVG(net60) AS mean60,
           CORR(pre_theo,net30) AS rho30, CORR(pre_theo,net60) AS rho60,
           STDDEV_SAMP(net30) AS sd30, STDDEV_SAMP(net60) AS sd60
    FROM outcomes
), rates AS (
    SELECT SUM(points_redeemed) AS redeemed, SUM(points_awarded) AS awarded,
           SUM(points_redeemed) / SUM(outstanding_points) AS daily_redemption_hazard
    FROM workspace.royale.gold_points_liability_day WHERE gaming_date<DATE '2025-05-01'
), data AS (
    SELECT *, CAST(FLOOR(june_active_players/2) AS BIGINT) AS players_per_arm,
           DATEDIFF(DATE '2026-01-01', DATE '2025-09-04') AS remaining_reset_days
    FROM activity CROSS JOIN enrollment CROSS JOIN rates
), weekly_control AS (
    SELECT AVG(IF(relative_week>=0,carded_coin_in,NULL))
           - AVG(IF(relative_week<0,carded_coin_in,NULL)) * AVG(IF(relative_week>=0,uncarded_coin_in,NULL))
             / NULLIF(AVG(IF(relative_week<0,uncarded_coin_in,NULL)),0) AS weekly_carded_coin_in_usd
    FROM workspace.royale.gold_comp_control_week WHERE relative_week BETWEEN -4 AND 3
), inputs AS (
    SELECT d.*, e.excess_valuation_usd, w.weekly_carded_coin_in_usd,
           SUM(f.theo_usd)/SUM(f.coin_in_usd) AS floor_theo_hold
    FROM data d CROSS JOIN workspace.royale.gold_points_liability_bridge e
    CROSS JOIN weekly_control w CROSS JOIN workspace.royale.gold_floor_day f
    WHERE e.valuation='economic'
    GROUP BY ALL
)
SELECT *, (1.959964+0.841621)*sd30*SQRT(1-rho30*rho30)
           *SQRT(1.0/players_per_arm+1.0/(june_active_players-players_per_arm)) AS mde30_usd,
       (1.959964+0.841621)*sd60*SQRT(1-rho60*rho60)
           *SQRT(1.0/players_per_arm+1.0/(june_active_players-players_per_arm)) AS mde60_usd,
       redeemed/awarded AS historical_redeemed_share,
       1-EXP(-daily_redemption_hazard*remaining_reset_days) AS redeem_before_reset,
       excess_valuation_usd*(1-EXP(-daily_redemption_hazard*remaining_reset_days)) AS breakage_adjusted_exposure_usd,
       weekly_carded_coin_in_usd*floor_theo_hold*remaining_reset_days/7 AS projected_theo_at_risk_usd
FROM inputs
), cases AS (
    SELECT 'A-INSPECT' AS action_type_id, i.machine_id AS target_id, a.horizon_days,
           i.p_actionable_low AS p_low, i.p_actionable_mid AS p_mid, i.p_actionable_high AS p_high,
           i.loss_per_day_usd*a.operating_days AS value_low_usd,
           i.loss_per_day_usd*a.operating_days AS value_mid_usd,
           i.loss_per_day_usd*a.operating_days AS value_high_usd,
           DATE '2025-07-02' AS measurement_date
    FROM workspace.royale.gold_inspect_voi i CROSS JOIN workspace.royale.gold_action_cost a
    WHERE a.action_type_id='A-INSPECT' AND i.bonferroni_p<0.05 AND i.loss_per_day_usd>0
    UNION ALL
    SELECT 'A-COMP-PILOT','A-COMP-PILOT',a.horizon_days,0.10,0.30,0.50,
           0.10*GREATEST(0,d.excess_valuation_usd*(1-EXP(-0.70*d.daily_redemption_hazard*d.remaining_reset_days))
                              - d.projected_theo_at_risk_usd),
           0.35*GREATEST(0,d.breakage_adjusted_exposure_usd-d.projected_theo_at_risk_usd),
           0.60*GREATEST(0,d.excess_valuation_usd*(1-EXP(-1.30*d.daily_redemption_hazard*d.remaining_reset_days))
                              - d.projected_theo_at_risk_usd),
           DATE '2025-09-04'
    FROM pilot_design d CROSS JOIN workspace.royale.gold_action_cost a
    WHERE a.action_type_id='A-COMP-PILOT'
    UNION ALL
    SELECT 'A-SURVEY','A-SURVEY',a.horizon_days,0.10,0.20,0.40,
           p.cost_per_unit_usd,p.cost_per_unit_usd,p.cost_per_unit_usd,DATE '2025-08-07'
    FROM workspace.royale.gold_action_cost a
    JOIN workspace.royale.gold_action_cost p ON p.action_type_id='A-PROMO' AND p.horizon_days=a.horizon_days
    WHERE a.action_type_id='A-SURVEY'
)
SELECT c.*, a.cost_per_unit_usd AS cash_cost_usd, p_low*value_low_usd AS low_voi_usd,
       p_mid*value_mid_usd AS mid_voi_usd, p_high*value_high_usd AS high_voi_usd,
       p_mid*value_mid_usd-a.cost_per_unit_usd AS expected_voi_net_usd,
       CASE WHEN c.action_type_id='A-COMP-PILOT' THEN
           (SELECT mde60_usd/NULLIF(mean60,0)<=0.025 FROM pilot_design)
           ELSE TRUE END AS power_eligible
FROM cases c JOIN workspace.royale.gold_action_cost a USING (action_type_id,horizon_days);

CREATE OR REPLACE TABLE workspace.royale.gold_action_voi_scored USING DELTA AS
SELECT * FROM workspace.royale.gold_action_voi;

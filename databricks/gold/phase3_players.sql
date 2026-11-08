CREATE OR REPLACE VIEW workspace.royale.gold_player_outcome_window AS
SELECT player_id, SUM(tracked_coin_in_usd) AS coin_in_usd, SUM(tracked_payout_usd) AS payout_usd,
       SUM(tracked_net_usd) AS player_net_usd, SUM(theo_usd) AS theo_usd, SUM(luck_residual_usd) AS player_luck_usd,
       SUM(comp_cost_usd) AS comp_cost_usd, SUM(tracked_contribution_usd) AS contribution_usd,
       NTILE(10) OVER (ORDER BY SUM(theo_usd) DESC, player_id) AS theo_decile
FROM workspace.royale.player_period
WHERE period_month BETWEEN '2025-01' AND '2025-06'
GROUP BY player_id;

CREATE OR REPLACE VIEW workspace.royale.gold_player_decile_month AS
SELECT p.period_month, p.tier_end, p.home_region, p.age_band, o.theo_decile,
       COUNT(*) AS player_months, SUM(p.tracked_coin_in_usd) AS coin_in_usd,
       SUM(p.tracked_payout_usd) AS payout_usd, SUM(p.tracked_net_usd) AS player_net_usd,
       SUM(p.theo_usd) AS theo_usd, SUM(p.luck_residual_usd) AS player_luck_usd,
       SUM(p.comp_cost_usd) AS comp_cost_usd, SUM(p.tracked_contribution_usd) AS contribution_usd
FROM workspace.royale.player_period p
JOIN workspace.royale.gold_player_outcome_window o USING (player_id)
WHERE p.period_month BETWEEN '2025-01' AND '2025-06'
GROUP BY p.period_month, p.tier_end, p.home_region, p.age_band, o.theo_decile;

CREATE OR REPLACE VIEW workspace.royale.gold_player_net_histogram AS
WITH outcomes AS (
    SELECT period_month AS period, tracked_net_usd AS net_usd, tracked_coin_in_usd AS coin_in_usd FROM workspace.royale.player_period
    UNION ALL
    SELECT 'Jan–Jun' AS period, player_net_usd AS net_usd, coin_in_usd FROM workspace.royale.gold_player_outcome_window
), bins AS (
    SELECT *,
           CASE WHEN coin_in_usd = 0 THEN 0 WHEN net_usd < -1000 THEN 1 WHEN net_usd < -100 THEN 2 WHEN net_usd < 0 THEN 3
                WHEN net_usd = 0 THEN 4 WHEN net_usd <= 100 THEN 5 WHEN net_usd <= 1000 THEN 6 ELSE 7 END AS bin_id
    FROM outcomes
)
SELECT period, bin_id, COUNT(*) AS observations, SUM(net_usd) AS player_net_usd
FROM bins GROUP BY period, bin_id;

CREATE OR REPLACE VIEW workspace.royale.gold_player_outcome_split AS
WITH labeled AS (
    SELECT player_net_usd,
           CASE WHEN coin_in_usd = 0 THEN 'No tracked gaming'
                WHEN player_net_usd = 0 THEN 'Exactly zero'
                WHEN player_net_usd > 0 THEN 'Winner' ELSE 'Loser' END AS outcome
    FROM workspace.royale.gold_player_outcome_window
)
SELECT outcome, COUNT(*) AS players, SUM(player_net_usd) AS player_net_usd
FROM labeled GROUP BY outcome;

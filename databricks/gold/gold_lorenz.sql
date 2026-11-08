CREATE OR REPLACE VIEW workspace.royale.gold_lorenz AS
WITH player_totals AS (
    SELECT player_id,
           SUM(theo_usd) AS tracked_theo_usd,
           SUM(tracked_coin_in_usd) AS tracked_coin_in_usd,
           SUM(tracked_net_usd) AS tracked_net_usd
    FROM workspace.royale.player_period
    WHERE period_month BETWEEN '2025-01' AND '2025-06'
    GROUP BY player_id
), ranked AS (
    SELECT *,
           ROW_NUMBER() OVER (ORDER BY tracked_theo_usd DESC, player_id) AS player_rank,
           COUNT(*) OVER () AS player_count,
           SUM(tracked_theo_usd) OVER () AS total_theo_usd,
           SUM(tracked_coin_in_usd) OVER () AS total_coin_in_usd
    FROM player_totals
), cumulative AS (
    SELECT player_rank, player_count, total_theo_usd, total_coin_in_usd,
           SUM(tracked_theo_usd) OVER ranked_rows AS cumulative_theo_usd,
           SUM(tracked_coin_in_usd) OVER ranked_rows AS cumulative_coin_in_usd,
           SUM(tracked_net_usd) OVER ranked_rows AS cumulative_player_net_usd
    FROM ranked
    WINDOW ranked_rows AS (ORDER BY player_rank ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
)
SELECT *,
       CAST(player_rank AS DOUBLE) / player_count AS cumulative_player_share,
       cumulative_theo_usd / NULLIF(total_theo_usd, 0) AS cumulative_theo_share,
       cumulative_coin_in_usd / NULLIF(total_coin_in_usd, 0) AS cumulative_coin_in_share
FROM cumulative;

CREATE OR REPLACE VIEW workspace.royale.gold_concentration AS
WITH cutoffs AS (
    SELECT 1 AS top_percent
    UNION ALL
    SELECT 10
), selected_ranks AS (
    SELECT top_percent, MAX(player_rank) AS player_rank
    FROM cutoffs
    CROSS JOIN workspace.royale.gold_lorenz
    WHERE player_rank * 100 <= player_count * top_percent
    GROUP BY top_percent
)
SELECT top_percent, player_rank AS group_players, player_count,
       cumulative_player_share AS player_share,
       cumulative_theo_usd AS tracked_theo_usd,
       cumulative_theo_share AS tracked_theo_share,
       cumulative_coin_in_usd AS tracked_coin_in_usd,
       cumulative_coin_in_share AS tracked_coin_in_share,
       cumulative_player_net_usd AS tracked_player_net_usd
FROM selected_ranks
JOIN workspace.royale.gold_lorenz USING (player_rank);

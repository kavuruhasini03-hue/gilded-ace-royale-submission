WITH funded AS (
    SELECT * FROM workspace.royale.gold_action_plan WHERE selected AND horizon_days=30 AND action_type_id <> 'A-HOLD'
), funded_quantities AS (
    SELECT action_type_id, SUM(quantity) AS quantity, MAX(quantity_limit) AS quantity_limit
    FROM funded GROUP BY action_type_id
), machine_targets AS (
    SELECT target_id AS machine_id FROM funded
    WHERE incompatibility_group='same_machine' AND action_type_id <> 'A-MOVE-BANK' AND target_id <> 'GM-BOTTOM-10'
    UNION ALL
    SELECT v.machine_id FROM funded a JOIN workspace.royale.gold_machine_verdict v ON a.target_id=v.last_bank_id
    WHERE a.action_type_id='A-MOVE-BANK'
    UNION ALL
    SELECT v.machine_id FROM funded a CROSS JOIN workspace.royale.gold_machine_verdict v
    WHERE a.target_id='GM-BOTTOM-10' AND v.gm_rank<=10
), checks AS (
    SELECT (SELECT kept_usd >= 0 AND funded_action_types <= 3 FROM workspace.royale.gold_cage_slip) AS budget_ok,
           NOT EXISTS(SELECT 1 FROM funded_quantities WHERE quantity > quantity_limit OR quantity < 1) AS limits_ok,
           (SELECT COUNT(DISTINCT action_type_id) FROM funded WHERE incompatibility_group='comp_policy') <= 1
               AS comp_policy_ok,
           NOT EXISTS(SELECT machine_id FROM machine_targets GROUP BY machine_id HAVING COUNT(*)>1) AS machines_ok,
           (SELECT COUNT(*) FROM workspace.royale.gold_action_cost
            WHERE action_type_id='A-REPLACE-LEASE' AND horizon_days=30 AND operating_days=16 AND cost_per_unit_usd=3380)=1
               AS lease_ok,
           (SELECT COUNT(DISTINCT action_type_id) FROM workspace.royale.gold_action_plan WHERE horizon_days=30)=
               (SELECT COUNT(*) FROM workspace.royale.action_catalog) AS catalog_coverage_ok,
           NOT EXISTS(SELECT 1 FROM workspace.royale.gold_action_plan
                      WHERE operating_days <= 0 AND mid_uplift_usd <> 0) AS lead_time_ok,
           NOT EXISTS(SELECT 1 FROM workspace.royale.gold_action_plan p JOIN workspace.royale.gold_action_cost a
                      USING (action_type_id, horizon_days) WHERE p.horizon_days=30
                      AND ABS(p.cash_cost_usd - p.quantity * a.cost_per_unit_usd) > 0.01) AS july_formula_ok
)
SELECT *, ASSERT_TRUE(budget_ok AND limits_ok AND comp_policy_ok AND machines_ok AND lease_ok
    AND catalog_coverage_ok AND lead_time_ok AND july_formula_ok, 'Action plan constraints failed') AS quality_gate
FROM checks;

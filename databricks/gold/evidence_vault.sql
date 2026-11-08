CREATE OR REPLACE VIEW workspace.royale.gold_claims_evidence AS
SELECT * FROM workspace.royale.gold_claims_evidence_core
UNION ALL
SELECT 'Outstanding points reprice after May 1', 'Evidence Vault',
       'gold_points_liability_bridge / comp_control.sql',
       CONCAT(valuation, ' value moved from USD ', ROUND(apr30_usd, 2), ' to USD ', ROUND(may28_usd, 2),
              '. Excess over normal accrual: USD ', ROUND(excess_valuation_usd, 2)),
       'Counterfactual repeats the previous 28-day point accrual at the April 30 realized redemption rate',
       'Values at observed redemption mix and full use, before breakage or timing. They are not accounting liabilities.'
FROM workspace.royale.gold_points_liability_bridge
UNION ALL
SELECT 'Carded play relative to uncarded after May 1', 'High-Roller Ladder',
       'gold_comp_control_effect / comp_control.sql',
       CONCAT(metric, ': ', ROUND(estimate, 4), ' (90% interval ', ROUND(ci90_lower, 4), ' to ', ROUND(ci90_upper, 4), ')'),
       'Uncarded exposure control, weekly blocks, and pre-trend test in gold_comp_control_pretrend',
       'Card use and customer mix can shift. This comparison cannot create an uncarded per-player outcome.'
FROM workspace.royale.gold_comp_control_effect
UNION ALL
SELECT label, 'Floor Radar', 'gold_back_forty_lasting_gap / demand_mechanisms.sql',
       CONCAT(ROUND(lasting_gap_usd_per_machine_day, 2), ' USD per machine-day vs January'),
       'Post-closure vs January, with a separate rest-of-floor contrast',
       'Descriptive persistence, potentially affected by seasonality or other changes.'
FROM workspace.royale.gold_back_forty_lasting_gap
UNION ALL
SELECT 'Technician coverage must cover package cost', 'Cashier’s Cage',
       'gold_tech_shift_economics / tech_shift_economics.sql',
       CONCAT(target, ' at ', horizon_days, ' days: USD ', ROUND(full_recovery_theo_per_shift * funded_shifts, 2),
              ' even at full recovery vs USD ', ROUND(package_cost_usd, 2), ' package cost'),
       'Compare actual waiting hours priced by model profile for grave and Saturday evening',
       'Full wait removal is an upper-bound scenario for the modeled tickets, before operational constraints.'
FROM workspace.royale.gold_tech_shift_economics
UNION ALL
SELECT 'Fund positive July information value and preserve the rest', 'Cashier’s Cage',
       'gold_action_plan / action_plan.sql',
       CONCAT('USD ', ROUND(kept_usd, 2), ' retained'),
       'Catalogue-wide comparison, uncertainty scenarios and ±30% downtime-value sensitivity',
       'Information values are scenario assumptions. A-HOLD remains the zero-value comparison.'
FROM workspace.royale.gold_cage_slip
UNION ALL
SELECT CONCAT(action_type_id, ' · ', target_label), 'Cashier’s Cage',
       CONCAT(evidence_view, ' / action_plan.sql'),
       CONCAT('July base net USD ', ROUND(expected_net_usd, 2), ', range USD ',
              ROUND(low_net_usd, 2), ' to ', ROUND(high_net_usd, 2)),
       success_rule, assumption
FROM workspace.royale.gold_action_plan
WHERE horizon_days = 30 AND action_type_id <> 'A-HOLD';

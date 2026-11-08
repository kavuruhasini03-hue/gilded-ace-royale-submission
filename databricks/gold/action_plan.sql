CREATE OR REPLACE VIEW workspace.royale.gold_action_plan AS
WITH quiet AS (
    SELECT PERCENTILE(theo_per_available_machine_hour, 0.10) AS quiet_theo_per_hour
    FROM workspace.royale.gold_forecast_tech_timing
), verdict AS (
    SELECT * FROM workspace.royale.gold_machine_verdict
), bank AS (
    SELECT COUNT(*) AS machines, GREATEST(0, -SUM(machine_specific_usd)) AS shortfall
    FROM verdict WHERE last_bank_name = 'Hotel Corridor · Bank 40'
), maintenance AS (
    SELECT COUNT(DISTINCT machine_id) AS machines, SUM(leak_usd) AS leak_usd
    FROM workspace.royale.gold_machine_day WHERE manufacturer = 'Ridgeline'
), period AS (
    SELECT COUNT(*) AS observed_days FROM workspace.royale.calendar_day
), wayfinding AS (
    SELECT GREATEST(0, -MAX(g.lasting_gap_usd_per_day)) * SUM(d.theo_usd) / SUM(d.coin_in_usd) AS daily_theo_gap
    FROM workspace.royale.gold_back_forty_lasting_gap g
    CROSS JOIN workspace.royale.gold_machine_day d WHERE d.zone_id = 'Z-B40'
), promotion AS (
    SELECT GREATEST(0, MAX(matched_theo_gap_usd)) AS observed_theo_gap
    FROM workspace.royale.gold_event_demand WHERE event_type = 'property_promotion'
), moves AS (
    SELECT a.action_type_id, 'M-1184' AS target_id, 'M-1184 to Center Pit · Bank 07 (L-07-3)' AS target_label,
           a.horizon_days, 1 AS quantity, a.cost_per_unit_usd AS cash_cost_usd,
           a.downtime_minutes / 60.0 * q.quiet_theo_per_hour AS disruption_theo_usd,
           0 AS low_uplift_usd, 0.25 * GREATEST(0, -v.location_usd) * a.operating_days / p.observed_days AS mid_uplift_usd,
           0.50 * GREATEST(0, -v.location_usd) * a.operating_days / p.observed_days AS high_uplift_usd,
           'Recapture 0% / 25% / 50% of the location gap. Slot L-07-3 was vacant in the July 3 placement records. Center Pit had 168.7 entries per covered hour versus 22.8 in Back Forty. Three machines with the same settings are within 16 metres.' AS assumption,
           'Compare expected win per available hour over 28 days with same-setting peers in Center Pit. Use the machine’s own pre-move rate as context. Back Forty is exposed to signage, so it is not a control. At the end of August, keep the machine and reassess Bank 40 if it reaches its new peers. Review replacement if a clear gap persists. Keep measuring if the result is inconclusive.' AS success_rule
    FROM workspace.royale.gold_action_cost a CROSS JOIN quiet q CROSS JOIN period p CROSS JOIN verdict v
    WHERE a.action_type_id='A-MOVE-MACHINE' AND v.machine_id='M-1184'
    UNION ALL
    SELECT a.action_type_id, 'B-40', 'Hotel Corridor · Bank 40', a.horizon_days, 1, a.cost_per_unit_usd,
           a.downtime_minutes / 60.0 * q.quiet_theo_per_hour * b.machines,
           0, 0.25 * b.shortfall * a.operating_days / p.observed_days,
           0.50 * b.shortfall * a.operating_days / p.observed_days,
           'Scenario recovers 0% / 25% / 50% of net bank machine-specific shortfall. The bank cluster is descriptive.',
           'Preselect a comparable bank and receiving site. Advance only if net combined theo improves after displacement.'
    FROM workspace.royale.gold_action_cost a CROSS JOIN quiet q CROSS JOIN period p CROSS JOIN bank b
    WHERE a.action_type_id='A-MOVE-BANK'
), replacement_targets AS (
    SELECT machine_id AS target_id, CONCAT(machine_id, ' · ', last_bank_name) AS target_label,
           1 AS quantity, uplift_per_day, uplift_per_day_lower, uplift_per_day_upper
    FROM verdict WHERE long_term_candidate
    UNION ALL
    SELECT 'GM-BOTTOM-10', 'GM bottom ten', COUNT(*), SUM(uplift_per_day),
           SUM(uplift_per_day_lower), SUM(uplift_per_day_upper)
    FROM verdict WHERE gm_rank<=10
), replacements AS (
    SELECT a.action_type_id, v.target_id, v.target_label, a.horizon_days, v.quantity,
           v.quantity * a.cost_per_unit_usd, v.quantity * a.downtime_minutes / 60.0 * q.quiet_theo_per_hour,
           a.operating_days * v.uplift_per_day_lower, a.operating_days * v.uplift_per_day,
           a.operating_days * v.uplift_per_day_upper,
           'Full peer gap after catalog lead. Individual range is the 90% interval. The GM basket uses summed endpoints as scenarios.',
           'Verify slot-adjusted theo lift against the installed unit and track realized lease or purchase payback.'
    FROM workspace.royale.gold_action_cost a CROSS JOIN replacement_targets v CROSS JOIN quiet q
    WHERE a.action_type_id IN ('A-REPLACE-LEASE','A-REPLACE-BUY')
), staffing AS (
    SELECT 'A-TECH-SHIFT', t.target, t.target, t.horizon_days, 1, t.package_cost_usd, 0,
           0.25*t.full_recovery_theo_per_shift*t.funded_shifts, 0.50*t.full_recovery_theo_per_shift*t.funded_shifts,
           0.75*t.full_recovery_theo_per_shift*t.funded_shifts,
           'Recover 25% / 50% / 75% of wait within shift hours, priced at the affected machine hourly theo. Saturday-only uses full packages.',
           'Measure reduced wait by staffed hour and renew only if recovered theo covers package cost.'
    FROM workspace.royale.gold_tech_shift_economics t
), operational AS (
    SELECT a.action_type_id, 'Ridgeline', 'Ridgeline', a.horizon_days, 1, a.cost_per_unit_usd,
           a.downtime_minutes / 60.0 * q.quiet_theo_per_hour * m.machines,
           0, 0.20 * m.leak_usd * LEAST(a.operating_days, 90) / p.observed_days,
           0.35 * m.leak_usd * LEAST(a.operating_days, 90) / p.observed_days,
           'One sweep with up to 90 days of effect. Recovers 0% / 20% / 35% of all observed Ridgeline leak, an optimistic addressable base.',
           'Compare fault hours per 1,000 scheduled hours with other manufacturers and deduct installation downtime.'
    FROM workspace.royale.gold_action_cost a CROSS JOIN quiet q CROSS JOIN maintenance m CROSS JOIN period p
    WHERE a.action_type_id='A-PREVENTIVE'
    UNION ALL
    SELECT a.action_type_id, 'Z-B40', 'Back Forty', a.horizon_days, 1, a.cost_per_unit_usd, 0,
           0, 0.25*w.daily_theo_gap*a.operating_days, 0.50*w.daily_theo_gap*a.operating_days,
           'Recover 0% / 25% / 50% of descriptive post-closure gap. Annual case assumes the gap and effect persist.',
           'Compare July 11 through July 30 with the 20 gaming days before installation, using the rest of the floor as a control. Compare entries per covered sensor-hour and expected win per installed machine-day. At the end of August, keep and extend if both measures close at least 25% of their pre-test gap versus the rest of the floor. Otherwise revisit the bank-move test.'
    FROM workspace.royale.gold_action_cost a CROSS JOIN wayfinding w WHERE a.action_type_id='A-WAYFINDING'
    UNION ALL
    SELECT a.action_type_id, 'M-1158', 'M-1158 · payout check', a.horizon_days, 1, a.cost_per_unit_usd,
           a.downtime_minutes / 60.0 * q.quiet_theo_per_hour, 0, 0, 0,
           'Use multiplicity-adjusted anomaly screen and scenario probability of a real, fixable finding. Credit the observed deficit only after the lead.',
           'July 2: check meters and paytable independently. Correct only a verified discrepancy and monitor subsequent payouts.'
    FROM workspace.royale.gold_action_cost a CROSS JOIN quiet q WHERE a.action_type_id='A-INSPECT'
), unproven AS (
    SELECT a.action_type_id, a.action_type_id, a.name, a.horizon_days, 1, a.cost_per_unit_usd, 0, 0, 0,
           IF(a.action_type_id='A-PROMO', 0.25 * p.observed_theo_gap, 0),
           CASE a.action_type_id
             WHEN 'A-COMP-PILOT' THEN 'Randomize 1:1: current schedule near 5.85 vs restored schedule near 12.5 points per face dollar. Use all June-active tracked players, CUPED and a 60-day run with a day-30 safety look. No arm targets heavy losers.'
             WHEN 'A-COMP-CHANGE' THEN 'Historical control does not identify a reliable per-player lift or policy-specific savings.'
             WHEN 'A-PROMO' THEN 'Single event. Zero base credit. Upside scenario credits 25% of the best matched property promotion gap.'
             WHEN 'A-SURVEY' THEN 'Survey former and continuing High-Limit top-decile guests. Estimate whether evidence avoids an unnecessary $15,000 promotion.'
             ELSE 'No incremental cost or benefit.' END,
           CASE a.action_type_id
             WHEN 'A-COMP-PILOT' THEN 'September 4 if funded: assess 60-day intent-to-treat theo less comp cost with CUPED. Fund only if planning MDE is at most 2.5%.'
             WHEN 'A-COMP-CHANGE' THEN 'Require controlled evidence of incremental contribution after comp costs before rollout.'
             WHEN 'A-PROMO' THEN 'Compare incremental theo net of direct and comp costs against matched non-event dates.'
             WHEN 'A-SURVEY' THEN 'August 7: use actionable access or experience evidence to decide whether to cancel a High-Limit promotion.'
             ELSE 'Retain the budget and revisit when evidence supports spending.' END
    FROM workspace.royale.gold_action_cost a CROSS JOIN promotion p
    WHERE a.action_type_id IN ('A-COMP-PILOT','A-COMP-CHANGE','A-PROMO','A-SURVEY','A-HOLD')
), cases AS (
    SELECT * FROM moves UNION ALL SELECT * FROM replacements UNION ALL SELECT * FROM staffing
    UNION ALL SELECT * FROM operational UNION ALL SELECT * FROM unproven
)
SELECT c.*, a.name AS action_name, a.lead_days, a.operating_days, a.downtime_minutes,
       a.quantity_limit, a.incompatibility_group,
       (COALESCE(v.power_eligible AND v.expected_voi_net_usd-c.disruption_theo_usd>0,FALSE)
        OR (c.action_type_id='A-WAYFINDING' AND c.target_id='Z-B40' AND c.horizon_days=30)
        OR (c.action_type_id='A-MOVE-MACHINE' AND c.target_id='M-1184' AND c.horizon_days=30
            AND EXISTS (SELECT 1 FROM workspace.royale.floor_locations
                        WHERE location_id='L-07-3' AND node_type='slot' AND capacity=1)
            AND NOT EXISTS (SELECT 1 FROM workspace.royale.placements
                            WHERE location_id='L-07-3'
                              AND effective_from_utc <= TIMESTAMP '2025-07-03 13:00:00'
                              AND (effective_to_utc IS NULL OR effective_to_utc > TIMESTAMP '2025-07-03 13:00:00'))))
         AS selected,
       v.p_low, v.p_mid, v.p_high, v.value_mid_usd AS value_if_real_usd,
       CASE WHEN (c.action_type_id='A-MOVE-MACHINE' AND c.target_id='M-1184') OR c.action_type_id='A-WAYFINDING'
            THEN DATE '2025-08-31' ELSE v.measurement_date END AS measurement_date,
       CASE c.action_type_id
         WHEN 'A-TECH-SHIFT' THEN 'gold_tech_shift_economics'
         WHEN 'A-MOVE-BANK' THEN 'gold_adjusted_bottom10'
         WHEN 'A-MOVE-MACHINE' THEN 'gold_machine_verdict'
         WHEN 'A-REPLACE-LEASE' THEN 'gold_machine_verdict'
         WHEN 'A-REPLACE-BUY' THEN 'gold_machine_verdict'
         WHEN 'A-PREVENTIVE' THEN 'gold_fault_clusters'
         WHEN 'A-INSPECT' THEN 'gold_inspect_voi'
         WHEN 'A-WAYFINDING' THEN 'gold_back_forty_lasting_gap'
         WHEN 'A-COMP-PILOT' THEN 'gold_action_voi_scored'
         WHEN 'A-COMP-CHANGE' THEN 'gold_comp_control_effect'
         WHEN 'A-PROMO' THEN 'gold_event_demand'
         ELSE 'gold_action_plan'
       END AS evidence_view,
       COALESCE(v.low_voi_usd,low_uplift_usd) - c.cash_cost_usd - disruption_theo_usd AS low_net_usd,
       COALESCE(v.mid_voi_usd,mid_uplift_usd) - c.cash_cost_usd - disruption_theo_usd AS expected_net_usd,
       COALESCE(v.high_voi_usd,high_uplift_usd) - c.cash_cost_usd - disruption_theo_usd AS high_net_usd,
       CASE WHEN c.action_type_id IN ('A-TECH-SHIFT','A-PREVENTIVE') THEN 0.70 * mid_uplift_usd
            ELSE COALESCE(v.mid_voi_usd,mid_uplift_usd) END - c.cash_cost_usd - disruption_theo_usd AS net_lost_theo_minus_30_pct_usd,
       CASE WHEN c.action_type_id IN ('A-TECH-SHIFT','A-PREVENTIVE') THEN 1.30 * mid_uplift_usd
            ELSE COALESCE(v.mid_voi_usd,mid_uplift_usd) END - c.cash_cost_usd - disruption_theo_usd AS net_lost_theo_plus_30_pct_usd
FROM cases c JOIN workspace.royale.gold_action_cost a USING (action_type_id, horizon_days)
LEFT JOIN workspace.royale.gold_action_voi_scored v USING (action_type_id, target_id, horizon_days);

CREATE OR REPLACE VIEW workspace.royale.gold_cage_slip AS
SELECT COALESCE(SUM(cash_cost_usd), 0) AS spent_usd, 100000 - COALESCE(SUM(cash_cost_usd), 0) AS kept_usd,
       COUNT(DISTINCT IF(action_type_id <> 'A-HOLD', action_type_id, NULL)) AS funded_action_types
FROM workspace.royale.gold_action_plan WHERE selected AND horizon_days=30;

# Budget and forecast review

## Audit completed before implementation

The public site is vanilla HTML, CSS, JavaScript and inline SVG on Vercel. It builds with `twin/build.py` and reads same-origin `gold.json`. The July plan is the `#/plan` route in `twin/app.js`. Before this review, the repository and the only forecast-named MLflow experiment contained no fitted drift or level variant. The finished runs were the constant baseline and the weekday ridge.

The published Lakeview endpoint returned warehouse and revision metadata only. The current serialized definition was updated 0.569 seconds before that published revision. I ran all five dataset queries and all eight data-backed widget queries on the published warehouse. I compared their rows with the matching Gold projections, and ran `DESCRIBE QUERY` to verify types. No fields failed. The two staffing datasets compare to the dedicated staffing Gold view and the staffing subset of the action plan, respectively.

| Widget | Dataset | Rows | Types |
| --- | --- | ---: | --- |
| `cage-intro` | Introductory text | | No query |
| `spent` | `cage` | 1 | value: decimal(38,6) |
| `kept` | `cage` | 1 | value: decimal(38,6) |
| `hold-ref` | `cage` | 1 | value: decimal(38,6) |
| `action-board` | `actions` | 20 | action_type_id: string, target_label: string, selected: boolean, cash_cost_usd: decimal(38,6), expected_net_usd: double, low_net_usd: double, high_net_usd: double |
| `cage-slip` | `actions` | 20 | action_type_id: string, target_label: string, selected: boolean, quantity: bigint, cash_cost_usd: decimal(38,6), lead_days: int, operating_days: int, low_net_usd: double, expected_net_usd: double, high_net_usd: double, p_mid: double, measurement_date: date, assumption: string, success_rule: string, evidence_view: string |
| `annual-options` | `annual` | 20 | action_type_id: string, target_label: string, cash_cost_usd: decimal(38,6), expected_net_usd: double, low_net_usd: double, high_net_usd: double |
| `tech-compare` | `tech` | 2 | target: string, funded_shifts: bigint, package_cost_usd: decimal(38,6), full_recovery_theo_per_shift: decimal(38,6) |
| `tech-sensitivity` | `tech_sensitivity` | 3 | target_label: string, net_lost_theo_minus_30_pct_usd: double, expected_net_usd: double, net_lost_theo_plus_30_pct_usd: double |

The five source queries returned 1 cage row, 20 July actions, 20 annual actions, 2 staffing rows and 3 staffing sensitivity rows. The visual check of the signed-in page remains with the project owner. The review branch also contains an unpublished AI/BI budget-bar draft.

## Frozen model comparison

| Model | April MAE | May–June MAE | May–June MAPE |
| --- | ---: | ---: | ---: |
| Constant baseline | $203,431 | $218,258 | 16.43% |
| Seasonal (weekday mean) baseline | $40,715 | $68,699 | 5.02% |
| Weekday + events model (primary) | $65,287 | $51,129 | 3.84% |
| Trend model (tested, rejected) | $68,585 | $66,520 | 5.00% |

Residual is actual minus forecast. Negative values mean the forecast was too high.

| Weekday | Constant baseline | Seasonal baseline | Primary model | Rejected trend |
| --- | ---: | ---: | ---: | ---: |
| Mon | −$208,470 | −$35,689 | −$19,820 | −$51,899 |
| Tue | −$310,024 | −$38,047 | −$14,090 | −$45,098 |
| Wed | −$241,586 | −$6,648 | $15,109 | −$16,514 |
| Thu | −$117,681 | −$23,742 | $1,951 | −$31,484 |
| Fri | $214,512 | −$56,306 | −$39,448 | −$71,607 |
| Sat | $386,538 | −$49,138 | −$32,279 | −$64,438 |
| Sun | $19,296 | −$61,664 | −$44,805 | −$76,965 |

The trend estimated from January through April was upward after allowing for the weekday, holiday and event effects. That fitted slope helps explain why the added term worsened the overforecast on every weekday. It does not rule out other forms of drift. We predeclared a single trend variant, made the April comparison before reading holdout outcomes, and scored its frozen predictions once. We keep the current ridge as primary.

### Disclosure on the earlier score

Gilded Ace Locals Appreciation Week was announced May 26, after the April 30 forecast date. It affected seven dates in the earlier forecast, which scored $55,270.94 (4.06%). We removed the event, refit through April 30, froze the predictions, and rescored the holdout once. The primary model now scores $51,128.96 (3.84%), a 76.57% drop in mean absolute error from the constant forecast. [Primary run](https://dbc-a3bbfca6-850a.cloud.databricks.com/ml/experiments/2633256274998390/runs/aa13697e0b5a4a2da3af5f269c2f2393) · [Secondary trend run](https://dbc-a3bbfca6-850a.cloud.databricks.com/ml/experiments/2633256274998390/runs/cff3756efcee4ce9b896eefe12f54729).

## July staffing sensitivity

The sensitivity multiplies the original hourly expected-win recovery by the average non-event daily forecast ratio on eligible July dates. It also computes a generous upper bound using the largest eligible ratio and recovery of every modeled wait hour. It does not estimate new fault rates or use July actuals.

| Shift | Original recovery | Trend-scaled recovery | Upper bound | Package cost |
| --- | ---: | ---: | ---: | ---: |
| Grave | $380.91 | $395.25 | $798.13 | $11,520.00 |
| Saturday evening | $131.19 | $134.83 | $270.01 | $11,520.00 |

Neither shift covers its cost. The Gold pilot calculation independently returned 20,577 eligible players and minimum detectable changes of 6.44% at 30 days and 5.77% at 60 days. Neither meets the 2.5% funding threshold.

## Verification and screenshots

The input checks passed 62 checksums and sizes, 31 row-count and format comparisons, daily accounting, the off-floor exclusion, and the spring clock change. The warehouse gates passed floor and tracked-play reconciliation, exact bridges in three windows, gaming-day and hourly alignment, the frozen forecast split, and all budget and incompatibility checks. The SQL audit found only the documented daily percentage-error average as an average of ratios. The new model uses the same definition. The local browser passed the judge walkthrough, all nine exact KPI checks across three ranges, the new budget labels and option count, keyboard focus, phone-width overflow, and the legacy wording check with third-party cookies blocked. Contrast passed and the review build and edited copy contain no em dashes. The published AI/BI page was checked through its API and SQL; its signed-in visual pass remains manual.

- [July plan](screens/review/plan.png), [budget bar](screens/review/budget-allocation.png), and [phone-width budget](screens/review/budget-phone.png)
- [Model Room](screens/review/model.png) and [model comparison](screens/review/model-comparison.png)
- [Dates](screens/review/judge-01-dates.png), [bank and timeline](screens/review/judge-02-bank-timeline.png), [Gold tier](screens/review/judge-03-gold.png), and [inspection evidence](screens/review/judge-04-evidence.png)

## July machine scheduling

For the first eligible gaming days, the profile puts the inspection at 4 to 6 a.m. Thursday, July 3, and the move at 3 to 6 a.m. Friday, July 4. Expected win lost rounds to $6 and $14, versus $86 and $130 for the same durations beginning Saturday at 7 p.m. These are estimates from the April-frozen hourly profile, not actual July losses.

# Dashboard Royale methods

See [METHODS.md](../METHODS.md) for the data rules, concentration, comp reinvestment, 4-L bridge, verdicts, and competing-explanation methods.

## Standalone Gold dashboard

The judge page is built from the bundle's serverless `royale_twin_export` job. It uses the governed Gold queries behind the AI/BI dashboard and exports only public dashboard fields for demand, fault, and tier views. The job writes a per-run JSON file to the `exports` Volume. The build serves the exported rows in a same-origin Gold JSON file. The judge page needs no Databricks login, iframe, CDN, or third-party cookie.

Header metrics are ratios of sums. Theo captured divides expected win by expected win plus hourly leak and the observed location opportunity. Actual and theoretical hold divide the respective win by coin-in. Luck z divides the total actual-minus-theo residual by the square root of summed variance. Comp reinvestment uses floor-wide economic comp cost divided by tracked theo for the selected dates, with floor theo as the secondary line. The test compares nine browser KPIs to an independent Databricks Gold query on three windows, requiring exact equality at the display contract of two decimal places for dollars and eight for ratios and standardized scores.

Date, zone and bank filters use each machine's location on the gaming date. Whole-window ranks, the grouped concentration calculation, causal comparisons, holdout summary, and July funding retain their published scope. Tracked play and reward trends use daily guest-group totals. The Gold group uses the player’s end-of-month tier and six-month expected-win decile. The published concentration and player outcome split remain fixed to January through June. Machine timelines show local gaming hours, with unavailable-time exceptions from `gold_machine_hour_leak` and 23 hours for the spring transition. The unused source columns for visitation and weather are omitted from the public snapshot.

The SQL `AVG` audit found MAPE, an intentionally equal-weight mean of daily percentage errors, plus averages of per-day demand levels, week-block coin-in, model residuals and player outcomes. The equal-weight weekday reference is part of the calendar decomposition. None of these is used as an aggregate hold, occupancy, comp, or payout rate.

# Standalone Gold dashboard

The bundle's serverless `royale_twin_export` job writes a versioned JSON file under `/Volumes/workspace/royale/exports/`. The notebook is generated from the AI/BI dataset definitions, with public projections for demand, faults and tracked-player segments. The output contains only dashboard fields or machine-level fictional operating data. It omits raw player records, third-party source columns and credentials.

With a configured Databricks CLI profile and the Gold tables populated:

```sh
python3 twin/refresh.py
npm ci --prefix embed
node twin/qa.mjs
python3 twin/contrast.py
```

Use `python3 twin/refresh.py --run-id <id>` to rebuild from a completed export. The build writes `embed/public/index.html` and the same-origin `embed/public/gold.json`. The separate `/live` page uses the Databricks SDK and may require third-party content. The generated payload and build directory are ignored by Git.

On Pit Boss, date, zone and bank recalculate machine metrics and the bridge. Comp reinvestment is floor-wide and date-filtered. The Tier filter applies to the player-month breakdown. Fixed whole-window ranks, causal comparisons and July actions retain their published scope. Sparse machine-hour data records exceptions to normal availability. The timeline labels hours in Las Vegas time and skips the nonexistent spring-forward hour.

Vercel deploys the `embed/` directory, serves the generated `public/` directory, and rewrites `/live` to the original embed shell. Build first, then run `vercel deploy --prod --cwd embed` from an authenticated linked project. Production credentials belong in Vercel's server-side environment only.

The judge page loads one same-origin JSON file, `embed/public/gold.json`, produced from the Databricks export. There is no DuckDB or other data engine in the site build. Amounts are added from the selected gaming days, and ratios use their summed numerators and denominators. The Databricks footer shows the date recorded by the export job.

Sound effects and the quiet optional music loop are generated with the Web Audio API. Both settings start off and are remembered in the browser. The site uses no audio files. Reduced-motion settings disable motion effects.

The global date filter drives charts that have day-level data. The six-month player rankings and outcome split, the July budget, and published evidence comparisons keep the reference periods needed for their definitions. Untracked wagers have no guest profile, so guest group filters apply to tracked play and comp trends rather than the floor-wide comparison.

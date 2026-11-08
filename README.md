# The Gilded Ace

[Public source repository](https://github.com/kavuruhasini03-hue/gilded-ace-royale-submission)

We recommend not replacing any of the ten lowest-earning machines in July. Instead, inspect machine M-1158, hold off on the comp pilot until it can give a clear answer, and keep $98,800 of the budget in reserve.

The project examines six months at a fictional casino. The interactive dashboard uses figures exported from the Databricks Gold pipeline. It covers machine performance, demand, downtime, tracked play, comps, and the July plan.

[Open the public dashboard](https://gilded-ace-royale.vercel.app) · [Open Databricks AI/BI (workspace sign-in required)](https://dbc-a3bbfca6-850a.cloud.databricks.com/dashboardsv3/01f1daeb815914e69b3ef75f86f7d789/published?o=7474653288963289)

With the Databricks CLI signed in and Gold already built in an authorized workspace, run `python3 twin/refresh.py`. This deploys and runs the bundle's export job, downloads its JSON, and builds the website in `embed/public/`. To preview it, run `node embed/local.mjs` and open the local address it prints.

The data is available from the [official Dashboard Royale repository](https://github.com/tamu-datathon-org/dashboard-royale/tree/main/data). For a fresh workspace, make that official data directory available locally as `data/`, then run the following command with your workspace's SQL warehouse ID in both places. It creates the raw volume if needed.

```sh
python3 scripts/deploy_phase2.py --warehouse-id YOUR_WAREHOUSE_ID && python3 twin/refresh.py --warehouse-id YOUR_WAREHOUSE_ID
```

See the [setup and verification notes](twin/README.md), [methods](docs/METHODS.md), [write-up](submission/WRITEUP.md), [evidence ledger](submission/CLAIMS_EVIDENCE.md), [walkthrough script](submission/VIDEO_SCRIPT.md), [quality gates](submission/QUALITY.md), and [before and after screenshots](docs/screens/restyle/README.md).

The Databricks bundle and SQL are in `databricks/`. The AI/BI dashboard definition is in `dashboards/`. The public page source is in `twin/` and the deployment configuration is in `embed/`. This submission omits the challenge data, generated exports, and credentials. Sound and optional music are synthesized in the browser. No audio files are distributed.

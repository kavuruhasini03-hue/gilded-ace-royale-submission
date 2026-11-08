# Gilded Ace external embed

This app loads the published Databricks dashboard in dark mode using a dashboard-scoped OAuth token. Provisioning grants the dedicated reader direct SELECT on the exact Gold objects named in the dashboard, plus the catalog and schema navigation privileges and dashboard CAN RUN. Publication uses individual data permissions.

## Local run

1. Run `PYTHONDONTWRITEBYTECODE=1 python3 embed/provision.py` from the repository root if provisioning is needed.
2. Run `PYTHONDONTWRITEBYTECODE=1 python3 embed/start-local.py`. This passes a one-hour secret in process memory to a loopback-only server. Open `http://localhost:3000`.
3. Install Playwright with `npm --prefix embed ci` and run `npm --prefix embed run qa`. The check uses installed Chrome and saves screenshots under `docs/screens/`.

A successful page response does not imply the iframe loaded. The token exchange and approved-domain policy must both pass. The first run is recorded in `docs/screens/00-local-embed-blocked.png`.

## Hosting

The Node serverless handler lives in `api/token.mjs`. For a Node-function host such as Vercel, use `embed/` as the project root, serve the static assets at the root and route `/api/token` to the handler. Set `EMBED_ORIGIN` to the exact HTTPS origin and set `DATABRICKS_CLIENT_ID` and `DATABRICKS_CLIENT_SECRET` in server-side secrets. Use the dedicated reader, not an administrator's credentials. Configure an edge rate limit on the public token route. The browser gets only the one-hour scoped token, never the reader secret. Ask the workspace admin to approve the exact host domain before public deployment.

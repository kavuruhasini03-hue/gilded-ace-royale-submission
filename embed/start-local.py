"""Start localhost with a short-lived dedicated secret held in process memory."""
import os
from pathlib import Path
import subprocess
from provision import NAME, db

principal, = db("service-principals", "list", "--filter", f'displayName eq "{NAME}"')
record = db("service-principal-secrets-proxy", "create", principal["id"], "--lifetime", "3600s")
secret = record.get("secret")
if not secret:
    raise SystemExit("Databricks did not return the short-lived client secret.")
env = dict(os.environ, DATABRICKS_CLIENT_ID=principal["applicationId"], DATABRICKS_CLIENT_SECRET=secret)
subprocess.run(["node", "local.mjs"], cwd=Path(__file__).resolve().parent, env=env, check=True)

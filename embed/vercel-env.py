"""Send the dedicated reader credentials directly to Vercel Production."""
import argparse
import re
import subprocess
from pathlib import Path

from provision import NAME, db


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cli", help="Path to the authenticated Vercel CLI")
    parser.add_argument("origin", help="Verified production HTTPS origin assigned to this project")
    parser.add_argument("--global-config", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"https://[a-z0-9-]+\.vercel\.app", args.origin):
        parser.error("Expected an exact HTTPS vercel.app origin.")

    cwd = Path(__file__).resolve().parent
    cli = [args.cli]
    if args.global_config:
        cli += ["--global-config", str(args.global_config)]
    subprocess.run([*cli, "whoami"], cwd=cwd, check=True)
    subprocess.run([*cli, "project", "inspect", "gilded-ace-royale"], cwd=cwd, check=True)
    principal, = db("service-principals", "list", "--filter", f'displayName eq "{NAME}"')
    details = db("service-principals", "get", principal["id"])
    if {item["value"] for item in details.get("entitlements", [])} != {"workspace-consume"}:
        raise SystemExit("The reader must have Consumer access alone.")

    def send(name, value, kind):
        result = subprocess.run(
            [*cli, "env", "add", name, "--environment", "production", "--type", kind,
             "--project", "gilded-ace-royale", "--yes"],
            cwd=cwd, input=value, text=True, capture_output=True,
        )
        if result.returncode:
            raise SystemExit(f"Vercel could not add {name}; check the project and its Production settings.")
        print(f"Stored {name} in Vercel Production.")

    send("EMBED_ORIGIN", args.origin, "config")
    send("DATABRICKS_CLIENT_ID", principal["applicationId"], "secret")
    credential = db("service-principal-secrets-proxy", "create", principal["id"], "--lifetime", "2592000s")
    try:
        send("DATABRICKS_CLIENT_SECRET", credential["secret"], "secret")
    except BaseException:
        db("service-principal-secrets-proxy", "delete", principal["id"], str(credential["id"]))
        raise


if __name__ == "__main__":
    main()

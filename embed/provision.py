"""Configure the named dashboard and its dedicated reader without exposing credentials."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from deploy_phase2 import cli

DASHBOARD = "01f1daeb815914e69b3ef75f86f7d789"
WAREHOUSE = "46ae4ab074f3051d"
NAME = "gilded-ace-external-dashboard-reader"


def db(*args):
    return json.loads(cli("DEFAULT", *args) or "{}")


def main():
    definition = (ROOT / "dashboards/gilded_ace.lvdash.json").read_text()
    datasets = json.loads(definition)["datasets"]
    objects = set()
    for dataset in datasets:
        sources = re.findall(r"\b(?:FROM|JOIN)\s+([\w.]+)", "".join(dataset["queryLines"]), re.I)
        if not sources or any(not re.fullmatch(r"workspace\.royale\.gold_\w+", t) for t in sources):
            raise ValueError(f"Non-Gold dataset source: {dataset['name']}")
        objects.update(sources)

    matches = db("service-principals", "list", "--filter", f'displayName eq "{NAME}"')
    if len(matches) > 1:
        raise RuntimeError("Multiple dedicated principals exist. Resolve the duplicate before granting permissions.")
    principal = matches[0] if matches else db("service-principals", "create", "--display-name", NAME, "--active")
    app = principal["applicationId"]
    print(f"Dedicated principal {principal['id']} / {app}", flush=True)

    def grant(kind, target, privilege):
        payload = {"changes": [{"principal": app, "add": [privilege]}]}
        db("grants", "update", kind, target, "--json", json.dumps(payload))

    grant("catalog", "workspace", "USE_CATALOG")
    grant("schema", "workspace.royale", "USE_SCHEMA")
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(lambda target: grant("table", target, "SELECT"), sorted(objects)))
    print(f"Direct SELECT on {len(objects)} fixed Gold sources", flush=True)

    def object_permission(kind, target, level):
        payload = {"access_control_list": [{"service_principal_name": app, "permission_level": level}]}
        db("permissions", "update", kind, target, "--json", json.dumps(payload))

    object_permission("dashboards", DASHBOARD, "CAN_RUN")
    object_permission("warehouses", WAREHOUSE, "CAN_USE")
    db("lakeview", "update", DASHBOARD, "--dataset-catalog", "workspace", "--dataset-schema", "royale",
       "--serialized-dashboard", definition)
    db("lakeview", "publish", DASHBOARD, "--warehouse-id", WAREHOUSE, "--embed-credentials=false")
    published = db("lakeview", "get-published", DASHBOARD)
    if published.get("embed_credentials") is not False:
        raise RuntimeError("Publication did not confirm individual data permissions")
    print("Verified publication with individual data permissions", flush=True)
    print("Approved domains:", db("settings", "aibi-dashboard-embedding-approved-domains", "get"), flush=True)


if __name__ == "__main__":
    main()

"""Render the published Gold claims ledger as a submission document."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
dataset = json.loads((root / "embed/.gold-export.json").read_text())["evidence"]
rows = [dict(zip(dataset["columns"], values)) for values in dataset["rows"]]
out = ["# Claims and evidence", "", "[Public source repository](https://github.com/kavuruhasini03-hue/gilded-ace-royale-submission)", "", "Generated from `workspace.royale.gold_claims_evidence`.", ""]
for row in sorted(rows, key=lambda r: (r["widget"], r["claim"], r["result"])):
    out += [f"## {row['claim']}", "", f"Dashboard page: {row['widget']}",
            f"Gold source and query: {row['evidence']}", f"Result: {row['result']}",
            f"Alternative tested: {row['alternative_tested']}", f"Limitation: {row['limitation']}", ""]
(root / "submission/CLAIMS_EVIDENCE.md").write_text("\n".join(out).replace(chr(8212), ". ").replace("GM bottom ten", "general manager’s bottom ten").replace("The GM basket", "The ten-machine group"))

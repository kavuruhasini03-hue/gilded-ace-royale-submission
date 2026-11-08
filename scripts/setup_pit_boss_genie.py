"""Create the workspace-only Pit Boss Genie space with curated Gold SQL."""
import json
from uuid import NAMESPACE_URL, uuid5

from deploy_phase2 import cli, execute_sql

TITLE = "Ask the Pit Boss"
WAREHOUSE = "46ae4ab074f3051d"
PROFILE = "DEFAULT"
SCHEMA = "workspace.royale."
QUESTIONS = [
    ("What is funded in July and how much stays in reserve?",
     "SELECT spent_usd, kept_usd, funded_action_types FROM "+SCHEMA+"gold_cage_slip"),
    ("Why is the comp pilot deferred?",
     "SELECT cash_cost_usd, selected, success_rule FROM "+SCHEMA+
     "gold_action_plan WHERE action_type_id='A-COMP-PILOT' AND horizon_days=30"),
    ("How accurate is the forecast on May and June?",
     "SELECT model, scored_days, mae_usd, mape_pct FROM "+SCHEMA+"gold_forecast_holdout_metrics ORDER BY model"),
    ("How much expected house win was lost to downtime?",
     "SELECT ROUND(SUM(leak_usd),2) AS expected_win_lost_usd FROM "+SCHEMA+"gold_kpi_header"),
]
TABLES = ("gold_action_plan", "gold_cage_slip", "gold_forecast_holdout_metrics", "gold_kpi_header")


def key(prefix, question):
    return uuid5(NAMESPACE_URL, "gilded-ace-genie/"+prefix+"/"+question).hex


def main():
    for question, query in QUESTIONS:
        if not execute_sql(PROFILE, WAREHOUSE, query):
            raise RuntimeError("Empty answer for: "+question)
    spaces = json.loads(cli(PROFILE, "genie", "list-spaces"))
    if isinstance(spaces, dict):
        spaces = spaces.get("spaces", [])
    existing = next((s for s in spaces if s["title"] == TITLE), None)
    if existing:
        print(existing["space_id"])
        return
    spec = {"version": 2, "config": {"sample_questions": [
        {"id":key("sample", question), "question":[question]} for question,_ in QUESTIONS]},
        "data_sources": {"tables":[{"identifier":SCHEMA+t} for t in TABLES]},
        "instructions": {
            "text_instructions":[{"id":key("instruction", TITLE),"content":[
                "The Gilded Ace is a fictional casino. Use only the listed Gold sources.",
                "Use the exact approved SQL for the example questions. July decisions are fixed snapshots.",
                "For rates, divide sums. Expected house win is theo. Never describe payout anomalies as proof of misconduct.",
                "Explain that a trial can be deferred even if learning has modeled value. Never target heavy losers.",
                "The primary forecast uses events known by April 30. May and June are the 61-day holdout.",
            ]}],
            "example_question_sqls":[{"id":key("sql", q),"question":[q],"sql":[sql]} for q,sql in QUESTIONS],
        }}
    spec["config"]["sample_questions"].sort(key=lambda q: q["id"])
    spec["instructions"]["example_question_sqls"].sort(key=lambda q: q["id"])
    created = json.loads(cli(PROFILE, "genie", "create-space", "--json", json.dumps({
        "title":TITLE, "description":"Workspace-only questions about the fictional casino's approved Gold figures.",
        "warehouse_id":WAREHOUSE,"serialized_space":json.dumps(spec)})))
    print(created["space_id"])


if __name__ == "__main__":
    main()

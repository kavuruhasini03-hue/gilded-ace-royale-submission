import json
from pyspark.sql import functions as F

spark.sql("CREATE VOLUME IF NOT EXISTS workspace.royale.exports")
dbutils.widgets.text("export_id", "")
export_id = dbutils.widgets.get("export_id")
assert export_id.isdigit(), "Expected a numeric job run ID"
path = f"/Volumes/workspace/royale/exports/twin-{export_id}.json"
spark.conf.set("spark.sql.session.timeZone", "UTC")

with open(path, "w", encoding="utf-8") as output:
    output.write("{")
    for index, (name, query) in enumerate(QUERIES.items()):
        frame = spark.sql(query)
        encoded = frame.select(F.to_json(F.struct("*"), {"ignoreNullFields": "false"}).alias("line"))
        if index:
            output.write(",")
        output.write(json.dumps(name) + ':{"columns":' + json.dumps(frame.columns) + ',"rows":[')
        for row_index, row in enumerate(encoded.toLocalIterator()):
            if row_index:
                output.write(",")
            values = json.loads(row.line)
            output.write(json.dumps([values[c] for c in frame.columns], separators=(",", ":"), ensure_ascii=False))
        output.write("]}")
    output.write("}")
dbutils.jobs.taskValues.set(key="export_path", value=path)

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError
from datetime import datetime, timezone
import json
import uuid
import random
import time

NAMESPACE  = "teradata://dummy-logs-customer"          # tells Validio: these are Teradata tables
PRODUCER   = "https://example.com/sql-lineage-tool"   # identifies our tool
SCHEMA_URL = "https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent"


def is_table_volatile(tree):
    if not isinstance(tree, exp.Create):
        return False
    else:
        table_prop = tree.find(exp.StabilityProperty)
        if table_prop is None:
            return False
        if table_prop.name.upper() == "VOLATILE":
            return True
        else:
            return False

def full_name(table):
    if table.db:
        return f"{table.db}.{table.name}"
    else:
        return table.name

def get_table_lineage (tree,temp_tables):
    WRITE_TYPES=(
        exp.Create,
        exp.Insert,
        exp.Update,
        exp.Merge 
    )
    if isinstance(tree, WRITE_TYPES):
        print("yes it is write statement. It belongs CTAS,insert, update, merge")
    else:
        print("Lineage cannot be determined")
        return None

    first_level = tree.this
    if isinstance(first_level, exp.Table):
        target_table_node = first_level
    elif isinstance(first_level,exp.Schema) and isinstance(first_level.this, exp.Table):
         target_table_node = first_level.this
    else:
        print("target cannot be determined")
        return None
    print("-----start-----")
    print(f"target db={target_table_node.db} target table = {target_table_node.name}")
    sources = []
    for node in tree.find_all(exp.Table):
        if node is not target_table_node:
            print(f"source db={node.db} souce table name={node.name}")
            temp_src_list = temp_tables.get(full_name(node))
            print("temp_src_list type ",type(temp_src_list),"temp_src_list",temp_src_list)
            if temp_src_list is not None:
                print("inside if before extend ",temp_src_list)
                sources.extend(temp_src_list)               
            else:
                sources.append(full_name(node))
    
    if is_table_volatile(tree):        
        temp_tables[full_name(target_table_node)] =sources
        print("inside is table volatile",temp_tables)
        return None  
    print("-----end-----")
    return (full_name(target_table_node), sources)

def read_sql_statemets(file_path):
    with open(file_path,"r",encoding="utf-8") as f:
        sql_text = f.read()

    sql_statements=[]
    for sql_stmt in sql_text.split(";"):
        lines =[]
        for line in sql_stmt.splitlines():
            sql_ln= line.strip()
            if not sql_ln.startswith("--"):
                lines.append(sql_ln)

        sql = "\n".join(lines).strip()
        if sql:
            sql_statements.append(sql)
    return sql_statements


#build event for open lineage api for each sql statement as part of lineage
def build_event_for_api(target,sources,job_name):
    input_source_tables=[]
    for src_tables in sources:
        inp_item={
            "namespace": NAMESPACE,
            "name": src_tables
        }
        input_source_tables.append(inp_item)

    event = {
        "eventType": "COMPLETE",
        "eventTime": datetime.now(timezone.utc).isoformat(),
        "run":{"runId": str(uuid.uuid4())},
        "job": {"namespace": "dummy-assignment-query-log", "name": job_name},
        "producer":PRODUCER,
        "schemaURL": SCHEMA_URL,
        "outputs": [{"namespace":NAMESPACE, "name": target}],
        "inputs": input_source_tables
    }
    return event

def mock_validio_api_call(event):
    """Pretends to be Validio's OpenLineage endpoint. Returns an HTTP status code."""
    required_fields = ["eventType", "eventTime", "run", "job"]
    # 1. Like Validio: a missing required field is rejected with 400
    for field in required_fields:
        if field not in event:
            print(f"Missing required field: {field}")
            return 400  # Bad Request
    # 2. Simulate temporary problems, so retry can be tested
    random_number = random.random()
    if random_number < 0.2:
        print("Simulating too many requests (rate limit)")
        return 429  # rate limit
    elif random_number > 0.2 and random_number < 0.3:
        print("Simulating a internal server error (500)")
        return 500  # server error
    else:
        print("Simulating a successful API call (200)")
        return 200  # OK

def call_validio_api_with_retry(event, max_retries=3, base_wait=0.5):
    """Send one event. Returns True if accepted, False if it finally failed."""

    job_name = event.get("job", {}).get("name", "unknown")
    if job_name == "unknown":
        print("Warning: job name is unknown, cannot log retries properly.")
        return False
    else:
        for i in range(1,max_retries+1):
            status_code = mock_validio_api_call(event)
            if status_code == 200:
                print(f"Event for job {job_name} accepted by Validio.")
                return True
            elif status_code in (400, 401, 403, 404):
                print(f"Event for job {job_name} rejected with status code {status_code}. No retry.")
                return False
            elif status_code in (429, 500, 502, 503, 504) and i < max_retries:
                wait_time = base_wait * (2 ** i)
                print(f"Retrying event for job {job_name} after {wait_time} seconds due to status code {status_code}.")
                time.sleep(wait_time)
            else:
                print(f"Event for job {job_name} FAILED after{max_retries} attempts with status code {status_code}.")
                return False


def main():
    lineage=[]
    temp_tables={}
    file_path = "data/query_log.sql"
    sql_statements=read_sql_statemets(file_path)
    i=0
    for sql in sql_statements:
        i= i+1
        if sql.strip().upper().startswith(("EXEC ", "EXECUTE ", "CALL ")):
            print("FLAG: macro/procedure call, lineage not recoverable from log text")
            continue
        try:
            tree = sqlglot.parse_one(sql, read="teradata")   # SQL text → tree
        except ParseError as e:
            print(f"Error parsing SQL statement {i}:{sql} : {e}")
            continue

        print(f"printing source and target tables for sql{i}")
        try:
            result_set=get_table_lineage(tree,temp_tables)
        except Exception as e:
            print(f"Error processing SQL statement {i}:{sql} : {e}")
            if "VOLATILE"in sql.upper():
                print("WARNING: volatile table, not created , if used as source table in later sqls, lineage may be incomplete")
            continue

        if result_set is None:  # nothing to unpack handle scenario without target ,or plain select.
            continue
        if result_set not in lineage: # avoid duplicates combination of target and sources
            lineage.append(result_set)

    print("temp tables")
    print(temp_tables)
    print("printing lineage")

    # build events for open lineage api
    events=[]
    i=0
    for target, sources in lineage:
        i=i+1
        print(f"{target} -> {sources}")
        events.append(build_event_for_api(target,sources,f"sql_job_{i}"))
    
    print("printing events in json format for open lineage api")
    max_retries=3
    base_wait=0.5
    sent =0
    failed =0
    for event in events:
        print(json.dumps(event, indent=2))
        #status_code = mock_validio_api_call(event)
        status_code = call_validio_api_with_retry(event, max_retries, base_wait)
        if status_code== True:
            sent = sent +1  
        else:
            failed = failed +1
    print(f"Total events sent successfully: {sent}, Total events failed: {failed}")


if __name__ == "__main__":
    main()
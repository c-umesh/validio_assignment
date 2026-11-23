import sqlglot
from sqlglot.errors import ParseError
import json

from reader import read_sql_statements
from lineage import get_table_lineage, full_name, is_table_volatile
from build_and_upload_api import build_event_for_api, call_validio_api_with_retry

def main():
    lineage=[]
    temp_tables={}
    file_path = "data/query_log.sql"
    sql_statements=read_sql_statements(file_path)
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
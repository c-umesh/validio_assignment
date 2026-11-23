
from datetime import datetime, timezone
import uuid
import random
import time

NAMESPACE  = "teradata://dummy-logs-customer"          # tells Validio: these are Teradata tables
PRODUCER   = "https://example.com/sql-lineage-tool"   # identifies our tool
SCHEMA_URL = "https://openlineage.io/spec/2-0-2/OpenLineage.json#/$defs/RunEvent"


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

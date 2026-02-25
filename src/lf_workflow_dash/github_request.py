import json
from urllib.parse import urlencode

import requests

from lf_workflow_dash.string_helpers import coerce_copier_version, get_conclusion_time, read_copier_version


def update_workflow_status(workflow_elem, token):  # pragma: no cover
    """Determine the status of a workflow run, using the github API.

    Args:
        workflow_elem (WorkflowElemData): the workflow to request
        token (str): auth token for hitting the github API
    """
    if workflow_elem is None:
        return

    print("  ", workflow_elem.workflow_name)
    # Make request
    request_url = (
        f"https://api.github.com/repos/{workflow_elem.owner}/{workflow_elem.repo}"
        f"/actions/workflows/{workflow_elem.workflow_name}/runs"
    )
    query_params = {}
    if workflow_elem.branch:
        query_params["branch"] = workflow_elem.branch
    if len(query_params) > 0:
        request_url += "?" + urlencode(query_params, doseq=True)

    payload = {}
   # headers = {
    ##   "Authorization": f"Bearer {token}",
    #}#
    headers = {
        "accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }
    try:
            response = requests.request("GET", request_url, headers=headers, data=payload, timeout=15)
            print(f"Requesting {workflow_elem.repo}/{workflow_elem.workflow_name}: {response.status_code}")
            status_code = response.status_code
            conclusion = "pending"
            conclusion_time = ""
            is_stale = False

           
            if response.status_code != 200:
                print(f"DEBUG: Full Response: {response.text}") # This captures 404/403 errors
            # Process data
            if status_code == 200:  # API was successful
                response_json = response.json()
                print(f"DEBUG: {workflow_elem.repo} - {workflow_elem.workflow_name} - Found {len(response_json.get('workflow_runs', []))} runs")
                if len(response_json["workflow_runs"]) == 0:  # workflow has no runs
                    conclusion = "not yet run"

                else:
                    last_run = response_json["workflow_runs"][0]
                    workflow_elem.friendly_name = last_run["name"]

                    # Get the workflow conclusion ("success", "failure", etc)
                    conclusion = last_run["conclusion"]

                    # Get the time this workflow concluded (in New York time)
                    conclusion_time, is_stale = get_conclusion_time(last_run)
                    raw_time = last_run.get("updated_at")

# Use the new formatter
                    friendly_time = format_time_ago(raw_time)

                    # Check if the workflow is currently being executed
                    if conclusion is None:
                        print(f"      ✅ {workflow_elem.repo}: Setting status to {conclusion}")
                        # try next most recent
                        if len(response_json["workflow_runs"]) > 1:
                            last_run = response_json["workflow_runs"][1]
                            conclusion = last_run["conclusion"]
                            conclusion_time, is_stale = get_conclusion_time(last_run)
                        else:
                            conclusion = "pending"
                            conclusion_time = ""
                    workflow_elem.set_status(conclusion, friendly_time, is_stale)
        
            else:
                print("    ", status_code, request_url)
                conclusion = status_code

                 #  wor kflow_elem.set_status(conclusion, conclusion_time, is_stale)
    except Exception:
        workflow_elem.set_status("request failed", "", False)


def update_copier_version(project_data, token, copier_semver):  # pragma: no cover
    """Find the copier version from the repo's `.copier_answers.yml` file.

    Args:
        project_data (ProjectData): container for the project's data
        token (str): auth token for hitting the github API
    """
    request_url = (
        f"https://raw.githubusercontent.com/{project_data.owner}/{project_data.repo}/main/.copier-answers.yml"
    )

    headers = {"Authorization": f"Bearer {token}"}
    response = requests.request("GET", request_url, headers=headers, timeout=15)

    project_data.set_copier_version(
        coerce_copier_version(read_copier_version(response.content)), copier_semver
    )


def get_copier_version(context, token):  # pragma: no cover
    """Get the current version of the copier template for projects."""

    request_url = f"https://api.github.com/repos/{context['copier_project']}/releases/latest"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.request("GET", request_url, headers=headers, timeout=15)
    response_json = response.json()
    context["copier_semver"] = coerce_copier_version(response_json["tag_name"])

from datetime import datetime, timezone

def format_time_ago(timestamp_str):
    """Converts a GitHub UTC timestamp into a 'time ago' string."""
    if not timestamp_str:
        return "Never"
    
    try:
        # Parse the GitHub ISO format (e.g., 2026-02-17T15:00:00Z)
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - dt
        
        minutes = int(diff.total_seconds() / 60)
        if minutes < 1: return "just now"
        if minutes < 60: return f"{minutes}m ago"
        
        hours = int(minutes / 60)
        if hours < 24: return f"{hours}h ago"
        
        return f"{int(hours / 24)}d ago"
    except Exception:
        return timestamp_str # Fallback to raw string if parsing fails
    
def parse_ctrf_summary(json_content):
    """Extracts summary metrics from CTRF JSON data."""
    try:
        data = json.loads(json_content)
        summary = data.get("results", {}).get("summary", {})
        passed = summary.get("passed", 0)
        total = summary.get("tests", 0)
        return f"{passed}/{total} Tests" if total > 0 else "0/0 Tests"
    except Exception:
        return "N/A"
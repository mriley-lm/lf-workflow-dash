import os
from datetime import datetime

import pytz
from jinja2 import Environment, FileSystemLoader

from lf_workflow_dash.data_types import read_yaml_file
from lf_workflow_dash.github_request import get_copier_version, update_copier_version, update_workflow_status


def update_html(out_file, context):
    """Fetch the jinja template, and update with all of the gathered context.

    Args:
        out_file (str): path to write the hydrated html file to
        context (dict): local variables representing workflow status
    """
    environment = Environment(
        loader=FileSystemLoader("templates/"),
        extensions=['jinja2.ext.do'] 
    )
    template = environment.get_template("dash_template.jinja")
    out_dir = os.path.dirname(out_file)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_file, mode="w", encoding="utf-8") as results:
        results.write(template.render(context))


def update_status(context, token):  # pragma: no cover
    """Issue requests to the github JSON API and update each workflow status accordingly.

    Args:
        context (dict): local variables representing workflow status
        token (str): github personal access token
    """
    for project in context["all_projects"]:
        try:
            print(f"Checking {project.owner}/{project.repo}...")
            print(project.repo)
            try:
                update_copier_version(project, token, context["copier_semver"])
            except Exception:
                project.set_copier_version("N/A", context["copier_semver"])
            update_workflow_status(project.smoke_test, token)
            update_workflow_status(project.build_docs, token)
            update_workflow_status(project.benchmarks, token)
            update_workflow_status(project.live_build, token)
            for other_wf in project.other_workflows:
                update_workflow_status(other_wf, token)
        except Exception as e:
            print(f"  ⚠️ Skipping {project.repo} due to error: {e}")
            continue # Ensure we reach update_html() at the end

def do_the_work(token, datafile, outfile):  # pragma: no cover
    """Wrapper to call all of the methods necessary to build the final hydrated page.

    Args:
        token (str): github personal access token
        datafile (str): path to the yaml config file with workflow data
        outfile (str): write to write the hyrated html file to
    """
    context = read_yaml_file(datafile)
    get_copier_version(context, token)
    update_status(context, token)
    # Set dashboard last updated to when we generate the page (not when we read the config)
    tz = pytz.timezone("America/New_York")
    context["last_updated"] = datetime.now(tz).strftime("%H:%M %B %d, %Y (US/Eastern)")
    update_html(outfile, context)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 4:
        print("Usage: update_dashboard.py <GITHUB_TOKEN> <config.yaml> <output.html>", file=sys.stderr)
        sys.exit(1)
    do_the_work(token=sys.argv[1], datafile=sys.argv[2], outfile=sys.argv[3])

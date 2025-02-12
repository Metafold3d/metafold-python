"""Helper script to dispatch workflows."""
from argparse import ArgumentParser, FileType
from metafold import MetafoldClient
from pathlib import Path
from pprint import pprint
import json
import os
import sys


def main():
    parser = ArgumentParser(description="Run workflow from YAML definition")
    parser.add_argument(
        "workflow", nargs="?",
        type=FileType("r"), default=sys.stdin, help="workflow definition")

    parser.add_argument("--assets", help="workflow asset mapping")
    parser.add_argument("--params", help="workflow parameter mapping")

    parser.add_argument(
        "--asset-uploads", nargs="*",
        type=Path, help="assets to upload before dispatch")

    project_id = os.environ.get("METAFOLD_PROJECT_ID")
    parser.add_argument("-p", "--project-id", default=project_id)

    client_id = os.environ.get("METAFOLD_CLIENT_ID")
    parser.add_argument("--client-id", default=client_id)

    client_secret = os.environ.get("METAFOLD_CLIENT_SECRET")
    parser.add_argument("--client-secret", default=client_secret)

    auth_domain = os.environ.get("METAFOLD_AUTH_DOMAIN", "metafold3d.us.auth0.com")
    parser.add_argument("--auth-domain", default=auth_domain)

    base_url = os.environ.get("METAFOLD_BASE_URL", "https://api.metafold3d.com/")
    parser.add_argument("--base-url", default=base_url)

    args = parser.parse_args()

    if not args.project_id:
        parser.error("project id is required")
    if not args.client_id:
        parser.error("client id is required")
    if not args.client_secret:
        parser.error("client secret is required")

    assets = None
    if args.assets:
        assets = json.loads(args.assets)

    params = None
    if args.params:
        params = json.loads(args.params)

    m = MetafoldClient(
        project_id=args.project_id,
        client_id=args.client_id,
        client_secret=args.client_secret,
        auth_domain=args.auth_domain,
        base_url=args.base_url)

    if args.asset_uploads:
        print("Uploading assets…")
        for p in args.asset_uploads:
            m.assets.create(p.resolve())

    print("Running workflow…")
    definition = args.workflow.read()
    w = m.workflows.run(definition, assets=assets, parameters=params)

    print(f"Workflow completed: {w.state}")

    for job_id in w.jobs:
        j = m.jobs.get(job_id)
        match j.state:
            case "success":
                if j.outputs and j.outputs.assets:
                    pprint(j.outputs.assets)
                if j.outputs and j.outputs.params:
                    pprint(j.outputs.params)
            case "failure":
                print(f"Job {j.id} failed: {j.error}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

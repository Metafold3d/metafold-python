"""Example script demonstrating running multiple jobs in parallel.

Note the Metafold API applies rate limiting to job dispatches so running jobs in
parallel will give limited performance improvements.

Usage:
    python examples/lattice_metrics_parallel.py -t <token> -p <project> -n <procs>

For more details on the available job types please refer to the Metafold REST API
documentation.
"""
from argparse import ArgumentParser
from functools import partial
from metafold import MetafoldClient
from multiprocessing import Pool
from pprint import pprint
import os

lattice_types = [
    "Gyroid",
    "SchwarzD",
    "I2Y",
    "CI2Y",
    "S",
    "SD1",
    "P",
    "F",
    "Schwarz",
    "D",
    "IWP",
    "CD",
    "CP",
    "CY",
    "CS",
    "W",
    "Y",
    "C_Y",
    "PM_Y",
    "CPM_Y",
    "FRD",
    "SchwarzN",
    "SchwarzW",
    "SchwarzPW",
]


def main() -> None:
    parser = ArgumentParser(description="Compute metrics for surface lattices")
    parser.add_argument("-t", "--token", type=str, help="access token")
    parser.add_argument("-p", "--project", type=str, help="project id", required=True)
    parser.add_argument("-n", "--procs", type=int, default=4)

    args = parser.parse_args()

    token = args.token or os.environ.get("METAFOLD_ACCESS_TOKEN")
    if not token:
        parser.error("access token is required")

    with Pool(args.procs) as p:
        f = partial(evaluate_metrics, token, args.project)
        p.map(f, lattice_types)


def evaluate_metrics(access_token: str, project_id: str, lattice_type: str) -> None:
    metafold = MetafoldClient(access_token, project_id)

    print(f"Running evaluate_metrics ({lattice_type}) job...")
    job = metafold.jobs.run("evaluate_metrics", {
        "graph": {
            "operators": [
                {
                    "type": "GenerateSamplePoints",
                    "parameters": {
                        "size": [1.0, 1.0, 1.0],
                        "resolution": [64, 64, 64],
                    },
                },
                {
                    "type": "SampleSurfaceLattice",
                    "parameters": {
                        "lattice_type": lattice_type,
                        "scale": [1.0, 1.0, 1.0],
                    },
                },
                {
                    "type": "Redistance",
                    "parameters": {
                        "size": [1.0, 1.0, 1.0],
                    },
                },
                {
                    "type": "Threshold",
                    "parameters": {
                        "width": 0.04,
                    },
                },
            ],
            "edges": [
                {"source": 0, "target": [1, "Points"]},
                {"source": 1, "target": [2, "Samples"]},
                {"source": 2, "target": [3, "Samples"]},
            ],
        },
        "point_source": 0,
    })
    print(f"{lattice_type}:")
    pprint(job.meta)


if __name__ == "__main__":
    main()

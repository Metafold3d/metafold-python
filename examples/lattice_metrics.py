"""Example script demonstrating running multiple jobs.

Usage:
    python examples/lattice_metrics.py -t <token> -p <project>

For more details on the available job types please refer to the Metafold REST API
documentation.
"""
from argparse import ArgumentParser
from metafold import MetafoldClient
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

    args = parser.parse_args()

    token = args.token or os.environ.get("METAFOLD_ACCESS_TOKEN")
    if not token:
        parser.error("access token is required")

    metafold = MetafoldClient(token, args.project)

    for lattice_type in lattice_types:
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

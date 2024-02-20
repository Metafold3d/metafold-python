"""Example script demonstrating running multiple jobs (beam lattices).

Usage:
    python examples/beam_lattice_metrics.py -t <token> -p <project>

For more details on the available job types please refer to the Metafold REST API
documentation.
"""
from argparse import ArgumentParser
from metafold import MetafoldClient
from pprint import pprint
from typing import TypedDict
import os
import requests


class Lattice(TypedDict):
    # There are other fields but we don't care to capture them here
    name: str
    display_name: str
    other_names: str
    positions: list[float]
    node_ids: list[int]


lattice_url = "https://lightcycle-static.us-southeast-1.linodeobjects.com/lib/beam_lattice.json"


def main() -> None:
    parser = ArgumentParser(description="Compute metrics for beam lattices")
    parser.add_argument("-t", "--token", type=str, help="access token")
    parser.add_argument("-p", "--project", type=str, help="project id", required=True)

    args = parser.parse_args()

    token = args.token or os.environ.get("METAFOLD_ACCESS_TOKEN")
    if not token:
        parser.error("access token is required")

    metafold = MetafoldClient(token, args.project)

    library = get_lattice_library()

    for lattice_type in library:
        lattice = library[lattice_type]
        lattice_name = lattice["display_name"]

        # Build arrays-of-arrays by iterating through flattened data in strides
        nodes = [
            lattice["positions"][i:i + 3]
            for i in range(0, len(lattice["positions"]), 3)
        ]
        edges = [
            lattice["node_ids"][i:i + 2]
            for i in range(0, len(lattice["node_ids"]), 2)
        ]

        print(f"Running evaluate_metrics ({lattice_name}) job...")
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
                        "type": "SampleLattice",
                        "parameters": {
                            "lattice_data": {
                                "nodes": nodes,
                                "edges": edges,
                            },
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


def get_lattice_library() -> dict[str, Lattice]:
    r = requests.get(lattice_url)
    return r.json()


if __name__ == "__main__":
    main()

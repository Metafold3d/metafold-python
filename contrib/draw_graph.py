from matplotlib import pyplot
import networkx as nx
import numpy as np
from metafold.func import (
    CSGIntersect,
    EllipsoidPrimitive,
    GenerateSamplePoints,
    Redistance,
    SampleSurfaceLattice,
    SampleSurfaceLattice_Parameters,
    Threshold,
)
from metafold.nx import GraphEvaluator


def draw_graph(graph: nx.MultiDiGraph, font_family: str = "Inter") -> None:
    """Draw the given Metafold shape graph in topological order.
    """
    for layer, nodes in enumerate(nx.topological_generations(graph)):
        # multipartite_layout expects the layer as a node attribute, so add the
        # numeric layer value as a node attribute.
        for node in nodes:
            graph.nodes[node]["layer"] = layer

    # Compute the multipartite_layout using the "layer" node attribute
    pos = nx.multipartite_layout(graph, subset_key="layer", align="horizontal")
    # Reverse Y position
    for p in pos.values():
        p[1] = -p[1]

    fig, ax = pyplot.subplots()
    nx.draw_networkx(graph, pos=pos, node_size=800, node_shape="", with_labels=False, ax=ax)

    labels = dict((n, n.type) for n in graph.nodes)
    nx.draw_networkx_labels(
        graph,
        pos=pos,
        labels=labels,
        font_family=font_family,
        font_size=10,
        bbox=dict(facecolor="white"),
        ax=ax,
    )

    edge_labels = dict((e, e[2]) for e in graph.edges)
    nx.draw_networkx_edge_labels(
        graph,
        pos=pos,
        edge_labels=edge_labels,
        font_family=font_family,
        rotate=False,
        ax=ax
    )

    fig.tight_layout()
    pyplot.show()


if __name__ == "__main__":
    source = GenerateSamplePoints({
        "size": [2, 2, 2],
        "resolution": [64, 64, 64],
    })

    gyroidParams: SampleSurfaceLattice_Parameters = {
        "lattice_type": "Gyroid",
        "scale": [0.25, 0.25, 0.25],
    }

    f = Threshold(
        Redistance(
            CSGIntersect(
                SampleSurfaceLattice(source, gyroidParams),
                EllipsoidPrimitive(source, {"size": np.array([1, 1, 1])}),
            ),
        ),
    )
    e = GraphEvaluator()
    f(e)
    draw_graph(e.graph)

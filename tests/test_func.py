import numpy as np
from metafold.func_types import JSONEvaluator
from metafold.func import (
    CSGIntersect,
    EllipsoidPrimitive,
    GenerateSamplePoints,
    LoadVolume,
    PointSource,
    Redistance,
    SampleSurfaceLattice,
    SampleSurfaceLattice_Parameters,
    SampleVolume,
    Threshold,
    VolumeAsset,
)
from metafold.nx import GraphEvaluator


def test_build_graph_json():
    source = GenerateSamplePoints({
        "size": [2, 2, 2],
        "resolution": [64, 64, 64],
    })

    gyroidParams: SampleSurfaceLattice_Parameters = {
        "lattice_type": "Gyroid",
        "scale": [0.25, 0.25, 0.25],
    }


    # NOTE: This should fail to compile during type checking
    # f = Redistance(CSGIntersect(source, EllipsoidPrimitive(source)))

    want = {
        "operators": [
            {
                "type": "GenerateSamplePoints",
                "parameters": {
                    "size": [2, 2, 2],
                    "resolution": [64, 64, 64],
                },
            },
            {
                "type": "SampleSurfaceLattice",
                "parameters": {
                    "lattice_type": "Gyroid",
                    "scale": [0.25, 0.25, 0.25],
                },
            },
            {
                "type": "SampleBox",
                "parameters": {
                    "shape_type": "Ellipsoid",
                    "size": [1, 1, 1],
                },
            },
            {
                "type": "CSG",
                "parameters": {
                    "operation": "Intersect",
                },
            },
            {"type": "Redistance"},
            {"type": "Threshold"},
        ],
        "edges": [
            {"source": 0, "target": [1, "Points"]},   # GenerateSamplePoints -> SampleBox
            {"source": 0, "target": [2, "Points"]},   # GenerateSamplePoints -> SampleSurfaceLattice
            {"source": 1, "target": [3, "A"]},        # SampleSurfaceLattice -> CSG
            {"source": 2, "target": [3, "B"]},        #            SampleBox -> CSG
            {"source": 3, "target": [4, "Samples"]},  #                  CSG -> Redistance
            {"source": 4, "target": [5, "Samples"]},  #           Redistance -> Threshold
        ],
    }

    f = Threshold(
        Redistance(
            CSGIntersect(
                SampleSurfaceLattice(source, gyroidParams),
                EllipsoidPrimitive(source, {"size": np.array([1, 1, 1])}),
            ),
        ),
    )
    e = JSONEvaluator()
    f(e)

    assert e.json() == want

    # With deferred point source
    f = Threshold(
        Redistance(
            CSGIntersect(
                SampleSurfaceLattice(PointSource, gyroidParams),
                EllipsoidPrimitive(PointSource, {"size": np.array([1, 1, 1])}),
            ),
        ),
    )
    e = JSONEvaluator(source)
    f(e)

    assert e.json() == want


def test_build_graph_json_with_assets():
    source = GenerateSamplePoints({
        "size": [2, 2, 2],
        "resolution": [64, 64, 64],
    })

    volumeAsset: VolumeAsset = {
        "file_type": "Raw",
        "path": "foo.bin",
    }
    volume = LoadVolume(volumeAsset, {"resolution": [64, 64, 64]})

    f = Threshold(
        Redistance(
            SampleVolume(source, volume, {
                "volume_size": [2, 2, 2],
                "volume_offset": [-1, -1, -1],
            }),
        ),
    )
    e = JSONEvaluator()
    f(e)

    assert e.json() == {
        "operators": [
            {
                "type": "GenerateSamplePoints",
                "parameters": {
                    "size": [2, 2, 2],
                    "resolution": [64, 64, 64],
                },
            },
            {
                "type": "LoadVolume",
                "parameters": {
                    "volume_data": volumeAsset,
                    "resolution": [64, 64, 64],
                },
            },
            {
                "type": "SampleVolume",
                "parameters": {
                    "volume_size": [2, 2, 2],
                    "volume_offset": [-1, -1, -1],
                },
            },
            {"type": "Redistance"},
            {"type": "Threshold"},
        ],
        "edges": [
            {"source": 0, "target": [2, "Points"]},   # GenerateSamplePoints -> SampleVolume
            {"source": 1, "target": [2, "Volume"]},   #           LoadVolume -> SampleVolume
            {"source": 2, "target": [3, "Samples"]},  #         SampleVolume -> Redistance
            {"source": 3, "target": [4, "Samples"]},  #           Redistance -> Threshold
        ],
    }


def test_build_nx_graph():
    source = GenerateSamplePoints({
        "size": [2, 2, 2],
        "resolution": [64, 64, 64],
    })

    gyroidParams: SampleSurfaceLattice_Parameters = {
        "lattice_type": "Gyroid",
        "scale": [0.25, 0.25, 0.25],
    }

    edges = [
        # (source, target, key)
        ("GenerateSamplePoints", "SampleSurfaceLattice", "Points"),
        ("GenerateSamplePoints", "SampleBox", "Points"),
        ("SampleSurfaceLattice", "CSG", "A"),
        ("SampleBox", "CSG", "B"),
        ("CSG", "Redistance", "Samples"),
        ("Redistance", "Threshold", "Samples"),
    ]

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

    want = set(edges)
    for source_operator, target_operator, key in e.graph.edges:
        want.remove((source_operator.type, target_operator.type, key))
    assert len(want) == 0, f"{want} edges not found in graph"

    # With deferred point source
    f = Threshold(
        Redistance(
            CSGIntersect(
                SampleSurfaceLattice(PointSource, gyroidParams),
                EllipsoidPrimitive(PointSource, {"size": np.array([1, 1, 1])}),
            ),
        ),
    )
    e = GraphEvaluator(source)
    f(e)

    want = set(edges)
    for source_operator, target_operator, key in e.graph.edges:
        want.remove((source_operator.type, target_operator.type, key))
    assert len(want) == 0, f"{want} edges not found in graph"

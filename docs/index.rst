.. metafold documentation master file, created by
   sphinx-quickstart on Tue Jan 30 12:37:10 2024.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Metafold SDK for Python
=======================

Installation
------------

.. code-block::

    pip install metafold

Quickstart
----------

Create a :class:`metafold.MetafoldClient` to interact with the API. To do so you will
need :doc:`an access token and the ID of a project <init>` to perform operations
against. ::

    from metafold import MetafoldClient

    access_token = "..."
    project_id = "123"

    metafold = MetafoldClient(access_token, project_id)

.. _client-initialized:

With the client initialized, you can now start running jobs. For example, we can
evaluate the surface area of a single gyroid unit cell::

    job = metafold.jobs.run("evaluate_metrics", {
        "graph": {
            "operators": [
                {
                    "type": "GenerateSamplePoints",
                    "parameters": {
                        "size": [1.0, 1.0, 1.0],
                        "resolution": [128, 128, 128],
                    },
                },
                {
                    "type": "SampleSurfaceLattice",
                    "parameters": {
                        "lattice_type": "Gyroid",
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

    print(job.meta["surface_area"])

Jobs are expected to complete within minutes (with some exceptions). You may increase
the ``timeout`` when calling :meth:`metafold.jobs.JobsEndpoint.run`::

    job = metafold.jobs.run("...", params, timeout=600)  # 10 mins

Many jobs require assets. You can upload an asset to your project directly from disk::

    asset = metafold.assets.create("/path/to/mesh.obj")
    print(asset)

You can list the assets in the project. The list should include the asset you just
uploaded::

    assets = metafold.assets.list()
    for a in assets:
        print(a)

You can also filter the list for assets with a specific name. Filter queries use a
simple syntax, see the `API documentation`_ for more details. ::

    assets = metafold.assets.list(q="filename:mesh.obj")
    print(assets[0])

Assets are referenced in job parameters by **filename**. For example::

    job = metafold.jobs.run("sample_triangle_mesh", {
        "mesh_filename": asset.filename,  # "mesh.obj"
        "max_resolution": 128,
    })

Most jobs produce at least one asset. You may access them from the returned
:class:`metafold.jobs.Job` object::

    print(job.assets[0])

For more complete examples, please refer to the `examples`_ in the source code repo.

.. _API documentation: https://metafold3d.notion.site/Metafold-REST-API-059f01a419a74811a9d2dcafe75c871b#65833c70939d4d6490f2a4defe825d46
.. _examples: https://github.com/Metafold3d/metafold-python/tree/master/examples

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   init
   modules

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

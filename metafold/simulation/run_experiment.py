"""
run_experiment — declarative entry point for compression experiments.

Accepts a plain dict (or a zip containing mesh files + a JSON manifest)
and delegates to CompressionSimulation + CompressionExperiment.

The dict format mirrors the style of the prototype Grasshopper manifest so
that the same file a design tool exports can eventually drive the experiment
directly, and could in future be used to generate the results manifest too.

JSON manifest format
--------------------
{
    "project_name": "midsole_sweep",
    "created":      "2026-05-28T10:00:00",
    "generator":    "grasshopper-dtb-export",

    "parts": [
        {
            "type": "piston_cylinder",
            "velocity": [           # optional — defaults to DEFAULT_PISTON_VELOCITY
                [0.0,    0, 0,  0.0],
                [0.002,  0, 0, -1.25],
                [0.02,   0, 0,  0.0],
                [0.022,  0, 0,  1.0],
                [0.04,   0, 0,  0.0]
            ]
        },
        {"type": "piston_mesh", "file": "piston.ply", "velocity": [...]},
        {
            "type":           "mesh",
            "name":           "midsole",
            "material":       "default_midsole_nominal",
            "file":           "mid.ply",
            "representative": true
        }
    ],

    "varying": [
        {"part": "midsole", "files": ["v1.ply", "v2.ply", "v3.ply"]},
        {"part": "midsole", "material": [
            "default_midsole_nominal",
            "default_outsole",
            {
                "density": 200.0,
                "thermal_conductivity": 45,
                "specific_heat": 4.8e-4,
                "constitutive_model": {
                    "type": "comp_mooney_rivlin",
                    "params": {"he_constant_1": 1.2e5, "he_constant_2": 1.5e5, "he_PR": 0.43}
                }
            }
        ]},
        {"field": "max_time", "values": [0.02, 0.04]}
    ],

    "simulation": {
        "max_time": 0.04,
        "max_resolution": 512
    },

    "workflow_steps": [
        "compress",
        "force_displacement",
        {"step": "metrics", "parts": ["midsole", "outsole"]}
    ]
}

Available material presets
--------------------------
    Defaults:   "default_midsole_nominal", "default_outsole", "default_upper_foam",
                "default_piston_material", "default_support_material"
    Named:      "material_abs", "material_aluminum", "material_basf_epd",
                "material_basf_pp1400_xy", "material_basf_pp1400_z",
                "material_basf_rg3280", "material_basf_tpu01",
                "material_eos_pa11", "material_eos_tpe300",
                "material_epu_41", "material_epu_45",
                "material_nylon_6", "material_nylon_12",
                "material_pla", "material_stainless_steel",
                "material_ti64", "material_tpu"

Available workflow steps (default: all)
----------------------------------------
    "compute_bvh", "metrics", "compress", "von_mises_stress",
    "effective_strain", "force_displacement", "stress_strain",
    "particle_displacement", "energy_metrics"

Zip format (for run_experiment_from_zip)
-----------------------------------------
A zip containing:
  - experiment.json   the manifest (required, at the zip root)
  - *.ply / *.stl     mesh files referenced by parts[].file and varying[].files

Returns
-------
str — the Metafold project_id for the completed experiment.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Optional, Union
from zipfile import ZipFile

from metafold import MetafoldClient

import metafold.materials as _materials_module
from metafold.materials import Material
from metafold.simulation.compression_experiment import (
    CompressionExperiment,
    ExperimentVarying,
    VaryMaterial,
    VaryMesh,
    VarySimulationParameter,
)
from metafold.simulation.compression_simulation import (
    CompressionSimulation,
    ExperimentMesh,
    ExperimentPart,
    ExperimentPistonCylinder,
    ExperimentPistonMesh,
    SimulationParameters,
    WorkflowStep,
)

# Build preset lookup from all Material constants in the materials module.
# Keys are lowercased constant names, e.g. "default_midsole_nominal", "material_tpu".
_MATERIAL_PRESETS: dict[str, Material] = {
    name.lower(): obj
    for name, obj in vars(_materials_module).items()
    if isinstance(obj, Material)
}


def _resolve_material(value: Union[str, dict, Material]) -> Material:
    if isinstance(value, Material):
        return value
    if isinstance(value, dict):
        return Material.from_dict(value)
    key = value.lower()
    if key in _MATERIAL_PRESETS:
        return _MATERIAL_PRESETS[key]
    raise ValueError(
        f"Unknown material preset {value!r}. "
        f"Available: {list(_MATERIAL_PRESETS)}. "
        "Pass a Material instance or inline dict for custom materials."
    )


def _build_parts(parts_config: list[dict]) -> list[ExperimentPart]:
    parts: list[ExperimentPart] = []
    for entry in parts_config:
        part_type = entry.get("type", "mesh")

        if part_type == "piston_cylinder":
            kwargs = {}
            if "velocity" in entry:
                kwargs["velocity"] = entry["velocity"]
            parts.append(ExperimentPistonCylinder(**kwargs))

        elif part_type == "piston_mesh":
            kwargs = {"filename": entry["file"]}
            if "velocity" in entry:
                kwargs["velocity"] = entry["velocity"]
            parts.append(ExperimentPistonMesh(**kwargs))

        else:
            if "name" not in entry:
                raise ValueError(f"Mesh part is missing 'name': {entry}")
            if "material" not in entry:
                raise ValueError(f"Part {entry['name']!r} is missing 'material'")
            if "file" not in entry:
                raise ValueError(f"Part {entry['name']!r} is missing 'file'")

            parts.append(
                ExperimentMesh(
                    name=entry["name"],
                    material=_resolve_material(entry["material"]),
                    filename=entry["file"],
                    representative_part=entry.get("representative", False),
                )
            )
    return parts


def _build_varying(varying_config: list[dict]) -> list[ExperimentVarying]:
    varying: list[ExperimentVarying] = []
    for entry in varying_config:
        if "part" in entry and "files" in entry:
            files = entry["files"]
            if not isinstance(files, list):
                raise ValueError(
                    f"varying 'files' must be a list of filenames, got: {files!r}"
                )
            varying.append(VaryMesh(entry["part"], files))

        elif "part" in entry and "material" in entry:
            materials = entry["material"]
            if not isinstance(materials, list):
                materials = [materials]
            varying.append(
                VaryMaterial(entry["part"], [_resolve_material(m) for m in materials])
            )

        elif "field" in entry and "values" in entry:
            varying.append(VarySimulationParameter(entry["field"], entry["values"]))

        else:
            raise ValueError(f"Unrecognised varying entry: {entry}")
    return varying


def _build_workflow_steps(steps_config: list) -> list[WorkflowStep]:
    steps = []
    for entry in steps_config:
        if isinstance(entry, str):
            steps.append(WorkflowStep(entry))
        elif isinstance(entry, dict):
            if "step" not in entry:
                raise ValueError(f"workflow_steps entry is missing 'step': {entry}")
            part_names = entry.get("parts", [])
            steps.append(WorkflowStep(entry["step"], *part_names))
        else:
            raise ValueError(f"Unrecognised workflow_steps entry: {entry!r}")
    return steps


def _build_simulation_parameters(sim_config: dict) -> SimulationParameters:
    params = SimulationParameters()
    for field_path, value in sim_config.items():
        parts = field_path.split(".")
        obj = params
        for part in parts[:-1]:
            obj = getattr(obj, part)
        setattr(obj, parts[-1], value)
    return params


def run_experiment(
    config: dict,
    output_path: str = "",
    access_token: Optional[str] = None,
    base_url: str = "https://api.metafold3d.com/",
    credentials: Optional[dict] = None,
    wait_for_results: bool = False,
) -> str:
    """Create and run a compression experiment from a config dict.

    output_path overrides config["output_path"] when supplied, which is
    useful when the caller controls where results land (e.g. an API handler
    using a temp directory).

    Provide exactly one of:
    - access_token: a bearer token (e.g. user JWT forwarded from the request).
      base_url must also be set to match the token's audience.
    - credentials: dict with keys client_id, client_secret, auth_domain, base_url.
      Used for server-side service account auth — no env reads.
    - neither: CompressionSimulation reads credentials from the environment via
      dotenv (local / programmable use).

    By default this returns as soon as the simulation workflows have been
    dispatched (after assets are uploaded and prep workflows finish); results
    stay server-side. Pass wait_for_results=True to block until every
    simulation finishes and download the results into output_path.

    Returns the Metafold project_id for the experiment.
    """
    project_name = config.get("project_name", "")
    if not project_name:
        raise ValueError("project_name is required")

    resolved_output_path = output_path or config.get("output_path", "")
    if not resolved_output_path:
        raise ValueError("output_path must be provided in config or as an argument")

    ply_folder = config.get("ply_folder", "")
    project_id = config.get("project_id", "")

    parts = _build_parts(config.get("parts", []))
    varying = _build_varying(config.get("varying", []))
    sim_params = _build_simulation_parameters(config.get("simulation", {}))

    sim_kwargs: dict = dict(
        parts=parts,
        simulation_name=project_name,
        stl_folder_path=ply_folder or resolved_output_path,
        output_path=resolved_output_path,
        simulation_parameters=sim_params,
        project_id=project_id,
        project_name=project_name,
        create_project_if_needed=not bool(project_id),
    )
    if "workflow_steps" in config:
        sim_kwargs["workflow_steps"] = _build_workflow_steps(config["workflow_steps"])

    if access_token is not None:
        sim_kwargs["client"] = MetafoldClient(
            access_token=access_token,
            project_id=project_id or None,
            base_url=base_url,
        )
    elif credentials is not None:
        sim_kwargs["client"] = MetafoldClient(
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"],
            auth_domain=credentials.get("auth_domain", "metafold3d.us.auth0.com"),
            base_url=credentials.get("base_url", "https://api.metafold3d.com/"),
            project_id=project_id or None,
        )

    sim = CompressionSimulation(**sim_kwargs)

    CompressionExperiment(
        simulation=sim,
        varying=varying,
        auto_download_results=wait_for_results,
    )

    return sim.project_id


def run_experiment_from_zip(
    zip_path: Union[str, Path],
    output_path: str,
    project_id: str = "",
    access_token: Optional[str] = None,
    base_url: str = "https://api.metafold3d.com/",
    credentials: Optional[dict] = None,
    wait_for_results: bool = False,
) -> str:
    """Extract a zip containing experiment.json + mesh files and run the experiment.

    The zip must contain an experiment.json at its root. All mesh files
    referenced by parts[].file and varying[].files are resolved relative
    to the extracted directory.

    project_id, when provided, overrides any project_id in the manifest and
    skips project creation (the project already exists).

    access_token, when provided, is forwarded to run_experiment — see its
    docstring. When omitted, credentials are loaded from the environment.

    By default this returns once the simulation workflows are dispatched;
    pass wait_for_results=True to block until they finish and download the
    results into output_path (see run_experiment).

    Returns the Metafold project_id for the experiment.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        with ZipFile(zip_path) as zf:
            zf.extractall(tmp_dir)

        manifest_path = Path(tmp_dir) / "experiment.json"
        if not manifest_path.exists():
            found = [p.name for p in Path(tmp_dir).iterdir()]
            raise ValueError(
                f"Zip must contain an experiment.json at its root. Found: {found}"
            )

        config = json.loads(manifest_path.read_text())
        config["ply_folder"] = tmp_dir
        if project_id:
            config["project_id"] = project_id

        return run_experiment(
            config,
            output_path=output_path,
            access_token=access_token,
            base_url=base_url,
            credentials=credentials,
            wait_for_results=wait_for_results,
        )

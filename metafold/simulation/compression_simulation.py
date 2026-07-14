import copy
from dataclasses import dataclass, field
from enum import Enum
from shutil import copyfileobj
from typing import Any, Optional, Union
from io import BytesIO
import uuid

from requests import HTTPError
import yaml
from dotenv import load_dotenv  # type: ignore
from metafold import MetafoldClient
from pathlib import Path
from numpy.typing import DTypeLike
from simulation_configurator import (
    Simulation,
    Grid,
    BoundaryConditions,
    GeometryStore,
    Archive,
    Contact,
    Mpm,
)
from simulation_configurator.element import CompositeElement, Element
from simulation_configurator.grid import Face
from simulation_configurator.shapes import Box, File, Cylinder, Parallelepiped
from plyfile import PlyData, PlyElement
from tempfile import TemporaryDirectory
from time import sleep
from xml.etree import ElementTree
from zipfile import ZipFile
import json
import numpy as np
import os
import pandas as pd

from metafold.assets import Asset
from metafold.materials import (
    DEFAULT_PISTON_MATERIAL,
    DEFAULT_SUPPORT_MATERIAL,
    Material,
)
from metafold.projects import Access, ProjectType
from metafold.utils import sha256_file
from metafold.workflows import Workflow


DEFAULT_PISTON_VELOCITY = [
    [0.000000, 0, 0, 0.0000000],
    [0.000666, 0, 0, -0.8750000],
    [0.002000, 0, 0, -1.2500000],
    [0.004666, 0, 0, -1.3500000],
    [0.006666, 0, 0, -1.7500000],
    [0.010000, 0, 0, -2.1000000],
    [0.010666, 0, 0, -2.0000000],
    [0.012000, 0, 0, -1.9000000],
    [0.017334, 0, 0, -0.9000000],
    [0.020000, 0, 0, 0.0000000],
    [0.021334, 0, 0, 0.4084350],
    [0.023466, 0, 0, 1.0169675],
    [0.029334, 0, 0, 1.9527605],
    [0.032000, 0, 0, 1.8673950],
    [0.033334, 0, 0, 1.7003345],
    [0.034666, 0, 0, 1.4592990],
    [0.037334, 0, 0, 0.7984375],
    [0.040000, 0, 0, 0.0000000],
]

ZERO_VELOCITY = [
    [0.000, 0.0, 0.0, 0.0],
    [1.000, 0.0, 0.0, 0.0],
]


class BoundaryCondition(Enum):
    SYMMETRIC          = "symmetric"           # symmetry plane (acts as frictionless wall)
    VELOCITY_DIRICHLET = "velocity_dirichlet"  # velocity fixed to zero at the face
    VELOCITY_NEUMANN   = "velocity_neumann"    # zero velocity gradient (free face)


DEFAULT_BOUNDARY_CONDITIONS = {
    "x-": BoundaryCondition.SYMMETRIC,
    "x+": BoundaryCondition.SYMMETRIC,
    "y-": BoundaryCondition.SYMMETRIC,
    "y+": BoundaryCondition.SYMMETRIC,
    "z-": BoundaryCondition.VELOCITY_DIRICHLET,
    "z+": BoundaryCondition.VELOCITY_DIRICHLET,
}


def _velocity_neumann_face(side: str):
    # simulation_configurator.Face only provides fixed (symmetry) and unfixed
    # (velocity Dirichlet) faces; build the Neumann variant here until it can
    # move into a simulation-configurator release.
    face = CompositeElement("Face", {"side": side})
    bc_type = CompositeElement(
        "BCType",
        {"id": "all", "label": "Velocity", "var": "Neumann"},
    )
    bc_type.add(Element("value", data="[0.0, 0.0, 0.0]"))
    face.add(bc_type)
    return face


_FACE_BUILDERS = {
    BoundaryCondition.SYMMETRIC: Face.fixed,
    BoundaryCondition.VELOCITY_DIRICHLET: Face.unfixed,
    BoundaryCondition.VELOCITY_NEUMANN: _velocity_neumann_face,
}


def _normalize_boundary_conditions(
    boundary_conditions: dict,
) -> dict[str, BoundaryCondition]:
    """Merge per-face boundary conditions over the defaults.

    Values may be BoundaryCondition members or their string values (as parsed
    from an experiment manifest). Faces not present keep their default.
    """
    unknown = set(boundary_conditions) - set(DEFAULT_BOUNDARY_CONDITIONS)
    if unknown:
        raise ValueError(
            f"Unknown boundary condition face(s) {sorted(unknown)}; "
            f"expected faces {sorted(DEFAULT_BOUNDARY_CONDITIONS)}"
        )
    resolved = dict(DEFAULT_BOUNDARY_CONDITIONS)
    for side, bc in boundary_conditions.items():
        resolved[side] = BoundaryCondition(bc) if isinstance(bc, str) else bc
    return resolved


class ForceSource(Enum):
    BOUNDARY_FORCE       = "boundary_force"        # uses boundary_force_zminus (default)
    RIGID_REACTION_FORCE = "rigid_reaction_force"  # uses rigid reaction force of force_source_part


@dataclass
class SimulationParameters:
    init_time: float = 0.0
    output_int: float = 0.002
    max_time: float = 0.04
    delt_min: float = 0.0
    delt_max: float = 0.001
    timestep_multiplier: float = 0.25
    max_resolution: float = 512
    force_displacement_shift_mm: float = 0.0

    margin_xy: float = 0.01
    margin_z: float = 0.025

    points_per_cell: int = 2
    extra_cells: list[int] = field(default_factory=lambda: [1, 1, 1])
    patches: list[int] = field(default_factory=lambda: [4, 2, 2])

    # Per-face boundary conditions; faces omitted here use the default.
    boundary_conditions: dict[str, BoundaryCondition] = field(
        default_factory=lambda: dict(DEFAULT_BOUNDARY_CONDITIONS)
    )
    force_source: ForceSource = ForceSource.BOUNDARY_FORCE
    # Part whose rigid_reaction_force feeds force-displacement when
    # force_source is RIGID_REACTION_FORCE. Empty string means the piston.
    force_source_part: str = ""


@dataclass
class ExperimentPart:
    name: str
    material: Material


@dataclass
class ExperimentMesh(ExperimentPart):
    filename: str = ""


@dataclass
class ExperimentPrimitive(ExperimentPart):
    shape_parameters: dict = field(default_factory=dict)

    def get_bounds(self) -> tuple[np.ndarray, np.ndarray]:
        """Return (min, max) axis-aligned bounding box in metres.
        Override in concrete shape subclasses."""
        raise NotImplementedError(f"{type(self).__name__} must implement get_bounds()")


@dataclass
class ExperimentCylinder(ExperimentPrimitive):
    shape_parameters: dict = field(
        default_factory=lambda: {
            "top": [-0.001, 0.055, 0.045],
            "bottom": [-0.001, 0.055, 0.065],
            "radius": 0.020,
        }
    )

    def get_bounds(self) -> tuple[np.ndarray, np.ndarray]:
        top = np.array(self.shape_parameters["top"], dtype=np.float32)
        bot = np.array(self.shape_parameters["bottom"], dtype=np.float32)
        r = self.shape_parameters["radius"]
        return np.minimum(top, bot) - r, np.maximum(top, bot) + r


@dataclass
class ExperimentBox(ExperimentPrimitive):
    shape_parameters: dict = field(
        default_factory=lambda: {
            "min": [-0.001, -0.001, -0.001],
            "max": [0.001, 0.001, 0.001],
        }
    )

    def get_bounds(self) -> tuple[np.ndarray, np.ndarray]:
        return (
            np.array(self.shape_parameters["min"], dtype=np.float32),
            np.array(self.shape_parameters["max"], dtype=np.float32),
        )


@dataclass
class ExperimentParallelepiped(ExperimentPrimitive):
    shape_parameters: dict = field(
        default_factory=lambda: {
            "p1": [-0.025399, 0.114013, -0.001500],
            "p2": [0.024442, 0.110025, -0.001500],
            "p3": [-0.024442, 0.125975, -0.001500],
            "p4": [-0.025399, 0.114013, -0.025],
        }
    )

    def get_bounds(self) -> tuple[np.ndarray, np.ndarray]:
        pts = np.stack(
            [
                np.array(self.shape_parameters[k], dtype=np.float32)
                for k in ("p1", "p2", "p3", "p4")
            ]
        )
        return pts.min(axis=0), pts.max(axis=0)


@dataclass
class ExperimentPistonBase:
    velocity: Optional[list] = field(default_factory=lambda: DEFAULT_PISTON_VELOCITY)
    contact_type: str = "rigid"
    mu: float = 0.0


@dataclass
class ExperimentPistonMesh(ExperimentMesh, ExperimentPistonBase):
    name: str = "piston"
    material: Material = field(default_factory=lambda: DEFAULT_PISTON_MATERIAL)
    filename: str = "piston.ply"


@dataclass
class ExperimentPistonCylinder(ExperimentCylinder, ExperimentPistonBase):
    name: str = "piston"
    material: Material = field(default_factory=lambda: DEFAULT_PISTON_MATERIAL)


@dataclass
class ExperimentPistonBox(ExperimentBox, ExperimentPistonBase):
    name: str = "piston"
    material: Material = field(default_factory=lambda: DEFAULT_PISTON_MATERIAL)


@dataclass
class ExperimentSupportBase:
    name: str = "support"
    velocity: Optional[list] = field(default_factory=lambda: ZERO_VELOCITY)
    contact_type: str = "specified_friction"
    mu: float = 0.1


@dataclass
class ExperimentSupportMesh(ExperimentMesh, ExperimentSupportBase):
    material: Material = field(default_factory=lambda: DEFAULT_SUPPORT_MATERIAL)


@dataclass
class ExperimentSupportCylinder(ExperimentCylinder, ExperimentSupportBase):
    material: Material = field(default_factory=lambda: DEFAULT_SUPPORT_MATERIAL)


@dataclass
class ExperimentSupportBox(ExperimentBox, ExperimentSupportBase):
    material: Material = field(default_factory=lambda: DEFAULT_SUPPORT_MATERIAL)


@dataclass
class ExperimentSupportParallelepiped(ExperimentParallelepiped, ExperimentSupportBase):
    material: Material = field(default_factory=lambda: DEFAULT_SUPPORT_MATERIAL)


@dataclass
class ReferenceData:
    csv_path: Path = Path("")
    curve_zip_path: Path = Path("reference/reference.csv")
    loading_energy = 17.65
    unloading_energy = 12.60
    energy_absorbed = 5.06
    volume = 853000.0


class WorkflowStepType(Enum):
    COMPUTE_BVH = "compute_bvh"
    METRICS = "metrics"
    COMPRESS = "compress"
    VON_MISES_STRESS = "von_mises_stress"
    EFFECTIVE_STRAIN = "effective_strain"
    FORCE_DISPLACEMENT = "force_displacement"
    STRESS_STRAIN = "stress_strain"
    PARTICLE_DISPLACEMENT = "particle_displacement"
    ENERGY_METRICS = "energy_metrics"
    REDUCE_RESULTS = "reduce_results"


class WorkflowStep:
    type: WorkflowStepType
    part_names: list[str]

    def __init__(self, type: Union[WorkflowStepType, str], *part_names):
        self.type = WorkflowStepType(type) if isinstance(type, str) else type
        if len(part_names) == 1 and isinstance(part_names[0], list):
            self.part_names = part_names[0]
        else:
            self.part_names = list(part_names)

        # validate
        if self.part_names and self.type in [
            WorkflowStepType.STRESS_STRAIN,
            WorkflowStepType.FORCE_DISPLACEMENT,
        ]:
            raise ValueError(
                f"Specifying part_names is not supported for type {self.type.value}"
            )


class CompressionSimulation:
    @dataclass
    class PartInfo:
        part: ExperimentPart
        file_path: Optional[Path] = None
        asset: Optional[Asset] = None
        # Filename of the volume asset produced by sample-mesh in the prep
        # workflow. Downstream main-workflow jobs (metrics, compress) consume
        # this directly as an asset by filename.
        volume_filename: Optional[str] = None
        # Mesh bounds ({"min": [...], "max": [...]}, mm) reported by the
        # pass-1 preprocess job; used to density-match sampling resolutions.
        bounds: Optional[dict] = None
        # Output asset filenames from the pass-1 preprocess/BVH jobs, bound
        # as inputs to the pass-2 sample job so nothing is recomputed.
        preprocessed_filename: Optional[str] = None
        bvh_filename: Optional[str] = None
        # Sampling resolution (longest axis) assigned for the pass-2 sample job.
        sample_resolution: Optional[int] = None
        # From the prep metrics job; None until prep completes.
        interior_volume: Optional[float] = None
        patch: dict = field(default_factory=dict)
        jobs: dict[str, Any] = field(default_factory=lambda: {})
        part_unique_name = ""
        material_index: int = 0
        material_name: str = ""
        # When True the part participates in material-index numbering and
        # gets a geometry/material block in the UPS, but is excluded from
        # contacts (so it's non-interacting) and skipped in the results
        # download. Used by VaryMesh to "null out" a mesh per-sim while
        # keeping material indices consistent across sims.
        disabled: bool = False

        def to_state_dict(self) -> dict:
            return {
                "part_unique_name": self.part_unique_name,
                "material_index": self.material_index,
                "material_name": self.material_name,
                "jobs": self.jobs,
                "is_piston": isinstance(self.part, ExperimentPistonBase),
                "part_name": self.part.name,
                "disabled": self.disabled,
                "interior_volume": self.interior_volume,
            }

        def restore_from_state_dict(self, saved: dict):
            self.part_unique_name = saved["part_unique_name"]
            self.material_index = saved["material_index"]
            self.material_name = saved["material_name"]
            self.jobs = saved["jobs"]
            self.disabled = saved.get("disabled", False)
            self.interior_volume = saved.get("interior_volume")

    client: MetafoldClient
    project_id: str = ""
    stl_folder: Optional[Path] = None
    out_dir: Optional[Path] = None
    results: list = []
    simulation_name: str = ""
    simulation_parameters: SimulationParameters
    piston_velocity: list[list[float]]

    create_project_if_needed: bool = False
    force_reupload_files: bool = False

    reference_data: ReferenceData

    ups: Optional[Any] = None
    manifest: dict = {}

    part_infos: list[PartInfo]

    workflow_steps: list[WorkflowStep]
    workflow_yaml: str = ""
    workflow_jobs: dict[str, dict] = {}
    workflow_params: dict[str, Any] = {}
    workflow_assets: dict[str, Any] = {}
    workflow: Optional[Workflow] = None
    use_legacy_results_format: bool = False
    project_name: str = ""

    prep_workflows: list[Workflow] = []
    prep_workflow_batch_size: int = 10
    write_ups: bool = True
    # Sample spacing (mm) anchored to the union ("total box") of every part's
    # bounds: longest_axis(total_box) / (max_resolution - 1). Cached so
    # experiment variants sampled later match the base simulation's density.
    sample_spacing: Optional[float] = None

    def __init__(
        self,
        parts: list[ExperimentPart],
        simulation_name: str,
        project_id: str = "",
        stl_folder_path: str = "PLY",
        env_source: str | None = ".env.dev",
        output_path: str = "",
        client: Optional[MetafoldClient] = None,
        simulation_parameters: SimulationParameters = SimulationParameters(),
        reference_data: ReferenceData = ReferenceData(),
        workflow_steps: list[Union[WorkflowStep, tuple, WorkflowStepType, str]] = [
            WorkflowStep(WorkflowStepType.COMPUTE_BVH),
            WorkflowStep(WorkflowStepType.METRICS),
            WorkflowStep(WorkflowStepType.COMPRESS),
            WorkflowStep(WorkflowStepType.VON_MISES_STRESS),
            WorkflowStep(WorkflowStepType.EFFECTIVE_STRAIN),
            WorkflowStep(WorkflowStepType.FORCE_DISPLACEMENT),
            # stress_strain is opt-in (not default): callers add it via workflow_steps.
            WorkflowStep(WorkflowStepType.PARTICLE_DISPLACEMENT),
            WorkflowStep(WorkflowStepType.ENERGY_METRICS),
            # reduce-results is auto-added in build_workflow (not a step).
        ],
        force_reupload_files=False,
        prep_workflow_batch_size: int = 10,
        create_project_if_needed: bool = True,
        project_name: str = "",
        use_legacy_results_format: bool = False,
        write_ups: bool = True,
    ):
        if not output_path:
            if project_name:
                output_path = project_name
            else:
                output_path = "data"  # default

        self.simulation_name = simulation_name
        self.simulation_parameters = simulation_parameters
        self.reference_data = reference_data
        self.workflow_steps = self._clean_workflow_steps_input(workflow_steps)
        self.force_reupload_files = force_reupload_files
        self.prep_workflow_batch_size = prep_workflow_batch_size
        self.write_ups = write_ups
        self.use_legacy_results_format = use_legacy_results_format
        self.create_project_if_needed = create_project_if_needed
        self.project_name = project_name

        # build the parts list
        self.part_infos = []
        for part in parts:
            inner_part = CompressionSimulation.PartInfo(part)
            inner_part.part_unique_name = part.name
            if isinstance(part, ExperimentPistonBase):
                # pistons have to go first
                self.part_infos.insert(0, inner_part)
            else:
                self.part_infos.append(inner_part)

        self.setup_ply_files(stl_folder_path)
        self.setup_results(output_path)
        if client is None:
            self.client = self.setup_client(env_source, project_id)
        else:
            self.client = client

    def _write_ups(self, content: str, filename: str) -> None:
        if self.write_ups and self.out_dir is not None:
            (self.out_dir / filename).write_text(content)

    @staticmethod
    def _clean_workflow_steps_input(workflow_steps_in: list):
        workflow_steps = []
        for step_in in workflow_steps_in:
            if isinstance(step_in, WorkflowStep):
                step = step_in
            elif isinstance(step_in, WorkflowStepType):
                step = WorkflowStep(type=step_in)
            elif isinstance(step_in, str):
                step = WorkflowStep(type=WorkflowStepType(step_in))
            elif isinstance(step_in, tuple):
                step = WorkflowStep(*step_in)
            else:
                raise ValueError(f"Unknown value in workflow_steps {step}")
            workflow_steps.append(step)
        return workflow_steps

    def prepare(self):
        self.populate_assets()
        self.sample_assets()
        self.collect_sampled_volumes()
        self.create_sim_config()
        self.build_workflow()

    def cancel(self):
        for prep_workflow in self.prep_workflows:
            if prep_workflow.state not in ["success", "failure", "canceled"]:
                self.client.workflows.cancel(prep_workflow.id)
        self.prep_workflows = []

        if self.workflow is not None and self.workflow.state not in [
            "success",
            "failure",
            "canceled",
        ]:
            self.client.workflows.cancel(self.workflow.id)
            self.workflow = None

    def run(self, upload_server_manifest: bool = False):
        if not self.workflow_yaml:
            self.prepare()
        self.run_workflow()
        if upload_server_manifest:
            self.upload_server_manifest()

    def download_results(self):
        self.write_results()

    def setup_results(self, output_path):
        self.out_dir = Path(output_path)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.results = []
        self.reload_results()

    @property
    def results_filename(self) -> Path:
        assert self.out_dir is not None
        return self.out_dir / f"{self.simulation_name}_results.json"

    def _save_results(self):
        state = {
            "results": self.results,
            "part_infos": [p.to_state_dict() for p in self.part_infos],
        }
        with open(self.results_filename, "w") as f:
            json.dump(state, f, indent=2)

    def reload_results(self):
        """Reload persisted results and part-info state from disk if the
        results file exists."""
        self.results = []
        if not self.results_filename.is_file():
            return
        with open(self.results_filename) as f:
            state = json.load(f)

        # Back-compat: if the file is a bare list, it's pre-state-save
        if isinstance(state, list):
            self.results = state
            return

        self.results = state.get("results", [])
        saved_parts = state.get("part_infos", [])
        # Restore part_info fields by matching on part_name
        for saved in saved_parts:
            for p in self.part_infos:
                if p.part.name == saved["part_name"]:
                    p.restore_from_state_dict(saved)
                    break

    @staticmethod
    def cancel_active_workflows(client: MetafoldClient, project_id: str) -> list[str]:
        """Cancel all in-flight (pending/started) workflows for a project.

        Returns the number of workflows cancelled. Used when re-running an
        experiment on an existing project, whose previous results we're about
        to overwrite anyway.
        """
        cancelled = []
        for state in ("pending", "started"):
            for wf in client.workflows.list(q=f"state:{state}", project_id=project_id):
                try:
                    client.workflows.cancel(wf.id, project_id=project_id)
                    cancelled.append(wf.id)
                except HTTPError:
                    # Workflow already finished/uncancellable — ignore and move on.
                    pass
        return cancelled

    @staticmethod
    def find_or_create_project(
        project_name: str,
        access_token: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        auth_domain: str = "metafold3d.us.auth0.com",
        base_url: str = "https://api.metafold3d.com/",
        cancel_existing_workflows: bool = True,
    ) -> str:
        """Find an existing project by name or create a new one.

        Supply either access_token (server context — never reads from env) or
        client_id + client_secret (local/programmable use, reads from env via
        setup_client). base_url must match the audience the token was issued for.

        When cancel_existing_workflows is True and an existing project is
        reused, its running workflows are cancelled first.

        Returns the project_id string.
        """
        client = MetafoldClient(
            access_token=access_token,
            client_id=client_id,
            client_secret=client_secret,
            auth_domain=auth_domain,
            base_url=base_url,
        )
        # Quote the project_name string for multi-word name searchess
        existing = [
            p for p in client.projects.list(q=f'name:"{project_name}"')
            if p.name == project_name  # ensure full match
        ]
        if existing:
            project_id = existing[0].id
            if cancel_existing_workflows:
                CompressionSimulation.cancel_active_workflows(client, project_id)
            return project_id
        created = client.projects.create(
            project_name,
            access=Access.PRIVATE,
            type=ProjectType.DIGITAL_TEST_BENCH_EXPERIMENT,
        )
        return created.id

    def setup_client(self, env_source, project_id) -> MetafoldClient:
        if env_source is not None:
            load_dotenv(env_source)

        if not project_id:
            self.project_id = os.environ.get("METAFOLD_PROJECT_ID", "")
        else:
            self.project_id = project_id

        if not project_id and (self.project_name or self.create_project_if_needed):
            if self.project_name == "":
                self.project_name = "experiment_" + str(uuid.uuid4())
            self.project_id = CompressionSimulation.find_or_create_project(
                self.project_name,
                client_id=os.environ["METAFOLD_CLIENT_ID"],
                client_secret=os.environ["METAFOLD_CLIENT_SECRET"],
                auth_domain=os.environ.get("METAFOLD_AUTH_DOMAIN", "metafold3d.us.auth0.com"),
                base_url=os.environ.get("METAFOLD_BASE_URL", "https://api.metafold3d.com/"),
            )

        if self.project_id:
            self.client = MetafoldClient(
                project_id=self.project_id,
                client_id=os.environ["METAFOLD_CLIENT_ID"],
                client_secret=os.environ["METAFOLD_CLIENT_SECRET"],
                auth_domain=os.environ["METAFOLD_AUTH_DOMAIN"],
                base_url=os.environ["METAFOLD_BASE_URL"],
            )
            return self.client
        else:
            raise ValueError('Must have one of project_id, project_name, or create_project_if_needed ')

    @staticmethod
    def _resolve_stl_path(
        stl_filename: str, stl_folder_path: Path, name: str
    ) -> Optional[Path]:
        if stl_filename is None:
            return None
        p = Path(stl_filename)

        # If it has an extension, resolve it directly
        if p.suffix:
            candidate = p if p.is_absolute() else stl_folder_path / p
            if candidate.is_file():
                return candidate
            raise ValueError(f"STL file for part '{name}' not found: {candidate}")

        # No extension — try both, prefer .ply
        base = p if p.is_absolute() else stl_folder_path / p
        ply = base.with_suffix(".ply")
        stl = base.with_suffix(".stl")

        if ply.is_file():
            return ply
        if stl.is_file():
            return stl

        raise ValueError(f"STL file for part '{name}' not found: {base}(.ply/.stl)")

    def resolve_file_path(self, part_info):
        if hasattr(part_info.part, "filename"):
            part_info.file_path = self._resolve_stl_path(
                part_info.part.filename, self.stl_folder, part_info.part_unique_name
            )
            # just in case we had a fully or partially specified filename, clean it up here
            if not part_info.file_path is None:
                part_info.part.filename = part_info.file_path.name

    def setup_ply_files(self, stl_folder_path):
        # Folder containing your STL files
        self.stl_folder = Path(stl_folder_path).resolve()

        for p in self.part_infos:
            self.resolve_file_path(p)

    def populate_assets(self, part_infos=None):
        if part_infos is None:
            part_infos = self.part_infos

        for info in part_infos:
            if info.file_path and info.asset is None:
                # Quote the filename so the search parser keeps it as one term,
                # and match it exactly (the search is a case-insensitive ILIKE).
                existing = [
                    a for a in self.client.assets.list(q=f'filename:"{info.part.filename}"')
                    if a.filename == info.part.filename
                ]
                asset = None
                if existing:
                    asset = existing[0]
                    checksum = sha256_file(info.file_path)
                    if asset.checksum != checksum or self.force_reupload_files:
                        # file has changed so replace it
                        self.client.assets.delete(asset_id=asset.id)
                        asset = None
                if asset is None:
                    asset = self.client.assets.create(str(info.file_path))
                info.asset = asset

    def _build_preprocess_workflow_for_batch(self, batch: list) -> tuple[str, dict, dict]:
        """Build the pass-1 prep workflow: preprocess (+ BVH) per part. The
        preprocess job outputs each mesh's exact bounds, used to density-match
        the pass-2 sampling resolutions. No sampling happens in this pass."""
        jobs: dict = {}
        params: dict = {}
        assets: dict = {}

        for part_info in batch:
            if not hasattr(part_info.part, "filename"):
                continue
            if part_info.part.filename is None:
                continue
            unique_name = part_info.part_unique_name

            preprocess_job = f"preprocess-mesh-{unique_name}"
            jobs[preprocess_job] = {"type": "mesh/preprocess"}
            assets[f"{preprocess_job}.mesh"] = part_info.part.filename
            part_info.jobs["preprocess-mesh"] = preprocess_job

            if self._get_step(WorkflowStepType.COMPUTE_BVH, part_info.part.name):
                compute_bvh_job = f"compute-bvh-{unique_name}"
                jobs[compute_bvh_job] = {
                    "type": "mesh/compute-bvh",
                    "needs": [preprocess_job],
                    "assets": {"mesh": preprocess_job},
                }
                part_info.jobs["compute-bvh"] = compute_bvh_job

        workflow_yaml = yaml.dump({"jobs": jobs}, default_flow_style=False)
        return workflow_yaml, params, assets

    def _build_sample_workflow_for_batch(self, batch: list) -> tuple[str, dict, dict]:
        """Build the pass-2 sampling workflow: one implicit/from-mesh job per
        part at its density-matched resolution, reusing the preprocessed mesh
        and BVH assets produced in pass 1."""
        jobs: dict = {}
        params: dict = {}
        assets: dict = {}

        for part_info in batch:
            if not hasattr(part_info.part, "filename"):
                continue
            if part_info.part.filename is None:
                continue
            unique_name = part_info.part_unique_name

            sample_mesh_job = f"sample-mesh-{unique_name}"
            if part_info.preprocessed_filename:
                # Bind the pass-1 outputs directly; nothing is recomputed.
                jobs[sample_mesh_job] = {"type": "implicit/from-mesh"}
                assets[f"{sample_mesh_job}.mesh"] = part_info.preprocessed_filename
                if part_info.bvh_filename:
                    assets[f"{sample_mesh_job}.bvh"] = part_info.bvh_filename
            else:
                # Pass-1 outputs unavailable for this part: fall back to the
                # full in-workflow chain (slightly wasteful, never wrong).
                preprocess_job = f"preprocess-mesh-{unique_name}"
                jobs[preprocess_job] = {"type": "mesh/preprocess"}
                assets[f"{preprocess_job}.mesh"] = part_info.part.filename
                part_info.jobs["preprocess-mesh"] = preprocess_job

                sample_mesh_def: dict = {
                    "type": "implicit/from-mesh",
                    "needs": [preprocess_job],
                    "assets": {"mesh": preprocess_job},
                }
                if self._get_step(WorkflowStepType.COMPUTE_BVH, part_info.part.name):
                    compute_bvh_job = f"compute-bvh-{unique_name}"
                    jobs[compute_bvh_job] = {
                        "type": "mesh/compute-bvh",
                        "needs": [preprocess_job],
                        "assets": {"mesh": preprocess_job},
                    }
                    part_info.jobs["compute-bvh"] = compute_bvh_job
                    sample_mesh_def["needs"].append(compute_bvh_job)
                    sample_mesh_def["assets"]["bvh"] = compute_bvh_job
                jobs[sample_mesh_job] = sample_mesh_def

            resolution = part_info.sample_resolution or int(
                self.simulation_parameters.max_resolution
            )
            params[f"{sample_mesh_job}.resolution"] = f"{resolution}"
            part_info.jobs["sample-mesh"] = sample_mesh_job

            # Metrics run in prep (not the main workflow) so interior volume
            # is known before dispatch, when the server manifest is uploaded.
            if self._is_analysis_target(part_info.part) and self._get_step(
                WorkflowStepType.METRICS, part_info.part.name
            ):
                metrics_job = f"metrics-{unique_name}"
                jobs[metrics_job] = {
                    "type": "implicit/metrics",
                    "needs": [sample_mesh_job],
                    "assets": {"volume": sample_mesh_job},
                    "parameters": {
                        "volume_size": {"job": sample_mesh_job, "parameter": "patch_size"},
                        "volume_offset": {"job": sample_mesh_job, "parameter": "patch_offset"},
                        "volume_resolution": {"job": sample_mesh_job, "parameter": "patch_resolution"},
                    },
                }
                part_info.jobs["metrics"] = metrics_job

        workflow_yaml = yaml.dump({"jobs": jobs}, default_flow_style=False)
        return workflow_yaml, params, assets

    def _run_workflow_batches(self, batches: list, build_workflow_fn) -> list:
        """Dispatch one workflow per batch (all in parallel), then wait for
        every workflow to finish. Raises if any failed."""
        workflows = []
        for batch in batches:
            workflow_yaml, params, assets = build_workflow_fn(batch)
            wf = self.client.workflows.run_async(
                workflow_yaml, parameters=params, assets=assets
            )
            workflows.append(wf)

        for i, wf in enumerate(workflows):
            while wf.state not in ["success", "failure", "canceled"]:
                sleep(1)
                wf = self.client.workflows.get(wf.id)
            workflows[i] = wf

        failed = [wf for wf in workflows if wf.state != "success"]
        if failed:
            raise RuntimeError(f"{len(failed)} prep workflow(s) failed")
        return workflows

    @staticmethod
    def _job_output_asset_filename(job) -> Optional[str]:
        """First output asset filename of a job, preferring the named outputs
        mapping and falling back to the deprecated flat asset list."""
        outputs = getattr(job, "outputs", None)
        named = getattr(outputs, "assets", None) if outputs is not None else None
        if isinstance(named, dict):
            for asset in named.values():
                filename = getattr(asset, "filename", None)
                if filename:
                    return filename
        for asset in getattr(job, "assets", None) or []:
            filename = getattr(asset, "filename", None)
            if filename:
                return filename
        return None

    def _collect_preprocess_outputs(self, part_infos: list, workflows: list):
        """Read mesh bounds and output asset filenames from the pass-1
        preprocess/BVH jobs onto each part_info."""
        jobs_by_name = {
            job.name: job
            for wf in workflows
            for job_id in wf.jobs
            if (job := self.client.jobs.get(job_id)) is not None
        }
        for info in part_infos:
            pre_job = jobs_by_name.get(info.jobs.get("preprocess-mesh", ""), None)
            if pre_job is None:
                continue

            outputs = getattr(pre_job, "outputs", None)
            out_params = getattr(outputs, "params", None) if outputs is not None else None
            if isinstance(out_params, dict) and "bounds" in out_params:
                bounds = out_params["bounds"]
                info.bounds = json.loads(bounds) if isinstance(bounds, str) else bounds
            info.preprocessed_filename = self._job_output_asset_filename(pre_job)

            bvh_job = jobs_by_name.get(info.jobs.get("compute-bvh", ""), None)
            if bvh_job is not None:
                info.bvh_filename = self._job_output_asset_filename(bvh_job)

    @staticmethod
    def _bounds_longest_axis(bounds: dict) -> float:
        mn = np.array(bounds["min"], dtype=np.float64)
        mx = np.array(bounds["max"], dtype=np.float64)
        return float(np.max(mx - mn))

    @staticmethod
    def _part_bounds_mm(info):
        """(min, max) axis-aligned bounds of a part in mm, or None. Mesh parts
        report bounds via the pass-1 preprocess job (mm); primitives report
        them analytically via get_bounds() (metres)."""
        part = info.part
        if isinstance(part, ExperimentPrimitive):
            pmin, pmax = part.get_bounds()
            return (
                np.array(pmin, dtype=np.float64) * 1000.0,
                np.array(pmax, dtype=np.float64) * 1000.0,
            )
        if info.bounds:
            return (
                np.array(info.bounds["min"], dtype=np.float64),
                np.array(info.bounds["max"], dtype=np.float64),
            )
        return None

    def _union_bounds_mm(self, part_infos: list):
        """Union ("total box") of every part's bounds in mm, or None."""
        mins, maxs = [], []
        for info in part_infos:
            b = self._part_bounds_mm(info)
            if b is not None:
                mins.append(b[0])
                maxs.append(b[1])
        if not mins:
            return None
        return np.min(mins, axis=0), np.max(maxs, axis=0)

    def _ensure_sample_spacing(self, part_infos: list):
        """Set sample_spacing (mm) from the total box of all parts, if unset.
        Anchoring to the union — not one 'representative' part — makes
        max_resolution the resolution of the whole simulation's longest axis."""
        if self.sample_spacing is not None:
            return
        max_resolution = max(2, int(self.simulation_parameters.max_resolution))
        union = self._union_bounds_mm(part_infos)
        if union is not None:
            longest = float(np.max(union[1] - union[0]))
            if longest > 0:
                self.sample_spacing = longest / (max_resolution - 1)

    def _assign_sample_resolutions(self, all_infos: list, mesh_infos: list):
        """Anchor sample spacing to the total box (union of all part bounds),
        then give each mesh a resolution scaled to its own size so every part
        samples at the same spatial density."""
        max_resolution = max(2, int(self.simulation_parameters.max_resolution))
        self._ensure_sample_spacing(all_infos)

        for info in mesh_infos:
            if self.sample_spacing and info.bounds:
                longest = self._bounds_longest_axis(info.bounds)
                info.sample_resolution = max(
                    2, int(round(longest / self.sample_spacing)) + 1
                )
            else:
                # Fallback: sample at max_resolution over the part's own bounds.
                info.sample_resolution = max_resolution

    def sample_assets(self, part_infos=None):
        if part_infos is None:
            part_infos = self.part_infos

        mesh_parts = [p for p in part_infos if hasattr(p.part, "filename")]
        batch_size = self.prep_workflow_batch_size
        batches = [
            mesh_parts[i : i + batch_size]
            for i in range(0, max(len(mesh_parts), 1), batch_size)
        ]

        # Pass 1: preprocess (+ BVH) every mesh. The preprocess job reports
        # each mesh's exact bounds without sampling anything.
        preprocess_workflows = self._run_workflow_batches(
            batches, self._build_preprocess_workflow_for_batch
        )
        self._collect_preprocess_outputs(mesh_parts, preprocess_workflows)

        # Anchor sample spacing to the total box (union of all parts, primitives
        # included) so every part samples at the same spatial density.
        self._assign_sample_resolutions(part_infos, mesh_parts)

        # Pass 2: sample each mesh at its density-matched resolution, reusing
        # the preprocessed/BVH assets from pass 1.
        sample_workflows = self._run_workflow_batches(
            batches, self._build_sample_workflow_for_batch
        )

        self.prep_workflows = preprocess_workflows + sample_workflows

    def collect_sampled_volumes(self, part_infos=None):
        if part_infos is None:
            part_infos = self.part_infos

        # Build a name → job lookup across all prep workflows so we can find
        # the right job for each part regardless of which batch it ran in.
        prep_workflow_jobs = {
            job.name: job
            for prep_workflow in self.prep_workflows
            for job_id in prep_workflow.jobs
            if (job := self.client.jobs.get(job_id)) is not None
        }
        for info in part_infos:
            sample_job = prep_workflow_jobs.get(info.jobs.get("sample-mesh", ""), None)
            if sample_job is None:
                continue

            # Patch info comes from the sample-mesh job's output params,
            # describing the volume's size/offset/resolution in metres.
            mesh_patch = sample_job.outputs.params
            info.patch = {
                "size": json.loads(mesh_patch["patch_size"]),
                "offset": json.loads(mesh_patch["patch_offset"]),
                "resolution": json.loads(mesh_patch["patch_resolution"]),
            }

            # The .bin file is the actual volume data we want downstream jobs
            # to consume. Falls back to any non-empty filename in case the
            # asset extension changes.
            volume_asset = next(
                (a for a in sample_job.assets if a.filename.endswith(".bin")), None
            )
            if volume_asset is None:
                volume_asset = next((a for a in sample_job.assets if a.filename), None)
            if volume_asset is not None:
                info.volume_filename = volume_asset.filename

            metrics_job = prep_workflow_jobs.get(info.jobs.get("metrics", ""))
            if metrics_job is not None:
                raw = metrics_job.outputs.params.get("interior_volume")
                if raw is not None:
                    info.interior_volume = float(raw)

    def _total_interior_volume(self, workflow: Optional[Workflow] = None) -> float:
        """Sum interior volumes across analysis-target parts. Falls back to
        the main-workflow metrics readback for experiments dispatched before
        metrics moved to the prep workflow."""
        total = 0.0
        for part_info in self.part_infos:
            if not self._is_analysis_target(part_info.part) or part_info.disabled:
                continue
            if part_info.interior_volume is not None:
                total += part_info.interior_volume
                continue
            metrics_job = part_info.jobs.get("metrics", "")
            if workflow is not None and metrics_job:
                raw = workflow.get_parameter(f"{metrics_job}.interior_volume")
                if raw is not None:
                    total += float(raw)
        return total

    def get_part_info(self, name):
        for info in self.part_infos:
            if info.part.name == name:
                return info
        return None

    def create_sim_config(self, name_suffix=""):
        """
        The grid spans the total box (union of every part's bounds) and is
        sized by the shared sample spacing — no representative part.
        Piston velocity is [0,0,0] in the UPS — actual motion driven by velocity.txt.
        """
        name = self.simulation_name

        sim = Simulation(
            name,
            max_time=self.simulation_parameters.max_time,
            init_time=self.simulation_parameters.init_time,
            delt_min=self.simulation_parameters.delt_min,
            delt_max=self.simulation_parameters.delt_max,
            timestep_multiplier=self.simulation_parameters.timestep_multiplier,
        )

        # Total box: union of every part's bounding box so nothing is clipped.
        # Primitives report bounds via get_bounds() in metres, mesh parts via
        # their sampled patch (offset/size in mm).
        grid_min = np.array([np.inf, np.inf, np.inf], dtype=np.float32)
        grid_max = np.array([-np.inf, -np.inf, -np.inf], dtype=np.float32)
        for info in self.part_infos:
            part = info.part
            if isinstance(part, ExperimentPrimitive):
                pmin, pmax = part.get_bounds()
            elif info.patch:
                pmin = np.array(info.patch["offset"], dtype=np.float32) / 1000.0
                pmax = np.array(info.patch["size"], dtype=np.float32) / 1000.0 + pmin
            else:
                continue
            grid_min = np.minimum(grid_min, pmin)
            grid_max = np.maximum(grid_max, pmax)

        # Apply margins after all parts are included. Note z- gets no margin
        # since the bottom of the grid is the support boundary the stack sits on
        grid_min[:2] -= self.simulation_parameters.margin_xy
        grid_max[:2] += self.simulation_parameters.margin_xy
        grid_max[2] += self.simulation_parameters.margin_z

        grid_size = grid_max - grid_min
        # Every part is sampled at this uniform (isotropic) spacing, so the grid
        # cells match particle spacing. mm -> m.
        self._ensure_sample_spacing(self.part_infos)
        spacing = (self.sample_spacing or 1.0) * 1e-3
        grid_resolution = np.ceil(
            grid_size / (self.simulation_parameters.points_per_cell * spacing)
        ).astype(np.int32)

        grid = Grid(
            {
                "size": grid_size.tolist(),
                "offset": grid_min.tolist(),
                "resolution": grid_resolution.tolist(),
                "extraCells": self.simulation_parameters.extra_cells,
                "patches": self.simulation_parameters.patches,
            }
        )
        bcs = BoundaryConditions()
        boundary_conditions = _normalize_boundary_conditions(
            self.simulation_parameters.boundary_conditions
        )
        for side, bc in boundary_conditions.items():
            bcs._sub_elements[side] = _FACE_BUILDERS[bc](side)
        grid.add(bcs)

        store = GeometryStore()

        material_index = 0
        for info in self.part_infos:
            part = info.part
            material_name = f"{info.part.name}{name_suffix}_mat"
            info.material_name = material_name
            info.material_index = material_index
            material_dict = part.material.to_dict()
            store.add_material(material_name, material_dict, force=True)
            material_index += 1

        for info in self.part_infos:
            part = info.part
            material_name = info.material_name
            geometry_element = None
            common_attribs = {
                "material": material_name,
                "res": [2, 2, 2],
                "velocity": [
                    0,
                    0,
                    0,
                ],  # actual motion driven by velocity.txt via rigid contact
                "temperature": 300,
            }
            element_name = f"{info.part.name}{name_suffix}"
            # rigid parts (piston/support) get 1 or 2, deformable meshes get default
            if isinstance(part, ExperimentPistonBase):
                common_attribs["color"] = 1
            elif isinstance(part, ExperimentSupportBase):
                common_attribs["color"] = 2

            if isinstance(part, ExperimentCylinder):
                geometry_element = Cylinder(
                    element_name, part.shape_parameters, **common_attribs
                )
            elif isinstance(part, ExperimentBox):
                geometry_element = Box(
                    element_name, part.shape_parameters, **common_attribs
                )
            elif isinstance(part, ExperimentParallelepiped):
                geometry_element = Parallelepiped(
                    element_name, part.shape_parameters, **common_attribs
                )
            elif isinstance(part, ExperimentMesh):
                geometry_element = File(
                    element_name, f"{element_name}.pts", **common_attribs
                )
            else:
                raise RuntimeError(f"Unsupported part type: {type(part).__name__}")
            store.add(geometry_element)

        outputs_indices_key = ",".join(str(i) for i in range(len(self.part_infos)))
        all_outputs = [
            "boundary_force_zminus",
            "boundary_force_zplus",
            "kinetic_energy",
            "strain_energy",
        ]
        if self.simulation_parameters.force_source == ForceSource.RIGID_REACTION_FORCE:
            all_outputs.append("rigid_reaction_force")
        archive = Archive(
            outputs={
                outputs_indices_key: ["deformation_measure", "position", "stress"],
                "all": all_outputs,
            },
            output_interval=self.simulation_parameters.output_int,
        )

        # One rigid contact per rigid body (piston + each support).
        # Each contact pairs that rigid body with all enabled deformable parts.
        deformable_indices = [
            i
            for i, info in enumerate(self.part_infos)
            if not (
                isinstance(info.part, ExperimentPistonBase)
                or isinstance(info.part, ExperimentSupportBase)
            )
            and not info.disabled
        ]

        rigid_contacts = []
        for info in self.part_infos:
            if info.disabled:
                continue
            if isinstance(info.part, (ExperimentPistonBase, ExperimentSupportBase)):
                rigid_contacts.append(
                    Contact(
                        type=info.part.contact_type,
                        filename=f"velocity_{info.part_unique_name}.txt",
                        mu=info.part.mu,
                        master_material=info.material_index,
                        direction=[1, 1, 1],
                        materials=deformable_indices,
                    )
                )

        single_velocity_contact = Contact(
            type="single_velocity",
            materials=deformable_indices,
        )

        for c in rigid_contacts:
            store.add_contact(c)
        store.add_contact(single_velocity_contact)

        mpm = Mpm(
            time_integrator="explicit",
            interpolator="fast_cpdi",
            boundary_traction_faces="[zminus,zplus]",
            DoExplicitHeatConduction="false",
        )

        sim.add([mpm, archive, store, grid])

        # this stuff should be fixed laster, this is just a workaround
        self.ups = sim.to_xml()
        ElementTree.indent(self.ups)

    def _add_to_workflow_metrics(self, part_infos: list[PartInfo]):
        # Duplicates the prep metrics jobs (which feed the server manifest):
        # removing these changed main-workflow scheduling and left it pending,
        # so they stay until that's understood.
        for part_info in part_infos:
            part = part_info.part
            if not self._is_analysis_target(part):
                continue
            if not part_info.volume_filename:
                continue
            metrics_job_name = f"metrics-{part_info.part_unique_name}"
            self.workflow_jobs[metrics_job_name] = {
                "type": "implicit/metrics",
            }
            # Reference the prep volume directly as an asset
            self.workflow_assets[f"{metrics_job_name}.volume"] = (
                part_info.volume_filename
            )
            self.workflow_params[f"{metrics_job_name}.volume_size"] = json.dumps(
                part_info.patch["size"]
            )
            self.workflow_params[f"{metrics_job_name}.volume_offset"] = json.dumps(
                part_info.patch["offset"]
            )
            self.workflow_params[f"{metrics_job_name}.volume_resolution"] = json.dumps(
                part_info.patch["resolution"]
            )

    def _add_to_workflow_compress(self, part_infos: list[PartInfo]):
        compress_job_name = "compress"
        # Only parts that have a volume go into the compress assets list
        parts_with_volume = [p for p in part_infos if p.volume_filename]

        self.workflow_jobs[compress_job_name] = {
            "type": "sim/custom",
        }

        # compress.volume is a list of volume asset filenames in part order
        self.workflow_assets[f"{compress_job_name}.volume"] = [
            p.volume_filename for p in parts_with_volume
        ]

        volume_sizes = []
        volume_offsets = []
        volume_resolutions = []
        for part_info in parts_with_volume:
            volume_sizes.append(json.dumps(part_info.patch["size"]))
            volume_offsets.append(json.dumps(part_info.patch["offset"]))
            volume_resolutions.append(json.dumps(part_info.patch["resolution"]))
            part_info.jobs["compress"] = compress_job_name

        assert self.ups is not None
        self.workflow_params[f"{compress_job_name}.ups"] = self._dump_xml(
            self.ups, encoding="ISO-8859-1", xml_declaration=True
        )
        self.workflow_params[f"{compress_job_name}.volume_size"] = volume_sizes
        self.workflow_params[f"{compress_job_name}.volume_offset"] = volume_offsets
        self.workflow_params[f"{compress_job_name}.volume_resolution"] = (
            volume_resolutions
        )

        # Each rigid body with a velocity array gets its own text file.
        # Naming: "velocity_{part_name}.txt" — referenced by its contact element.
        text_inputs = {}
        for part_info in part_infos:
            if (
                hasattr(part_info.part, "velocity")
                and part_info.part.velocity is not None
            ):
                text_inputs[f"velocity_{part_info.part_unique_name}.txt"] = (
                    part_info.part.velocity
                )
        self.workflow_params[f"{compress_job_name}.text_inputs"] = json.dumps(
            text_inputs
        )

    def _add_to_workflow_postprocess(
        self,
        part_infos: list[PartInfo],
        input_job_name,
        new_job_name_base,
        material_key_param=None,
    ):
        new_job_type = f"sim/postprocess/{new_job_name_base}"
        input_jobs = list(
            dict.fromkeys(
                p.jobs[input_job_name] for p in part_infos if input_job_name in p.jobs
            )
        )
        job_index = 1
        for input_job_name in input_jobs:
            new_job_name = (
                f"{new_job_name_base}{'' if job_index > 0 else str(job_index)}"
            )
            job_index += 1

            self.workflow_jobs[new_job_name] = {
                "type": new_job_type,
                "needs": [input_job_name],
                "assets": {"data": input_job_name},
            }

            # set the job on all the relevant parts
            for part_info in part_infos:
                if part_info.jobs.get(input_job_name, "") == input_job_name:
                    part_info.jobs[new_job_name_base] = new_job_name

        # include every material for the keys
        if material_key_param:
            material_key_values = [
                f"/material{i}/{material_key_param}" for i in range(len(part_infos))
            ]
            self.workflow_params[f"{new_job_name_base}.keys"] = json.dumps(
                material_key_values
            )

    def _get_piston_info(self):
        piston_info = next(
            (p for p in self.part_infos if isinstance(p.part, ExperimentPistonBase)),
            None,
        )
        return piston_info

    def _get_force_source_info(self):
        """PartInfo of the body whose rigid_reaction_force is measured."""
        name = self.simulation_parameters.force_source_part
        if name:
            info = self.get_part_info(name)
            if info is None:
                raise RuntimeError(f"Unknown force_source_part: {name}")
            return info
        piston_info = self._get_piston_info()
        if piston_info is None:
            raise RuntimeError(
                "force_source RIGID_REACTION_FORCE requires a piston part "
                "or an explicit force_source_part"
            )
        return piston_info

    def _add_to_workflow_von_mises_stress(self, part_infos: list[PartInfo]):
        self._add_to_workflow_postprocess(
            part_infos, "compress", "von-mises-stress", "cauchy_stress"
        )

    def _add_to_workflow_effective_strain(self, part_infos: list[PartInfo]):
        self._add_to_workflow_postprocess(
            part_infos, "compress", "effective-strain", "deformation_gradient"
        )

    def _add_to_workflow_force_displacement(self, part_infos: list[PartInfo]):
        job_name_base = "force-displacement"
        self._add_to_workflow_postprocess(part_infos, "compress", job_name_base)
        if self.simulation_parameters.force_source == ForceSource.RIGID_REACTION_FORCE:
            source = self._get_force_source_info()
            keys = [f"/material{source.material_index}/rigid_reaction_force"]
        else:
            keys = ["/boundary_force_zminus"]
        self.workflow_params[f"{job_name_base}.keys"] = json.dumps(keys)
        self.workflow_params[f"{job_name_base}.method"] = "BoundaryForce"
        # Find the piston part — there should be exactly one
        piston_info = self._get_piston_info()
        if piston_info and piston_info.part.velocity:
            self.workflow_params[f"{job_name_base}.piston_velocity"] = json.dumps(
                [
                    [row[0], [row[1], row[2], row[3]]]
                    for row in piston_info.part.velocity
                ]
            )

    def _add_to_workflow_stress_strain(self, part_infos: list[PartInfo]):
        # One stress-strain job per deformable part, each normalizing the shared
        # (global) force-displacement curve by that part's own cross-section
        # (X*Y) and height (Z). Named stress-strain-<part> like metrics-<part>.
        fd_job = next(
            (p.jobs["force-displacement"] for p in part_infos
             if "force-displacement" in p.jobs),
            None,
        )
        if fd_job is None:
            return
        for part_info in part_infos:
            if not self._is_analysis_target(part_info.part):
                continue
            if part_info.disabled or not part_info.patch:
                continue
            job_name = f"stress-strain-{part_info.part_unique_name}"
            self.workflow_jobs[job_name] = {
                "type": "sim/postprocess/stress-strain",
                "needs": [fd_job],
                "assets": {"data": fd_job},
            }
            self.workflow_params[f"{job_name}.keys"] = json.dumps(
                ["/force_displacement"]
            )
            size = part_info.patch["size"]
            self.workflow_params[f"{job_name}.compression_area"] = str(
                size[0] * size[1]
            )
            self.workflow_params[f"{job_name}.initial_length"] = str(size[2])
            part_info.jobs["stress-strain"] = job_name

    def _add_to_workflow_particle_displacement(self, part_infos: list[PartInfo]):
        self._add_to_workflow_postprocess(
            part_infos, "compress", "particle-displacement", "position"
        )

    def _add_to_workflow_energy_metrics(self, part_infos: list[PartInfo]):
        self._add_to_workflow_postprocess(
            part_infos, "force-displacement", "energy-metrics"
        )

    # One merged reduce-results job consumes the particle-data outputs the
    # browser renders and produces a compact (trimmed + int16 + decimated) HDF5.
    # Auto-added whenever compress ran; the manifest points DTB at its output.
    _REDUCE_SOURCE_JOBS = [
        "compress", "von-mises-stress", "effective-strain",
        "particle-displacement",
    ]
    _REDUCE_JOB_NAME = "reduce-results"

    def _add_to_workflow_reduce_results(self):
        sources = [j for j in self._REDUCE_SOURCE_JOBS if j in self.workflow_jobs]
        if "compress" not in sources:
            return  # nothing to preview without particle positions
        self.workflow_jobs[self._REDUCE_JOB_NAME] = {
            "type": "sim/postprocess/reduce-results",
            "needs": sources,
            "assets": {"data": [{"job": s, "asset": "output"} for s in sources]},
        }

    def build_workflow(self, name_suffix=""):
        self.workflow_yaml = ""
        self.workflow_params = {}
        self.workflow_jobs = {}
        self.workflow_assets = {}

        for step in self.workflow_steps:
            try:
                part_infos_for_step = (
                    [self.get_part_info(p_name) for p_name in step.part_names]
                    if step.part_names
                    else self.part_infos
                )
            except KeyError as e:
                raise RuntimeError(
                    f"Unknown part name {e.args[0]} in workflow step {step.type.value}"
                )
            if step.type == WorkflowStepType.METRICS:
                self._add_to_workflow_metrics(part_infos_for_step)
            elif step.type == WorkflowStepType.COMPRESS:
                self._add_to_workflow_compress(part_infos_for_step)
            elif step.type == WorkflowStepType.VON_MISES_STRESS:
                self._add_to_workflow_von_mises_stress(part_infos_for_step)
            elif step.type == WorkflowStepType.EFFECTIVE_STRAIN:
                self._add_to_workflow_effective_strain(part_infos_for_step)
            elif step.type == WorkflowStepType.FORCE_DISPLACEMENT:
                self._add_to_workflow_force_displacement(part_infos_for_step)
            elif step.type == WorkflowStepType.STRESS_STRAIN:
                self._add_to_workflow_stress_strain(part_infos_for_step)
            elif step.type == WorkflowStepType.PARTICLE_DISPLACEMENT:
                self._add_to_workflow_particle_displacement(part_infos_for_step)
            elif step.type == WorkflowStepType.ENERGY_METRICS:
                self._add_to_workflow_energy_metrics(part_infos_for_step)
            elif step.type == WorkflowStepType.COMPUTE_BVH:
                pass  # this is done on the prep workflow, not here

        # Always emit the browser preview when there's particle data to preview.
        self._add_to_workflow_reduce_results()

        self.workflow_yaml = yaml.dump(
            {"jobs": self.workflow_jobs}, default_flow_style=False, sort_keys=False
        )
        ups_str = self._dump_xml(self.ups, encoding="ISO-8859-1", xml_declaration=True)
        self._write_ups(ups_str, f"{self.simulation_name}.ups")

        return self.workflow_yaml, self.workflow_params

    def run_workflow(self, name_suffix=""):
        self.workflow = self.client.workflows.run_async(
            self.workflow_yaml,
            parameters=self.workflow_params,
            assets=self.workflow_assets,
        )

        ret = {
            "id": self.workflow.id,
            "name": self.simulation_name,
            "totalEnergyAbsorption": 100.0,
        }
        for info in self.part_infos:
            if hasattr(info.part, "filename"):
                element_name = f"{info.part.name}{name_suffix}"
                ret[f"stl_{element_name}"] = str(info.part.filename)
        self.results.append(ret)
        self._save_results()

    @staticmethod
    def _dump_xml(et: ElementTree.ElementTree, **kwargs) -> str:
        with BytesIO() as b:
            et.write(b, **kwargs)
            return b.getvalue().decode()

    @staticmethod
    def _write_ply(
        df: pd.DataFrame, columns: list[tuple[str, DTypeLike]], zf: ZipFile, name: str
    ):
        """
        Write one PLY file per timestep.
        df must have a 'time' level in its index and columns: x, y, z, + whatever
        is listed in `columns`.
        """
        cols = [("x", np.float32), ("y", np.float32), ("z", np.float32)] + columns

        for i, (_, group) in enumerate(df.groupby("time")):
            data_out = np.empty((len(group),), dtype=cols)
            for col, _ in cols:
                if col in group:
                    data_out[col] = group[col].values
            elem_out = PlyElement.describe(data_out, "vertex")

            filename = f"{name}/ply/part.{i:04d}.ply"
            with zf.open(filename, "w") as f:
                PlyData([elem_out]).write(f)

    @staticmethod
    def write_histogram_csv(df, f, **kwargs):
        df = df.droplevel(1)
        df = df[["bin_left", "frequency"]]
        df.rename(columns={"bin_left": "bin_edges", "frequency": "count"}, inplace=True)
        codes, _ = df.index.factorize()
        df.index = pd.Index(codes, name="timestep")
        df.to_csv(f, **kwargs)

    def make_manifest(self):
        manifest_config = [
            {"key": "name", "heading": "Name", "filtering": True},
            {"key": "volume", "heading": "Volume (mm³)", "filtering": False},
            {
                "key": "loadingEnergy",
                "heading": "Loading Energy (J)",
                "filtering": False,
            },
            {
                "key": "unloadingEnergy",
                "heading": "Unloading Energy (J)",
                "filtering": False,
            },
            {
                "key": "energyAbsorbed",
                "heading": "Absorbed Energy (J)",
                "filtering": False,
            },
        ]
        self.manifest = {
            "resultsListConfig": manifest_config,
            "cardsConfig": {"A": [], "B": [], "C": []},
            "simulationPreviewConfig": {
                "variables": [
                    {"key": "vonMisesStress", "displayName": "von Mises Stress"},
                    {"key": "effectiveStrain", "displayName": "Effective Strain"},
                    {"key": "displacement", "displayName": "Displacement"},
                    {"key": "material", "displayName": "Material"},
                ],
                "dataSource": "ply",
                "materialsConfig": {
                    str(i): {
                        "displayName": part_info.part_unique_name,
                        **(
                            {"useSolidColor": True}
                            if isinstance(part_info.part, ExperimentPistonBase)
                            else {}
                        ),
                    }
                    for i, part_info in enumerate(self.part_infos)
                },
            },
        }
        if self._contains_step(WorkflowStepType.FORCE_DISPLACEMENT):
            self.manifest["cardsConfig"]["A"] = [
                {
                    "id": "forceDisplacement",
                    "title": "Force-Displacement",
                    "component": "MultiExperimentLineChart",
                    "props": {
                        "xColumn": "displacement",
                        "yColumn": "force",
                        "yMin": 0.0,
                        "xAxisLabel": "Displacement (mm)",
                        "yAxisLabel": "Force (N)",
                        "dataSource": "forceDisplacement",
                        "referenceCurve": {
                            "resultId": "1",
                            "dataSource": "referenceCurve",
                            "xColumn": "displacement",
                            "yColumn": "force",
                        },
                        "tooltips": [
                            {
                                "dataColumn": "energy_absorbed_cumulative",
                                "title": "Energy Absorbed (J)",
                            },
                        ],
                    },
                },
            ]
        self.manifest["cardsConfig"]["B"] = [
            {
                "id": "LoadCumulativeEnergy",
                "title": "Load-Cumulative Energy",
                "component": "MultiExperimentLineChart",
                "props": {
                    "xColumn": "force",
                    "yColumn": "energy_absorbed_cumulative",
                    "yMin": 0.0,
                    "xAxisLabel": "Load (N)",
                    "yAxisLabel": "Cumulative Energy (J)",
                    # forceDisplacement CSV contains both force and
                    # energy_absorbed_cumulative so it feeds both card A and B.
                    "dataSource": "loadingForceDisplacement",
                    "referenceCurve": {
                        "resultId": "1",
                        "dataSource": "referenceCurve",
                        "xColumn": "load",
                        "yColumn": "energy_absorbed_cumulative",
                    },
                    "tooltips": [
                        {
                            "dataColumn": "energy_absorbed_cumulative",
                            "title": "Energy Absorbed (J)",
                        },
                    ],
                },
            },
        ]
        self.manifest["cardsConfig"]["C"] = [
            {
                "id": "energyVolume",
                "title": "Energy Absorbed-Interior Volume",
                "component": "MultiExperimentScatterPlot",
                "props": {
                    "xDataKey": "volume",
                    "yDataKey": "energyAbsorbed",
                    "xAxisLabel": "Interior Volume (mm³)",
                    "yAxisLabel": "Energy Absorbed (J)",
                    "colorScaleMeasurement": "energyAbsorbed",
                },
            },
        ]

    def _contains_step(self, step_type: WorkflowStepType):
        return any(step.type == step_type for step in self.workflow_steps)

    def _get_step(self, step_type: WorkflowStepType, part_name=None):
        for step in self.workflow_steps:
            if step.type == step_type:
                if part_name is None or (
                    part_name in step.part_names or not step.part_names
                ):
                    return step
        return None

    @staticmethod
    def _apply_force_displacement_correction(
        df: pd.DataFrame, shift_mm: float
    ) -> pd.DataFrame:
        """Remove the 'toe' region from the start (displacement < shift_mm) and
        re-zero both displacement and force so the curve starts at (0, 0).
        Also appends a final (0, 0) row to close the loop."""
        if shift_mm <= 0 or df.empty:
            return df

        df = df.copy()
        df["displacement"] = df["displacement"] - shift_mm
        df = df[df["displacement"] >= 0].copy()
        if df.empty:
            return df

        df["displacement"] = df["displacement"] - df["displacement"].iloc[0]
        if "force" in df.columns:
            df["force"] = df["force"] - df["force"].iloc[0]
        df.reset_index(drop=True, inplace=True)
        df.loc[0, "displacement"] = 0.0
        if "force" in df.columns:
            df.loc[0, "force"] = 0.0
            zero_row = pd.DataFrame([{col: 0.0 for col in df.columns}])
            df = pd.concat([df, zero_row], ignore_index=True)
        return df

    def write_results(self):
        if not self.results:
            print(
                f"No persisted results for '{self.simulation_name}' — nothing to download."
            )
            return
        zip_filename = self.out_dir / "out.zip"
        with ZipFile(zip_filename, "w") as zf:
            if not self.use_legacy_results_format:
                self._write_results_to_zip_v2(zf)
                self._write_manifest_to_zip_v2(zf, self.results)
            else:
                self._write_results_to_zip(zf)
                self._write_manifest_to_zip(zf, self.results)

    @staticmethod
    def _is_analysis_target(p: ExperimentPart):
        if isinstance(p, ExperimentPistonBase) or isinstance(p, ExperimentSupportBase):
            return False
        return True

    def _write_results_to_zip(self, zf: ZipFile):
        """Poll each workflow in self.results, download assets, and write
        per-sim files into the given zip. Mutates each entry of self.results
        in place, adding 'data', 'volume', 'energyAbsorbed', etc."""
        for result in self.results:
            w = self.client.workflows.get(result["id"])
            while w.state not in ["success", "failure", "canceled"]:
                sleep(1)
                # refresh the workflow
                w = self.client.workflows.get(w.id)

            if w.state == "success":
                name = self.simulation_name
                data: dict[str, Any] = {}

                # Mesh previews — copy the original input file directly into
                # the zip. No mesh-from-volume job; the input mesh is the mesh
                stl_assets = []
                for part_info in self.part_infos:
                    if not self._is_analysis_target(part_info.part):
                        continue
                    if part_info.disabled:
                        continue
                    if part_info.file_path is None:
                        continue
                    mat_idx = part_info.material_index
                    src_path = part_info.file_path
                    zip_path = (
                        f"{name}/mesh_{part_info.part_unique_name}"
                        f"{src_path.suffix.lower()}"
                    )
                    with open(src_path, "rb") as src, zf.open(zip_path, "w") as dst:
                        copyfileobj(src, dst)
                    stl_assets.append({"bodyId": mat_idx, "fileName": zip_path})

                data["stl"] = stl_assets

                with TemporaryDirectory() as tempdir:
                    hdf_filename = Path(tempdir) / "out.h5"

                    # ----------------------------------------------------------
                    # Build a per-material dataframe then concat into one big df.
                    #
                    # For each material we collect:
                    #   - x, y, z          (from compress.output)
                    #   - vonMisesStress   (from von-mises-stress.output)
                    #   - effectiveStrain  (from effective-strain.output)
                    #   - displacement     (from particle-displacement.output)
                    #   - material         (integer label so the viewer can colour by part)
                    #
                    # All four per-material dataframes are concat'd vertically before
                    # write_ply is called, so every particle from every material ends
                    # up in every PLY frame.
                    # ----------------------------------------------------------

                    # Download all three postprocess HDF files once each
                    vm_hdf = None
                    if self._contains_step(WorkflowStepType.VON_MISES_STRESS):
                        vm_asset = w.get_asset("von-mises-stress.output")
                        if vm_asset is not None:
                            vm_hdf = Path(tempdir) / "von_mises.h5"
                            self.client.assets.download_file(vm_asset.id, vm_hdf)

                    es_hdf = None
                    if self._contains_step(WorkflowStepType.EFFECTIVE_STRAIN):
                        es_asset = w.get_asset("effective-strain.output")
                        if es_asset is not None:
                            es_hdf = Path(tempdir) / "eff_strain.h5"
                            self.client.assets.download_file(es_asset.id, es_hdf)

                    pd_hdf = None
                    if self._contains_step(WorkflowStepType.PARTICLE_DISPLACEMENT):
                        pd_asset = w.get_asset("particle-displacement.output")
                        if pd_asset is not None:
                            pd_hdf = Path(tempdir) / "part_disp.h5"
                            self.client.assets.download_file(pd_asset.id, pd_hdf)

                    uo_hdf = None
                    if self._contains_step(WorkflowStepType.COMPRESS):
                        uo_asset = w.get_asset("compress.output")
                        if uo_asset is not None:
                            uo_hdf = Path(tempdir) / "compress.h5"
                            self.client.assets.download_file(uo_asset.id, uo_hdf)

                    material_dfs = []  # one entry per material, concat'd at the end

                    def to_indexed(df):
                        """Normalise to (time, id) MultiIndex regardless of whether the
                        HDF stored them as columns or already as the index."""
                        return df.reset_index().set_index(["time", "id"])

                    for part_info in self.part_infos:
                        if part_info.disabled:
                            continue
                        mat_idx = part_info.material_index
                        mat_key = f"material{mat_idx}"

                        # --- positions (m → mm) ---
                        pos = None
                        if (
                            self._contains_step(WorkflowStepType.COMPRESS)
                            and uo_hdf is not None
                        ):
                            try:
                                with pd.HDFStore(uo_hdf) as store:
                                    key = f"/{mat_key}/position"
                                    if key in store:
                                        pos = store[key]
                                if pos is not None:
                                    pos = (
                                        to_indexed(pos)[["x", "y", "z"]] * 1e3
                                    )  # m → mm
                            except Exception as e:
                                pass

                        # --- von Mises stress ---
                        vm = None
                        if (
                            self._contains_step(WorkflowStepType.VON_MISES_STRESS)
                            and vm_hdf is not None
                        ):
                            try:
                                with pd.HDFStore(vm_hdf) as store:
                                    key = f"/{mat_key}/von_mises_stress"
                                    if key in store:
                                        vm = store[key]
                                if vm is not None:
                                    vm = to_indexed(vm)[["v"]].rename(
                                        columns={"v": "vonMisesStress"}
                                    )
                            except Exception as e:
                                pass

                        # --- effective strain ---
                        es = None
                        if (
                            self._contains_step(WorkflowStepType.EFFECTIVE_STRAIN)
                            and es_hdf is not None
                        ):
                            try:
                                with pd.HDFStore(es_hdf) as store:
                                    key = f"/{mat_key}/effective_strain"
                                    if key in store:
                                        es = store[key]
                                if es is not None:
                                    es = to_indexed(es)[["v"]].rename(
                                        columns={"v": "effectiveStrain"}
                                    )
                            except Exception as e:
                                pass

                        # --- displacement magnitude ---
                        disp = None
                        if (
                            self._contains_step(WorkflowStepType.PARTICLE_DISPLACEMENT)
                            and pd_hdf is not None
                        ):
                            try:
                                with pd.HDFStore(pd_hdf) as store:
                                    key = f"/{mat_key}/particle_displacement"
                                    if key in store:
                                        disp = store[key]
                                if disp is not None:
                                    disp = to_indexed(disp)[["norm"]].rename(
                                        columns={"norm": "displacement"}
                                    )
                            except Exception as e:
                                pass

                        # Join all variables for this material on (time, id)
                        mat_df = None
                        if pos is not None:
                            mat_df = pos
                        if vm is not None:
                            if mat_df is not None:
                                mat_df = mat_df.join(vm)
                            else:
                                mat_df = vm
                        if es is not None:
                            if mat_df is not None:
                                mat_df = mat_df.join(es)
                            else:
                                mat_df = es
                        if disp is not None:
                            if mat_df is not None:
                                mat_df = mat_df.join(disp)
                            else:
                                mat_df = disp
                        if mat_df is not None:
                            mat_df["material"] = (
                                mat_idx  # integer label (0=piston … 3=outsole)
                            )
                            material_dfs.append(mat_df)

                    # Combine all materials into one big dataframe
                    if material_dfs:
                        ply_data = pd.concat(material_dfs)
                        ply_data = (
                            ply_data.reset_index()
                        )  # bring time back as a plain column for groupby

                    # ----------------------------------------------------------
                    if self._contains_step(WorkflowStepType.VON_MISES_STRESS):
                        assert vm_hdf is not None
                        with pd.HDFStore(vm_hdf) as store:
                            filename = f"{name}/vonMisesStress.csv"
                            if "/material1/von_mises_stress" in store:
                                with zf.open(filename, "w") as f:
                                    store["/material1/von_mises_stress"].to_csv(
                                        f, index=False
                                    )
                                data["vonMisesStress"] = filename

                            filename = f"{name}/vonMisesStressHistogram.csv"
                            if "/material1/von_mises_stress_histogram" in store:
                                with zf.open(filename, "w") as f:
                                    self.write_histogram_csv(
                                        store["/material1/von_mises_stress_histogram"],
                                        f,
                                    )
                                data["vonMisesStressHistogram"] = filename

                    if self._contains_step(WorkflowStepType.EFFECTIVE_STRAIN):
                        assert es_hdf is not None
                        with pd.HDFStore(es_hdf) as store:
                            filename = f"{name}/effectiveStrain.csv"
                            if "/material1/effective_strain" in store:
                                with zf.open(filename, "w") as f:
                                    store["/material1/effective_strain"].to_csv(
                                        f, index=False
                                    )
                                data["effectiveStrain"] = filename

                            filename = f"{name}/effectiveStrainHistogram.csv"
                            if "/material1/effective_strain_histogram" in store:
                                with zf.open(filename, "w") as f:
                                    self.write_histogram_csv(
                                        store["/material1/effective_strain_histogram"],
                                        f,
                                    )
                                data["effectiveStrainHistogram"] = filename

                    # Force-displacement (feeds card A and card B)
                    df = None
                    energy_absorbed_cumulative = None
                    loading_energy = None
                    unloading_energy = None
                    if self._contains_step(WorkflowStepType.FORCE_DISPLACEMENT):
                        fd_asset = w.get_asset("force-displacement.output")
                        assert fd_asset
                        self.client.assets.download_file(fd_asset.id, hdf_filename)
                        with pd.HDFStore(hdf_filename) as store:
                            df = store["/force_displacement"].reset_index()
                            df = self._apply_force_displacement_correction(
                                df,
                                self.simulation_parameters.force_displacement_shift_mm,
                            )

                            filename = f"{name}/forceDisplacement.csv"
                            with zf.open(filename, "w") as f:
                                df.to_csv(f)
                            data["forceDisplacement"] = filename

                    if self._contains_step(WorkflowStepType.ENERGY_METRICS):
                        raw_energy_absorbed = w.get_parameter("energy-metrics.energy_absorbed")
                        raw_loading_energy = w.get_parameter("energy-metrics.loading_energy")
                        raw_unloading_energy = w.get_parameter("energy-metrics.unloading_energy")
                        if raw_energy_absorbed is not None:
                            energy_absorbed_cumulative = float(raw_energy_absorbed)
                        if raw_loading_energy is not None:
                            loading_energy = float(raw_loading_energy)
                        if raw_unloading_energy is not None:
                            unloading_energy = float(raw_unloading_energy)

                        if raw_energy_absorbed is not None:
                            filename = f"{name}/loadingForceDisplacement.csv"
                            if self.reference_data.csv_path.is_file():
                                if (
                                    str(self.reference_data.curve_zip_path)
                                    not in zf.namelist()
                                ):
                                    with zf.open(
                                        str(self.reference_data.curve_zip_path), "w"
                                    ) as f:
                                        with open(
                                            self.reference_data.csv_path, "rb"
                                        ) as ref:
                                            f.write(ref.read())
                            else:
                                print(
                                    "WARNING: reference.csv not found — overlay will not appear."
                                )

                            if df is not None:
                                disp0 = df["displacement"].iloc[0]
                                split_idx = (df["displacement"] - disp0).abs().idxmax()
                                loading = df[df["time"] <= df.loc[split_idx, "time"]]
                                with zf.open(filename, "w") as f:
                                    loading.to_csv(f)
                                data["loadingForceDisplacement"] = filename

                    # Stress-strain: one curve per deformable part.
                    if self._contains_step(WorkflowStepType.STRESS_STRAIN):
                        for part_info in self.part_infos:
                            if not self._is_analysis_target(part_info.part):
                                continue
                            if part_info.disabled:
                                continue
                            i = part_info.material_index
                            ss_asset = w.get_asset(
                                f"stress-strain-{part_info.part_unique_name}.output"
                            )
                            if ss_asset is None:
                                continue
                            self.client.assets.download_file(ss_asset.id, hdf_filename)
                            with pd.HDFStore(hdf_filename) as store:
                                filename = f"{name}/stressStrain{i}.csv"
                                with zf.open(filename, "w") as f:
                                    store["/stress_strain"].to_csv(f)
                                data[f"stressStrain{i}"] = filename

                    # ----------------------------------------------------------
                    # Write PLY files from the combined all-material dataframe.
                    # Every frame contains particles from all four materials with
                    # vonMisesStress, effectiveStrain, displacement, and a material
                    # label so the viewer can colour by part.
                    # ----------------------------------------------------------
                    ply_columns: list[tuple[str, DTypeLike]] = []
                    if self._contains_step(WorkflowStepType.VON_MISES_STRESS):
                        ply_columns.append(("vonMisesStress", np.float32))
                    if self._contains_step(WorkflowStepType.EFFECTIVE_STRAIN):
                        ply_columns.append(("effectiveStrain", np.float32))
                    if self._contains_step(WorkflowStepType.FORCE_DISPLACEMENT):
                        ply_columns.append(("displacement", np.float32))
                    ply_columns.append(("material", np.int32))
                    self._write_ply(
                        ply_data,
                        ply_columns,
                        zf,
                        name,
                    )
                    data["ply"] = f"{name}/ply/part.####.ply"

                    # Sum interior volumes from all parts
                    total_volume = self._total_interior_volume(w)

                    result.update(
                        {
                            "data": data,
                            "volume": total_volume,
                        }
                    )
                    if energy_absorbed_cumulative is not None:
                        result["energyAbsorbed"] = energy_absorbed_cumulative
                    if loading_energy is not None:
                        result["loadingEnergy"] = round(loading_energy, 4)
                    if unloading_energy is not None:
                        result["unloadingEnergy"] = round(unloading_energy, 4)

    def _results_have_energy_metrics(self, results: list) -> bool:
        return self._contains_step(WorkflowStepType.ENERGY_METRICS)

    def _write_manifest_to_zip(self, zf: ZipFile, all_results: list):
        reference_result = {
            "id": "1",
            "name": "Reference (experimental)",
            "isExperimental": True,
            "project": "stride",
            "material": "Reference",
            "volume": self.reference_data.volume,
            "originalVolume": 0,
            "density": 0,
            "energyAbsorbed": self.reference_data.energy_absorbed,
            "loadingEnergy": self.reference_data.loading_energy,
            "unloadingEnergy": self.reference_data.unloading_energy,
            "data": {"referenceCurve": str(self.reference_data.curve_zip_path)},
        }

        self.make_manifest()
        m = copy.deepcopy(self.manifest)
        m["results"] = [reference_result] + all_results

        with zf.open("manifest.json", "w") as f:
            f.write(json.dumps(m, indent=2).encode())

    @staticmethod
    def _mesh_data_key(part_unique_name: str) -> str:
        """Build the data key for a part's mesh preview, e.g. 'midsole' → 'midsole_mesh'."""
        return f"{part_unique_name}_mesh"

    def _write_results_to_zip_v2(self, zf: ZipFile):
        """New schema: ship HDF files into the zip and reference per-material
        datasets via {name, path} entries in `data`. Mesh previews are copies
        of the original input PLY files. Disabled parts are skipped entirely."""
        name = self.simulation_name

        # Always write mesh files regardless of workflow outcome, for debugging.
        mesh_data: dict[str, Any] = {}
        for part_info in self.part_infos:
            if part_info.file_path is None:
                continue
            zip_path = (
                f"{name}/original_{part_info.part_unique_name}"
                f"{part_info.file_path.suffix.lower()}"
            )
            with (
                open(part_info.file_path, "rb") as src,
                zf.open(zip_path, "w") as dst,
            ):
                copyfileobj(src, dst)
            if self._is_analysis_target(part_info.part) and not part_info.disabled:
                mesh_data[self._mesh_data_key(part_info.part.name)] = {"name": zip_path}

        for result in self.results:
            w = self.client.workflows.get(result["id"])
            while w.state not in ["success", "failure", "canceled"]:
                sleep(1)
                w = self.client.workflows.get(w.id)

            if w.state != "success":
                continue

            data: dict[str, Any] = dict(mesh_data)

            # Number of materials drives per-material data keys.
            n_materials = len(self.part_infos)

            with TemporaryDirectory() as tempdir:
                tempdir_path = Path(tempdir)

                # Postprocess HDFs that ship whole. Each entry:
                # (step, asset_name, basename, dataset_root, key_prefix, has_histogram)
                full_hdf_refs = [
                    (
                        WorkflowStepType.VON_MISES_STRESS,
                        "von-mises-stress.output",
                        "von_mises.h5",
                        "von_mises_stress",
                        "vonMisesStress",
                        True,
                    ),
                    (
                        WorkflowStepType.EFFECTIVE_STRAIN,
                        "effective-strain.output",
                        "eff_strain.h5",
                        "effective_strain",
                        "effectiveStrain",
                        True,
                    ),
                    (
                        WorkflowStepType.PARTICLE_DISPLACEMENT,
                        "particle-displacement.output",
                        "part_disp.h5",
                        "particle_displacement",
                        "particleDisplacement",
                        False,
                    ),
                ]

                for (
                    step,
                    asset_name,
                    basename,
                    dataset_root,
                    key_prefix,
                    has_histogram,
                ) in full_hdf_refs:
                    if not self._contains_step(step):
                        continue
                    asset = w.get_asset(asset_name)
                    if asset is None:
                        continue
                    local_path = tempdir_path / basename
                    self.client.assets.download_file(asset.id, local_path)
                    zip_path = f"{name}/{basename}"
                    zf.write(local_path, arcname=zip_path)
                    for i in range(n_materials):
                        if self.part_infos[i].disabled:
                            continue
                        data[f"{key_prefix}{i}"] = {
                            "name": zip_path,
                            "path": f"/material{i}/{dataset_root}",
                        }
                        if has_histogram:
                            data[f"{key_prefix}Histogram{i}"] = {
                                "name": zip_path,
                                "path": f"/material{i}/{dataset_root}_histogram",
                            }

                # Compress output: download whole, but ship only the position
                # datasets to keep the zip small.
                if self._contains_step(WorkflowStepType.COMPRESS):
                    uo_asset = w.get_asset("compress.output")
                    if uo_asset is not None:
                        uo_hdf = tempdir_path / "compress.h5"
                        self.client.assets.download_file(uo_asset.id, uo_hdf)

                        pn_hdf = tempdir_path / "position.h5"
                        with (
                            pd.HDFStore(uo_hdf, "r") as src,
                            pd.HDFStore(pn_hdf, "w") as dst,
                        ):
                            for i in range(n_materials):
                                if self.part_infos[i].disabled:
                                    continue
                                path = f"/material{i}/position"
                                if path in src:
                                    dst[path] = src[path]

                        pn_zip_path = f"{name}/position.h5"
                        zf.write(pn_hdf, arcname=pn_zip_path)
                        for i in range(n_materials):
                            if self.part_infos[i].disabled:
                                continue
                            data[f"position{i}"] = {
                                "name": pn_zip_path,
                                "path": f"/material{i}/position",
                            }

                # Force-displacement: ship whole.
                energy_absorbed_cumulative = None
                loading_energy = None
                unloading_energy = None
                if self._contains_step(WorkflowStepType.FORCE_DISPLACEMENT):
                    fd_asset = w.get_asset("force-displacement.output")
                    if fd_asset is not None:
                        fd_hdf = tempdir_path / "force_disp.h5"
                        self.client.assets.download_file(fd_asset.id, fd_hdf)
                        fd_zip_path = f"{name}/force_disp.h5"
                        zf.write(fd_hdf, arcname=fd_zip_path)
                        data["forceDisplacement"] = {
                            "name": fd_zip_path,
                            "path": "/force_displacement",
                        }

                if self._contains_step(WorkflowStepType.ENERGY_METRICS):
                    raw_ea = w.get_parameter("energy-metrics.energy_absorbed")
                    raw_le = w.get_parameter("energy-metrics.loading_energy")
                    raw_ue = w.get_parameter("energy-metrics.unloading_energy")
                    if raw_ea is not None:
                        energy_absorbed_cumulative = float(raw_ea)
                    if raw_le is not None:
                        loading_energy = float(raw_le)
                    if raw_ue is not None:
                        unloading_energy = float(raw_ue)

                # Stress-strain: ship one whole file per deformable part.
                if self._contains_step(WorkflowStepType.STRESS_STRAIN):
                    for part_info in self.part_infos:
                        if not self._is_analysis_target(part_info.part):
                            continue
                        if part_info.disabled:
                            continue
                        i = part_info.material_index
                        ss_asset = w.get_asset(
                            f"stress-strain-{part_info.part_unique_name}.output"
                        )
                        if ss_asset is not None:
                            ss_hdf = tempdir_path / f"stress_strain_{i}.h5"
                            self.client.assets.download_file(ss_asset.id, ss_hdf)
                            ss_zip_path = f"{name}/stress_strain_{i}.h5"
                            zf.write(ss_hdf, arcname=ss_zip_path)
                            data[f"stressStrain{i}"] = {
                                "name": ss_zip_path,
                                "path": "/stress_strain",
                            }

            # Sum interior volumes across analysis-target parts.
            total_volume = self._total_interior_volume(w)

            result.update(
                {
                    "data": data,
                    "volume": total_volume,
                }
            )
            if energy_absorbed_cumulative is not None:
                result["energyAbsorbed"] = round(float(energy_absorbed_cumulative), 4)
            if loading_energy is not None:
                result["loadingEnergy"] = round(float(loading_energy), 4)
            if unloading_energy is not None:
                result["unloadingEnergy"] = round(float(unloading_energy), 4)

    def _write_manifest_to_zip_v2(self, zf: ZipFile, all_results: list):
        """New schema manifest. If reference data is configured, prepend a
        reference result entry that the viewer will display alongside the
        sim results."""
        self.make_manifest_v2(results=list(all_results))
        m = copy.deepcopy(self.manifest)

        results_list = list(all_results)

        # Prepend reference experimental data if a reference CSV is configured.
        if self.reference_data.csv_path.is_file():
            reference_result = self._build_reference_result_v2(zf)
            if reference_result is not None:
                results_list = [reference_result] + results_list

        m["results"] = results_list

        with zf.open("manifest.json", "w") as f:
            f.write(json.dumps(m, indent=2).encode())

    def _build_job_id_lookup(self, workflow: Workflow) -> dict[str, str]:
        """Build a {local_job_name: server_job_id} lookup for the given workflow.
        Used when assembling the server-side manifest that references assets
        by jobId/assetName."""
        lookup: dict[str, str] = {}
        for job_id in workflow.jobs:
            job = self.client.jobs.get(job_id)
            if job is None or job.name is None:
                continue
            lookup[job.name] = job_id
        return lookup

    @property
    def server_manifest_filename(self) -> Path:
        assert self.out_dir is not None
        return self.out_dir / f"manifest.json"

    def _build_server_data_for_workflow(self, workflow: Workflow, job_id_lookup: dict[str, str]) -> dict[str, Any]:

        server_data: dict[str, Any] = {}

        # Mesh previews — reference uploaded source asset by filename.
        for part_info in self.part_infos:
            if not self._is_analysis_target(part_info.part):
                continue
            if part_info.disabled:
                continue
            if part_info.file_path is None:
                continue
            server_data[self._mesh_data_key(part_info.part.name)] = {
                "name": part_info.file_path.name,
            }

        n_materials = len(self.part_infos)

        # Per-material HDF blocks. Mirrors the layout in _write_results_to_zip_v2.
        full_hdf_refs = [
            (
                WorkflowStepType.VON_MISES_STRESS,
                "von_mises_stress",
                "vonMisesStress",
                True,
                "von-mises-stress",
            ),
            (
                WorkflowStepType.EFFECTIVE_STRAIN,
                "effective_strain",
                "effectiveStrain",
                True,
                "effective-strain",
            ),
            (
                WorkflowStepType.PARTICLE_DISPLACEMENT,
                "particle_displacement",
                "particleDisplacement",
                False,
                "particle-displacement",
            ),
        ]
        # Point the particle datasets DTB renders at the merged reduce-results
        # job (compact int16/decimated), falling back to the raw job if preview
        # didn't run. Histograms are tiny — leave them on the raw job.
        reduce_job_id = job_id_lookup.get(self._REDUCE_JOB_NAME, "")
        for step, dataset_root, key_prefix, has_histogram, local_job in full_hdf_refs:
            if not self._contains_step(step):
                continue
            raw_job_id = job_id_lookup.get(local_job, "")
            data_job_id = reduce_job_id or raw_job_id
            for i in range(n_materials):
                if self.part_infos[i].disabled:
                    continue
                server_data[f"{key_prefix}{i}"] = {
                    "jobId": data_job_id,
                    "assetName": "output",
                    "path": f"/material{i}/{dataset_root}",
                }
                if has_histogram:
                    server_data[f"{key_prefix}Histogram{i}"] = {
                        "jobId": raw_job_id,
                        "assetName": "output",
                        "path": f"/material{i}/{dataset_root}_histogram",
                    }

        if self._contains_step(WorkflowStepType.COMPRESS):
            job_id = reduce_job_id or job_id_lookup.get("compress", "")
            for i in range(n_materials):
                if self.part_infos[i].disabled:
                    continue
                server_data[f"position{i}"] = {
                    "jobId": job_id,
                    "assetName": "output",
                    "path": f"/material{i}/position",
                }

        if self._contains_step(WorkflowStepType.FORCE_DISPLACEMENT):
            server_data["forceDisplacement"] = {
                "jobId": job_id_lookup.get("force-displacement", ""),
                "assetName": "output",
                "path": "/force_displacement",
            }

        if self._contains_step(WorkflowStepType.STRESS_STRAIN):
            for part_info in self.part_infos:
                if not self._is_analysis_target(part_info.part):
                    continue
                if part_info.disabled:
                    continue
                i = part_info.material_index
                server_data[f"stressStrain{i}"] = {
                    "jobId": job_id_lookup.get(
                        f"stress-strain-{part_info.part_unique_name}", ""
                    ),
                    "assetName": "output",
                    "path": "/stress_strain",
                }

        return server_data

    def _build_server_scalars_for_workflow(
        self, workflow: Workflow, job_id_lookup: dict[str, str]
    ) -> dict[str, Any]:
        """Build top-level scalar fields for a server manifest result entry.
        Volume is inlined (from prep workflow parameters); energy values are
        refs that the server resolves from the energy-metrics job output."""
        scalars: dict[str, Any] = {}
        scalars["volume"] = self._total_interior_volume(workflow)

        if self._contains_step(WorkflowStepType.ENERGY_METRICS):
            em_job_id = job_id_lookup.get("energy-metrics", "")
            scalars["energyAbsorbed"] = {
                "jobId": em_job_id,
                "outputParam": "energy_absorbed",
            }
            scalars["loadingEnergy"] = {
                "jobId": em_job_id,
                "outputParam": "loading_energy",
            }
            scalars["unloadingEnergy"] = {
                "jobId": em_job_id,
                "outputParam": "unloading_energy",
            }

        return scalars

    def _write_server_manifest_for_pairs(
        self, pairs: list[tuple["CompressionSimulation", dict]]
    ) -> Optional[dict]:
        """Shared manifest-write path. `pairs` is a list of (sim, result) tuples;
        each result's server data is built from its associated sim's part_infos.
        Used by both single-sim and experiment-level manifest writes."""
        server_results = []
        for sim, result in pairs:
            wf_id = result.get("id")
            if not wf_id:
                continue
            server_result = {k: v for k, v in result.items() if k != "data"}
            try:
                workflow = sim.client.workflows.get(wf_id)
                job_id_lookup = sim._build_job_id_lookup(workflow)
                server_result["data"] = sim._build_server_data_for_workflow(workflow, job_id_lookup)
                server_result.update(sim._build_server_scalars_for_workflow(workflow, job_id_lookup))
            except Exception as e:
                print(f"WARNING: couldn't build server data for {wf_id}: {e}")
                server_result["data"] = {}
            server_results.append(server_result)

        self.make_manifest_v2(results=server_results)
        manifest = copy.deepcopy(self.manifest)
        manifest["results"] = server_results
        self.server_manifest_filename.write_bytes(
            json.dumps(manifest, indent=2).encode()
        )
        return manifest

    def write_server_manifest(self) -> Optional[dict]:
        """Build and write a server manifest covering this sim's own results."""
        if not self.results:
            print(f"No results for '{self.simulation_name}' — nothing to write.")
            return None
        pairs = [(self, r) for r in self.results]
        return self._write_server_manifest_for_pairs(pairs)

    def upload_server_manifest(self) -> None:
        """Build, write, and set the server manifest as project data."""
        manifest = self.write_server_manifest()
        if manifest is None:
            return
        self.client.projects.update(data=manifest)
        print(f"Uploaded server manifest to project {self.project_id}")

    def _build_reference_result_v2(self, zf: ZipFile) -> Optional[dict]:
        """Read the reference CSV (expected columns: Displacement, Force),
        write it as an HDF into the zip, and return a result entry pointing
        at it. Returns None if the CSV can't be read."""
        try:
            ref_df = pd.read_csv(self.reference_data.csv_path)
        except Exception as e:
            print(f"WARNING: failed to read reference CSV: {e}")
            return None

        # Normalize column names to what the viewer expects.
        rename_map = {}
        for col in ref_df.columns:
            lower = col.lower()
            if lower == "displacement":
                rename_map[col] = "displacement"
            elif lower == "force":
                rename_map[col] = "force"
        ref_df = ref_df.rename(columns=rename_map)

        if "displacement" not in ref_df.columns or "force" not in ref_df.columns:
            print(
                "WARNING: reference CSV missing 'displacement' or 'force' columns — "
                "reference curve will not appear."
            )
            return None

        ref_df = ref_df[["displacement", "force"]]

        with TemporaryDirectory() as tempdir:
            hdf_path = Path(tempdir) / "reference.h5"
            with pd.HDFStore(hdf_path, "w") as store:
                store["/reference"] = ref_df
            zip_path = "reference.h5"
            zf.write(hdf_path, arcname=zip_path)

        return {
            "id": "1",
            "name": "Reference (experimental)",
            "isExperimental": True,
            "volume": self.reference_data.volume,
            "energyAbsorbed": self.reference_data.energy_absorbed,
            "loadingEnergy": self.reference_data.loading_energy,
            "unloadingEnergy": self.reference_data.unloading_energy,
            "data": {
                "forceDisplacement": {
                    "name": zip_path,
                    "path": "/reference",
                },
            },
        }

    def make_manifest_v2(self, results: list = []):
        """Build the new-schema manifest. References per-material data keys
        (vonMisesStress0, vonMisesStress1, etc.) and ships partPreviewConfig
        for each analysis-target part."""
        self.manifest = {
            "resultsListConfig": [
                {"key": "name", "heading": "Name", "filtering": True},
            ],
            "cardsConfig": {"A": [], "B": [], "C": []},
            "simulationPreviewConfig": {
                "dataSource": "position",
                "variables": [],
                "materialsConfig": {
                    str(i): {
                        "displayName": part_info.part_unique_name,
                        **(
                            {"useSolidColor": True}
                            if isinstance(part_info.part, ExperimentPistonBase)
                            else {}
                        ),
                    }
                    for i, part_info in enumerate(self.part_infos)
                },
            },
            "partPreviewConfig": [
                {
                    "displayName": part_info.part.name,
                    "dataSource": self._mesh_data_key(part_info.part.name),
                    "fileFormat": part_info.file_path.suffix.lstrip(".").lower(),
                }
                for part_info in self.part_infos
                if self._is_analysis_target(part_info.part)
                and part_info.file_path
                and not part_info.disabled
            ],
        }

        if self._contains_step(WorkflowStepType.VON_MISES_STRESS):
            self.manifest["simulationPreviewConfig"]["variables"].append(
                {
                    "displayName": "von Mises Stress",
                    "dataSource": "vonMisesStress",
                    "column": "v",
                }
            )
        if self._contains_step(WorkflowStepType.EFFECTIVE_STRAIN):
            self.manifest["simulationPreviewConfig"]["variables"].append(
                {
                    "displayName": "Effective Strain",
                    "dataSource": "effectiveStrain",
                    "column": "v",
                }
            )
        if self._contains_step(WorkflowStepType.PARTICLE_DISPLACEMENT):
            self.manifest["simulationPreviewConfig"]["variables"].append(
                {
                    "displayName": "Displacement",
                    "dataSource": "particleDisplacement",
                    "column": "norm",
                }
            )

        if self._contains_step(WorkflowStepType.FORCE_DISPLACEMENT):
            self.manifest["cardsConfig"]["A"] = [
                {
                    "id": "forceDisplacement",
                    "title": "Force-Displacement",
                    "component": "MultiExperimentLineChart",
                    "props": {
                        "xColumn": "displacement",
                        "yColumn": "force",
                        "yMin": 0.0,
                        "xAxisLabel": "Displacement (mm)",
                        "yAxisLabel": "Force (N)",
                        "dataSource": "forceDisplacement",
                        "tooltips": [
                            {
                                "dataColumn": "energy_absorbed_cumulative",
                                "title": "Energy Absorbed (J)",
                            },
                        ],
                    },
                },
            ]

        # One stress-strain card per deformable part (keyed stressStrain{i}),
        # under force-displacement: same data, per-part normalizations.
        if self._contains_step(WorkflowStepType.STRESS_STRAIN):
            for part_info in self.part_infos:
                if not self._is_analysis_target(part_info.part):
                    continue
                if part_info.disabled:
                    continue
                i = part_info.material_index
                self.manifest["cardsConfig"]["A"].append(
                    {
                        "id": f"stressStrain{i}",
                        "title": f"{part_info.part_unique_name} Stress-Strain",
                        "component": "MultiExperimentLineChart",
                        "props": {
                            "xColumn": "strain",
                            "yColumn": "stress",
                            "yMin": 0.0,
                            "xAxisLabel": "Strain",
                            "yAxisLabel": "Stress (MPa)",
                            "dataSource": f"stressStrain{i}",
                        },
                    }
                )

        # One von Mises histogram card per deformable part (keyed
        # vonMisesStressHistogram{i}).
        self.manifest["cardsConfig"]["B"] = []
        if self._contains_step(WorkflowStepType.VON_MISES_STRESS):
            for part_info in self.part_infos:
                if not self._is_analysis_target(part_info.part):
                    continue
                if part_info.disabled:
                    continue
                i = part_info.material_index
                self.manifest["cardsConfig"]["B"].append(
                    {
                        "id": f"vonMisesStress{i}",
                        "title": f"{part_info.part_unique_name} von Mises Stress",
                        "component": "SingleExperimentHistogram",
                        "props": {
                            "dataSource": f"vonMisesStressHistogram{i}",
                            "xAxisLabel": "von Mises Stress",
                            "yAxisLabel": "Frequency",
                        },
                    }
                )

        if self._results_have_energy_metrics(results):
            self.manifest["resultsListConfig"].append(
                {"key": "volume", "heading": "Volume (mm³)", "filtering": False},
            )
            self.manifest["resultsListConfig"].append(
                {
                    "key": "energyAbsorbed",
                    "heading": "Absorbed Energy (J)",
                    "filtering": False,
                }
            )
            self.manifest["resultsListConfig"].append(
                            {
                    "key": "loadingEnergy",
                    "heading": "Loading Energy (J)",
                    "filtering": False,
                }
            )
            self.manifest["resultsListConfig"].append(
                {
                    "key": "unloadingEnergy",
                    "heading": "Unloading Energy (J)",
                    "filtering": False,
                }
            )
            self.manifest["cardsConfig"]["C"].append(
                {
                    "id": "energyVolume",
                    "title": "Energy Absorbed-Interior Volume",
                    "component": "MultiExperimentScatterPlot",
                    "props": {
                        "xDataKey": "volume",
                        "yDataKey": "energyAbsorbed",
                        "xAxisLabel": "Interior Volume (mm³)",
                        "yAxisLabel": "Energy Absorbed (J)",
                        "colorScaleMeasurement": "energyAbsorbed",
                    },
                }
            )



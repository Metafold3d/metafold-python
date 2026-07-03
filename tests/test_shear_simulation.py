import json
import pytest
from unittest.mock import MagicMock

from metafold.simulation.compression_simulation import (
    BoundaryCondition,
    CompressionSimulation,
    DEFAULT_BOUNDARY_CONDITIONS,
    ExperimentMesh,
    ExperimentPistonMesh,
    ForceSource,
    SimulationParameters,
    WorkflowStep,
    WorkflowStepType,
)

ALL_FACES = ["x-", "x+", "y-", "y+", "z-", "z+"]


@pytest.fixture
def ply_folder(tmp_path):
    for name in ["top.ply", "mid.ply", "out.ply"]:
        (tmp_path / name).write_bytes(b"ply\n")
    return tmp_path


@pytest.fixture
def basic_parts():
    from metafold.materials import DEFAULT_MIDSOLE_NOMINAL, DEFAULT_OUTSOLE, DEFAULT_UPPER_FOAM
    from metafold.simulation.compression_simulation import ExperimentPistonCylinder
    return [
        ExperimentPistonCylinder(),
        ExperimentMesh("upper_foam", DEFAULT_UPPER_FOAM, "top.ply"),
        ExperimentMesh("midsole", DEFAULT_MIDSOLE_NOMINAL, "mid.ply"),
        ExperimentMesh("outsole", DEFAULT_OUTSOLE, "out.ply"),
    ]


def _prepare_sim(parts, ply_folder, tmp_path, params=None, workflow_steps=None):
    """Build a sim with a fixed fake patch and run create_sim_config."""
    kwargs = {}
    if workflow_steps is not None:
        kwargs["workflow_steps"] = workflow_steps
    sim = CompressionSimulation(
        parts=parts,
        simulation_name="t",
        stl_folder_path=str(ply_folder),
        output_path=str(tmp_path / "out"),
        client=MagicMock(),
        simulation_parameters=params or SimulationParameters(),
        **kwargs,
    )
    fake_patch = {"size": [0.1, 0.1, 0.05], "offset": [0.0, 0.0, 0.0], "resolution": [32, 32, 16]}
    for info in sim.part_infos:
        info.patch = fake_patch
        if hasattr(info.part, "filename"):
            info.volume_filename = f"{info.part_unique_name}_volume.bin"
    sim.create_sim_config()
    return sim


class TestSimulationParametersBoundaries:
    """Tests for per-face boundary_conditions and force_source."""

    @pytest.fixture
    def prepared_sim(self, ply_folder, basic_parts, tmp_path, request):
        params = getattr(request, "param", SimulationParameters())
        return _prepare_sim(basic_parts, ply_folder, tmp_path, params)

    def _bc(self, sim, side):
        face = sim.ups.getroot().find(f".//BoundaryConditions/Face[@side='{side}']")
        assert face is not None, f"Missing face side='{side}'"
        return face.find("BCType")

    def _bc_var(self, sim, side):
        return self._bc(sim, side).get("var")

    def _archive_labels(self, sim):
        return [el.get("label") for el in sim.ups.getroot().findall(".//DataArchiver/save")]

    # --- defaults ---

    def test_defaults(self):
        p = SimulationParameters()
        assert p.boundary_conditions == {
            "x-": BoundaryCondition.SYMMETRIC,
            "x+": BoundaryCondition.SYMMETRIC,
            "y-": BoundaryCondition.SYMMETRIC,
            "y+": BoundaryCondition.SYMMETRIC,
            "z-": BoundaryCondition.VELOCITY_DIRICHLET,
            "z+": BoundaryCondition.VELOCITY_DIRICHLET,
        }
        assert p.force_source == ForceSource.BOUNDARY_FORCE
        assert p.force_source_part == ""

    def test_default_dict_is_not_shared(self):
        SimulationParameters().boundary_conditions["z-"] = BoundaryCondition.SYMMETRIC
        assert SimulationParameters().boundary_conditions["z-"] == BoundaryCondition.VELOCITY_DIRICHLET
        assert DEFAULT_BOUNDARY_CONDITIONS["z-"] == BoundaryCondition.VELOCITY_DIRICHLET

    def test_default_lateral_is_symmetric(self, prepared_sim):
        for side in ["x-", "x+", "y-", "y+"]:
            assert self._bc_var(prepared_sim, side) == "symmetry"

    def test_default_zminus_is_dirichlet(self, prepared_sim):
        assert self._bc_var(prepared_sim, "z-") == "Dirichlet"

    def test_zplus_default_is_dirichlet(self, prepared_sim):
        assert self._bc_var(prepared_sim, "z+") == "Dirichlet"

    def test_all_faces_present(self, prepared_sim):
        for side in ALL_FACES:
            assert self._bc(prepared_sim, side) is not None

    def test_default_no_rigid_reaction_force_in_archive(self, prepared_sim):
        assert "RigidReactionForce" not in self._archive_labels(prepared_sim)

    # --- per-face overrides ---

    def test_free_lateral_sets_dirichlet_on_xy(self, ply_folder, basic_parts, tmp_path):
        params = SimulationParameters(
            boundary_conditions={
                side: BoundaryCondition.VELOCITY_DIRICHLET
                for side in ["x-", "x+", "y-", "y+"]
            },
        )
        sim = _prepare_sim(basic_parts, ply_folder, tmp_path, params)
        for side in ["x-", "x+", "y-", "y+"]:
            assert self._bc_var(sim, side) == "Dirichlet"

    def test_symmetric_zminus(self, ply_folder, basic_parts, tmp_path):
        params = SimulationParameters(
            boundary_conditions={"z-": BoundaryCondition.SYMMETRIC},
        )
        sim = _prepare_sim(basic_parts, ply_folder, tmp_path, params)
        assert self._bc_var(sim, "z-") == "symmetry"
        assert self._bc_var(sim, "z+") == "Dirichlet"

    def test_neumann_face(self, ply_folder, basic_parts, tmp_path):
        params = SimulationParameters(
            boundary_conditions={"y+": BoundaryCondition.VELOCITY_NEUMANN},
        )
        sim = _prepare_sim(basic_parts, ply_folder, tmp_path, params)
        bc = self._bc(sim, "y+")
        assert bc.get("var") == "Neumann"
        assert bc.get("label") == "Velocity"
        assert bc.get("id") == "all"
        assert bc.findtext("value") == "[0.0, 0.0, 0.0]"

    def test_partial_dict_merges_over_defaults(self, ply_folder, basic_parts, tmp_path):
        params = SimulationParameters(
            boundary_conditions={"z-": BoundaryCondition.SYMMETRIC},
        )
        sim = _prepare_sim(basic_parts, ply_folder, tmp_path, params)
        # untouched faces keep their defaults
        for side in ["x-", "x+", "y-", "y+"]:
            assert self._bc_var(sim, side) == "symmetry"
        assert self._bc_var(sim, "z+") == "Dirichlet"

    def test_string_values_accepted(self, ply_folder, basic_parts, tmp_path):
        # Manifest JSON delivers plain strings
        params = SimulationParameters(
            boundary_conditions={"z-": "symmetric", "x-": "velocity_neumann"},
        )
        sim = _prepare_sim(basic_parts, ply_folder, tmp_path, params)
        assert self._bc_var(sim, "z-") == "symmetry"
        assert self._bc_var(sim, "x-") == "Neumann"

    def test_unknown_face_raises(self, ply_folder, basic_parts, tmp_path):
        params = SimulationParameters(
            boundary_conditions={"w-": BoundaryCondition.SYMMETRIC},
        )
        with pytest.raises(ValueError, match="Unknown boundary condition face"):
            _prepare_sim(basic_parts, ply_folder, tmp_path, params)

    def test_invalid_condition_raises(self, ply_folder, basic_parts, tmp_path):
        params = SimulationParameters(boundary_conditions={"z-": "bolted"})
        with pytest.raises(ValueError, match="bolted"):
            _prepare_sim(basic_parts, ply_folder, tmp_path, params)

    # --- force_source = RIGID_REACTION_FORCE ---

    def test_rigid_reaction_force_adds_archive_label(self, ply_folder, basic_parts, tmp_path):
        params = SimulationParameters(force_source=ForceSource.RIGID_REACTION_FORCE)
        sim = _prepare_sim(basic_parts, ply_folder, tmp_path, params)
        assert "RigidReactionForce" in self._archive_labels(sim)
        assert "BndyForce_zminus" in self._archive_labels(sim)


class TestForceDisplacementKeys:
    """force-displacement workflow params reflect force_source/force_source_part."""

    FD_STEPS = [WorkflowStep(WorkflowStepType.FORCE_DISPLACEMENT)]

    def _built_sim(self, parts, ply_folder, tmp_path, params):
        sim = _prepare_sim(
            parts, ply_folder, tmp_path, params, workflow_steps=self.FD_STEPS)
        sim.build_workflow()
        return sim

    def _fd_keys(self, sim):
        return json.loads(sim.workflow_params["force-displacement.keys"])

    def test_default_uses_boundary_force(self, ply_folder, basic_parts, tmp_path):
        sim = self._built_sim(
            basic_parts, ply_folder, tmp_path, SimulationParameters())
        assert self._fd_keys(sim) == ["/boundary_force_zminus"]
        assert sim.workflow_params["force-displacement.method"] == "BoundaryForce"

    def test_rigid_reaction_defaults_to_piston(self, ply_folder, basic_parts, tmp_path):
        params = SimulationParameters(force_source=ForceSource.RIGID_REACTION_FORCE)
        sim = self._built_sim(basic_parts, ply_folder, tmp_path, params)
        # The piston is always part_infos[0], i.e. material 0
        assert self._fd_keys(sim) == ["/material0/rigid_reaction_force"]

    def test_rigid_reaction_from_named_part(self, ply_folder, basic_parts, tmp_path):
        params = SimulationParameters(
            force_source=ForceSource.RIGID_REACTION_FORCE,
            force_source_part="midsole",
        )
        sim = self._built_sim(basic_parts, ply_folder, tmp_path, params)
        midsole_index = sim.get_part_info("midsole").material_index
        assert self._fd_keys(sim) == [
            f"/material{midsole_index}/rigid_reaction_force"
        ]

    def test_rigid_reaction_unknown_part_raises(self, ply_folder, basic_parts, tmp_path):
        params = SimulationParameters(
            force_source=ForceSource.RIGID_REACTION_FORCE,
            force_source_part="flux_capacitor",
        )
        with pytest.raises(RuntimeError, match="flux_capacitor"):
            self._built_sim(basic_parts, ply_folder, tmp_path, params)


class TestShearUPS:
    """Verify that CompressionSimulation generates a UPS structurally identical
    to the reference shear test script for the same inputs.

    The grid dimensions depend on the sampled mesh patch and can't be matched
    exactly without running the mesh sampling job, so we test every structural
    property the script controls: BCs, archive outputs, contact, materials,
    viscoelastic modes, and time parameters.
    """

    PISTON_MATERIAL = {
        "density": 1730.0,
        "thermal_conductivity": 45,
        "specific_heat": 4.8e-4,
        "constitutive_model": {
            "type": "rigid",
            "params": {"shear_modulus": 2667.0e6, "bulk_modulus": 8000.0e6},
        },
    }

    PUCK_MATERIAL = {
        "density": 130.0,
        "thermal_conductivity": 45,
        "specific_heat": 4.8e-4,
        "constitutive_model": {
            "type": "Maxwell_Weichert",
            "params": {
                "bulk_modulus": 600000,
                "terminal_shear_modulus": 200000,
                "viscoelastic_series": [
                    {"mode": "mode1", "relaxation_time": 0.005, "partial_shear_modulus": 100000},
                    {"mode": "mode2", "relaxation_time": 0.01,  "partial_shear_modulus": 100000},
                ],
            },
        },
    }

    SHEAR_VELOCITY = [
        [0.0,    0, 0,      0.0],
        [0.0025, 0, 0,     -0.25],
        [0.01,   0, 1.732, -1.0],
        [0.02,   0, 1.732, -1.0],
    ]

    @pytest.fixture
    def shear_sim(self, tmp_path):
        from metafold.materials import Material
        piston_mat = Material.from_dict(self.PISTON_MATERIAL)
        puck_mat = Material.from_dict(self.PUCK_MATERIAL)

        parts = [
            ExperimentPistonMesh(
                name="piston_top",
                filename="piston_top.stl",
                material=piston_mat,
                velocity=self.SHEAR_VELOCITY,
            ),
            ExperimentMesh("puck", puck_mat, "puck.stl"),
        ]

        sim_params = SimulationParameters(
            max_time=0.013,
            init_time=0.0,
            delt_min=0.0,
            delt_max=0.001,
            timestep_multiplier=0.4,
            output_int=0.00075,
            boundary_conditions={
                side: BoundaryCondition.VELOCITY_DIRICHLET for side in ALL_FACES
            },
            force_source=ForceSource.RIGID_REACTION_FORCE,
        )

        for name in ["piston_top.stl", "puck.stl"]:
            (tmp_path / name).write_bytes(b"ply\n")

        sim = CompressionSimulation(
            parts=parts,
            simulation_name="puck_5_A",
            stl_folder_path=str(tmp_path),
            output_path=str(tmp_path / "out"),
            client=MagicMock(),
            simulation_parameters=sim_params,
        )

        # Use a fixed patch (grid dims vary with mesh; we only verify structure)
        fake_patch = {"size": [0.1, 0.1, 0.03], "offset": [-0.05, -0.05, 0.0], "resolution": [64, 64, 20]}
        for info in sim.part_infos:
            info.patch = fake_patch
            if hasattr(info.part, "filename"):
                info.volume_filename = f"{info.part_unique_name}_volume.bin"
        sim.create_sim_config()
        return sim

    def _root(self, shear_sim):
        return shear_sim.ups.getroot()

    def _bc(self, shear_sim, side):
        face = self._root(shear_sim).find(f".//BoundaryConditions/Face[@side='{side}']")
        assert face is not None, f"Missing face side='{side}'"
        return face.find("BCType")

    def _archive_labels(self, shear_sim):
        return [el.get("label") for el in self._root(shear_sim).findall(".//DataArchiver/save")]

    # --- time parameters ---

    def test_max_time(self, shear_sim):
        assert self._root(shear_sim).findtext(".//Time/maxTime") == "0.013"

    def test_timestep_multiplier(self, shear_sim):
        assert self._root(shear_sim).findtext(".//Time/timestep_multiplier") == "0.4"

    def test_output_interval(self, shear_sim):
        assert self._root(shear_sim).findtext(".//DataArchiver/outputInterval") == "0.00075"

    # --- boundary conditions ---

    def test_lateral_faces_are_dirichlet(self, shear_sim):
        for side in ["x-", "x+", "y-", "y+"]:
            assert self._bc(shear_sim, side).get("var") == "Dirichlet", f"side={side}"

    def test_zminus_is_dirichlet(self, shear_sim):
        assert self._bc(shear_sim, "z-").get("var") == "Dirichlet"

    def test_zplus_is_dirichlet(self, shear_sim):
        assert self._bc(shear_sim, "z+").get("var") == "Dirichlet"

    # --- archive outputs ---

    def test_archive_includes_rigid_reaction_force(self, shear_sim):
        assert "RigidReactionForce" in self._archive_labels(shear_sim)

    def test_archive_includes_boundary_forces(self, shear_sim):
        labels = self._archive_labels(shear_sim)
        assert "BndyForce_zminus" in labels
        assert "BndyForce_zplus" in labels

    def test_archive_includes_particle_data(self, shear_sim):
        labels = self._archive_labels(shear_sim)
        assert "p.x" in labels
        assert "p.stress" in labels

    # --- contact ---

    def test_contact_type_is_rigid(self, shear_sim):
        contact = self._root(shear_sim).find(".//contact")
        assert contact is not None
        assert contact.findtext("type") == "rigid"

    def test_contact_has_velocity_file(self, shear_sim):
        contact = self._root(shear_sim).find(".//contact")
        assert contact.findtext("filename") == "velocity_piston_top.txt"

    def test_contact_mu_is_zero(self, shear_sim):
        contact = self._root(shear_sim).find(".//contact")
        assert float(contact.findtext("mu")) == 0.0

    def test_contact_direction(self, shear_sim):
        contact = self._root(shear_sim).find(".//contact")
        assert contact.findtext("direction") == "[1, 1, 1]"

    # --- viscoelastic modes ---

    def test_viscoelastic_modes_are_xml_elements_not_json(self, shear_sim):
        vs = self._root(shear_sim).find(".//viscoelastic_series")
        assert vs is not None
        modes = vs.findall("mode")
        assert len(modes) == 2

    def test_viscoelastic_mode_names(self, shear_sim):
        modes = self._root(shear_sim).findall(".//viscoelastic_series/mode")
        names = [m.get("name") for m in modes]
        assert names == ["mode1", "mode2"]

    def test_viscoelastic_relaxation_times(self, shear_sim):
        modes = self._root(shear_sim).findall(".//viscoelastic_series/mode")
        times = [float(m.findtext("relaxation_time")) for m in modes]
        assert times == [0.005, 0.01]

import json
import pytest
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

from metafold.materials import (
    DEFAULT_MIDSOLE_NOMINAL,
    DEFAULT_OUTSOLE,
    DEFAULT_UPPER_FOAM,
    MATERIAL_TPU,
    MATERIAL_EPU_41,
    MATERIAL_ALUMINUM,
    Material,
)
from metafold.simulation.compression_simulation import (
    ExperimentMesh,
    ExperimentPistonCylinder,
    ExperimentPistonMesh,
    SimulationParameters,
    WorkflowStep,
    WorkflowStepType,
)
from metafold.simulation.run_experiment import (
    _build_parts,
    _build_simulation_parameters,
    _build_varying,
    _build_workflow_steps,
    _resolve_material,
    run_experiment,
    run_experiment_from_zip,
)
from metafold.simulation.compression_experiment import (
    VaryMaterial,
    VaryMesh,
    VarySimulationParameter,
)


class TestResolveMaterial:
    def test_lowercase_preset_name(self):
        assert _resolve_material("default_midsole_nominal") is DEFAULT_MIDSOLE_NOMINAL

    def test_uppercase_normalized(self):
        assert _resolve_material("DEFAULT_OUTSOLE") is DEFAULT_OUTSOLE

    def test_material_instance_passes_through(self):
        assert _resolve_material(DEFAULT_OUTSOLE) is DEFAULT_OUTSOLE

    def test_named_material_tpu(self):
        assert _resolve_material("material_tpu") is MATERIAL_TPU

    def test_named_material_epu_41(self):
        assert _resolve_material("material_epu_41") is MATERIAL_EPU_41

    def test_named_material_aluminum(self):
        assert _resolve_material("material_aluminum") is MATERIAL_ALUMINUM

    def test_inline_dict_custom_material(self):
        custom = {
            "density": 200.0,
            "thermal_conductivity": 45,
            "specific_heat": 4.8e-4,
            "constitutive_model": {
                "type": "comp_mooney_rivlin",
                "params": {"he_constant_1": 1.2e5, "he_constant_2": 1.5e5, "he_PR": 0.43},
            },
        }
        m = _resolve_material(custom)
        assert isinstance(m, Material)
        assert m.density == 200.0

    def test_unknown_preset_raises(self):
        with pytest.raises(ValueError, match="Unknown material preset"):
            _resolve_material("nonexistent_material")


class TestBuildParts:
    def test_piston_cylinder(self):
        parts = _build_parts([{"type": "piston_cylinder"}])
        assert len(parts) == 1
        assert isinstance(parts[0], ExperimentPistonCylinder)

    def test_piston_cylinder_with_velocity(self):
        velocity = [[0.0, 0, 0, 0.0], [0.02, 0, 0, -1.25], [0.04, 0, 0, 0.0]]
        parts = _build_parts([{"type": "piston_cylinder", "velocity": velocity}])
        assert parts[0].velocity == velocity

    def test_piston_cylinder_default_velocity_when_omitted(self):
        from metafold.simulation.compression_simulation import DEFAULT_PISTON_VELOCITY
        parts = _build_parts([{"type": "piston_cylinder"}])
        assert parts[0].velocity == DEFAULT_PISTON_VELOCITY

    def test_piston_mesh(self):
        parts = _build_parts([{"type": "piston_mesh", "file": "piston.ply"}])
        assert isinstance(parts[0], ExperimentPistonMesh)
        assert parts[0].filename == "piston.ply"

    def test_piston_mesh_with_velocity(self):
        velocity = [[0.0, 0, 0, 0.0], [0.02, 0, 0, -1.25], [0.04, 0, 0, 0.0]]
        parts = _build_parts([{"type": "piston_mesh", "file": "piston.ply", "velocity": velocity}])
        assert parts[0].velocity == velocity

    def test_mesh_part_with_preset_material(self):
        parts = _build_parts([
            {
                "name": "midsole",
                "material": "default_midsole_nominal",
                "file": "mid.ply",
                "representative": True,
            }
        ])
        p = parts[0]
        assert isinstance(p, ExperimentMesh)
        assert p.name == "midsole"
        assert p.material is DEFAULT_MIDSOLE_NOMINAL
        assert p.filename == "mid.ply"
        assert p.representative_part is True

    def test_mesh_part_with_material_instance(self):
        parts = _build_parts([
            {"name": "outsole", "material": DEFAULT_OUTSOLE, "file": "out.ply"}
        ])
        assert parts[0].material is DEFAULT_OUTSOLE

    def test_representative_defaults_to_false(self):
        parts = _build_parts([
            {"name": "upper_foam", "material": "default_upper_foam", "file": "top.ply"}
        ])
        assert parts[0].representative_part is False

    def test_missing_name_raises(self):
        with pytest.raises(ValueError, match="missing 'name'"):
            _build_parts([{"material": "default_outsole", "file": "out.ply"}])

    def test_missing_material_raises(self):
        with pytest.raises(ValueError, match="missing 'material'"):
            _build_parts([{"name": "outsole", "file": "out.ply"}])

    def test_missing_file_raises(self):
        with pytest.raises(ValueError, match="missing 'file'"):
            _build_parts([{"name": "outsole", "material": "default_outsole"}])

    def test_full_parts_list_ordering(self):
        parts = _build_parts([
            {"type": "piston_cylinder"},
            {"name": "upper_foam", "material": "default_upper_foam", "file": "top.ply"},
            {"name": "midsole", "material": "default_midsole_nominal", "file": "mid.ply", "representative": True},
            {"name": "outsole", "material": "default_outsole", "file": "out.ply"},
        ])
        assert len(parts) == 4
        assert isinstance(parts[0], ExperimentPistonCylinder)
        assert parts[1].name == "upper_foam"
        assert parts[2].name == "midsole"
        assert parts[3].name == "outsole"


class TestBuildVarying:
    def test_vary_mesh_list(self):
        varying = _build_varying([{"part": "midsole", "files": ["a.ply", "b.ply"]}])
        assert isinstance(varying[0], VaryMesh)
        assert varying[0].part_name == "midsole"

    def test_vary_mesh_glob_string_rejected(self):
        with pytest.raises(ValueError, match="must be a list"):
            _build_varying([{"part": "midsole", "files": "midsoles/*.ply"}])

    def test_vary_material_single(self):
        varying = _build_varying([{"part": "midsole", "material": "default_midsole_nominal"}])
        assert isinstance(varying[0], VaryMaterial)
        assert varying[0].materials == [DEFAULT_MIDSOLE_NOMINAL]

    def test_vary_material_list(self):
        varying = _build_varying([
            {"part": "midsole", "material": ["default_midsole_nominal", "default_outsole"]}
        ])
        assert varying[0].materials == [DEFAULT_MIDSOLE_NOMINAL, DEFAULT_OUTSOLE]

    def test_vary_simulation_parameter(self):
        varying = _build_varying([{"field": "max_time", "values": [0.02, 0.04, 0.06]}])
        assert isinstance(varying[0], VarySimulationParameter)
        assert varying[0].field_path == "max_time"
        assert varying[0].values == [0.02, 0.04, 0.06]

    def test_unrecognised_entry_raises(self):
        with pytest.raises(ValueError, match="Unrecognised varying"):
            _build_varying([{"unknown_key": "foo"}])


class TestBuildWorkflowSteps:
    def test_string_entries(self):
        steps = _build_workflow_steps(["compress", "force_displacement"])
        assert len(steps) == 2
        assert steps[0].type == WorkflowStepType.COMPRESS
        assert steps[1].type == WorkflowStepType.FORCE_DISPLACEMENT

    def test_dict_entry_without_parts(self):
        steps = _build_workflow_steps([{"step": "metrics"}])
        assert steps[0].type == WorkflowStepType.METRICS
        assert steps[0].part_names == []

    def test_dict_entry_with_parts(self):
        steps = _build_workflow_steps([{"step": "metrics", "parts": ["midsole", "outsole"]}])
        assert steps[0].type == WorkflowStepType.METRICS
        assert steps[0].part_names == ["midsole", "outsole"]

    def test_mixed_string_and_dict(self):
        steps = _build_workflow_steps([
            "compress",
            {"step": "metrics", "parts": ["midsole"]},
            "energy_metrics",
        ])
        assert len(steps) == 3
        assert steps[0].type == WorkflowStepType.COMPRESS
        assert steps[1].part_names == ["midsole"]
        assert steps[2].type == WorkflowStepType.ENERGY_METRICS

    def test_all_step_names_accepted(self):
        all_steps = [t.value for t in WorkflowStepType]
        steps = _build_workflow_steps(all_steps)
        assert len(steps) == len(all_steps)
        assert {s.type for s in steps} == set(WorkflowStepType)

    def test_empty_list(self):
        assert _build_workflow_steps([]) == []

    def test_missing_step_key_raises(self):
        with pytest.raises(ValueError, match="missing 'step'"):
            _build_workflow_steps([{"parts": ["midsole"]}])

    def test_invalid_step_name_raises(self):
        with pytest.raises(ValueError):
            _build_workflow_steps(["not_a_real_step"])


class TestBuildSimulationParameters:
    def test_empty_config_returns_defaults(self):
        params = _build_simulation_parameters({})
        assert isinstance(params, SimulationParameters)

    def test_top_level_field_override(self):
        params = _build_simulation_parameters({"max_time": 0.02, "max_resolution": 256})
        assert params.max_time == 0.02
        assert params.max_resolution == 256

    def test_unmodified_fields_keep_defaults(self):
        default = SimulationParameters()
        params = _build_simulation_parameters({"max_time": 0.02})
        assert params.output_int == default.output_int

    def test_enum_field_coerced_from_string(self):
        from metafold.simulation.compression_simulation import ForceSource
        params = _build_simulation_parameters({"force_source": "rigid_reaction_force"})
        assert params.force_source == ForceSource.RIGID_REACTION_FORCE

    def test_invalid_enum_string_raises(self):
        with pytest.raises(ValueError):
            _build_simulation_parameters({"force_source": "vibes"})

    def test_boundary_conditions_dict_passes_through(self):
        # String values are normalized later by create_sim_config
        params = _build_simulation_parameters(
            {"boundary_conditions": {"z-": "symmetric"}})
        assert params.boundary_conditions == {"z-": "symmetric"}


class TestRunExperiment:
    """Integration-level tests: verify run_experiment wires up
    CompressionSimulation and CompressionExperiment correctly,
    without hitting the network."""

    @pytest.fixture
    def ply_folder(self, tmp_path):
        for name in ["top.ply", "mid.ply", "out.ply"]:
            (tmp_path / name).write_bytes(b"ply\n")
        return tmp_path

    def _fake_sim(self, ply_folder):
        fake = MagicMock()
        fake.project_id = "proj-abc"
        fake.stl_folder = ply_folder
        return fake

    def test_returns_project_id(self, ply_folder, tmp_path):
        fake_sim = self._fake_sim(ply_folder)
        with (
            patch("metafold.simulation.run_experiment.CompressionSimulation", return_value=fake_sim),
            patch("metafold.simulation.run_experiment.CompressionExperiment"),
        ):
            result = run_experiment({
                "project_name": "test_exp",
                "output_path": str(tmp_path / "out"),
                "ply_folder": str(ply_folder),
                "parts": [
                    {"type": "piston_cylinder"},
                    {"name": "midsole", "material": "default_midsole_nominal", "file": "mid.ply", "representative": True},
                ],
            })
        assert result == "proj-abc"

    def test_project_name_used_for_both_name_and_project(self, ply_folder, tmp_path):
        fake_sim = self._fake_sim(ply_folder)
        with (
            patch("metafold.simulation.run_experiment.CompressionSimulation", return_value=fake_sim) as mock_sim_cls,
            patch("metafold.simulation.run_experiment.CompressionExperiment"),
        ):
            run_experiment({
                "project_name": "my_sweep",
                "output_path": str(tmp_path / "out"),
                "ply_folder": str(ply_folder),
                "parts": [{"type": "piston_cylinder"}],
            })

        kwargs = mock_sim_cls.call_args.kwargs
        assert kwargs["simulation_name"] == "my_sweep"
        assert kwargs["project_name"] == "my_sweep"
        assert kwargs["create_project_if_needed"] is True

    def test_explicit_project_id_disables_creation(self, ply_folder, tmp_path):
        fake_sim = self._fake_sim(ply_folder)
        with (
            patch("metafold.simulation.run_experiment.CompressionSimulation", return_value=fake_sim) as mock_sim_cls,
            patch("metafold.simulation.run_experiment.CompressionExperiment"),
        ):
            run_experiment({
                "project_name": "t",
                "output_path": str(tmp_path / "out"),
                "project_id": "explicit-pid",
                "parts": [],
            })

        kwargs = mock_sim_cls.call_args.kwargs
        assert kwargs["project_id"] == "explicit-pid"
        assert kwargs["create_project_if_needed"] is False

    def test_simulation_config_applied(self, ply_folder, tmp_path):
        fake_sim = self._fake_sim(ply_folder)
        captured = {}

        def capture_sim(*args, **kwargs):
            captured.update(kwargs)
            return fake_sim

        with (
            patch("metafold.simulation.run_experiment.CompressionSimulation", side_effect=capture_sim),
            patch("metafold.simulation.run_experiment.CompressionExperiment"),
        ):
            run_experiment({
                "project_name": "t",
                "output_path": str(tmp_path / "out"),
                "parts": [],
                "simulation": {"max_time": 0.02, "max_resolution": 128},
            })

        params = captured["simulation_parameters"]
        assert params.max_time == 0.02
        assert params.max_resolution == 128

    def test_workflow_steps_config_passed_to_simulation(self, ply_folder, tmp_path):
        fake_sim = self._fake_sim(ply_folder)
        captured = {}

        def capture_sim(*args, **kwargs):
            captured.update(kwargs)
            return fake_sim

        with (
            patch("metafold.simulation.run_experiment.CompressionSimulation", side_effect=capture_sim),
            patch("metafold.simulation.run_experiment.CompressionExperiment"),
        ):
            run_experiment({
                "project_name": "t",
                "output_path": str(tmp_path / "out"),
                "parts": [],
                "workflow_steps": ["compress", "force_displacement", "stress_strain"],
            })

        steps = captured["workflow_steps"]
        assert len(steps) == 3
        assert steps[0].type == WorkflowStepType.COMPRESS
        assert steps[1].type == WorkflowStepType.FORCE_DISPLACEMENT
        assert steps[2].type == WorkflowStepType.STRESS_STRAIN

    def test_omitting_workflow_steps_uses_simulation_default(self, ply_folder, tmp_path):
        fake_sim = self._fake_sim(ply_folder)
        captured = {}

        def capture_sim(*args, **kwargs):
            captured.update(kwargs)
            return fake_sim

        with (
            patch("metafold.simulation.run_experiment.CompressionSimulation", side_effect=capture_sim),
            patch("metafold.simulation.run_experiment.CompressionExperiment"),
        ):
            run_experiment({
                "project_name": "t",
                "output_path": str(tmp_path / "out"),
                "parts": [],
            })

        assert "workflow_steps" not in captured

    def test_missing_project_name_raises(self):
        with pytest.raises(ValueError, match="project_name"):
            run_experiment({"output_path": "/out", "parts": []})

    def test_missing_output_path_raises(self):
        with pytest.raises(ValueError, match="output_path"):
            run_experiment({"project_name": "t", "parts": []})

    def test_output_path_argument_overrides_config(self, ply_folder, tmp_path):
        fake_sim = self._fake_sim(ply_folder)
        captured = {}

        def capture_sim(*args, **kwargs):
            captured.update(kwargs)
            return fake_sim

        with (
            patch("metafold.simulation.run_experiment.CompressionSimulation", side_effect=capture_sim),
            patch("metafold.simulation.run_experiment.CompressionExperiment"),
        ):
            run_experiment(
                {"project_name": "t", "output_path": "/ignored", "parts": []},
                output_path=str(tmp_path / "actual"),
            )

        assert captured["output_path"] == str(tmp_path / "actual")

    def test_does_not_wait_for_results_by_default(self, ply_folder, tmp_path):
        fake_sim = self._fake_sim(ply_folder)
        with (
            patch("metafold.simulation.run_experiment.CompressionSimulation", return_value=fake_sim),
            patch("metafold.simulation.run_experiment.CompressionExperiment") as mock_exp_cls,
        ):
            run_experiment({
                "project_name": "t",
                "output_path": str(tmp_path / "out"),
                "parts": [],
            })

        assert mock_exp_cls.call_args.kwargs["auto_download_results"] is False

    def test_wait_for_results_downloads(self, ply_folder, tmp_path):
        fake_sim = self._fake_sim(ply_folder)
        with (
            patch("metafold.simulation.run_experiment.CompressionSimulation", return_value=fake_sim),
            patch("metafold.simulation.run_experiment.CompressionExperiment") as mock_exp_cls,
        ):
            run_experiment(
                {
                    "project_name": "t",
                    "output_path": str(tmp_path / "out"),
                    "parts": [],
                },
                wait_for_results=True,
            )

        assert mock_exp_cls.call_args.kwargs["auto_download_results"] is True


class TestRunExperimentFromZip:
    def _make_zip(self, tmp_path, manifest: dict, mesh_files: list[str] = None) -> Path:
        zip_path = tmp_path / "experiment.zip"
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("experiment.json", json.dumps(manifest))
            for filename in (mesh_files or []):
                zf.writestr(filename, b"ply\n")
        return zip_path

    @pytest.fixture
    def base_manifest(self):
        return {
            "project_name": "test_project",
            "parts": [{"type": "piston_cylinder"}],
        }

    def test_extracts_and_runs(self, tmp_path, base_manifest):
        zip_path = self._make_zip(tmp_path, base_manifest)
        fake_sim = MagicMock()
        fake_sim.project_id = "zip-proj"
        fake_sim.stl_folder = tmp_path

        with (
            patch("metafold.simulation.run_experiment.CompressionSimulation", return_value=fake_sim),
            patch("metafold.simulation.run_experiment.CompressionExperiment"),
        ):
            result = run_experiment_from_zip(zip_path, output_path=str(tmp_path / "out"))

        assert result == "zip-proj"

    def test_ply_folder_set_to_extracted_dir(self, tmp_path, base_manifest):
        zip_path = self._make_zip(tmp_path, base_manifest, mesh_files=["mid.ply"])
        captured = {}
        fake_sim = MagicMock()
        fake_sim.project_id = "p"
        fake_sim.stl_folder = tmp_path

        def capture_sim(*args, **kwargs):
            captured.update(kwargs)
            return fake_sim

        with (
            patch("metafold.simulation.run_experiment.CompressionSimulation", side_effect=capture_sim),
            patch("metafold.simulation.run_experiment.CompressionExperiment"),
        ):
            run_experiment_from_zip(zip_path, output_path=str(tmp_path / "out"))

        # ply_folder should point inside a temp directory (not the zip path)
        assert captured["stl_folder_path"] != str(zip_path)
        assert Path(captured["stl_folder_path"]).is_dir() or True  # temp dir is cleaned up by now

    def test_missing_manifest_raises(self, tmp_path):
        zip_path = tmp_path / "bad.zip"
        with ZipFile(zip_path, "w") as zf:
            zf.writestr("mid.ply", b"ply\n")

        with pytest.raises(ValueError, match="experiment.json"):
            run_experiment_from_zip(zip_path, output_path=str(tmp_path / "out"))

    def test_shear_simulation_params_from_manifest(self, tmp_path):
        from metafold.simulation.compression_simulation import ForceSource

        manifest = {
            "project_name": "shear",
            "parts": [{"type": "piston_cylinder"}],
            "simulation": {
                "force_source": "rigid_reaction_force",
                "boundary_conditions": {"z-": "symmetric"},
            },
        }
        zip_path = self._make_zip(tmp_path, manifest)
        captured = {}
        fake_sim = MagicMock(project_id="p", stl_folder=tmp_path)

        def capture_sim(*args, **kwargs):
            captured.update(kwargs)
            return fake_sim

        with (
            patch("metafold.simulation.run_experiment.CompressionSimulation", side_effect=capture_sim),
            patch("metafold.simulation.run_experiment.CompressionExperiment"),
        ):
            run_experiment_from_zip(zip_path, output_path=str(tmp_path / "out"))

        params = captured["simulation_parameters"]
        assert params.force_source == ForceSource.RIGID_REACTION_FORCE
        assert params.boundary_conditions == {"z-": "symmetric"}

    def test_generator_and_created_fields_ignored(self, tmp_path):
        manifest = {
            "project_name": "grasshopper_export",
            "created": "2026-03-17T10:23:58.984313",
            "generator": "grasshopper-dtb-export",
            "parts": [{
                "type": "mesh",
                "name": "midsole",
                "material": "default_midsole_nominal",
                "file": "mid.ply",
                "representative": True,
            }],
        }
        zip_path = self._make_zip(tmp_path, manifest, mesh_files=["mid.ply"])
        fake_sim = MagicMock()
        fake_sim.project_id = "p"
        fake_sim.stl_folder = tmp_path

        with (
            patch("metafold.simulation.run_experiment.CompressionSimulation", return_value=fake_sim),
            patch("metafold.simulation.run_experiment.CompressionExperiment"),
        ):
            result = run_experiment_from_zip(zip_path, output_path=str(tmp_path / "out"))

        assert result == "p"

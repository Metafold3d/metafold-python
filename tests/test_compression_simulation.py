import pytest
from unittest.mock import MagicMock
import json
import yaml

from metafold.simulation.compression_simulation import (
    DEFAULT_PISTON_VELOCITY,
    CompressionSimulation,
    ExperimentMesh,
    ExperimentPistonBase,
    ExperimentPistonCylinder,
    WorkflowStep,
    WorkflowStepType,
)
from metafold.materials import (
    DEFAULT_MIDSOLE_NOMINAL,
    DEFAULT_OUTSOLE,
    DEFAULT_UPPER_FOAM,
)


@pytest.fixture
def ply_folder(tmp_path):
    """Create a tmp folder with dummy ply files matching the example."""
    for name in ["top.ply", "mid.ply", "out.ply"]:
        (tmp_path / name).write_bytes(b"ply\n")
    return tmp_path


@pytest.fixture
def basic_parts():
    return [
        ExperimentPistonCylinder(),
        ExperimentMesh("upper_foam", DEFAULT_UPPER_FOAM, "top.ply"),
        ExperimentMesh("midsole", DEFAULT_MIDSOLE_NOMINAL, "mid.ply", representative_part=True),
        ExperimentMesh("outsole", DEFAULT_OUTSOLE, "out.ply"),
    ]


@pytest.fixture
def sim(ply_folder, basic_parts, tmp_path):
    return CompressionSimulation(
        parts=basic_parts,
        simulation_name="test_sim",
        stl_folder_path=str(ply_folder),
        output_path=str(tmp_path / "out"),
        client=MagicMock(),
    )


class TestConstruction:
    def test_basic_construction_succeeds(self, sim):
        assert sim.simulation_name == "test_sim"
        assert len(sim.part_infos) == 4

    def test_piston_is_first_part(self, sim):
        # pistons must come first for material index 0
        assert isinstance(sim.part_infos[0].part, ExperimentPistonBase)

    def test_output_dir_created(self, ply_folder, basic_parts, tmp_path):
        out = tmp_path / "new_dir"
        assert not out.exists()
        CompressionSimulation(
            parts=basic_parts,
            simulation_name="t",
            stl_folder_path=str(ply_folder),
            output_path=str(out),
            client=MagicMock(),
        )
        assert out.is_dir()

    def test_ply_files_resolved(self, sim, ply_folder):
        for info in sim.part_infos:
            if hasattr(info.part, "filename") and not isinstance(info.part, ExperimentPistonBase):
                assert info.file_path is not None
                assert info.file_path.is_file()

    def test_missing_ply_raises(self, ply_folder, tmp_path):
        parts = [
            ExperimentMesh("midsole", DEFAULT_MIDSOLE_NOMINAL, "nonexistent.ply", representative_part=True),
        ]
        with pytest.raises(ValueError, match="not found"):
            CompressionSimulation(
                parts=parts,
                simulation_name="t",
                stl_folder_path=str(ply_folder),
                output_path=str(tmp_path / "out"),
                client=MagicMock(),
            )

class TestValidation:
    def test_requires_representative_part(self, ply_folder, tmp_path):
        parts = [
            ExperimentPistonCylinder(),
            ExperimentMesh("midsole", DEFAULT_MIDSOLE_NOMINAL, "mid.ply"),  # no rep
        ]
        with pytest.raises(ValueError, match="representative_part"):
            CompressionSimulation(
                parts=parts,
                simulation_name="t",
                stl_folder_path=str(ply_folder),
                output_path=str(tmp_path / "out"),
                client=MagicMock(),
            )

    def test_only_one_representative_part_allowed(self, ply_folder, tmp_path):
        parts = [
            ExperimentMesh("midsole", DEFAULT_MIDSOLE_NOMINAL, "mid.ply", representative_part=True),
            ExperimentMesh("outsole", DEFAULT_OUTSOLE, "out.ply", representative_part=True),
        ]
        with pytest.raises(ValueError, match="At most one"):
            CompressionSimulation(
                parts=parts,
                simulation_name="t",
                stl_folder_path=str(ply_folder),
                output_path=str(tmp_path / "out"),
                client=MagicMock(),
            )


class TestWorkflowStepsInput:
    def test_accepts_workflow_step_instance(self):
        steps = CompressionSimulation._clean_workflow_steps_input([
            WorkflowStep(WorkflowStepType.COMPRESS),
        ])
        assert steps[0].type == WorkflowStepType.COMPRESS

    def test_accepts_enum(self):
        steps = CompressionSimulation._clean_workflow_steps_input([WorkflowStepType.COMPRESS])
        assert steps[0].type == WorkflowStepType.COMPRESS

    def test_accepts_string(self):
        steps = CompressionSimulation._clean_workflow_steps_input(["compress"])
        assert steps[0].type == WorkflowStepType.COMPRESS

    def test_accepts_tuple_with_part_names(self):
        steps = CompressionSimulation._clean_workflow_steps_input([
            (WorkflowStepType.METRICS, "midsole", "outsole"),
        ])
        assert steps[0].type == WorkflowStepType.METRICS
        assert steps[0].part_names == ["midsole", "outsole"]

    def test_stress_strain_with_part_names_rejected(self):
        with pytest.raises(ValueError, match="not supported"):
            WorkflowStep(WorkflowStepType.STRESS_STRAIN, "midsole")


class TestContainsStep:
    def test_default_contains_compress(self, sim):
        assert sim._contains_step(WorkflowStepType.COMPRESS)

    def test_missing_step(self, ply_folder, basic_parts, tmp_path):
        s = CompressionSimulation(
            parts=basic_parts,
            simulation_name="t",
            stl_folder_path=str(ply_folder),
            output_path=str(tmp_path / "out"),
            client=MagicMock(),
            workflow_steps=[WorkflowStep(WorkflowStepType.COMPRESS)],
        )
        assert not s._contains_step(WorkflowStepType.VON_MISES_STRESS)


class TestBuildWorkflow:
    """Tests for workflow construction. These skip prepare() and manually
    populate the minimal part_info state that build_workflow needs."""

    @pytest.fixture
    def prepared_sim(self, sim):
        """A sim with fake patches and volume filenames set on each part_info,
        so create_sim_config and build_workflow can run without the client."""
        fake_patch = {
            "size":       [0.1, 0.1, 0.05],
            "offset":     [0.0, 0.0, 0.0],
            "resolution": [32, 32, 16],
        }
        for info in sim.part_infos:
            info.patch = fake_patch
            if hasattr(info.part, "filename"):
                info.volume_filename = f"{info.part_unique_name}_volume.bin"
        sim.create_sim_config()
        return sim

    def test_create_sim_config_assigns_material_indices(self, prepared_sim):
        indices = [info.material_index for info in prepared_sim.part_infos]
        assert indices == list(range(len(prepared_sim.part_infos)))

    def test_create_sim_config_piston_is_material_zero(self, prepared_sim):
        piston = prepared_sim.part_infos[0]
        assert isinstance(piston.part, ExperimentPistonBase)
        assert piston.material_index == 0

    def test_build_workflow_has_per_part_metrics_jobs(self, prepared_sim):
        yaml_str, _ = prepared_sim.build_workflow()
        loaded = yaml.safe_load(yaml_str)
        # one metrics job per non-piston mesh part
        for info in prepared_sim.part_infos:
            if not isinstance(info.part, ExperimentPistonBase) and hasattr(info.part, "filename"):
                assert f"metrics-{info.part_unique_name}" in loaded["jobs"]

    def test_build_workflow_compress_has_velocity(self, prepared_sim):
        _, params = prepared_sim.build_workflow()
        text_inputs = json.loads(params["compress.text_inputs"])
        assert "velocity_piston.txt" in text_inputs
        assert text_inputs["velocity_piston.txt"] == DEFAULT_PISTON_VELOCITY

    def test_build_workflow_compress_references_volume_assets(self, prepared_sim):
        prepared_sim.build_workflow()
        # compress.volume should be a list of volume filenames
        compress_assets = prepared_sim.workflow_assets["compress.volume"]
        assert isinstance(compress_assets, list)
        # one entry per mesh part with a volume_filename (i.e. excluding the cylinder piston)
        expected = [
            info.volume_filename
            for info in prepared_sim.part_infos
            if info.volume_filename
        ]
        assert compress_assets == expected

    def test_build_workflow_skips_disabled_steps(self, ply_folder, basic_parts, tmp_path):
        s = CompressionSimulation(
            parts=basic_parts,
            simulation_name="t",
            stl_folder_path=str(ply_folder),
            output_path=str(tmp_path / "out"),
            client=MagicMock(),
            workflow_steps=[
                WorkflowStep(WorkflowStepType.METRICS),
                WorkflowStep(WorkflowStepType.COMPRESS),
            ],
        )
        fake_patch = {"size": [0.1]*3, "offset": [0.0]*3, "resolution": [16]*3}
        for info in s.part_infos:
            info.patch = fake_patch
            if hasattr(info.part, "filename"):
                info.volume_filename = f"{info.part_unique_name}.bin"
        s.create_sim_config()
        yaml_str, _ = s.build_workflow()
        loaded = yaml.safe_load(yaml_str)
        # force-displacement wasn't requested
        assert not any("force-displacement" in k for k in loaded["jobs"])


class TestSampleAssets:
    def _make_success_workflow(self, job_names=()):
        """Return a mock workflow that is already in 'success' state."""
        wf = MagicMock()
        wf.state = "success"
        wf.jobs = list(job_names)
        return wf

    def test_batch_size_configurable(self, ply_folder, basic_parts, tmp_path):
        s = CompressionSimulation(
            parts=basic_parts,
            simulation_name="t",
            stl_folder_path=str(ply_folder),
            output_path=str(tmp_path / "out"),
            client=MagicMock(),
            prep_workflow_batch_size=5,
        )
        assert s.prep_workflow_batch_size == 5

    def test_fewer_parts_than_batch_size_runs_one_workflow(self, sim):
        # 3 mesh parts, batch_size=10 → 1 workflow
        sim.client.workflows.run_async.return_value = self._make_success_workflow()
        sim.sample_assets()
        assert sim.client.workflows.run_async.call_count == 1
        assert len(sim.prep_workflows) == 1

    def test_parts_split_into_multiple_batches(self, ply_folder, basic_parts, tmp_path):
        # 3 mesh parts, batch_size=2 → 2 workflows
        sim = CompressionSimulation(
            parts=basic_parts,
            simulation_name="t",
            stl_folder_path=str(ply_folder),
            output_path=str(tmp_path / "out"),
            client=MagicMock(),
            prep_workflow_batch_size=2,
        )
        sim.client.workflows.run_async.return_value = self._make_success_workflow()
        sim.sample_assets()
        assert sim.client.workflows.run_async.call_count == 2
        assert len(sim.prep_workflows) == 2

    def test_all_workflows_launched_before_any_wait(self, sim):
        # run_async should be called for all batches before workflows.get is polled
        call_log = []
        sim.client.workflows.run_async.side_effect = lambda *a, **kw: (
            call_log.append("launch") or self._make_success_workflow()
        )
        sim.client.workflows.get.side_effect = lambda id: (
            call_log.append("poll") or self._make_success_workflow()
        )
        sim.sample_assets()
        # all launches happened before any polls
        last_launch = max(i for i, e in enumerate(call_log) if e == "launch")
        first_poll = next((i for i, e in enumerate(call_log) if e == "poll"), len(call_log))
        assert last_launch < first_poll

    def test_failed_workflow_raises(self, sim):
        failed_wf = MagicMock()
        failed_wf.state = "failure"
        failed_wf.jobs = []
        sim.client.workflows.run_async.return_value = failed_wf
        with pytest.raises(RuntimeError, match="prep workflow"):
            sim.sample_assets()

    def test_sample_mesh_job_recorded_on_part_info(self, sim):
        sim.client.workflows.run_async.return_value = self._make_success_workflow()
        sim.sample_assets()
        for info in sim.part_infos:
            if hasattr(info.part, "filename"):
                assert "sample-mesh" in info.jobs
                assert "preprocess-mesh" in info.jobs



class TestWorkflowYaml:
    def test_workflow_yaml_matches_expected(self, ply_folder, basic_parts, tmp_path):
        sim = CompressionSimulation(
            parts=basic_parts,
            simulation_name="test_sim",
            stl_folder_path=str(ply_folder),
            output_path=str(tmp_path / "out"),
            client=MagicMock(),
        )
        fake_patch = {
            "size":       [0.1, 0.1, 0.05],
            "offset":     [0.0, 0.0, 0.0],
            "resolution": [32, 32, 16],
        }
        for info in sim.part_infos:
            info.patch = fake_patch
            if hasattr(info.part, "filename"):
                info.volume_filename = f"{info.part_unique_name}_volume.bin"
        sim.create_sim_config()

        yaml_str, workflow_params = sim.build_workflow()
        expected_yaml = """
jobs:
  metrics-upper_foam:
    type: implicit/metrics
  metrics-midsole:
    type: implicit/metrics
  metrics-outsole:
    type: implicit/metrics
  compress:
    type: sim/custom
  von-mises-stress:
    type: sim/postprocess/von-mises-stress
    needs:
    - compress
    assets:
      data: compress
  effective-strain:
    type: sim/postprocess/effective-strain
    needs:
    - compress
    assets:
      data: compress
  force-displacement:
    type: sim/postprocess/force-displacement
    needs:
    - compress
    assets:
      data: compress
  stress-strain:
    type: sim/postprocess/stress-strain
    needs:
    - force-displacement
    assets:
      data: force-displacement
  particle-displacement:
    type: sim/postprocess/particle-displacement
    needs:
    - compress
    assets:
      data: compress
"""
        assert yaml_str.strip() == expected_yaml.strip()

        # Check workflow_assets has the right volume references
        assert sim.workflow_assets["metrics-upper_foam.volume"] == "upper_foam_volume.bin"
        assert sim.workflow_assets["metrics-midsole.volume"] == "midsole_volume.bin"
        assert sim.workflow_assets["metrics-outsole.volume"] == "outsole_volume.bin"
        assert sim.workflow_assets["compress.volume"] == [
            "upper_foam_volume.bin",
            "midsole_volume.bin",
            "outsole_volume.bin",
        ]

        expected_params = json.loads(r"""
        {
        "compress.volume_offset": [
            "[0.0, 0.0, 0.0]",
            "[0.0, 0.0, 0.0]",
            "[0.0, 0.0, 0.0]"
        ],
        "compress.volume_resolution": [
            "[32, 32, 16]",
            "[32, 32, 16]",
            "[32, 32, 16]"
        ],
        "compress.volume_size": [
            "[0.1, 0.1, 0.05]",
            "[0.1, 0.1, 0.05]",
            "[0.1, 0.1, 0.05]"
        ],
        "effective-strain.keys": "[\"/material0/deformation_gradient\", \"/material1/deformation_gradient\", \"/material2/deformation_gradient\", \"/material3/deformation_gradient\"]",
        "force-displacement.keys": "[\"/boundary_force_zminus\"]",
        "force-displacement.method": "BoundaryForce",
        "metrics-midsole.volume_offset": "[0.0, 0.0, 0.0]",
        "metrics-midsole.volume_resolution": "[32, 32, 16]",
        "metrics-midsole.volume_size": "[0.1, 0.1, 0.05]",
        "metrics-outsole.volume_offset": "[0.0, 0.0, 0.0]",
        "metrics-outsole.volume_resolution": "[32, 32, 16]",
        "metrics-outsole.volume_size": "[0.1, 0.1, 0.05]",
        "metrics-upper_foam.volume_offset": "[0.0, 0.0, 0.0]",
        "metrics-upper_foam.volume_resolution": "[32, 32, 16]",
        "metrics-upper_foam.volume_size": "[0.1, 0.1, 0.05]",
        "particle-displacement.keys": "[\"/material0/position\", \"/material1/position\", \"/material2/position\", \"/material3/position\"]",
        "stress-strain.initial_length": "0.05",
        "stress-strain.keys": "[\"/force_displacement\"]",
        "von-mises-stress.keys": "[\"/material0/cauchy_stress\", \"/material1/cauchy_stress\", \"/material2/cauchy_stress\", \"/material3/cauchy_stress\"]"
        }
        """)
        for key, value in expected_params.items():
            assert key in workflow_params, f"missing key: {key}"
            assert workflow_params[key] == value, f"mismatch for {key}: {workflow_params[key]!r} != {value!r}"


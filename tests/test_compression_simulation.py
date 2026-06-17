from io import BytesIO
from zipfile import ZipFile

import pytest
from unittest.mock import MagicMock
import json
import yaml
from pathlib import Path

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


class TestGridBounds:
    """The grid must enclose every part, not just the representative one, so
    nothing (e.g. an outsole below the midsole) gets clipped."""

    def _grid_bounds(self, sim):
        """Return (lower, upper) of the generated UPS grid box, in metres."""
        root = sim.ups.getroot()
        lower = json.loads(root.findtext(".//Grid//Box/lower"))
        upper = json.loads(root.findtext(".//Grid//Box/upper"))
        return lower, upper

    def _prepare(self, sim, patches):
        """Assign each part_info a patch (by unique name) and build the config."""
        for info in sim.part_infos:
            info.patch = patches[info.part_unique_name]
            if hasattr(info.part, "filename"):
                info.volume_filename = f"{info.part_unique_name}_volume.bin"
        sim.create_sim_config()

    def test_low_mesh_part_expands_grid_downward(self, sim):
        # The regression: a mesh part (outsole) below the representative midsole
        # must still expand the grid down. Before the fix, mesh parts were
        # skipped and the outsole's bottom got clipped.
        # Patch offsets/sizes are in mm; outsole bottom at -50 mm is below all
        # other parts (incl. the piston cylinder, whose lowest point is +25 mm).
        rep = {"size": [100.0, 100.0, 50.0], "offset": [0.0, 0.0, 0.0], "resolution": [32, 32, 16]}
        low = {"size": [100.0, 100.0, 20.0], "offset": [0.0, 0.0, -50.0], "resolution": [32, 32, 8]}
        patches = {
            "piston": rep, "upper_foam": rep, "midsole": rep, "outsole": low,
        }
        self._prepare(sim, patches)
        lower, _ = self._grid_bounds(sim)
        mz = sim.simulation_parameters.margin_z
        # grid bottom (metres) = outsole bottom (-50 mm = -0.05 m) minus margin.
        assert lower[2] == pytest.approx(-0.05 - mz, abs=1e-6)

    def test_bottom_margin_clearance_added(self, sim):
        # Bottom (z-) clearance was previously missing entirely. With all parts
        # flush at z=0, the grid bottom must sit margin_z below the lowest part.
        flat = {"size": [0.1, 0.1, 0.05], "offset": [0.0, 0.0, 0.0], "resolution": [32, 32, 16]}
        self._prepare(sim, {n: flat for n in
                            ["piston", "upper_foam", "midsole", "outsole"]})
        lower, _ = self._grid_bounds(sim)
        mz = sim.simulation_parameters.margin_z
        # Lowest part bottom is z=0 (piston cylinder sits higher), so the grid
        # bottom is exactly -margin_z.
        assert lower[2] == pytest.approx(-mz, abs=1e-6)


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
  energy-metrics:
    type: sim/postprocess/energy-metrics
    needs:
    - force-displacement
    assets:
      data: force-displacement
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



class TestMeshDataKey:
    def test_simple_name(self):
        assert CompressionSimulation._mesh_data_key("midsole") == "midsole_mesh"

    def test_underscored_name(self):
        assert CompressionSimulation._mesh_data_key("upper_foam") == "upper_foam_mesh"

    def test_numeric_suffix(self):
        assert CompressionSimulation._mesh_data_key("support_1") == "support_1_mesh"


class TestMakeManifestV2:
    """Tests for make_manifest_v2 — manifest structure only, no I/O."""

    @pytest.fixture
    def sim_with_full_steps(self, ply_folder, basic_parts, tmp_path):
        return CompressionSimulation(
            parts=basic_parts,
            simulation_name="t",
            stl_folder_path=str(ply_folder),
            output_path=str(tmp_path / "out"),
            client=MagicMock(),
        )

    def test_results_list_config_has_name_column_always(self, sim_with_full_steps):
        sim_with_full_steps.make_manifest_v2(results=[])
        keys = [c["key"] for c in sim_with_full_steps.manifest["resultsListConfig"]]
        assert "name" in keys

    def test_results_list_config_has_energy_columns_when_step_present(self, sim_with_full_steps):
        sim_with_full_steps.make_manifest_v2(results=[])
        keys = [c["key"] for c in sim_with_full_steps.manifest["resultsListConfig"]]
        assert keys == ["name", "volume", "energyAbsorbed", "loadingEnergy", "unloadingEnergy"]

    def test_results_list_config_no_energy_columns_when_step_absent(self, ply_folder, basic_parts, tmp_path):
        sim = CompressionSimulation(
            parts=basic_parts,
            simulation_name="t",
            stl_folder_path=str(ply_folder),
            output_path=str(tmp_path / "out"),
            client=MagicMock(),
            workflow_steps=[WorkflowStep(WorkflowStepType.COMPRESS)],
        )
        sim.make_manifest_v2(results=[])
        keys = [c["key"] for c in sim.manifest["resultsListConfig"]]
        assert keys == ["name"]

    def test_card_c_present_when_energy_metrics_step_present(self, sim_with_full_steps):
        sim_with_full_steps.make_manifest_v2(results=[])
        card_c = sim_with_full_steps.manifest["cardsConfig"]["C"]
        assert len(card_c) == 1
        assert card_c[0]["id"] == "energyVolume"

    def test_card_c_absent_when_no_energy_metrics(self, ply_folder, basic_parts, tmp_path):
        sim = CompressionSimulation(
            parts=basic_parts,
            simulation_name="t",
            stl_folder_path=str(ply_folder),
            output_path=str(tmp_path / "out"),
            client=MagicMock(),
            workflow_steps=[WorkflowStep(WorkflowStepType.COMPRESS)],
        )
        sim.make_manifest_v2(results=[])
        assert sim.manifest["cardsConfig"]["C"] == []

    def test_simulation_preview_data_source(self, sim_with_full_steps):
        sim_with_full_steps.make_manifest_v2()
        assert sim_with_full_steps.manifest["simulationPreviewConfig"]["dataSource"] == "position"

    def test_simulation_preview_variables_full(self, sim_with_full_steps):
        sim_with_full_steps.make_manifest_v2()
        variables = sim_with_full_steps.manifest["simulationPreviewConfig"]["variables"]
        names = [v["dataSource"] for v in variables]
        assert "vonMisesStress" in names
        assert "effectiveStrain" in names
        assert "particleDisplacement" in names

    def test_simulation_preview_variables_skipped_when_step_missing(
        self, ply_folder, basic_parts, tmp_path
    ):
        sim = CompressionSimulation(
            parts=basic_parts,
            simulation_name="t",
            stl_folder_path=str(ply_folder),
            output_path=str(tmp_path / "out"),
            client=MagicMock(),
            workflow_steps=[WorkflowStep(WorkflowStepType.COMPRESS)],
        )
        sim.make_manifest_v2()
        assert sim.manifest["simulationPreviewConfig"]["variables"] == []

    def test_materials_config_uses_part_names(self, sim_with_full_steps):
        sim_with_full_steps.make_manifest_v2()
        materials = sim_with_full_steps.manifest["simulationPreviewConfig"]["materialsConfig"]
        assert set(materials.keys()) == {"0", "1", "2", "3"}
        assert materials["0"]["displayName"] == "piston"
        assert materials["0"].get("useSolidColor") is True

    def test_materials_config_non_piston_no_solid_color(self, sim_with_full_steps):
        sim_with_full_steps.make_manifest_v2()
        materials = sim_with_full_steps.manifest["simulationPreviewConfig"]["materialsConfig"]
        for idx, info in enumerate(sim_with_full_steps.part_infos):
            if not isinstance(info.part, ExperimentPistonBase):
                assert "useSolidColor" not in materials[str(idx)]

    def test_part_preview_config_excludes_piston(self, sim_with_full_steps):
        sim_with_full_steps.make_manifest_v2()
        previews = sim_with_full_steps.manifest["partPreviewConfig"]
        names = [p["displayName"] for p in previews]
        assert "piston" not in names
        assert "upper_foam" in names
        assert "midsole" in names
        assert "outsole" in names

    def test_part_preview_config_uses_mesh_data_key(self, sim_with_full_steps):
        sim_with_full_steps.make_manifest_v2()
        previews = sim_with_full_steps.manifest["partPreviewConfig"]
        for p in previews:
            assert p["dataSource"] == f"{p['displayName']}_mesh"

    def test_part_preview_config_file_format(self, sim_with_full_steps):
        sim_with_full_steps.make_manifest_v2()
        previews = sim_with_full_steps.manifest["partPreviewConfig"]
        for p in previews:
            assert p["fileFormat"] == "ply"

    def test_card_a_present_when_force_displacement_step_present(self, sim_with_full_steps):
        sim_with_full_steps.make_manifest_v2()
        assert "A" in sim_with_full_steps.manifest["cardsConfig"]
        assert sim_with_full_steps.manifest["cardsConfig"]["A"][0]["id"] == "forceDisplacement"

    def test_card_a_empty_when_no_force_displacement(self, ply_folder, basic_parts, tmp_path):
        sim = CompressionSimulation(
            parts=basic_parts,
            simulation_name="t",
            stl_folder_path=str(ply_folder),
            output_path=str(tmp_path / "out"),
            client=MagicMock(),
            workflow_steps=[WorkflowStep(WorkflowStepType.COMPRESS)],
        )
        sim.make_manifest_v2()
        assert sim.manifest["cardsConfig"]["A"] == []


class TestResultsHaveEnergyMetrics:
    def test_returns_true_when_energy_metrics_step_present(self, ply_folder, basic_parts, tmp_path):
        sim = CompressionSimulation(
            parts=basic_parts,
            simulation_name="t",
            stl_folder_path=str(ply_folder),
            output_path=str(tmp_path / "out"),
            client=MagicMock(),
        )
        assert sim._results_have_energy_metrics([]) is True

    def test_returns_false_when_energy_metrics_step_absent(self, ply_folder, basic_parts, tmp_path):
        sim = CompressionSimulation(
            parts=basic_parts,
            simulation_name="t",
            stl_folder_path=str(ply_folder),
            output_path=str(tmp_path / "out"),
            client=MagicMock(),
            workflow_steps=[WorkflowStep(WorkflowStepType.COMPRESS)],
        )
        assert sim._results_have_energy_metrics([]) is False


class TestWriteResultsToZipV2:
    """Tests for _write_results_to_zip_v2 using a mocked workflow.

    Tests use a workflow_steps list that excludes COMPRESS and
    FORCE_DISPLACEMENT because those branches read the downloaded HDF
    files (for position extraction and energy calculation respectively),
    which would require valid HDF content from our mock client. The
    other postprocess HDFs ship whole and only need an empty file on
    disk, which the mock provides.
    """

    @pytest.fixture
    def prepared_sim(self, ply_folder, basic_parts, tmp_path):
        sim = CompressionSimulation(
            parts=basic_parts,
            simulation_name="ts",
            stl_folder_path=str(ply_folder),
            output_path=str(tmp_path / "out"),
            client=MagicMock(),
            use_legacy_results_format=False,
            workflow_steps=[
                WorkflowStep(WorkflowStepType.METRICS),
                WorkflowStep(WorkflowStepType.VON_MISES_STRESS),
                WorkflowStep(WorkflowStepType.EFFECTIVE_STRAIN),
                WorkflowStep(WorkflowStepType.PARTICLE_DISPLACEMENT),
                WorkflowStep(WorkflowStepType.STRESS_STRAIN),
            ],
        )
        # Mocked download_file needs to actually create the file so
        # zf.write can read it back.
        def fake_download(asset_id, path):
            Path(path).touch()
        sim.client.assets.download_file.side_effect = fake_download

        for i, info in enumerate(sim.part_infos):
            info.material_index = i
            info.jobs["metrics"] = f"metrics-{info.part_unique_name}"
        sim.results = [{"id": "wf-1", "name": "ts"}]
        return sim

    def _mock_success_workflow(self):
        wf = MagicMock()
        wf.state = "success"
        asset = MagicMock()
        asset.id = "asset-x"
        wf.get_asset.return_value = asset
        wf.get_parameter.return_value = "1000"
        return wf

    def test_skips_failed_workflow(self, prepared_sim):
        failed = MagicMock()
        failed.state = "failure"
        prepared_sim.client.workflows.get.return_value = failed

        with BytesIO() as buf:
            with ZipFile(buf, "w") as zf:
                prepared_sim._write_results_to_zip_v2(zf)
            buf.seek(0)
            with ZipFile(buf) as zf:
                # Mesh files are always written for debugging even on failure;
                # no HDF data files should be present.
                names = zf.namelist()
                assert all("original_" in n for n in names)
                assert not any(n.endswith(".h5") for n in names)

    def test_mesh_previews_named_with_original_prefix(self, prepared_sim):
        prepared_sim.client.workflows.get.return_value = self._mock_success_workflow()

        with BytesIO() as buf:
            with ZipFile(buf, "w") as zf:
                prepared_sim._write_results_to_zip_v2(zf)
            buf.seek(0)
            with ZipFile(buf) as zf:
                names = zf.namelist()
                assert "ts/original_upper_foam.ply" in names
                assert "ts/original_midsole.ply" in names
                assert "ts/original_outsole.ply" in names
                assert not any("piston" in n for n in names)

    def test_mesh_data_keys_use_underscore_format(self, prepared_sim):
        prepared_sim.client.workflows.get.return_value = self._mock_success_workflow()

        with BytesIO() as buf:
            with ZipFile(buf, "w") as zf:
                prepared_sim._write_results_to_zip_v2(zf)

        result = prepared_sim.results[0]
        assert "upper_foam_mesh" in result["data"]
        assert "midsole_mesh" in result["data"]
        assert "outsole_mesh" in result["data"]
        assert result["data"]["midsole_mesh"]["name"] == "ts/original_midsole.ply"

    def test_per_material_hdf_data_keys(self, prepared_sim):
        prepared_sim.client.workflows.get.return_value = self._mock_success_workflow()

        with BytesIO() as buf:
            with ZipFile(buf, "w") as zf:
                prepared_sim._write_results_to_zip_v2(zf)

        result = prepared_sim.results[0]
        for i in range(4):
            assert f"vonMisesStress{i}" in result["data"]
            assert result["data"][f"vonMisesStress{i}"]["path"] == f"/material{i}/von_mises_stress"
            assert result["data"][f"vonMisesStress{i}"]["name"] == "ts/von_mises.h5"

    def test_per_material_histogram_keys(self, prepared_sim):
        prepared_sim.client.workflows.get.return_value = self._mock_success_workflow()

        with BytesIO() as buf:
            with ZipFile(buf, "w") as zf:
                prepared_sim._write_results_to_zip_v2(zf)

        result = prepared_sim.results[0]
        for i in range(4):
            assert f"vonMisesStressHistogram{i}" in result["data"]
            assert (
                result["data"][f"vonMisesStressHistogram{i}"]["path"]
                == f"/material{i}/von_mises_stress_histogram"
            )

    def test_total_volume_sums_analysis_targets(self, prepared_sim):
        wf = self._mock_success_workflow()
        wf.get_parameter.return_value = "1000"
        prepared_sim.client.workflows.get.return_value = wf

        with BytesIO() as buf:
            with ZipFile(buf, "w") as zf:
                prepared_sim._write_results_to_zip_v2(zf)

        # 3 analysis-target parts × 1000 = 3000
        assert prepared_sim.results[0]["volume"] == 3000.0

    def test_no_step_means_no_hdf_download(self, ply_folder, basic_parts, tmp_path):
        sim = CompressionSimulation(
            parts=basic_parts,
            simulation_name="ts",
            stl_folder_path=str(ply_folder),
            output_path=str(tmp_path / "out"),
            client=MagicMock(),
            use_legacy_results_format=False,
            workflow_steps=[],
        )
        for i, info in enumerate(sim.part_infos):
            info.material_index = i
        sim.results = [{"id": "wf-1", "name": "ts"}]
        sim.client.workflows.get.return_value = self._mock_success_workflow()

        with BytesIO() as buf:
            with ZipFile(buf, "w") as zf:
                sim._write_results_to_zip_v2(zf)
            buf.seek(0)
            with ZipFile(buf) as zf:
                names = zf.namelist()
                assert not any(n.endswith(".h5") for n in names)

class TestSetupClient:
    """Tests for project_id resolution and project creation in setup_client.

    These mock MetafoldClient construction to avoid real network calls and
    only verify the logic of which path is taken based on the inputs.
    """

    @pytest.fixture(autouse=True)
    def env_vars(self, monkeypatch):
        """Provide the env vars MetafoldClient needs so construction doesn't blow up."""
        monkeypatch.setenv("METAFOLD_CLIENT_ID", "cid")
        monkeypatch.setenv("METAFOLD_CLIENT_SECRET", "csec")
        monkeypatch.setenv("METAFOLD_AUTH_DOMAIN", "auth.example.com")
        monkeypatch.setenv("METAFOLD_BASE_URL", "https://api.example.com")
        monkeypatch.delenv("METAFOLD_PROJECT_ID", raising=False)

    @pytest.fixture
    def patched_client_class(self, monkeypatch):
        """Replace MetafoldClient in the module so setup_client uses a fake.
        Returns the MagicMock class so tests can inspect call args."""
        from metafold.simulation import compression_simulation
        fake_class = MagicMock()
        monkeypatch.setattr(compression_simulation, "MetafoldClient", fake_class)
        return fake_class

    def _build_sim(self, ply_folder, basic_parts, tmp_path, **kwargs):
        """Build a sim that goes through setup_client. Don't pass `client=` so
        the constructor calls setup_client itself."""
        return CompressionSimulation(
            parts=basic_parts,
            simulation_name="t",
            stl_folder_path=str(ply_folder),
            output_path=str(tmp_path / "out"),
            **kwargs,
        )

    def test_explicit_project_id_used_directly(
        self, ply_folder, basic_parts, tmp_path, patched_client_class
    ):
        sim = self._build_sim(
            ply_folder, basic_parts, tmp_path,
            project_id="explicit-pid",
            create_project_if_needed=False,
        )
        assert sim.project_id == "explicit-pid"
        # MetafoldClient should be constructed once, with the project_id
        assert patched_client_class.call_count == 1
        kwargs = patched_client_class.call_args.kwargs
        assert kwargs["project_id"] == "explicit-pid"

    def test_env_var_project_id_used_when_no_arg(
        self, ply_folder, basic_parts, tmp_path, patched_client_class, monkeypatch
    ):
        monkeypatch.setenv("METAFOLD_PROJECT_ID", "env-pid")
        sim = self._build_sim(
            ply_folder, basic_parts, tmp_path,
            create_project_if_needed=False,
        )
        assert sim.project_id == "env-pid"
        assert patched_client_class.call_args.kwargs["project_id"] == "env-pid"

    def test_no_project_id_no_creation_raises(
        self, ply_folder, basic_parts, tmp_path, patched_client_class
    ):
        with pytest.raises(ValueError, match="project_id"):
            self._build_sim(
                ply_folder, basic_parts, tmp_path,
                create_project_if_needed=False,
            )

    def test_existing_project_by_name_is_reused(
        self, ply_folder, basic_parts, tmp_path, patched_client_class
    ):
        # First MetafoldClient() call (no project_id) returns a client whose
        # projects.list() finds an existing match.
        existing = MagicMock()
        existing.id = "existing-pid"
        first_client = MagicMock()
        first_client.projects.list.return_value = [existing]
        patched_client_class.side_effect = [first_client, MagicMock()]

        sim = self._build_sim(
            ply_folder, basic_parts, tmp_path,
            project_name="my_project",
            create_project_if_needed=True,
        )

        assert sim.project_id == "existing-pid"
        first_client.projects.list.assert_called_once_with(q="name:my_project")
        first_client.projects.create.assert_not_called()
        # MetafoldClient called twice — once without project_id, once with
        assert patched_client_class.call_count == 2
        assert patched_client_class.call_args_list[1].kwargs["project_id"] == "existing-pid"

    def test_new_project_created_when_name_not_found(
        self, ply_folder, basic_parts, tmp_path, patched_client_class
    ):
        created = MagicMock()
        created.id = "new-pid"
        first_client = MagicMock()
        first_client.projects.list.return_value = []
        first_client.projects.create.return_value = created
        patched_client_class.side_effect = [first_client, MagicMock()]

        sim = self._build_sim(
            ply_folder, basic_parts, tmp_path,
            project_name="brand_new",
            create_project_if_needed=True,
        )

        assert sim.project_id == "new-pid"
        first_client.projects.create.assert_called_once()
        # First positional arg is the name
        assert first_client.projects.create.call_args.args[0] == "brand_new"

    def test_auto_generated_project_name_when_create_flag_set(
        self, ply_folder, basic_parts, tmp_path, patched_client_class
    ):
        created = MagicMock()
        created.id = "auto-pid"
        first_client = MagicMock()
        first_client.projects.list.return_value = []
        first_client.projects.create.return_value = created
        patched_client_class.side_effect = [first_client, MagicMock()]

        sim = self._build_sim(
            ply_folder, basic_parts, tmp_path,
            create_project_if_needed=True,
        )

        # An auto-generated UUID-suffixed name was assigned and used
        assert sim.project_name.startswith("experiment_")
        first_client.projects.create.assert_called_once()
        assert first_client.projects.create.call_args.args[0].startswith("experiment_")
        assert sim.project_id == "auto-pid"

    def test_http_error_during_list_falls_through_to_create(
        self, ply_folder, basic_parts, tmp_path, patched_client_class
    ):
        from requests import HTTPError
        created = MagicMock()
        created.id = "fallback-pid"
        first_client = MagicMock()
        first_client.projects.list.side_effect = HTTPError("404")
        first_client.projects.create.return_value = created
        patched_client_class.side_effect = [first_client, MagicMock()]

        sim = self._build_sim(
            ply_folder, basic_parts, tmp_path,
            project_name="xyz",
            create_project_if_needed=True,
        )

        assert sim.project_id == "fallback-pid"
        first_client.projects.create.assert_called_once()


class TestFindOrCreateProjectCancel:
    """find_or_create_project should cancel a reused project's in-flight
    workflows when asked, since the new run overwrites those results."""

    @pytest.fixture
    def patched_client_class(self, monkeypatch):
        from metafold.simulation import compression_simulation
        fake_class = MagicMock()
        monkeypatch.setattr(compression_simulation, "MetafoldClient", fake_class)
        return fake_class

    def _wf(self, wid, state):
        w = MagicMock()
        w.id = wid
        w.state = state
        return w

    def test_cancels_active_workflows_on_existing_project(self, patched_client_class):
        client = patched_client_class.return_value
        existing = MagicMock()
        existing.id = "pid-1"
        client.projects.list.return_value = [existing]
        # list(q="state:pending") -> [w1]; list(q="state:started") -> [w2]
        client.workflows.list.side_effect = [
            [self._wf("w1", "pending")],
            [self._wf("w2", "started")],
        ]

        pid = CompressionSimulation.find_or_create_project(
            "existing", access_token="tok", base_url="http://x/",
            cancel_existing_workflows=True,
        )

        assert pid == "pid-1"
        cancelled = {c.args[0] for c in client.workflows.cancel.call_args_list}
        assert cancelled == {"w1", "w2"}

    def test_no_cancel_when_flag_off(self, patched_client_class):
        client = patched_client_class.return_value
        existing = MagicMock()
        existing.id = "pid-1"
        client.projects.list.return_value = [existing]

        CompressionSimulation.find_or_create_project(
            "existing", access_token="tok", base_url="http://x/",
        )

        client.workflows.cancel.assert_not_called()

    def test_no_cancel_when_creating_new_project(self, patched_client_class):
        client = patched_client_class.return_value
        client.projects.list.return_value = []  # nothing existing -> create
        created = MagicMock()
        created.id = "new-pid"
        client.projects.create.return_value = created

        pid = CompressionSimulation.find_or_create_project(
            "fresh", access_token="tok", base_url="http://x/",
            cancel_existing_workflows=True,
        )

        assert pid == "new-pid"
        client.workflows.cancel.assert_not_called()

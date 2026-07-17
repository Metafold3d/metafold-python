# tests/test_compression_experiment.py
import pytest
import copy
from pathlib import Path
from unittest.mock import MagicMock

from metafold.simulation.compression_experiment import (
    CompressionExperiment,
    VaryMesh,
    VaryMaterial,
    VarySimulationParameter,
    VaryVelocity,
)
from metafold.materials import Material, ConstitutiveModel, RigidParams


@pytest.fixture
def ply_folder(tmp_path):
    """Create dummy ply files matching a few patterns."""
    for name in ["mid-0.ply", "mid-1.ply", "mid-2.ply",
                 "out-0.ply", "out-1.ply", "out-2.ply"]:
        (tmp_path / name).write_bytes(b"ply\n")
    return tmp_path


@pytest.fixture
def mock_part_info():
    """Factory that builds a fake PartInfo-like object."""
    def _make(name, filename=None):
        info = MagicMock()
        info.part = MagicMock()
        info.part.name = name
        info.part.filename = filename or f"{name}.ply"
        info.part_unique_name = name
        return info
    return _make


@pytest.fixture
def mock_sim(mock_part_info, ply_folder, tmp_path):
    """A fake CompressionSimulation with just enough surface area for the
    experiment class to work."""
    sim = MagicMock()
    sim.stl_folder = ply_folder
    sim.out_dir = tmp_path
    sim.simulation_name = "base_sim"
    sim.part_infos = [
        mock_part_info("piston"),
        mock_part_info("midsole", "mid.ply"),
        mock_part_info("outsole", "out.ply"),
    ]
    # get_part_info returns by name
    sim.get_part_info.side_effect = lambda n: next(
        (p for p in sim.part_infos if p.part.name == n), None
    )
    return sim


@pytest.fixture
def basic_material():
    return Material(
        density=1000.0,
        thermal_conductivity=1.0,
        specific_heat=1.0,
        constitutive_model=ConstitutiveModel(
            params=RigidParams(shear_modulus=100.0, bulk_modulus=200.0)
        ),
    )


class TestVaryMesh:
    def test_resolves_glob_pattern(self, ply_folder):
        v = VaryMesh("midsole", "mid-*.ply")
        v.resolve(ply_folder)
        assert v.sim_count == 3
        assert all("mid-" in f for f in v.files)

    def test_files_sorted_naturally(self, ply_folder):
        # add a file that would break lexical sort
        (ply_folder / "mid-10.ply").write_bytes(b"ply\n")
        v = VaryMesh("midsole", "mid-*.ply")
        v.resolve(ply_folder)
        # expect 0, 1, 2, 10 — not 0, 1, 10, 2
        nums = [Path(f).stem.split("-")[-1] for f in v.files]
        assert nums == ["0", "1", "2", "10"]

    def test_accepts_explicit_list(self, ply_folder):
        files = [str(ply_folder / "mid-0.ply"), str(ply_folder / "mid-1.ply")]
        v = VaryMesh("midsole", files)
        v.resolve(ply_folder)
        assert v.files == files
        assert v.sim_count == 2

    def test_rejects_unknown_pattern_type(self, ply_folder):
        v = VaryMesh("midsole", 12345)
        with pytest.raises(ValueError, match="Unrecognized"):
            v.resolve(ply_folder)


class TestExperimentConstruction:
    def test_varying_part_names_populated(self, mock_sim):
        exp = CompressionExperiment(mock_sim, [
            VaryMesh("midsole", "mid-*.ply"),
            VaryMesh("outsole", "out-*.ply"),
        ], auto_run=False)
        assert exp.varying_part_names == ["midsole", "outsole"]

    def test_varying_files_resolved(self, mock_sim):
        varying = [VaryMesh("midsole", "mid-*.ply")]
        CompressionExperiment(mock_sim, varying, auto_run=False)
        assert varying[0].sim_count == 3


class TestExperimentNoVarying:
    def test_empty_varying_runs_one_sim(self, mock_sim):
        exp = CompressionExperiment(mock_sim, [], auto_run=False)
        exp.prepare()
        assert len(exp.sims) == 1

    def test_empty_varying_all_parts_are_invariant(self, mock_sim):
        exp = CompressionExperiment(mock_sim, [], auto_run=False)
        exp.prepare()
        invariant_names = [p.part.name for p in exp.experiment_part_infos]
        assert set(invariant_names) == {"piston", "midsole", "outsole"}


class TestExperimentPrepare:
    def test_prepare_creates_correct_number_of_sims(self, mock_sim):
        exp = CompressionExperiment(mock_sim, [VaryMesh("midsole", "mid-*.ply")], auto_run=False)
        exp.prepare()
        # 3 variant files → 3 sims
        assert len(exp.sims) == 3

    def test_prepare_assigns_unique_simulation_names(self, mock_sim):
        exp = CompressionExperiment(mock_sim, [VaryMesh("midsole", "mid-*.ply")], auto_run=False)
        exp.prepare()
        names = [s.simulation_name for s in exp.sims]
        assert len(set(names)) == len(names), f"duplicate names: {names}"

    def test_prepare_applies_variation_to_each_sim(self, mock_sim):
        v = VaryMesh("midsole", "mid-*.ply")
        exp = CompressionExperiment(mock_sim, [v])
        exp.prepare()
        # apply_to should hit each sim once — check varying part filenames differ
        filenames = []
        for s in exp.sims:
            midsole_info = next(p for p in s.part_infos if p.part.name == "midsole")
            filenames.append(midsole_info.part.filename)
        assert len(filenames) == len(filenames), "all sims got the same file"

    def test_invariant_parts_in_experiment_part_infos(self, mock_sim):
        exp = CompressionExperiment(mock_sim, [VaryMesh("midsole", "mid-*.ply")], auto_run=False)
        exp.prepare()
        names = [p.part.name for p in exp.experiment_part_infos]
        # piston and outsole aren't varying, so they appear once
        assert names.count("piston") == 1
        assert names.count("outsole") == 1
        # midsole has 3 forks
        assert names.count("midsole") == 3


class TestExperimentRun:
    def test_run_calls_lifecycle_on_each_sim(self, mock_sim):
        exp = CompressionExperiment(mock_sim, [VaryMesh("midsole", "mid-*.ply")], force_rerun=True)
        exp.prepare()
        exp.run()
        for s in exp.sims:
            s.create_sim_config.assert_called_once()
            s.build_workflow.assert_called_once()
            s.run_workflow.assert_called_once()


class TestDownloadResults:
    def test_download_results_writes_one_zip(self, mock_sim):
        exp = CompressionExperiment(mock_sim, [VaryMesh("midsole", "mid-*.ply")], auto_run=False)
        exp.prepare()
        exp.download_results()
        assert (mock_sim.out_dir / "out.zip").is_file()

    def test_download_results_calls_each_sim(self, mock_sim):
        exp = CompressionExperiment(mock_sim, [VaryMesh("midsole", "mid-*.ply")], auto_run=False)
        exp.prepare()
        # set sim.results so extend works
        for s in exp.sims:
            s.results = []
        exp.download_results()
        for s in exp.sims:
            s._write_results_to_zip_v2.assert_called_once()

    def test_download_results_writes_combined_manifest(self, mock_sim):
        exp = CompressionExperiment(mock_sim, [VaryMesh("midsole", "mid-*.ply")], auto_run=False)
        exp.prepare()
        # give each fake sim a result so they get combined
        for i, s in enumerate(exp.sims):
            s.results = [{"id": f"wf-{i}", "name": f"sim_{i}"}]
        exp.download_results()
        mock_sim._write_manifest_to_zip_v2.assert_called_once()
        _, passed_results = mock_sim._write_manifest_to_zip_v2.call_args[0]
        assert len(passed_results) == 3


class TestVaryMaterial:
    def test_resolve_sets_sim_count(self, basic_material, tmp_path):
        v = VaryMaterial("midsole", [basic_material, basic_material, basic_material])
        v.resolve(tmp_path)
        assert v.sim_count == 3

    def test_apply_to_sets_material(self, basic_material, mock_sim):
        m1 = copy.deepcopy(basic_material)
        m2 = copy.deepcopy(basic_material)
        m2.density = 2000.0
        v = VaryMaterial("midsole", [m1, m2])
        v.resolve(mock_sim.stl_folder)

        v.apply_to(0, mock_sim)
        midsole = mock_sim.get_part_info("midsole")
        assert midsole.part.material is m1

        v.apply_to(1, mock_sim)
        assert midsole.part.material is m2


class TestVaryMaterialSweep:
    def test_sweep_creates_one_material_per_value(self, basic_material):
        v = VaryMaterial.sweep("midsole", basic_material, "density", [100, 200, 300])
        assert v.sim_count == 0  # resolve not called yet
        assert len(v.materials) == 3

    def test_sweep_varies_top_level_field(self, basic_material):
        v = VaryMaterial.sweep("midsole", basic_material, "density", [100, 200, 300])
        densities = [m.density for m in v.materials]
        assert densities == [100, 200, 300]

    def test_sweep_varies_nested_field(self, basic_material):
        v = VaryMaterial.sweep(
            "midsole",
            basic_material,
            "constitutive_model.params.shear_modulus",
            [10.0, 20.0],
        )
        shears = [m.constitutive_model.params.shear_modulus for m in v.materials]
        assert shears == [10.0, 20.0]

    def test_sweep_materials_are_independent(self, basic_material):
        v = VaryMaterial.sweep(
            "midsole", basic_material,
            "constitutive_model.params.shear_modulus",
            [10.0, 20.0],
        )
        # mutating one shouldn't affect the other
        v.materials[0].constitutive_model.params.shear_modulus = 999.0
        assert v.materials[1].constitutive_model.params.shear_modulus == 20.0


PROFILES = [
    [[0.0, 0, 0, 0.0], [0.04, 0, 0, -1.25]],
    [[0.0, 0, 0, 0.0], [0.04, 0, 0, -2.50]],
]


class TestVaryVelocity:
    def test_resolve_sets_sim_count(self, tmp_path):
        v = VaryVelocity("piston", PROFILES)
        v.resolve(tmp_path)
        assert v.sim_count == 2

    def test_apply_to_sets_velocity(self, mock_sim):
        v = VaryVelocity("piston", PROFILES)
        v.apply_to(0, mock_sim)
        assert mock_sim.get_part_info("piston").part.velocity == PROFILES[0]
        v.apply_to(1, mock_sim)
        assert mock_sim.get_part_info("piston").part.velocity == PROFILES[1]

    def test_single_flat_profile_rejected(self):
        # one profile passed where a list of profiles is expected
        with pytest.raises(ValueError, match="list of \\[t, vx, vy, vz\\] rows"):
            VaryVelocity("piston", [[0.0, 0, 0, 0.0], [0.04, 0, 0, -1.25]])

    def test_malformed_row_rejected(self):
        with pytest.raises(ValueError, match="rows"):
            VaryVelocity("piston", [[[0.0, 0, 0]]])  # 3 floats, not 4

    def test_non_rigid_part_rejected(self, mock_sim):
        class PlainPart:  # no velocity attribute, unlike piston/support parts
            name = "midsole"

        info = MagicMock()
        info.part = PlainPart()
        mock_sim.get_part_info.side_effect = lambda n: info

        v = VaryVelocity("midsole", PROFILES)
        with pytest.raises(ValueError, match="not a rigid"):
            v.apply_to(0, mock_sim)


class TestSimulationNames:
    def _experiment(self, mock_sim, names, varying=None):
        return CompressionExperiment(
            mock_sim,
            varying if varying is not None else [VaryMesh("midsole", "mid-*.ply")],
            simulation_names=names,
            auto_run=False,
        )

    def test_custom_names_used(self, mock_sim):
        exp = self._experiment(mock_sim, ["a", "b", "c"])
        exp.prepare()
        assert [s.simulation_name for s in exp.sims] == ["a", "b", "c"]

    def test_blank_name_falls_back_to_auto(self, mock_sim):
        exp = self._experiment(mock_sim, ["a", "", "c"])
        exp.prepare()
        assert [s.simulation_name for s in exp.sims] == ["a", "base_sim_sim1", "c"]

    def test_short_list_falls_back_to_auto(self, mock_sim):
        exp = self._experiment(mock_sim, ["a"])
        exp.prepare()
        assert [s.simulation_name for s in exp.sims] == [
            "a", "base_sim_sim1", "base_sim_sim2"]

    def test_duplicate_names_rejected(self, mock_sim):
        with pytest.raises(ValueError, match="unique"):
            self._experiment(mock_sim, ["a", "a", "c"])

    def test_name_colliding_with_auto_name_rejected(self, mock_sim):
        # sim1's fallback name is base_sim_sim1; naming sim0 the same collides
        with pytest.raises(ValueError, match="unique"):
            self._experiment(mock_sim, ["base_sim_sim1"])

    def test_path_separator_rejected(self, mock_sim):
        with pytest.raises(ValueError, match="path separator"):
            self._experiment(mock_sim, ["run/1"])

    def test_none_entry_falls_back_to_auto(self, mock_sim):
        exp = self._experiment(mock_sim, [None, "custom2", None])
        exp.prepare()
        assert [s.simulation_name for s in exp.sims] == [
            "base_sim_sim0", "custom2", "base_sim_sim2"]

    def test_non_list_rejected(self, mock_sim):
        with pytest.raises(ValueError, match="list of strings"):
            self._experiment(mock_sim, "baseline")

    def test_non_string_entry_rejected(self, mock_sim):
        with pytest.raises(ValueError, match="list of strings"):
            self._experiment(mock_sim, ["a", 2])

    def test_force_rerun_clears_custom_named_results(self, mock_sim):
        stale = mock_sim.out_dir / "custom_a_results.json"
        stale.write_text("{}")
        exp = self._experiment(mock_sim, ["custom_a", "b", "c"])
        exp.force_rerun = True
        exp._clear_saved_state()
        assert not stale.exists()


class TestVaryingCountMismatch:
    def test_mismatched_counts_rejected(self, mock_sim):
        with pytest.raises(ValueError, match="same number"):
            CompressionExperiment(
                mock_sim,
                [
                    VaryMesh("midsole", "mid-*.ply"),  # 3 files
                    VaryVelocity("piston", PROFILES),  # 2 profiles
                ],
                auto_run=False,
            )

    def test_matching_counts_accepted(self, mock_sim):
        exp = CompressionExperiment(
            mock_sim,
            [
                VarySimulationParameter("max_time", [0.02, 0.04]),
                VaryVelocity("piston", PROFILES),
            ],
            auto_run=False,
        )
        assert exp.varying[0].sim_count == exp.varying[1].sim_count == 2


class TestVarySimulationParameter:
    def test_resolve_sets_sim_count(self, tmp_path):
        v = VarySimulationParameter("max_time", [0.02, 0.04, 0.06])
        v.resolve(tmp_path)
        assert v.sim_count == 3

    def test_apply_to_sets_top_level_field(self, mock_sim):
        mock_sim.simulation_parameters = MagicMock()
        mock_sim.simulation_parameters.max_time = 0.04

        v = VarySimulationParameter("max_time", [0.01, 0.02])
        v.apply_to(0, mock_sim)
        assert mock_sim.simulation_parameters.max_time == 0.01

        v.apply_to(1, mock_sim)
        assert mock_sim.simulation_parameters.max_time == 0.02

    def test_apply_to_sets_nested_field(self, mock_sim):
        params = MagicMock()
        params.grid = MagicMock()
        params.grid.resolution = 256
        mock_sim.simulation_parameters = params

        v = VarySimulationParameter("grid.resolution", [128, 512])
        v.apply_to(0, mock_sim)
        assert mock_sim.simulation_parameters.grid.resolution == 128

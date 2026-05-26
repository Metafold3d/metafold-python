import copy
import json
from typing import Any, List, Union, cast
import glob
from pathlib import Path
from metafold.simulation.compression_simulation import (
    CompressionSimulation,
    ExperimentMesh,
)
from metafold.materials import Material
from metafold.utils import natural_sort
from zipfile import ZipFile


class ExperimentVarying:
    sim_count: int = 0

    def resolve(self, _base_dir: Path) -> None:
        raise NotImplementedError


class VaryMesh(ExperimentVarying):
    part_name: str
    _input_pattern: Any
    files: list[str]

    def __init__(
        self, part_name: str, files_or_file_pattern: Union[str, List[str], List[Path]]
    ):
        self.part_name = part_name
        self._files_or_file_pattern = files_or_file_pattern

    def resolve(self, base_dir: Path):
        self.files = []
        if (
            isinstance(self._files_or_file_pattern, str)
            and "*" in self._files_or_file_pattern
        ):
            all_files = glob.glob(str(base_dir / self._files_or_file_pattern))
            self.files.extend(natural_sort(all_files))
        elif isinstance(self._files_or_file_pattern, List):
            self.files.extend(str(f) if f is not None else None for f in self._files_or_file_pattern)
        else:
            raise ValueError(f"Unrecognized file pattern {self._files_or_file_pattern}")
        self.sim_count = len(self.files)

    def apply_to(self, sim_index: int, sim: CompressionSimulation):
        part_info: CompressionSimulation.PartInfo = sim.get_part_info(self.part_name)
        if self.files[sim_index] is None:
            part_info.disabled = True
        else:
            cast(ExperimentMesh, part_info.part).filename = self.files[sim_index]
        sim.resolve_file_path(part_info)


class VaryMaterial(ExperimentVarying):
    part_name: str
    materials: List[Material]

    def __init__(self, part_name: str, materials: List[Material]):
        self.part_name = part_name
        self.materials = materials

    def resolve(self, base_dir: Path):
        self.sim_count = len(self.materials)

    def apply_to(self, sim_index: int, sim: CompressionSimulation):
        part_info: CompressionSimulation.PartInfo = sim.get_part_info(self.part_name)
        part_info.part.material = self.materials[sim_index]

    @classmethod
    def sweep(
        cls, part_name: str, base_material: Material, field_path: str, values: list
    ):
        """Create a VaryMaterial by varying one field on a base material.
        field_path is dotted, e.g. "constitutive_model.params.terminal_shear_modulus"
        """
        materials = []
        for v in values:
            m = copy.deepcopy(base_material)
            parts = field_path.split(".")
            obj = m
            for p in parts[:-1]:
                obj = getattr(obj, p)
            setattr(obj, parts[-1], v)
            materials.append(m)
        return cls(part_name, materials)


class VarySimulationParameter(ExperimentVarying):
    field_path: str
    values: list

    def __init__(self, field_path: str, values: list):
        self.field_path = field_path
        self.values = values

    def resolve(self, _base_dir: Path) -> None:
        self.sim_count = len(self.values)

    def apply_to(self, sim_index: int, sim: CompressionSimulation):
        parts = self.field_path.split(".")
        obj = sim.simulation_parameters
        for p in parts[:-1]:
            obj = getattr(obj, p)
        setattr(obj, parts[-1], self.values[sim_index])


class CompressionExperiment:
    base_simulation: CompressionSimulation
    varying: List[ExperimentVarying] = []
    varying_part_names: List[str] = []
    experiment_part_infos: List = []
    sims: List[CompressionSimulation] = []

    def __init__(
        self,
        simulation: CompressionSimulation,
        varying: List[ExperimentVarying],
        verbose: bool = True,
        force_rerun: bool = False,
        auto_run: bool = True,
        auto_download_results: bool = True,
        auto_upload_server_manifest: bool = True,
        use_legacy_results_format: bool = False,
        write_ups: bool = True,
    ):
        simulation.use_legacy_results_format = use_legacy_results_format
        simulation.write_ups = write_ups
        self.use_legacy_results_format = use_legacy_results_format
        self.base_simulation = simulation
        self.varying = varying
        self.verbose = verbose
        self.force_rerun = force_rerun
        self.varying_part_names = []
        for v in self.varying:
            assert self.base_simulation.stl_folder is not None
            v.resolve(self.base_simulation.stl_folder)
            if hasattr(v, "part_name"):
                self.varying_part_names.append(v.part_name)

        if auto_run:
            self.prepare()
            self.run(auto_upload_server_manifest)
            if auto_download_results:
                self.download_results()

    @property
    def _experiment_state_filename(self) -> Path:
        assert self.base_simulation.out_dir is not None
        return (
            self.base_simulation.out_dir
            / f"{self.base_simulation.simulation_name}_experiment.json"
        )

    def _clear_saved_state(self):
        """Delete the experiment state file and all per-sim results files."""
        if self._experiment_state_filename.is_file():
            self._experiment_state_filename.unlink()
        # delete per-sim results — we don't know sim names without state,
        # so just glob for anything matching the pattern
        for f in self.base_simulation.out_dir.glob(
            f"{self.base_simulation.simulation_name}_sim*_results.json"
        ):
            f.unlink()
        # delete out.zip if it exists
        out_zip = self.base_simulation.out_dir / "out.zip"
        if out_zip.is_file():
            out_zip.unlink()

    def _save_experiment_state(self):
        state = {
            "sim_names": [s.simulation_name for s in self.sims],
        }
        with open(self._experiment_state_filename, "w") as f:
            json.dump(state, f, indent=2)

    def _load_experiment_state(self) -> dict:
        if not self._experiment_state_filename.is_file():
            return {}
        with open(self._experiment_state_filename) as f:
            return json.load(f)

    def _log(self, msg: str):
        if self.verbose:
            print(f"[experiment] {msg}")

    def _clone_sim(self, sim_index: int):
        # do a deep copy but without the part infos
        base_part_infos = self.base_simulation.part_infos
        self.base_simulation.part_infos = []
        clone = copy.deepcopy(self.base_simulation)
        self.base_simulation.part_infos = base_part_infos

        # give each sim a unique name so zip paths don't collide
        clone.simulation_name = f"{self.base_simulation.simulation_name}_sim{sim_index}"

        # ok now for the part infos we want to do something different, we want to keep shared elements the same but fork
        # the part infos which we are varying, that way we dont mess up other copies when experiments vary things
        # but we also dont duplicate parts that are commmon
        clone.part_infos = copy.copy(base_part_infos)
        for forked_part_name in self.varying_part_names:
            part_info = clone.get_part_info(forked_part_name)
            new_part_info = copy.deepcopy(part_info)
            new_part_info.part_unique_name = f"{forked_part_name}_{sim_index}"
            # replace the part info in the cloned simualtion
            clone.part_infos[clone.part_infos.index(part_info)] = new_part_info
            self.experiment_part_infos.append(new_part_info)

        # now that the name has changed and everything is set up, reload its persisted results (if any)
        clone.reload_results()
        return clone

    def _populate_invariant_part_infos(self):
        for part_info in self.base_simulation.part_infos:
            if part_info.part.name not in self.varying_part_names:
                self.experiment_part_infos.append(part_info)

    def prepare(self):
        self._log("=== PREPARE EXPERIMENT ===")

        if self.force_rerun:
            self._log("Clearing saved state.")
            self._clear_saved_state()
        elif self._experiment_state_filename.is_file():
            self._log(
                "Experiment already run — skipping prepare. Use force_rerun=True to redo."
            )
            self._rebuild_sims_from_state()
            return

        self.experiment_part_infos = []
        self._populate_invariant_part_infos()

        sim_count = self.varying[0].sim_count if self.varying else 1
        self._log(f"Creating {sim_count} simulation variant(s)...")
        self.sims = []
        for sim_index in range(sim_count):
            self._log(f"  [{sim_index + 1}/{sim_count}] Cloning base simulation")
            local_sim = self._clone_sim(sim_index)
            for v in self.varying:
                v.apply_to(sim_index, local_sim)
            self.sims.append(local_sim)

        self._log(f"Uploading assets ({len(self.experiment_part_infos)} part(s))...")
        self.base_simulation.populate_assets(self.experiment_part_infos)
        self._log("Sampling assets...")
        self.base_simulation.sample_assets(self.experiment_part_infos)
        self._log("Collecting sampled volumes...")
        self.base_simulation.collect_sampled_volumes(self.experiment_part_infos)
        self._log("Prepare complete.")

    def run(self, upload_server_manifest: bool = False):
        self._log("=== RUN EXPERIMENT ===")

        # If prepare() short-circuited because state exists, skip run too
        if (
            not self.force_rerun
            and self._experiment_state_filename.is_file()
            and self.sims
        ):
            # sims were rebuilt from state in prepare, so there's nothing to run
            if all(s.results for s in self.sims):
                self._log(
                    "All simulations already dispatched. Use force_rerun=True to redo."
                )
                if upload_server_manifest:
                    self.upload_server_manifest()
                return

        for sim_index, local_sim in enumerate(self.sims):
            self._log(
                f"  [{sim_index + 1}/{len(self.sims)}] Running {local_sim.simulation_name}"
            )
            name_suffix = f"_sim{sim_index}"
            local_sim.create_sim_config(name_suffix)
            local_sim.build_workflow(name_suffix)
            local_sim.run_workflow(name_suffix)

        self._save_experiment_state()
        self._log("All workflows dispatched.")

        if upload_server_manifest:
            self.upload_server_manifest()

    def cancel(self):
        self._log("=== CANCEL EXPERIMENT ===")
        self.base_simulation.cancel()
        for local_sim in self.sims:
            local_sim.cancel()
        self._log("All workflows canceled.")

    def _rebuild_sims_from_state(self):
        """Rebuild self.sims from saved experiment state, for re-download
        without re-running prepare/run."""
        state = self._load_experiment_state()
        sim_names = state.get("sim_names", [])
        if not sim_names:
            return

        self.experiment_part_infos = []
        self._populate_invariant_part_infos()

        self.sims = []
        for sim_index, sim_name in enumerate(sim_names):
            local_sim = self._clone_sim(sim_index)
            # _clone_sim would have generated a name based on base + sim_index,
            # but we want to honor whatever name was persisted
            local_sim.simulation_name = sim_name
            local_sim.reload_results()
            self.sims.append(local_sim)

    def download_results(self):
        self._log("=== DOWNLOAD RESULTS ===")

        if not self.sims:
            self._log("No sims in memory — loading persisted experiment state...")
            self._rebuild_sims_from_state()
            if not self.sims:
                print("No experiment state found — run prepare() and run() first.")
                return

        zip_filename = self.base_simulation.out_dir / "out.zip"
        with ZipFile(zip_filename, "w") as zf:
            all_results = []
            for sim_index, local_sim in enumerate(self.sims):
                self._log(
                    f"  [{sim_index + 1}/{len(self.sims)}] Collecting results for {local_sim.simulation_name}"
                )
                if not self.use_legacy_results_format:
                    local_sim._write_results_to_zip_v2(zf)
                else:
                    local_sim._write_results_to_zip(zf)
                all_results.extend(local_sim.results)

            self._log(f"Writing combined manifest with {len(all_results)} result(s)...")
            if not self.use_legacy_results_format:
                self.base_simulation._write_manifest_to_zip_v2(zf, all_results)
            else:
                self.base_simulation._write_manifest_to_zip(zf, all_results)

        print(f"Experiment complete. Results written to: {zip_filename}")

    @property
    def server_manifest_filename(self) -> Path:
        return self.base_simulation.server_manifest_filename

    def write_server_manifest(self):
        """Build and write a combined server manifest across all sub-sims."""
        self._log("=== WRITE SERVER MANIFEST ===")
        if not self.sims:
            self._log("No sims in memory — loading persisted experiment state...")
            self._rebuild_sims_from_state()
            if not self.sims:
                print("No experiment state found — run prepare() and run() first.")
                return None
        pairs = [(s, r) for s in self.sims for r in s.results]
        return self.base_simulation._write_server_manifest_for_pairs(pairs)

    def upload_server_manifest(self) -> None:
        """Build, write, and set the combined experiment server manifest as project data."""
        manifest = self.write_server_manifest()
        if manifest is None:
            return
        self.base_simulation.client.projects.update(data=manifest)
        print(f"Uploaded server manifest to project {self.base_simulation.project_id}")

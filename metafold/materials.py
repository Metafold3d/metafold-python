from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Optional, Union, List, cast
from simulation_configurator.materials import (
    _materials as simulation_configurator_materials,
)


class ParamsBase:
    @classmethod
    def get_type(cls) -> str:
        raise NotImplementedError

    @classmethod
    def from_dict(cls, d: dict):
        from dataclasses import fields

        valid_keys = {f.name for f in fields(cast(Any, cls))}
        return cls(**{k: v for k, v in d.items() if k in valid_keys})


@dataclass
class RigidParams(ParamsBase):
    shear_modulus: float
    bulk_modulus: float

    @classmethod
    def get_type(self):
        return "rigid"

    def to_dict(self):
        return {"shear_modulus": self.shear_modulus, "bulk_modulus": self.bulk_modulus}


@dataclass
class HypoElasticParams(ParamsBase):
    G: float
    K: float

    @classmethod
    def get_type(self):
        return "hypo_elastic"

    def to_dict(self):
        return {"G": self.G, "K": self.K}


@dataclass
class ViscoTransIsoHyperParams(ParamsBase):
    bulk_modulus: float
    c1: float
    c2: float
    c3: float
    c4: float
    c5: float
    fiber_stretch: float
    direction_of_symm: List[float]
    failure_option: int
    max_fiber_strain: float
    max_matrix_strain: float
    y1: float
    y2: float
    y3: float
    y4: float
    y5: float
    y6: float
    t1: float
    t2: float
    t3: float
    t4: float
    t5: float
    t6: float

    @classmethod
    def get_type(cls):
        return "visco_trans_iso_hyper"

    @classmethod
    def from_dict(cls, d: dict) -> "ViscoTransIsoHyperParams":
        dos = d["direction_of_symm"]
        direction = [float(x) for x in dos.split()] if isinstance(dos, str) else [float(x) for x in dos]
        return cls(
            bulk_modulus=d["bulk_modulus"],
            c1=d["c1"], c2=d["c2"], c3=d["c3"], c4=d["c4"], c5=d["c5"],
            fiber_stretch=d["fiber_stretch"],
            direction_of_symm=direction,
            failure_option=d["failure_option"],
            max_fiber_strain=d["max_fiber_strain"],
            max_matrix_strain=d["max_matrix_strain"],
            y1=d["y1"], y2=d["y2"], y3=d["y3"], y4=d["y4"], y5=d["y5"], y6=d["y6"],
            t1=d["t1"], t2=d["t2"], t3=d["t3"], t4=d["t4"], t5=d["t5"], t6=d["t6"],
        )

    def to_dict(self):
        return {
            "bulk_modulus": float(self.bulk_modulus),
            "c1": float(self.c1),
            "c2": float(self.c2),
            "c3": float(self.c3),
            "c4": float(self.c4),
            "c5": float(self.c5),
            "fiber_stretch": float(self.fiber_stretch),
            # Emit as a numeric list so simulation_configurator serialises it correctly
            "direction_of_symm": [float(x) for x in self.direction_of_symm],
            "failure_option": int(self.failure_option),
            "max_fiber_strain": float(self.max_fiber_strain),
            "max_matrix_strain": float(self.max_matrix_strain),
            "y1": float(self.y1),
            "y2": float(self.y2),
            "y3": float(self.y3),
            "y4": float(self.y4),
            "y5": float(self.y5),
            "y6": float(self.y6),
            "t1": float(self.t1),
            "t2": float(self.t2),
            "t3": float(self.t3),
            "t4": float(self.t4),
            "t5": float(self.t5),
            "t6": float(self.t6),
        }


@dataclass
class CompMooneyRivlinParams(ParamsBase):
    he_constant_1: float
    he_constant_2: float
    he_PR: float

    @classmethod
    def get_type(self):
        return "comp_mooney_rivlin"

    def to_dict(self):
        return {
            "he_constant_1": self.he_constant_1,
            "he_constant_2": self.he_constant_2,
            "he_PR": self.he_PR,
        }


@dataclass
class UCNHParams(ParamsBase):
    shear_modulus: float
    bulk_modulus: float
    useModifiedEOS: bool
    usePlasticity: Optional[bool] = None
    yield_stress: Optional[float] = None
    hardening_modulus: Optional[float] = None
    alpha: Optional[float] = None

    @classmethod
    def get_type(self):
        return "UCNH"

    def to_dict(self):
        d = {
            "shear_modulus": self.shear_modulus,
            "bulk_modulus": self.bulk_modulus,
            "useModifiedEOS": str(self.useModifiedEOS).lower(),
        }
        if self.usePlasticity is not None:
            d["usePlasticity"] = str(self.usePlasticity).lower()
        if self.yield_stress is not None:
            d["yield_stress"] = self.yield_stress
        if self.hardening_modulus is not None:
            d["hardening_modulus"] = self.hardening_modulus
        if self.alpha is not None:
            d["alpha"] = self.alpha
        return d


@dataclass
class ViscoelasticMode:
    mode: str
    relaxation_time: float
    partial_shear_modulus: float

    def to_dict(self):
        return {
            "mode": self.mode,
            "relaxation_time": self.relaxation_time,
            "partial_shear_modulus": self.partial_shear_modulus,
        }


@dataclass
class MaxwellWeichertParams(ParamsBase):
    bulk_modulus: float
    terminal_shear_modulus: float
    viscoelastic_series: List[ViscoelasticMode]

    @classmethod
    def get_type(self):
        return "Maxwell_Weichert"

    def to_dict(self):
        return {
            "bulk_modulus": self.bulk_modulus,
            "terminal_shear_modulus": self.terminal_shear_modulus,
            "viscoelastic_series": [m.to_dict() for m in self.viscoelastic_series],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "MaxwellWeichertParams":
        return cls(
            bulk_modulus=d["bulk_modulus"],
            terminal_shear_modulus=d["terminal_shear_modulus"],
            viscoelastic_series=[
                ViscoelasticMode(**m) for m in d["viscoelastic_series"]
            ],
        )


@dataclass
class CompNeoHookParams(ParamsBase):
    bulk_modulus: float
    shear_modulus: float

    @classmethod
    def get_type(self):
        return "comp_neo_hook"

    def to_dict(self):
        return {"bulk_modulus": self.bulk_modulus, "shear_modulus": self.shear_modulus}


@dataclass
class YieldCondition:
    type: str  # e.g. "vonMises"

    def to_dict(self):
        return {"type": self.type}


@dataclass
class StabilityCheck:
    type: str  # e.g. "drucker"

    def to_dict(self):
        return {"type": self.type}


@dataclass
class JohnsonCookParams(ParamsBase):
    A: float
    B: float
    C: float
    n: float
    m: float

    @classmethod
    def get_type(self):
        return "johnson_cook"

    def to_dict(self):
        return {"A": self.A, "B": self.B, "C": self.C, "n": self.n, "m": self.m}


@dataclass
class FlowModel:
    params: JohnsonCookParams  # extend to Union if more flow models are added

    def to_dict(self):
        return {"type": self.params.get_type(), "params": self.params.to_dict()}


@dataclass
class ElasticPlasticParams(ParamsBase):
    shear_modulus: float
    bulk_modulus: float
    yield_condition: YieldCondition
    stability_check: StabilityCheck
    flow_model: FlowModel

    @classmethod
    def get_type(self):
        return "elastic_plastic"

    def to_dict(self):
        return {
            "shear_modulus": self.shear_modulus,
            "bulk_modulus": self.bulk_modulus,
            "yield_condition": self.yield_condition.to_dict(),
            "stability_check": self.stability_check.to_dict(),
            "flow_model": self.flow_model.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ElasticPlasticParams":
        FLOW_MODEL_CLASSES = {c.get_type(): c for c in [JohnsonCookParams]}
        flow_type = d["flow_model"]["type"]
        flow_cls = FLOW_MODEL_CLASSES[flow_type]
        return cls(
            shear_modulus=d["shear_modulus"],
            bulk_modulus=d["bulk_modulus"],
            yield_condition=YieldCondition(**d["yield_condition"]),
            stability_check=StabilityCheck(**d["stability_check"]),
            flow_model=FlowModel(params=flow_cls(**d["flow_model"]["params"])),
        )


@dataclass
class ConstitutiveModel:
    params: Union[
        RigidParams,
        CompMooneyRivlinParams,
        MaxwellWeichertParams,
        UCNHParams,
        CompNeoHookParams,
        ElasticPlasticParams,
        HypoElasticParams,
        ViscoTransIsoHyperParams,
    ]

    def to_dict(self):
        return {"type": self.params.get_type(), "params": self.params.to_dict()}




@dataclass
class Material:
    density: float
    thermal_conductivity: float
    specific_heat: float
    constitutive_model: ConstitutiveModel
    room_temp: Optional[float] = None
    melt_temp: Optional[float] = None

    def to_dict(self):
        d = {
            "density": self.density,
            "thermal_conductivity": self.thermal_conductivity,
            "specific_heat": self.specific_heat,
            "constitutive_model": self.constitutive_model.to_dict(),
        }
        if self.room_temp is not None:
            d["room_temp"] = self.room_temp
        if self.melt_temp is not None:
            d["melt_temp"] = self.melt_temp
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Material":
        params_classes: list[type[ParamsBase]] = [
            RigidParams,
            CompMooneyRivlinParams,
            UCNHParams,
            MaxwellWeichertParams,
            CompNeoHookParams,
            ElasticPlasticParams,
            HypoElasticParams,
            ViscoTransIsoHyperParams,
        ]
        PARAMS_CLASSES = {c.get_type(): c for c in params_classes}
        cm = d["constitutive_model"]
        params = PARAMS_CLASSES[cm["type"]].from_dict(cm["params"])
        return cls(
            density=d["density"],
            thermal_conductivity=d["thermal_conductivity"],
            specific_heat=d["specific_heat"],
            constitutive_model=ConstitutiveModel(params=params),
            room_temp=d.get("room_temp"),
            melt_temp=d.get("melt_temp"),
        )


DEFAULT_PISTON_MATERIAL = Material(
    density=1730.0,
    thermal_conductivity=45,
    specific_heat=4.8e-4,
    constitutive_model=ConstitutiveModel(
        params=RigidParams(shear_modulus=2667.0e6, bulk_modulus=8000.0e6)
    ),
)

DEFAULT_SUPPORT_MATERIAL = Material(
    density=7850,
    thermal_conductivity=45.0,
    specific_heat=4.8e-4,
    constitutive_model=ConstitutiveModel(
        params=RigidParams(shear_modulus=8.0e6, bulk_modulus=1.6e7)
    ),
)

DEFAULT_UPPER_FOAM = Material(
    density=150.0,
    thermal_conductivity=45,
    specific_heat=4.8e-4,
    constitutive_model=ConstitutiveModel(
        params=CompMooneyRivlinParams(
            he_constant_1=1.5e5, he_constant_2=1.75e5, he_PR=0.41
        )
    ),
)

DEFAULT_MIDSOLE_NOMINAL = Material(
    density=200.0,
    thermal_conductivity=45,
    specific_heat=4.8e-4,
    constitutive_model=ConstitutiveModel(
        params=MaxwellWeichertParams(
            bulk_modulus=931250,
            terminal_shear_modulus=43750,
            viscoelastic_series=[
                ViscoelasticMode(
                    mode="mode1", relaxation_time=0.15, partial_shear_modulus=25000
                ),
                ViscoelasticMode(
                    mode="mode2", relaxation_time=0.2, partial_shear_modulus=30000
                ),
                ViscoelasticMode(
                    mode="mode3", relaxation_time=0.25, partial_shear_modulus=15000
                ),
            ],
        )
    ),
)

DEFAULT_OUTSOLE = Material(
    density=1000.0,
    thermal_conductivity=45,
    specific_heat=4.8e-4,
    constitutive_model=ConstitutiveModel(
        params=CompMooneyRivlinParams(
            he_constant_1=2.5e5, he_constant_2=1.2e5, he_PR=0.47
        )
    ),
)

# import and wrap the imported material definitions
MATERIAL_ABS = Material.from_dict(simulation_configurator_materials["ABS"])
MATERIAL_ALUMINUM = Material.from_dict(simulation_configurator_materials["Aluminum"])
MATERIAL_BASF_EPD = Material.from_dict(simulation_configurator_materials["BASF_epd"])
# MATERIAL_BASF_PA11_XY     = Material.from_dict(simulation_configurator_materials["BASF_PA11_xy"])
# MATERIAL_BASF_PA11_Z      = Material.from_dict(simulation_configurator_materials["BASF_PA11_z"])
MATERIAL_BASF_PP1400_XY = Material.from_dict(
    simulation_configurator_materials["BASF_PP1400_xy"]
)
MATERIAL_BASF_PP1400_Z = Material.from_dict(
    simulation_configurator_materials["BASF_PP1400_z"]
)
MATERIAL_BASF_RG3280 = Material.from_dict(
    simulation_configurator_materials["BASF_RG3280"]
)
MATERIAL_BASF_TPU01 = Material.from_dict(
    simulation_configurator_materials["BASF_TPU01"]
)
MATERIAL_EOS_PA11 = Material.from_dict(simulation_configurator_materials["EOS_PA11"])
MATERIAL_EOS_TPE300 = Material.from_dict(
    simulation_configurator_materials["EOS_TPE300"]
)
MATERIAL_EPU_41 = Material.from_dict(simulation_configurator_materials["EPU_41"])
MATERIAL_EPU_45 = Material.from_dict(simulation_configurator_materials["EPU_45"])
MATERIAL_NYLON_6 = Material.from_dict(simulation_configurator_materials["Nylon_6"])
MATERIAL_NYLON_12 = Material.from_dict(simulation_configurator_materials["Nylon_12"])
MATERIAL_PLA = Material.from_dict(simulation_configurator_materials["PLA"])
MATERIAL_STAINLESS_STEEL = Material.from_dict(
    simulation_configurator_materials["StainlessSteel"]
)
MATERIAL_TI64 = Material.from_dict(simulation_configurator_materials["Ti64"])
MATERIAL_TPU = Material.from_dict(simulation_configurator_materials["TPU"])

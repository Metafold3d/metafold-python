import pytest
from metafold.materials import (
    CompMooneyRivlinParams,
    CompNeoHookParams,
    ConstitutiveModel,
    ElasticPlasticParams,
    FlowModel,
    HypoElasticParams,
    JohnsonCookParams,
    Material,
    MaxwellWeichertParams,
    RigidParams,
    StabilityCheck,
    UCNHParams,
    ViscoelasticMode,
    ViscoTransIsoHyperParams,
    YieldCondition,
)


def roundtrip(material: Material) -> Material:
    return Material.from_dict(material.to_dict())


class TestRigidParams:
    def test_roundtrip(self):
        m = Material(
            density=1730.0,
            thermal_conductivity=45.0,
            specific_heat=4.8e-4,
            constitutive_model=ConstitutiveModel(
                params=RigidParams(shear_modulus=2667e6, bulk_modulus=8000e6)
            ),
        )
        assert roundtrip(m).to_dict() == m.to_dict()

    def test_type_key(self):
        d = ConstitutiveModel(params=RigidParams(1.0, 2.0)).to_dict()
        assert d["type"] == "rigid"


class TestCompMooneyRivlinParams:
    def test_roundtrip(self):
        m = Material(
            density=150.0,
            thermal_conductivity=45.0,
            specific_heat=4.8e-4,
            constitutive_model=ConstitutiveModel(
                params=CompMooneyRivlinParams(he_constant_1=1.5e5, he_constant_2=1.75e5, he_PR=0.41)
            ),
        )
        assert roundtrip(m).to_dict() == m.to_dict()

    def test_type_key(self):
        d = ConstitutiveModel(params=CompMooneyRivlinParams(1.0, 2.0, 0.3)).to_dict()
        assert d["type"] == "comp_mooney_rivlin"


class TestCompNeoHookParams:
    def test_roundtrip(self):
        m = Material(
            density=100.0,
            thermal_conductivity=1.0,
            specific_heat=1.0,
            constitutive_model=ConstitutiveModel(
                params=CompNeoHookParams(bulk_modulus=1e6, shear_modulus=5e5)
            ),
        )
        assert roundtrip(m).to_dict() == m.to_dict()

    def test_type_key(self):
        d = ConstitutiveModel(params=CompNeoHookParams(1.0, 2.0)).to_dict()
        assert d["type"] == "comp_neo_hook"


class TestUCNHParams:
    def test_roundtrip_minimal(self):
        m = Material(
            density=500.0,
            thermal_conductivity=1.0,
            specific_heat=1.0,
            constitutive_model=ConstitutiveModel(
                params=UCNHParams(shear_modulus=1e6, bulk_modulus=2e6, useModifiedEOS=True)
            ),
        )
        assert roundtrip(m).to_dict() == m.to_dict()

    def test_roundtrip_with_plasticity(self):
        m = Material(
            density=500.0,
            thermal_conductivity=1.0,
            specific_heat=1.0,
            constitutive_model=ConstitutiveModel(
                params=UCNHParams(
                    shear_modulus=1e6,
                    bulk_modulus=2e6,
                    useModifiedEOS=False,
                    usePlasticity=True,
                    yield_stress=1e4,
                    hardening_modulus=1e3,
                    alpha=0.5,
                )
            ),
        )
        assert roundtrip(m).to_dict() == m.to_dict()

    def test_bool_serialised_as_lowercase_string(self):
        p = UCNHParams(shear_modulus=1.0, bulk_modulus=1.0, useModifiedEOS=True)
        assert p.to_dict()["useModifiedEOS"] == "true"
        p2 = UCNHParams(shear_modulus=1.0, bulk_modulus=1.0, useModifiedEOS=False)
        assert p2.to_dict()["useModifiedEOS"] == "false"

    def test_optional_fields_omitted_when_none(self):
        p = UCNHParams(shear_modulus=1.0, bulk_modulus=1.0, useModifiedEOS=True)
        d = p.to_dict()
        assert "usePlasticity" not in d
        assert "yield_stress" not in d

    def test_type_key(self):
        d = ConstitutiveModel(params=UCNHParams(1.0, 2.0, True)).to_dict()
        assert d["type"] == "UCNH"


class TestMaxwellWeichertParams:
    def test_roundtrip(self):
        m = Material(
            density=200.0,
            thermal_conductivity=45.0,
            specific_heat=4.8e-4,
            constitutive_model=ConstitutiveModel(
                params=MaxwellWeichertParams(
                    bulk_modulus=931250,
                    terminal_shear_modulus=43750,
                    viscoelastic_series=[
                        ViscoelasticMode("mode1", 0.15, 25000),
                        ViscoelasticMode("mode2", 0.20, 30000),
                    ],
                )
            ),
        )
        assert roundtrip(m).to_dict() == m.to_dict()

    def test_viscoelastic_modes_preserved(self):
        params = MaxwellWeichertParams(
            bulk_modulus=1.0,
            terminal_shear_modulus=1.0,
            viscoelastic_series=[
                ViscoelasticMode("mode1", 0.1, 100.0),
                ViscoelasticMode("mode2", 0.2, 200.0),
            ],
        )
        d = params.to_dict()
        assert len(d["viscoelastic_series"]) == 2
        assert d["viscoelastic_series"][0]["mode"] == "mode1"
        assert d["viscoelastic_series"][1]["relaxation_time"] == 0.2

    def test_type_key(self):
        d = ConstitutiveModel(
            params=MaxwellWeichertParams(1.0, 1.0, [])
        ).to_dict()
        assert d["type"] == "Maxwell_Weichert"


class TestElasticPlasticParams:
    def test_roundtrip(self):
        m = Material(
            density=7850.0,
            thermal_conductivity=45.0,
            specific_heat=4.8e-4,
            constitutive_model=ConstitutiveModel(
                params=ElasticPlasticParams(
                    shear_modulus=8e10,
                    bulk_modulus=1.6e11,
                    yield_condition=YieldCondition(type="vonMises"),
                    stability_check=StabilityCheck(type="drucker"),
                    flow_model=FlowModel(
                        params=JohnsonCookParams(A=0.9e9, B=0.5e9, C=0.014, n=0.26, m=1.03)
                    ),
                )
            ),
        )
        assert roundtrip(m).to_dict() == m.to_dict()

    def test_type_key(self):
        d = ConstitutiveModel(
            params=ElasticPlasticParams(
                shear_modulus=1.0,
                bulk_modulus=1.0,
                yield_condition=YieldCondition("vonMises"),
                stability_check=StabilityCheck("drucker"),
                flow_model=FlowModel(params=JohnsonCookParams(1, 1, 1, 1, 1)),
            )
        ).to_dict()
        assert d["type"] == "elastic_plastic"


class TestHypoElasticParams:
    def test_roundtrip(self):
        m = Material(
            density=1000.0,
            thermal_conductivity=1.0,
            specific_heat=1.0,
            constitutive_model=ConstitutiveModel(
                params=HypoElasticParams(G=1.5e6, K=3.0e6)
            ),
        )
        assert roundtrip(m).to_dict() == m.to_dict()

    def test_type_key(self):
        d = ConstitutiveModel(params=HypoElasticParams(G=1.0, K=2.0)).to_dict()
        assert d["type"] == "hypo_elastic"


class TestViscoTransIsoHyperParams:
    def _make_params(self, **overrides):
        defaults = dict(
            bulk_modulus=1.0e6,
            c1=1.0,
            c2=2.0,
            c3=3.0,
            c4=4.0,
            c5=5.0,
            fiber_stretch=1.1,
            direction_of_symm=[0.0, 1.0, 0.0],
            failure_option=0,
            max_fiber_strain=0.1,
            max_matrix_strain=0.2,
            y1=0.1, y2=0.2, y3=0.3, y4=0.4, y5=0.5, y6=0.6,
            t1=1.0, t2=2.0, t3=3.0, t4=4.0, t5=5.0, t6=6.0,
        )
        defaults.update(overrides)
        return ViscoTransIsoHyperParams(**defaults)

    def test_roundtrip(self):
        m = Material(
            density=1200.0,
            thermal_conductivity=0.5,
            specific_heat=1.0e-3,
            constitutive_model=ConstitutiveModel(params=self._make_params()),
        )
        assert roundtrip(m).to_dict() == m.to_dict()

    def test_type_key(self):
        d = ConstitutiveModel(params=self._make_params()).to_dict()
        assert d["type"] == "visco_trans_iso_hyper"

    def test_int_inputs_serialized_as_float(self):
        params = self._make_params(c3=0, c4=0, c5=0, direction_of_symm=[0, 1, 0])
        d = params.to_dict()
        assert isinstance(d["c3"], float)
        assert isinstance(d["c4"], float)
        assert isinstance(d["c5"], float)
        assert d["direction_of_symm"] == [0.0, 1.0, 0.0]
        assert all(isinstance(x, float) for x in d["direction_of_symm"])

    def test_failure_option_serialized_as_int(self):
        params = self._make_params(failure_option=1)
        d = params.to_dict()
        assert isinstance(d["failure_option"], int)


class TestMaterialOptionalFields:
    def test_optional_fields_omitted_when_none(self):
        m = Material(density=1.0, thermal_conductivity=1.0, specific_heat=1.0,
                     constitutive_model=ConstitutiveModel(params=RigidParams(1.0, 1.0)))
        d = m.to_dict()
        assert "room_temp" not in d
        assert "melt_temp" not in d

    def test_optional_fields_roundtrip(self):
        m = Material(
            density=1.0,
            thermal_conductivity=1.0,
            specific_heat=1.0,
            constitutive_model=ConstitutiveModel(params=RigidParams(1.0, 1.0)),
            room_temp=300.0,
            melt_temp=1500.0,
        )
        r = roundtrip(m)
        assert r.room_temp == 300.0
        assert r.melt_temp == 1500.0

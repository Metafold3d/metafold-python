import pytest
from metafold.materials import (
    CompMooneyRivlinParams,
    CompNeoHookParams,
    ConstitutiveModel,
    ElasticPlasticParams,
    FlowModel,
    HyperfoamParams,
    HyperfoamTerm,
    HypoElasticParams,
    JohnsonCookParams,
    Material,
    MaxwellWeichertParams,
    OrthotropicParams,
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


class TestHyperfoamParams:
    def _material(self):
        return Material(
            density=600.0,
            thermal_conductivity=0.15,
            specific_heat=1.36,
            constitutive_model=ConstitutiveModel(
                params=HyperfoamParams(
                    terms=[
                        HyperfoamTerm(mu=0.16e6, alpha=8.9, poisson_ratio=0.0),
                        HyperfoamTerm(mu=0.01e6, alpha=-2.0, poisson_ratio=0.0),
                    ],
                )
            ),
        )

    def test_roundtrip(self):
        m = self._material()
        assert roundtrip(m).to_dict() == m.to_dict()

    def test_type_key(self):
        d = ConstitutiveModel(
            params=HyperfoamParams(terms=[])
        ).to_dict()
        assert d["type"] == "hyperfoam"

    def test_bulk_modulus_not_emitted(self):
        # bulk_modulus is not part of the Ogden hyperfoam model.
        d = self._material().constitutive_model.params.to_dict()
        assert "bulk_modulus" not in d
        assert "K" not in d

    def test_legacy_bulk_modulus_ignored_on_from_dict(self):
        # Older scripts / GH plugins may still send bulk_modulus or K — ignore it.
        d = {
            "type": "hyperfoam",
            "params": {
                "bulk_modulus": 1.0e6,
                "K": 2.0e6,
                "terms": [{"mu": 0.16e6, "alpha": 8.9, "poisson_ratio": 0.0}],
            },
        }
        params = HyperfoamParams.from_dict(d["params"])
        assert len(params.terms) == 1
        assert "bulk_modulus" not in params.to_dict()

    def test_terms_preserved(self):
        d = self._material().constitutive_model.params.to_dict()
        assert len(d["terms"]) == 2
        # "_element" marks how the ups emitter renders each term.
        assert d["terms"][0]["_element"] == "term"
        assert d["terms"][0]["mu"] == 0.16e6
        assert d["terms"][1]["alpha"] == -2.0

    def test_pure_elastic_omits_viscoelastic_fields(self):
        d = self._material().constitutive_model.params.to_dict()
        assert "terminal_shear_modulus" not in d
        assert "viscoelastic_series" not in d

    def _viscoelastic_material(self):
        return Material(
            density=600.0,
            thermal_conductivity=0.15,
            specific_heat=1.36,
            constitutive_model=ConstitutiveModel(
                params=HyperfoamParams(
                    terms=[HyperfoamTerm(mu=0.16e6, alpha=8.9, poisson_ratio=0.0)],
                    terminal_shear_modulus=5.0e4,
                    viscoelastic_series=[
                        ViscoelasticMode("m1", 0.15, 25000),
                        ViscoelasticMode("m2", 0.20, 30000),
                    ],
                )
            ),
        )

    def test_viscoelastic_overlay_roundtrip(self):
        m = self._viscoelastic_material()
        assert roundtrip(m).to_dict() == m.to_dict()

    def test_viscoelastic_overlay_emitted(self):
        d = self._viscoelastic_material().constitutive_model.params.to_dict()
        assert d["terminal_shear_modulus"] == 5.0e4
        assert len(d["viscoelastic_series"]) == 2
        assert d["viscoelastic_series"][0]["mode"] == "m1"


class TestOrthotropicParams:
    def _material(self):
        return Material(
            density=1000.0,
            thermal_conductivity=1.0,
            specific_heat=1500,
            constitutive_model=ConstitutiveModel(
                params=OrthotropicParams(
                    E1=1e9, E2=2e9, E3=3e9,
                    nu12=0.3, nu13=0.3, nu23=0.3,
                    G12=0.5e9, G13=0.5e9, G23=0.5e9,
                    direction_a=[1.0, 0.0, 0.0],
                    direction_b=[0.0, 1.0, 0.0],
                )
            ),
        )

    def test_roundtrip(self):
        m = self._material()
        assert roundtrip(m).to_dict() == m.to_dict()

    def test_type_key(self):
        d = ConstitutiveModel(params=self._material().constitutive_model.params).to_dict()
        assert d["type"] == "orthotropic"

    def test_directions_are_numeric_lists(self):
        d = self._material().constitutive_model.params.to_dict()
        assert d["direction_a"] == [1.0, 0.0, 0.0]
        assert d["direction_b"] == [0.0, 1.0, 0.0]

    def test_from_dict_accepts_string_direction(self):
        # Directions may arrive as "x y z" strings (manifest form).
        m = self._material()
        d = m.to_dict()
        d["constitutive_model"]["params"]["direction_a"] = "1 0 0"
        assert OrthotropicParams.from_dict(d["constitutive_model"]["params"]).direction_a == [1.0, 0.0, 0.0]


class TestMaterialFromDictErrors:
    # from_dict must raise ValueError (not KeyError) so API callers return 400,
    # not 500. See lightcycle experiments blueprint.
    def _material_dict(self, mtype, params):
        return {
            "density": 1000.0, "thermal_conductivity": 1.0, "specific_heat": 1500,
            "constitutive_model": {"type": mtype, "params": params},
        }

    def test_unknown_type_raises_value_error(self):
        # A client newer than the server sends a type we don't know.
        d = self._material_dict("some_future_type", {})
        with pytest.raises(ValueError, match="Unknown constitutive model type"):
            Material.from_dict(d)

    def test_missing_param_raises_value_error(self):
        params = {
            "E1": 1e9, "E2": 1e9, "E3": 1e9,
            "nu12": 0.3, "nu13": 0.3, "nu23": 0.3,
            "G12": 5e8, "G13": 5e8, "G23": 5e8,
            "direction_a": [1.0, 0.0, 0.0], "direction_b": [0.0, 1.0, 0.0],
        }
        del params["E1"]
        with pytest.raises(ValueError, match="missing required param"):
            Material.from_dict(self._material_dict("orthotropic", params))

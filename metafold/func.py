# ruff: noqa: F401
# This file was automatically generated from the source file: func.py.in.
# Any edits should be made to the template file before re-running the codegen.
from typing import Literal, Optional, TypedDict, TypeVar, TYPE_CHECKING, Union
from typing import cast
import sys
if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias

try:
    import numpy as np
except ImportError:
    pass

from .func_types import (
    Evaluator,
    Func,
    FuncType,
    Assets,
    Inputs,
    POINT_SOURCE_VAR_TYPE,
    Params,
    Result,
    TypedFunc,
    TypedResult,

    # Parameter types
    Vec2i,
    Vec2f,
    Vec3i,
    Vec3f,
    Vec4i,
    Vec4f,
    Mat2f,
    Mat3f,
    Mat4f,
    UnitCell,

    # Asset types
    VolumeAsset,
    TriangleMeshAsset,
    CustomShapeAsset,
    ParametrizationAsset,
    LineNetworkAsset,
    LineNetworkBvhAsset,
    MeshBvhAsset,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    F = TypeVar("F", bound=Callable)
    def cache(f: F) -> F: ...
else:
    from functools import cache


@cache
def PointSource(eval_: Evaluator) -> TypedResult[Literal[FuncType.VEC3F]]:
    return cast(TypedResult[Literal[FuncType.VEC3F]], eval_(POINT_SOURCE_VAR_TYPE))


CSG_Enum_operation: TypeAlias = Literal["Intersect", "Subtract", "Union"]


class CSG_Parameters(TypedDict, total=False):
    operation: CSG_Enum_operation
    smoothing: float


class CSG(TypedFunc[Literal[FuncType.FLOAT]]):
    def __init__(
        self,
        a: TypedFunc[Literal[FuncType.FLOAT]],
        b: TypedFunc[Literal[FuncType.FLOAT]],
        parameters: Optional[CSG_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = {
            "A": a,
            "B": b,
        }
        self.assets: Optional[Assets]
        self.assets = None
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> TypedResult[Literal[FuncType.FLOAT]]:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "CSG",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return cast(TypedResult[Literal[FuncType.FLOAT]], r)


ComputeCurvatures_Enum_spacing_type: TypeAlias = Literal["Continuous", "Discrete"]


class ComputeCurvatures_Parameters(TypedDict, total=False):
    spacing_type: ComputeCurvatures_Enum_spacing_type
    step_size: float
    volume_size: Vec3f


class ComputeCurvatures(TypedFunc[Literal[FuncType.VEC3F]]):
    def __init__(
        self,
        samples: Func,
        parameters: Optional[ComputeCurvatures_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = {
            "Samples": samples,
        }
        self.assets: Optional[Assets]
        self.assets = None
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> TypedResult[Literal[FuncType.VEC3F]]:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "ComputeCurvatures",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return cast(TypedResult[Literal[FuncType.VEC3F]], r)


class ComputeNormals_Parameters(TypedDict, total=False):
    volume_offset: Vec3f
    volume_size: Vec3f
    xform: Mat4f


class ComputeNormals(TypedFunc[Literal[FuncType.VEC3F]]):
    def __init__(
        self,
        points: TypedFunc[Literal[FuncType.VEC3F]],
        volume: Func,
        parameters: Optional[ComputeNormals_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = {
            "Points": points,
            "Volume": volume,
        }
        self.assets: Optional[Assets]
        self.assets = None
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> TypedResult[Literal[FuncType.VEC3F]]:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "ComputeNormals",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return cast(TypedResult[Literal[FuncType.VEC3F]], r)


class GenerateSamplePoints_Parameters(TypedDict, total=False):
    offset: Vec3f
    resolution: Vec3i
    size: Vec3f
    xform: Mat4f


class GenerateSamplePoints(TypedFunc[Literal[FuncType.VEC3F]]):
    def __init__(
        self,
        parameters: Optional[GenerateSamplePoints_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = None
        self.assets: Optional[Assets]
        self.assets = None
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> TypedResult[Literal[FuncType.VEC3F]]:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "GenerateSamplePoints",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return cast(TypedResult[Literal[FuncType.VEC3F]], r)


GradeCellSize_Enum_shape_type: TypeAlias = Literal["Box", "Cylinder", "Ellipsoid", "Plane"]


class GradeCellSize_Parameters(TypedDict, total=False):
    num_steps: int
    offset: float
    shape_size: Vec3f
    shape_type: GradeCellSize_Enum_shape_type
    shape_xform: Mat4f
    step_size: float
    width: float
    xform: Mat4f


class GradeCellSize(TypedFunc[Literal[FuncType.VEC3F]]):
    def __init__(
        self,
        points: TypedFunc[Literal[FuncType.VEC3F]],
        parameters: Optional[GradeCellSize_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = {
            "Points": points,
        }
        self.assets: Optional[Assets]
        self.assets = None
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> TypedResult[Literal[FuncType.VEC3F]]:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "GradeCellSize",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return cast(TypedResult[Literal[FuncType.VEC3F]], r)


class InterpolateBoundaryCoords_Parameters(TypedDict, total=False):
    tolerance: float
    xform: Mat4f


class InterpolateBoundaryCoords(TypedFunc[Literal[FuncType.VEC3F]]):
    def __init__(
        self,
        points: TypedFunc[Literal[FuncType.VEC3F]],
        boundary_data: ParametrizationAsset,
        mesh_data: TriangleMeshAsset,
        parameters: Optional[InterpolateBoundaryCoords_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = {
            "Points": points,
        }
        self.assets: Optional[Assets]
        self.assets = {
            "boundary_data": boundary_data,
            "mesh_data": mesh_data,
        }
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> TypedResult[Literal[FuncType.VEC3F]]:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "InterpolateBoundaryCoords",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return cast(TypedResult[Literal[FuncType.VEC3F]], r)


class LinearFilter_Parameters(TypedDict, total=False):
    scale_a: float
    scale_b: float


class LinearFilter(TypedFunc[Literal[FuncType.FLOAT]]):
    def __init__(
        self,
        inputa: TypedFunc[Literal[FuncType.FLOAT]],
        inputb: TypedFunc[Literal[FuncType.FLOAT]],
        parameters: Optional[LinearFilter_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = {
            "InputA": inputa,
            "InputB": inputb,
        }
        self.assets: Optional[Assets]
        self.assets = None
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> TypedResult[Literal[FuncType.FLOAT]]:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "LinearFilter",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return cast(TypedResult[Literal[FuncType.FLOAT]], r)


class LoadSamplePoints_Parameters(TypedDict, total=False):
    points: Union[list[Vec3f], "np.ndarray"]


class LoadSamplePoints(TypedFunc[Literal[FuncType.VEC3F]]):
    def __init__(
        self,
        parameters: Optional[LoadSamplePoints_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = None
        self.assets: Optional[Assets]
        self.assets = None
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> TypedResult[Literal[FuncType.VEC3F]]:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "LoadSamplePoints",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return cast(TypedResult[Literal[FuncType.VEC3F]], r)


LoadVolume_Enum_component_type: TypeAlias = Literal["Byte", "Float", "Integer", "None", "Vec2f", "Vec2i", "Vec3f", "Vec3i", "Vec4f", "Vec4i"]


class LoadVolume_Parameters(TypedDict, total=False):
    component_type: LoadVolume_Enum_component_type
    resolution: Vec3i


class LoadVolume(Func):
    def __init__(
        self,
        volume_data: VolumeAsset,
        parameters: Optional[LoadVolume_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = None
        self.assets: Optional[Assets]
        self.assets = {
            "volume_data": volume_data,
        }
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> Result:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "LoadVolume",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return r


MapTexturePrimitive_Enum_shape_type: TypeAlias = Literal["Box", "Cylinder", "Ellipsoid", "Plane"]


class MapTexturePrimitive_Parameters(TypedDict, total=False):
    box_width: Vec3f
    scale: Vec2f
    shape_type: MapTexturePrimitive_Enum_shape_type
    shape_xform: Mat4f
    xform: Mat4f


class MapTexturePrimitive(TypedFunc[Literal[FuncType.VEC3F]]):
    def __init__(
        self,
        points: TypedFunc[Literal[FuncType.VEC3F]],
        image: TypedFunc[Literal[FuncType.FLOAT]],
        parameters: Optional[MapTexturePrimitive_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = {
            "Points": points,
            "Image": image,
        }
        self.assets: Optional[Assets]
        self.assets = None
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> TypedResult[Literal[FuncType.VEC3F]]:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "MapTexturePrimitive",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return cast(TypedResult[Literal[FuncType.VEC3F]], r)


class Redistance_Parameters(TypedDict, total=False):
    post_offset: float
    pre_offset: float


class Redistance(TypedFunc[Literal[FuncType.FLOAT]]):
    def __init__(
        self,
        samples: TypedFunc[Literal[FuncType.FLOAT]],
        parameters: Optional[Redistance_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = {
            "Samples": samples,
        }
        self.assets: Optional[Assets]
        self.assets = None
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> TypedResult[Literal[FuncType.FLOAT]]:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "Redistance",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return cast(TypedResult[Literal[FuncType.FLOAT]], r)


SampleBeam_Enum_node_type: TypeAlias = Literal["None", "Sphere"]


SampleBeam_Enum_section_type: TypeAlias = Literal["Box", "Circle", "Cross"]


class SampleBeam_Parameters(TypedDict, total=False):
    node_radius: float
    node_type: SampleBeam_Enum_node_type
    section_radius: float
    section_type: SampleBeam_Enum_section_type
    smoothing: float
    xform: Mat4f


class SampleBeam(TypedFunc[Literal[FuncType.FLOAT]]):
    def __init__(
        self,
        points: TypedFunc[Literal[FuncType.VEC3F]],
        bvh_data: LineNetworkBvhAsset,
        network_data: LineNetworkAsset,
        parameters: Optional[SampleBeam_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = {
            "Points": points,
        }
        self.assets: Optional[Assets]
        self.assets = {
            "bvh_data": bvh_data,
            "network_data": network_data,
        }
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> TypedResult[Literal[FuncType.FLOAT]]:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "SampleBeam",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return cast(TypedResult[Literal[FuncType.FLOAT]], r)


SampleBox_Enum_shape_type: TypeAlias = Literal["Box", "BoxFrame", "CappedCone", "Capsule", "Cylinder", "Ellipsoid", "Link", "Plane", "Torus"]


class SampleBox_Parameters(TypedDict, total=False):
    free_param: float
    shape_type: SampleBox_Enum_shape_type
    size: Vec3f
    xform: Mat4f


class SampleBox(TypedFunc[Literal[FuncType.FLOAT]]):
    def __init__(
        self,
        points: TypedFunc[Literal[FuncType.VEC3F]],
        parameters: Optional[SampleBox_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = {
            "Points": points,
        }
        self.assets: Optional[Assets]
        self.assets = None
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> TypedResult[Literal[FuncType.FLOAT]]:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "SampleBox",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return cast(TypedResult[Literal[FuncType.FLOAT]], r)


class SampleCustomShape_Parameters(TypedDict, total=False):
    xform: Mat4f


class SampleCustomShape(TypedFunc[Literal[FuncType.FLOAT]]):
    def __init__(
        self,
        points: TypedFunc[Literal[FuncType.VEC3F]],
        shader_data: CustomShapeAsset,
        parameters: Optional[SampleCustomShape_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = {
            "Points": points,
        }
        self.assets: Optional[Assets]
        self.assets = {
            "shader_data": shader_data,
        }
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> TypedResult[Literal[FuncType.FLOAT]]:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "SampleCustomShape",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return cast(TypedResult[Literal[FuncType.FLOAT]], r)


SampleLattice_Enum_node_type: TypeAlias = Literal["None", "Sphere"]


SampleLattice_Enum_section_type: TypeAlias = Literal["Box", "Circle", "Cross"]


class SampleLattice_Parameters(TypedDict, total=False):
    lattice_data: UnitCell
    node_radius: float
    node_type: SampleLattice_Enum_node_type
    scale: Vec3f
    scale_grading_range: Vec2f
    scale_grading_scale: Vec2f
    section_radius: float
    section_radius_grading_range: Vec2f
    section_radius_grading_scale: Vec2f
    section_type: SampleLattice_Enum_section_type
    smoothing: float
    xform: Mat4f


class SampleLattice(TypedFunc[Literal[FuncType.FLOAT]]):
    def __init__(
        self,
        points: TypedFunc[Literal[FuncType.VEC3F]],
        parameters: Optional[SampleLattice_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = {
            "Points": points,
        }
        self.assets: Optional[Assets]
        self.assets = None
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> TypedResult[Literal[FuncType.FLOAT]]:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "SampleLattice",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return cast(TypedResult[Literal[FuncType.FLOAT]], r)


class SampleSpinodoid_Parameters(TypedDict, total=False):
    angles: Vec3f
    density: float
    pore_size: float
    wave_count: int
    xform: Mat4f


class SampleSpinodoid(TypedFunc[Literal[FuncType.FLOAT]]):
    def __init__(
        self,
        points: TypedFunc[Literal[FuncType.VEC3F]],
        parameters: Optional[SampleSpinodoid_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = {
            "Points": points,
        }
        self.assets: Optional[Assets]
        self.assets = None
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> TypedResult[Literal[FuncType.FLOAT]]:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "SampleSpinodoid",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return cast(TypedResult[Literal[FuncType.FLOAT]], r)


SampleSurfaceLattice_Enum_lattice_type: TypeAlias = Literal["CD", "CI2Y", "CP", "CPM_Y", "CS", "CY", "C_Y", "D", "F", "FRD", "Gyroid", "I2Y", "IWP", "None", "P", "PM_Y", "S", "SD1", "Schwarz", "SchwarzD", "SchwarzN", "SchwarzPW", "SchwarzW", "W", "Y"]


class SampleSurfaceLattice_Parameters(TypedDict, total=False):
    lattice_type: SampleSurfaceLattice_Enum_lattice_type
    scale: Vec3f
    scale_grading_range: Vec2f
    scale_grading_scale: Vec2f
    threshold: float
    threshold_grading_offset: Vec2f
    threshold_grading_range: Vec2f
    xform: Mat4f


class SampleSurfaceLattice(TypedFunc[Literal[FuncType.FLOAT]]):
    def __init__(
        self,
        points: TypedFunc[Literal[FuncType.VEC3F]],
        parameters: Optional[SampleSurfaceLattice_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = {
            "Points": points,
        }
        self.assets: Optional[Assets]
        self.assets = None
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> TypedResult[Literal[FuncType.FLOAT]]:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "SampleSurfaceLattice",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return cast(TypedResult[Literal[FuncType.FLOAT]], r)


class SampleTriangleMesh_Parameters(TypedDict, total=False):
    cw_winding: int
    xform: Mat4f


class SampleTriangleMesh(TypedFunc[Literal[FuncType.FLOAT]]):
    def __init__(
        self,
        points: TypedFunc[Literal[FuncType.VEC3F]],
        mesh_data: TriangleMeshAsset,
        parameters: Optional[SampleTriangleMesh_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = {
            "Points": points,
        }
        self.assets: Optional[Assets]
        self.assets = {
            "mesh_data": mesh_data,
        }
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> TypedResult[Literal[FuncType.FLOAT]]:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "SampleTriangleMesh",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return cast(TypedResult[Literal[FuncType.FLOAT]], r)


class SampleTriangleMeshBvh_Parameters(TypedDict, total=False):
    xform: Mat4f


class SampleTriangleMeshBvh(TypedFunc[Literal[FuncType.FLOAT]]):
    def __init__(
        self,
        points: TypedFunc[Literal[FuncType.VEC3F]],
        bvh_data: MeshBvhAsset,
        mesh_data: TriangleMeshAsset,
        parameters: Optional[SampleTriangleMeshBvh_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = {
            "Points": points,
        }
        self.assets: Optional[Assets]
        self.assets = {
            "bvh_data": bvh_data,
            "mesh_data": mesh_data,
        }
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> TypedResult[Literal[FuncType.FLOAT]]:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "SampleTriangleMeshBvh",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return cast(TypedResult[Literal[FuncType.FLOAT]], r)


class SampleVolume_Parameters(TypedDict, total=False):
    volume_offset: Vec3f
    volume_size: Vec3f
    xform: Mat4f


class SampleVolume(Func):
    def __init__(
        self,
        points: TypedFunc[Literal[FuncType.VEC3F]],
        volume: Func,
        parameters: Optional[SampleVolume_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = {
            "Points": points,
            "Volume": volume,
        }
        self.assets: Optional[Assets]
        self.assets = None
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> Result:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "SampleVolume",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return r


class Shell_Parameters(TypedDict, total=False):
    offset: float
    thickness: float


class Shell(TypedFunc[Literal[FuncType.FLOAT]]):
    def __init__(
        self,
        samples: TypedFunc[Literal[FuncType.FLOAT]],
        parameters: Optional[Shell_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = {
            "Samples": samples,
        }
        self.assets: Optional[Assets]
        self.assets = None
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> TypedResult[Literal[FuncType.FLOAT]]:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "Shell",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return cast(TypedResult[Literal[FuncType.FLOAT]], r)


class Threshold_Parameters(TypedDict, total=False):
    width: float


class Threshold(TypedFunc[Literal[FuncType.BYTE]]):
    def __init__(
        self,
        samples: TypedFunc[Literal[FuncType.FLOAT]],
        parameters: Optional[Threshold_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = {
            "Samples": samples,
        }
        self.assets: Optional[Assets]
        self.assets = None
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> TypedResult[Literal[FuncType.BYTE]]:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "Threshold",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return cast(TypedResult[Literal[FuncType.BYTE]], r)


class TransformCylindricalCoords_Parameters(TypedDict, total=False):
    radial_scale: float
    xform: Mat4f


class TransformCylindricalCoords(TypedFunc[Literal[FuncType.VEC3F]]):
    def __init__(
        self,
        points: TypedFunc[Literal[FuncType.VEC3F]],
        parameters: Optional[TransformCylindricalCoords_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = {
            "Points": points,
        }
        self.assets: Optional[Assets]
        self.assets = None
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> TypedResult[Literal[FuncType.VEC3F]]:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "TransformCylindricalCoords",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return cast(TypedResult[Literal[FuncType.VEC3F]], r)


class TransformMirrorCoords_Parameters(TypedDict, total=False):
    mirror_normal: Vec3f
    mirror_point: Vec3f
    xform: Mat4f


class TransformMirrorCoords(TypedFunc[Literal[FuncType.VEC3F]]):
    def __init__(
        self,
        points: TypedFunc[Literal[FuncType.VEC3F]],
        parameters: Optional[TransformMirrorCoords_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = {
            "Points": points,
        }
        self.assets: Optional[Assets]
        self.assets = None
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> TypedResult[Literal[FuncType.VEC3F]]:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "TransformMirrorCoords",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return cast(TypedResult[Literal[FuncType.VEC3F]], r)


class TransformSphericalCoords_Parameters(TypedDict, total=False):
    xform: Mat4f


class TransformSphericalCoords(TypedFunc[Literal[FuncType.VEC3F]]):
    def __init__(
        self,
        points: TypedFunc[Literal[FuncType.VEC3F]],
        parameters: Optional[TransformSphericalCoords_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = {
            "Points": points,
        }
        self.assets: Optional[Assets]
        self.assets = None
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> TypedResult[Literal[FuncType.VEC3F]]:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "TransformSphericalCoords",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return cast(TypedResult[Literal[FuncType.VEC3F]], r)


TransformTwistCoords_Enum_axis: TypeAlias = Literal["X", "Y", "Z"]


class TransformTwistCoords_Parameters(TypedDict, total=False):
    axis: TransformTwistCoords_Enum_axis
    frequency: float
    xform: Mat4f


class TransformTwistCoords(TypedFunc[Literal[FuncType.VEC3F]]):
    def __init__(
        self,
        points: TypedFunc[Literal[FuncType.VEC3F]],
        parameters: Optional[TransformTwistCoords_Parameters] = None,
    ):
        self.inputs: Optional[dict[str, Func]]
        self.inputs = {
            "Points": points,
        }
        self.assets: Optional[Assets]
        self.assets = None
        self.parameters = parameters

    @cache
    def __call__(self, eval_: Evaluator) -> TypedResult[Literal[FuncType.VEC3F]]:
        inputs: Optional[Inputs] = None
        if self.inputs:
            inputs = dict((k, v(eval_)) for k, v in self.inputs.items())
        r = eval_(
            "TransformTwistCoords",
            inputs=inputs,
            assets=self.assets,
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], self.parameters),
        )
        return cast(TypedResult[Literal[FuncType.VEC3F]], r)


def BoxPrimitive(
    points: TypedFunc[Literal[FuncType.VEC3F]],
    parameters: Optional[SampleBox_Parameters] = None,
  ) -> TypedFunc[Literal[FuncType.FLOAT]]:
    parameters = parameters or {}
    parameters["shape_type"] = "Box"
    return SampleBox(points, parameters=parameters)


def BoxFramePrimitive(
    points: TypedFunc[Literal[FuncType.VEC3F]],
    parameters: Optional[SampleBox_Parameters] = None,
  ) -> TypedFunc[Literal[FuncType.FLOAT]]:
    parameters = parameters or {}
    parameters["shape_type"] = "BoxFrame"
    return SampleBox(points, parameters=parameters)


def CappedConePrimitive(
    points: TypedFunc[Literal[FuncType.VEC3F]],
    parameters: Optional[SampleBox_Parameters] = None,
  ) -> TypedFunc[Literal[FuncType.FLOAT]]:
    parameters = parameters or {}
    parameters["shape_type"] = "CappedCone"
    return SampleBox(points, parameters=parameters)


def CapsulePrimitive(
    points: TypedFunc[Literal[FuncType.VEC3F]],
    parameters: Optional[SampleBox_Parameters] = None,
  ) -> TypedFunc[Literal[FuncType.FLOAT]]:
    parameters = parameters or {}
    parameters["shape_type"] = "Capsule"
    return SampleBox(points, parameters=parameters)


def CylinderPrimitive(
    points: TypedFunc[Literal[FuncType.VEC3F]],
    parameters: Optional[SampleBox_Parameters] = None,
  ) -> TypedFunc[Literal[FuncType.FLOAT]]:
    parameters = parameters or {}
    parameters["shape_type"] = "Cylinder"
    return SampleBox(points, parameters=parameters)


def EllipsoidPrimitive(
    points: TypedFunc[Literal[FuncType.VEC3F]],
    parameters: Optional[SampleBox_Parameters] = None,
  ) -> TypedFunc[Literal[FuncType.FLOAT]]:
    parameters = parameters or {}
    parameters["shape_type"] = "Ellipsoid"
    return SampleBox(points, parameters=parameters)


def LinkPrimitive(
    points: TypedFunc[Literal[FuncType.VEC3F]],
    parameters: Optional[SampleBox_Parameters] = None,
  ) -> TypedFunc[Literal[FuncType.FLOAT]]:
    parameters = parameters or {}
    parameters["shape_type"] = "Link"
    return SampleBox(points, parameters=parameters)


def PlanePrimitive(
    points: TypedFunc[Literal[FuncType.VEC3F]],
    parameters: Optional[SampleBox_Parameters] = None,
  ) -> TypedFunc[Literal[FuncType.FLOAT]]:
    parameters = parameters or {}
    parameters["shape_type"] = "Plane"
    return SampleBox(points, parameters=parameters)


def TorusPrimitive(
    points: TypedFunc[Literal[FuncType.VEC3F]],
    parameters: Optional[SampleBox_Parameters] = None,
  ) -> TypedFunc[Literal[FuncType.FLOAT]]:
    parameters = parameters or {}
    parameters["shape_type"] = "Torus"
    return SampleBox(points, parameters=parameters)


def CSGIntersect(
    a: TypedFunc[Literal[FuncType.FLOAT]],
    b: TypedFunc[Literal[FuncType.FLOAT]],
    smoothing: Optional[float] = None,
) -> TypedFunc[Literal[FuncType.FLOAT]]:
    parameters: CSG_Parameters = {"operation": "Intersect"}
    if smoothing is not None:
        parameters["smoothing"] = smoothing
    return CSG(a, b, parameters=parameters)


def CSGSubtract(
    a: TypedFunc[Literal[FuncType.FLOAT]],
    b: TypedFunc[Literal[FuncType.FLOAT]],
    smoothing: Optional[float] = None,
) -> TypedFunc[Literal[FuncType.FLOAT]]:
    parameters: CSG_Parameters = {"operation": "Subtract"}
    if smoothing is not None:
        parameters["smoothing"] = smoothing
    return CSG(a, b, parameters=parameters)


def CSGUnion(
    a: TypedFunc[Literal[FuncType.FLOAT]],
    b: TypedFunc[Literal[FuncType.FLOAT]],
    smoothing: Optional[float] = None,
) -> TypedFunc[Literal[FuncType.FLOAT]]:
    parameters: CSG_Parameters = {"operation": "Union"}
    if smoothing is not None:
        parameters["smoothing"] = smoothing
    return CSG(a, b, parameters=parameters)

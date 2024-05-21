# ruff: noqa: F401
"""
This file was automatically generated from the source file: func.py.in.
Any edits should be made to the template file before re-running the codegen.
"""
from typing import Literal, Optional, TypedDict, TypeVar, TYPE_CHECKING
from typing import cast
import sys
if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias

from .func_types import (
    Evaluator,
    Func,
    FuncType,
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


def CSG(
    a: TypedFunc[Literal[FuncType.FLOAT]],
    b: TypedFunc[Literal[FuncType.FLOAT]],
    parameters: Optional[CSG_Parameters] = None,
) -> TypedFunc[Literal[FuncType.FLOAT]]:
    @cache
    def f(eval_: Evaluator) -> TypedResult[Literal[FuncType.FLOAT]]:
        r = eval_(
            "CSG",
            inputs={
                "A": a(eval_),
                "B": b(eval_),
            },
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], parameters),
        )
        return cast(TypedResult[Literal[FuncType.FLOAT]], r)
    return f


class ComputeNormals_Parameters(TypedDict, total=False):
    volume_offset: Vec3f
    volume_size: Vec3f
    xform: Mat4f


def ComputeNormals(
    points: TypedFunc[Literal[FuncType.VEC3F]],
    volume: Func,
    parameters: Optional[ComputeNormals_Parameters] = None,
) -> TypedFunc[Literal[FuncType.VEC3F]]:
    @cache
    def f(eval_: Evaluator) -> TypedResult[Literal[FuncType.VEC3F]]:
        r = eval_(
            "ComputeNormals",
            inputs={
                "Points": points(eval_),
                "Volume": volume(eval_),
            },
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], parameters),
        )
        return cast(TypedResult[Literal[FuncType.VEC3F]], r)
    return f


class GenerateSamplePoints_Parameters(TypedDict, total=False):
    offset: Vec3f
    resolution: Vec3i
    size: Vec3f
    xform: Mat4f


def GenerateSamplePoints(
    parameters: Optional[GenerateSamplePoints_Parameters] = None,
) -> TypedFunc[Literal[FuncType.VEC3F]]:
    @cache
    def f(eval_: Evaluator) -> TypedResult[Literal[FuncType.VEC3F]]:
        r = eval_(
            "GenerateSamplePoints",
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], parameters),
        )
        return cast(TypedResult[Literal[FuncType.VEC3F]], r)
    return f


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


def GradeCellSize(
    points: TypedFunc[Literal[FuncType.VEC3F]],
    parameters: Optional[GradeCellSize_Parameters] = None,
) -> TypedFunc[Literal[FuncType.VEC3F]]:
    @cache
    def f(eval_: Evaluator) -> TypedResult[Literal[FuncType.VEC3F]]:
        r = eval_(
            "GradeCellSize",
            inputs={
                "Points": points(eval_),
            },
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], parameters),
        )
        return cast(TypedResult[Literal[FuncType.VEC3F]], r)
    return f


class InterpolateBoundaryCoords_Parameters(TypedDict, total=False):
    tolerance: float
    xform: Mat4f


def InterpolateBoundaryCoords(
    points: TypedFunc[Literal[FuncType.VEC3F]],
    boundary_data: ParametrizationAsset,
    mesh_data: TriangleMeshAsset,
    parameters: Optional[InterpolateBoundaryCoords_Parameters] = None,
) -> TypedFunc[Literal[FuncType.VEC3F]]:
    @cache
    def f(eval_: Evaluator) -> TypedResult[Literal[FuncType.VEC3F]]:
        r = eval_(
            "InterpolateBoundaryCoords",
            inputs={
                "Points": points(eval_),
            },
            assets={
                "boundary_data": boundary_data,
                "mesh_data": mesh_data,
            },
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], parameters),
        )
        return cast(TypedResult[Literal[FuncType.VEC3F]], r)
    return f


class LinearFilter_Parameters(TypedDict, total=False):
    scale_a: float
    scale_b: float


def LinearFilter(
    inputa: TypedFunc[Literal[FuncType.FLOAT]],
    inputb: TypedFunc[Literal[FuncType.FLOAT]],
    parameters: Optional[LinearFilter_Parameters] = None,
) -> TypedFunc[Literal[FuncType.FLOAT]]:
    @cache
    def f(eval_: Evaluator) -> TypedResult[Literal[FuncType.FLOAT]]:
        r = eval_(
            "LinearFilter",
            inputs={
                "InputA": inputa(eval_),
                "InputB": inputb(eval_),
            },
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], parameters),
        )
        return cast(TypedResult[Literal[FuncType.FLOAT]], r)
    return f


class LoadSamplePoints_Parameters(TypedDict, total=False):
    points: Vec3f


def LoadSamplePoints(
    parameters: Optional[LoadSamplePoints_Parameters] = None,
) -> TypedFunc[Literal[FuncType.VEC3F]]:
    @cache
    def f(eval_: Evaluator) -> TypedResult[Literal[FuncType.VEC3F]]:
        r = eval_(
            "LoadSamplePoints",
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], parameters),
        )
        return cast(TypedResult[Literal[FuncType.VEC3F]], r)
    return f


LoadVolume_Enum_component_type: TypeAlias = Literal["Byte", "Float", "Integer", "None", "Vec2f", "Vec2i", "Vec3f", "Vec3i", "Vec4f", "Vec4i"]


class LoadVolume_Parameters(TypedDict, total=False):
    component_type: LoadVolume_Enum_component_type
    resolution: Vec3i


def LoadVolume(
    volume_data: VolumeAsset,
    parameters: Optional[LoadVolume_Parameters] = None,
) -> Func:
    @cache
    def f(eval_: Evaluator) -> Result:
        r = eval_(
            "LoadVolume",
            assets={
                "volume_data": volume_data,
            },
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], parameters),
        )
        return r
    return f


MapTexturePrimitive_Enum_shape_type: TypeAlias = Literal["Box", "Cylinder", "Ellipsoid", "Plane"]


class MapTexturePrimitive_Parameters(TypedDict, total=False):
    box_width: Vec3f
    scale: Vec2f
    shape_type: MapTexturePrimitive_Enum_shape_type
    shape_xform: Mat4f
    xform: Mat4f


def MapTexturePrimitive(
    points: TypedFunc[Literal[FuncType.VEC3F]],
    image: TypedFunc[Literal[FuncType.FLOAT]],
    parameters: Optional[MapTexturePrimitive_Parameters] = None,
) -> TypedFunc[Literal[FuncType.VEC3F]]:
    @cache
    def f(eval_: Evaluator) -> TypedResult[Literal[FuncType.VEC3F]]:
        r = eval_(
            "MapTexturePrimitive",
            inputs={
                "Points": points(eval_),
                "Image": image(eval_),
            },
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], parameters),
        )
        return cast(TypedResult[Literal[FuncType.VEC3F]], r)
    return f


class Redistance_Parameters(TypedDict, total=False):
    post_offset: float
    pre_offset: float


def Redistance(
    samples: TypedFunc[Literal[FuncType.FLOAT]],
    parameters: Optional[Redistance_Parameters] = None,
) -> TypedFunc[Literal[FuncType.FLOAT]]:
    @cache
    def f(eval_: Evaluator) -> TypedResult[Literal[FuncType.FLOAT]]:
        r = eval_(
            "Redistance",
            inputs={
                "Samples": samples(eval_),
            },
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], parameters),
        )
        return cast(TypedResult[Literal[FuncType.FLOAT]], r)
    return f


SampleBeam_Enum_node_type: TypeAlias = Literal["None", "Sphere"]


SampleBeam_Enum_section_type: TypeAlias = Literal["Box", "Circle", "Cross"]


class SampleBeam_Parameters(TypedDict, total=False):
    node_radius: float
    node_type: SampleBeam_Enum_node_type
    section_radius: float
    section_type: SampleBeam_Enum_section_type
    smoothing: float
    xform: Mat4f


def SampleBeam(
    points: TypedFunc[Literal[FuncType.VEC3F]],
    bvh_data: LineNetworkBvhAsset,
    network_data: LineNetworkAsset,
    parameters: Optional[SampleBeam_Parameters] = None,
) -> TypedFunc[Literal[FuncType.FLOAT]]:
    @cache
    def f(eval_: Evaluator) -> TypedResult[Literal[FuncType.FLOAT]]:
        r = eval_(
            "SampleBeam",
            inputs={
                "Points": points(eval_),
            },
            assets={
                "bvh_data": bvh_data,
                "network_data": network_data,
            },
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], parameters),
        )
        return cast(TypedResult[Literal[FuncType.FLOAT]], r)
    return f


SampleBox_Enum_shape_type: TypeAlias = Literal["Box", "BoxFrame", "CappedCone", "Capsule", "Cylinder", "Ellipsoid", "Link", "Plane", "Torus"]


class SampleBox_Parameters(TypedDict, total=False):
    free_param: float
    shape_type: SampleBox_Enum_shape_type
    size: Vec3f
    xform: Mat4f


def SampleBox(
    points: TypedFunc[Literal[FuncType.VEC3F]],
    parameters: Optional[SampleBox_Parameters] = None,
) -> TypedFunc[Literal[FuncType.FLOAT]]:
    @cache
    def f(eval_: Evaluator) -> TypedResult[Literal[FuncType.FLOAT]]:
        r = eval_(
            "SampleBox",
            inputs={
                "Points": points(eval_),
            },
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], parameters),
        )
        return cast(TypedResult[Literal[FuncType.FLOAT]], r)
    return f


class SampleCustomShape_Parameters(TypedDict, total=False):
    xform: Mat4f


def SampleCustomShape(
    points: TypedFunc[Literal[FuncType.VEC3F]],
    shader_data: CustomShapeAsset,
    parameters: Optional[SampleCustomShape_Parameters] = None,
) -> TypedFunc[Literal[FuncType.FLOAT]]:
    @cache
    def f(eval_: Evaluator) -> TypedResult[Literal[FuncType.FLOAT]]:
        r = eval_(
            "SampleCustomShape",
            inputs={
                "Points": points(eval_),
            },
            assets={
                "shader_data": shader_data,
            },
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], parameters),
        )
        return cast(TypedResult[Literal[FuncType.FLOAT]], r)
    return f


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


def SampleLattice(
    points: TypedFunc[Literal[FuncType.VEC3F]],
    parameters: Optional[SampleLattice_Parameters] = None,
) -> TypedFunc[Literal[FuncType.FLOAT]]:
    @cache
    def f(eval_: Evaluator) -> TypedResult[Literal[FuncType.FLOAT]]:
        r = eval_(
            "SampleLattice",
            inputs={
                "Points": points(eval_),
            },
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], parameters),
        )
        return cast(TypedResult[Literal[FuncType.FLOAT]], r)
    return f


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


def SampleSurfaceLattice(
    points: TypedFunc[Literal[FuncType.VEC3F]],
    parameters: Optional[SampleSurfaceLattice_Parameters] = None,
) -> TypedFunc[Literal[FuncType.FLOAT]]:
    @cache
    def f(eval_: Evaluator) -> TypedResult[Literal[FuncType.FLOAT]]:
        r = eval_(
            "SampleSurfaceLattice",
            inputs={
                "Points": points(eval_),
            },
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], parameters),
        )
        return cast(TypedResult[Literal[FuncType.FLOAT]], r)
    return f


class SampleTriangleMesh_Parameters(TypedDict, total=False):
    cw_winding: int
    xform: Mat4f


def SampleTriangleMesh(
    points: TypedFunc[Literal[FuncType.VEC3F]],
    mesh_data: TriangleMeshAsset,
    parameters: Optional[SampleTriangleMesh_Parameters] = None,
) -> TypedFunc[Literal[FuncType.FLOAT]]:
    @cache
    def f(eval_: Evaluator) -> TypedResult[Literal[FuncType.FLOAT]]:
        r = eval_(
            "SampleTriangleMesh",
            inputs={
                "Points": points(eval_),
            },
            assets={
                "mesh_data": mesh_data,
            },
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], parameters),
        )
        return cast(TypedResult[Literal[FuncType.FLOAT]], r)
    return f


class SampleVolume_Parameters(TypedDict, total=False):
    volume_offset: Vec3f
    volume_size: Vec3f
    xform: Mat4f


def SampleVolume(
    points: TypedFunc[Literal[FuncType.VEC3F]],
    volume: Func,
    parameters: Optional[SampleVolume_Parameters] = None,
) -> Func:
    @cache
    def f(eval_: Evaluator) -> Result:
        r = eval_(
            "SampleVolume",
            inputs={
                "Points": points(eval_),
                "Volume": volume(eval_),
            },
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], parameters),
        )
        return r
    return f


class Shell_Parameters(TypedDict, total=False):
    offset: float
    thickness: float


def Shell(
    samples: TypedFunc[Literal[FuncType.FLOAT]],
    parameters: Optional[Shell_Parameters] = None,
) -> TypedFunc[Literal[FuncType.FLOAT]]:
    @cache
    def f(eval_: Evaluator) -> TypedResult[Literal[FuncType.FLOAT]]:
        r = eval_(
            "Shell",
            inputs={
                "Samples": samples(eval_),
            },
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], parameters),
        )
        return cast(TypedResult[Literal[FuncType.FLOAT]], r)
    return f


class Threshold_Parameters(TypedDict, total=False):
    width: float


def Threshold(
    samples: TypedFunc[Literal[FuncType.FLOAT]],
    parameters: Optional[Threshold_Parameters] = None,
) -> TypedFunc[Literal[FuncType.BYTE]]:
    @cache
    def f(eval_: Evaluator) -> TypedResult[Literal[FuncType.BYTE]]:
        r = eval_(
            "Threshold",
            inputs={
                "Samples": samples(eval_),
            },
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], parameters),
        )
        return cast(TypedResult[Literal[FuncType.BYTE]], r)
    return f


class TransformCylindricalCoords_Parameters(TypedDict, total=False):
    radial_scale: float
    xform: Mat4f


def TransformCylindricalCoords(
    points: TypedFunc[Literal[FuncType.VEC3F]],
    parameters: Optional[TransformCylindricalCoords_Parameters] = None,
) -> TypedFunc[Literal[FuncType.VEC3F]]:
    @cache
    def f(eval_: Evaluator) -> TypedResult[Literal[FuncType.VEC3F]]:
        r = eval_(
            "TransformCylindricalCoords",
            inputs={
                "Points": points(eval_),
            },
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], parameters),
        )
        return cast(TypedResult[Literal[FuncType.VEC3F]], r)
    return f


TransformMirrorCoords_Enum_normal: TypeAlias = Literal["X", "Y", "Z"]


class TransformMirrorCoords_Parameters(TypedDict, total=False):
    normal: TransformMirrorCoords_Enum_normal
    xform: Mat4f


def TransformMirrorCoords(
    points: TypedFunc[Literal[FuncType.VEC3F]],
    parameters: Optional[TransformMirrorCoords_Parameters] = None,
) -> TypedFunc[Literal[FuncType.VEC3F]]:
    @cache
    def f(eval_: Evaluator) -> TypedResult[Literal[FuncType.VEC3F]]:
        r = eval_(
            "TransformMirrorCoords",
            inputs={
                "Points": points(eval_),
            },
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], parameters),
        )
        return cast(TypedResult[Literal[FuncType.VEC3F]], r)
    return f


class TransformSphericalCoords_Parameters(TypedDict, total=False):
    xform: Mat4f


def TransformSphericalCoords(
    points: TypedFunc[Literal[FuncType.VEC3F]],
    parameters: Optional[TransformSphericalCoords_Parameters] = None,
) -> TypedFunc[Literal[FuncType.VEC3F]]:
    @cache
    def f(eval_: Evaluator) -> TypedResult[Literal[FuncType.VEC3F]]:
        r = eval_(
            "TransformSphericalCoords",
            inputs={
                "Points": points(eval_),
            },
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], parameters),
        )
        return cast(TypedResult[Literal[FuncType.VEC3F]], r)
    return f


TransformTwistCoords_Enum_axis: TypeAlias = Literal["X", "Y", "Z"]


class TransformTwistCoords_Parameters(TypedDict, total=False):
    axis: TransformTwistCoords_Enum_axis
    frequency: float
    xform: Mat4f


def TransformTwistCoords(
    points: TypedFunc[Literal[FuncType.VEC3F]],
    parameters: Optional[TransformTwistCoords_Parameters] = None,
) -> TypedFunc[Literal[FuncType.VEC3F]]:
    @cache
    def f(eval_: Evaluator) -> TypedResult[Literal[FuncType.VEC3F]]:
        r = eval_(
            "TransformTwistCoords",
            inputs={
                "Points": points(eval_),
            },
            # https://github.com/python/mypy/issues/4976#issuecomment-460971843
            parameters=cast(Optional[Params], parameters),
        )
        return cast(TypedResult[Literal[FuncType.VEC3F]], r)
    return f


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

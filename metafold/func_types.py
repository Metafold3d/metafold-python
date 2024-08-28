from abc import abstractmethod
from enum import Enum
from typing import (
    Any,
    Annotated,
    Generic,
    Literal,
    Optional,
    Protocol,
    TypeVar,
    TypedDict,
    Union,
)
from typing import cast
import sys
if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias

try:
    import numpy as np
    _USE_NUMPY = True
except ImportError:
    _USE_NUMPY = False


Vec2i: TypeAlias = Union[
    Annotated[list[int], 2],
    "np.ndarray[Literal[2], np.dtype[np.int_]]",
]
Vec2f: TypeAlias = Union[
    Annotated[list[float], 2],
    "np.ndarray[Literal[2], np.dtype[np.float_]]",
]
Vec3i: TypeAlias = Union[
    Annotated[list[int], 3],
    "np.ndarray[Literal[3], np.dtype[np.int_]]",
]
Vec3f: TypeAlias = Union[
    Annotated[list[float], 3],
    "np.ndarray[Literal[3], np.dtype[np.float_]]",
]
Vec4i: TypeAlias = Union[
    Annotated[list[int], 4],
    "np.ndarray[Literal[4], np.dtype[np.int_]]",
]
Vec4f: TypeAlias = Union[
    Annotated[list[float], 4],
    "np.ndarray[Literal[4], np.dtype[np.float_]]",
]
Mat2f: TypeAlias = Union[
    Annotated[list[float], 4],
    "np.ndarray[tuple[Literal[2], Literal[2]], np.dtype[np.float_]]",
]
Mat3f: TypeAlias = Union[
    Annotated[list[float], 9],
    "np.ndarray[tuple[Literal[3], Literal[3]], np.dtype[np.float_]]",
]
Mat4f: TypeAlias = Union[
    Annotated[list[float], 16],
    "np.ndarray[tuple[Literal[4], Literal[4]], np.dtype[np.float_]]",
]


class UnitCell(TypedDict):
    nodes: Union[list[Vec3f], "np.ndarray"]
    edges: Union[list[Vec2i], "np.ndarray"]


class Asset(TypedDict):
    path: str


class VolumeAsset(Asset):
    file_type: Literal["Raw"]


class TriangleMeshAsset(Asset):
    file_type: Literal["MeshFile"]


class CustomShapeAsset(Asset):
    file_type: Literal["ShaderBinarySPIRV"]


class ParametrizationAsset(Asset): ...
class LineNetworkAsset(Asset): ...
class LineNetworkBvhAsset(Asset): ...
class MeshBvhAsset(Asset): ...


class FuncType(Enum):
    BYTE  = "Byte"
    INT   = "Int"
    FLOAT = "Float"
    VEC2I = "Vec2i"
    VEC2F = "Vec2f"
    VEC3I = "Vec3i"
    VEC3F = "Vec3f"
    VEC4I = "Vec4i"
    VEC4F = "Vec4f"
    MAT2F = "Mat2f"
    MAT3F = "Mat3f"
    MAT4F = "Mat4f"


T = TypeVar("T", bound=FuncType, covariant=True)


class Result: ...
class TypedResult(Result, Generic[T]): ...


Inputs: TypeAlias = dict[str, Result]
Assets: TypeAlias = dict[str, Asset]
Params: TypeAlias = dict[str, Any]


class Evaluator(Protocol):
    def __call__(
        self,
        type_: str,
        inputs: Optional[Inputs] = None,
        assets: Optional[Assets] = None,
        parameters: Optional[Params] = None,
    ) -> Result:
        ...


POINT_SOURCE_VAR_TYPE = "_PointSource"


class Func(Protocol):
    def __call__(self, eval_: Evaluator) -> Result: ...


class TypedFunc(Func, Protocol[T]): ...


class BaseEvaluator(Evaluator):
    def __init__(self, source: Optional[TypedFunc[Literal[FuncType.VEC3F]]] = None):
        self._source = source

    def __call__(
        self,
        type_: str,
        inputs: Optional[Inputs] = None,
        assets: Optional[Assets] = None,
        parameters: Optional[Params] = None,
    ) -> Result:
        if type_ == POINT_SOURCE_VAR_TYPE:
            if not self._source:
                raise Exception("Expected valid point source")
            return self._source(self)
        return self._eval(type_, inputs, assets, parameters)

    @abstractmethod
    def _eval(
        self,
        type_: str,
        inputs: Optional[Inputs] = None,
        assets: Optional[Assets] = None,
        parameters: Optional[Params] = None,
    ) -> Result:
        ...


class OperatorParams(TypedDict, total=False):
    parameters: dict[str, Any]


class Operator(OperatorParams):
    type: str


class Edge(TypedDict):
    source: int
    target: Annotated[list[Union[int, str]], 2]


class Graph(TypedDict):
    operators: list[Operator]
    edges: list[Edge]


class IndexResult(TypedResult):
    def __init__(self, index: int):
        self.index = index


class JSONEvaluator(BaseEvaluator):
    def __init__(self, source: Optional[TypedFunc[Literal[FuncType.VEC3F]]] = None):
        super().__init__(source=source)
        self._operators: list[Operator] = []
        self._edges: list[Edge] = []

    def json(self):
        return {
            "operators": self._operators,
            "edges": self._edges,
        }

    def _eval(
        self,
        type_: str,
        inputs: Optional[Inputs] = None,
        assets: Optional[Assets] = None,
        parameters: Optional[Params] = None,
    ) -> IndexResult:
        operator: Operator = self._make_operator(
            type_, assets=assets, parameters=parameters)
        target = len(self._operators)
        self._operators.append(operator)
        if inputs:
            for name, result in inputs.items():
                self._edges.append({
                    "source": cast(IndexResult, result).index,
                    "target": [target, name],
                })
        return IndexResult(target)

    def _make_operator(
        self,
        type_: str,
        assets: Optional[Assets] = None,
        parameters: Optional[Params] = None,
    ) -> Operator:
        operator: Operator = {"type": type_}
        if assets:
            parameters = parameters or {}
            parameters.update(assets)
        if parameters:
            for k, v in parameters.items():
                if _USE_NUMPY and isinstance(v, np.ndarray):
                    parameters[k] = v.flatten().tolist()
            operator["parameters"] = parameters
        return operator

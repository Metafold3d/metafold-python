from dataclasses import dataclass
from metafold.func_types import (
    Assets,
    BaseEvaluator,
    FuncType,
    Inputs,
    Params,
    TypedFunc,
    TypedResult,
)
from typing import Literal, Optional, cast
import networkx as nx


@dataclass(eq=False)
class Operator(object):
    type: str
    assets: Optional[Assets]
    params: Optional[Params]


class OperatorResult(TypedResult):
    def __init__(self, operator: Operator):
        self.operator = operator


class GraphEvaluator(BaseEvaluator):
    def __init__(self, source: Optional[TypedFunc[Literal[FuncType.VEC3F]]] = None):
        super().__init__(source=source)
        self._g: nx.MultiDiGraph[Operator] = nx.MultiDiGraph()

    @property
    def graph(self):
        return self._g

    def _eval(
        self,
        type_: str,
        inputs: Optional[Inputs] = None,
        assets: Optional[Assets] = None,
        parameters: Optional[Params] = None,
    ) -> OperatorResult:
        operator = Operator(type_, assets, parameters)
        self._g.add_node(operator)
        if inputs:
            for name, result in inputs.items():
                source = cast(OperatorResult, result).operator
                self._g.add_edge(source, operator, key=name)
        return OperatorResult(operator)

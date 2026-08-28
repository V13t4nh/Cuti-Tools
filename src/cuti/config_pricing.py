from __future__ import annotations

import ast
import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Mapping

from .errors import ConfigError, PricingError
from .config_pricing_math import _affine, _check_ast, _not_finite

REQUIRED = {
    "commission_rate": (0.125, "rate"),
    "vat_on_commission_rate": (0.21, "rate"),
    "shipping_eur": (35.0, "eur"),
    "eur_vnd_rate": (27000.0, "vnd_per_eur"),
    "min_margin_rate": (0.15, "rate"),
    "min_profit_eur": (50.0, "eur"),
}
DEFAULT_HELPERS = {"total_fee_multiplier": "commission_rate * (1 + vat_on_commission_rate)"}
DEFAULT_FORMULAS = {
    "net_proceeds": "hammer_eur - hammer_eur * total_fee_multiplier - shipping_eur - cost_eur",
    "profit_threshold": "max(cost_eur * min_margin_rate, min_profit_eur)",
}
_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")
_INPUT_UNITS = {"hammer_eur": "eur", "cost_eur": "eur"}
_UNITS = {"eur", "rate", "vnd_per_eur"}
_MAX_AFFINE_OPTIONS = 64


@dataclass(frozen=True, slots=True)
class PricingErrorDetail:
    field: str
    code: str
    message: str


class FormulaError(ConfigError):
    def __init__(self, field: str, code: str, message: str) -> None:
        super().__init__(message)
        self.field, self.code, self.message = field, code, message


@dataclass(frozen=True, slots=True)
class PricingParameter:
    name: str
    value: float
    unit: str
    required: bool
    removable: bool


@dataclass(frozen=True, slots=True)
class PricingProfile:
    parameters: tuple[PricingParameter, ...]
    helpers: tuple[tuple[str, str], ...]
    formulas: tuple[tuple[str, str], ...]
    source: str = "file"
    updated_at: str | None = None

    @property
    def values(self) -> dict[str, float]:
        return {item.name: item.value for item in self.parameters}

    @property
    def revision(self) -> str:
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {"parameters": [{"name": item.name, "value": item.value, "unit": item.unit,
                                 "required": item.required, "removable": item.removable} for item in self.parameters],
                "helpers": [{"name": n, "expression": e} for n, e in self.helpers],
                "formulas": dict(self.formulas)}

    def public(self) -> dict[str, object]:
        body = self.to_dict()
        body["revision"], body["source"], body["updated_at"] = self.revision, self.source, self.updated_at
        body["parameters"] = [{"name": item.name, "value": item.value, "unit": item.unit,
                               "required": item.required, "removable": item.removable} for item in self.parameters]
        body["input_variables"] = [{"name": n, "unit": u, "source": "system"} for n, u in _INPUT_UNITS.items()]
        body["capabilities"] = {"net_proceeds": {"valid": True, "inverse": "affine"},
                                 "profit_threshold": {"valid": True, "inverse": "monotone"}}
        return body

    def _trees(self) -> dict[str, ast.AST]:
        expressions = dict(self.helpers) | dict(self.formulas)
        trees: dict[str, ast.AST] = {}
        visiting: set[str] = set()
        def visit(name: str) -> ast.AST:
            if name in trees: return trees[name]
            if name in visiting: raise FormulaError(name, "cycle", "helper dependency cycle")
            if name not in expressions: raise FormulaError(name, "unknown_name", f"unknown expression {name}")
            visiting.add(name)
            try:
                tree = ast.parse(expressions[name], mode="eval").body
            except (SyntaxError, ValueError) as exc:
                raise FormulaError(name, "syntax", "expression has invalid syntax") from exc
            _check_ast(tree, name)
            for child in ast.walk(tree):
                if isinstance(child, ast.Name) and child.id in expressions: visit(child.id)
            visiting.remove(name); trees[name] = tree; return tree
        for name in expressions: visit(name)
        return trees

    def _resolve(self, node: object, variables: Mapping[str, float], trees: Mapping[str, object], stack: set[str] | None = None, memo: dict[str, float] | None = None) -> float:
        stack = set() if stack is None else stack
        memo = {} if memo is None else memo
        import ast
        if isinstance(node, ast.Constant): return float(node.value)
        if isinstance(node, ast.Name):
            if node.id in variables: return float(variables[node.id])
            if node.id in self.values: return self.values[node.id]
            if node.id in trees:
                if node.id in stack: raise FormulaError(node.id, "cycle", "helper dependency cycle")
                if node.id in memo: return memo[node.id]
                value = self._resolve(trees[node.id], variables, trees, stack | {node.id}, memo)
                memo[node.id] = value
                return value
            raise FormulaError(node.id, "unknown_name", f"unknown variable {node.id}")
        if isinstance(node, ast.UnaryOp):
            value = self._resolve(node.operand, variables, trees, stack, memo); return value if isinstance(node.op, ast.UAdd) else -value
        if isinstance(node, ast.BinOp):
            left, right = self._resolve(node.left, variables, trees, stack, memo), self._resolve(node.right, variables, trees, stack, memo)
            if isinstance(node.op, ast.Add): return left + right
            if isinstance(node.op, ast.Sub): return left - right
            if isinstance(node.op, ast.Mult): return left * right
            if isinstance(node.op, ast.Div):
                if right == 0: raise FormulaError("formula", "division_by_zero", "division by zero")
                return left / right
        if isinstance(node, ast.Call):
            values = [self._resolve(arg, variables, trees, stack, memo) for arg in node.args]
            return (min(values) if node.func.id == "min" else max(values))
        raise FormulaError("formula", "syntax", "unsupported expression")

    def evaluate(self, name: str, *, hammer_eur: float, cost_eur: float) -> float:
        if _not_finite(hammer_eur) or hammer_eur <= 0: raise PricingError("hammer_eur must be finite and > 0")
        if _not_finite(cost_eur) or cost_eur < 0: raise PricingError("cost_eur must be finite and >= 0")
        hammer_eur, cost_eur = float(hammer_eur), float(cost_eur)
        trees = self._trees(); formula = dict(self.formulas).get(name)
        if formula is None: raise FormulaError(name, "unknown_name", f"unknown formula {name}")
        value = self._resolve(trees[name], {"hammer_eur": hammer_eur, "cost_eur": cost_eur}, trees)
        if not math.isfinite(value): raise FormulaError(name, "non_finite", "formula result is not finite")
        return value

    def inverse_break_even(self, cost_eur: float, threshold_eur: float) -> float:
        if _not_finite(cost_eur) or _not_finite(threshold_eur) or cost_eur < 0 or threshold_eur < 0:
            raise PricingError("break-even inputs must be finite and nonnegative")
        options = _affine(dict(self.formulas)["net_proceeds"], self, self._trees(), set())
        if options is None or len(options) != 1: raise FormulaError("formulas.net_proceeds", "unsupported_inverse", "net_proceeds is not affine")
        a, b, c = options[0]
        if not all(math.isfinite(value) for value in (a, b, c)) or not a > 0 or not b < 0:
            raise FormulaError("formulas.net_proceeds", "unsupported_inverse", "net_proceeds requires finite a > 0 and b < 0")
        result = (threshold_eur - b * cost_eur - c) / a
        if not math.isfinite(result) or result < 0:
            raise FormulaError("break_even_hammer", "invalid_result", "break-even result must be finite and nonnegative")
        return result

    def validate(self) -> None:
        trees = self._trees()
        from .config_pricing_units import validate_units
        validate_units(self, trees)
        for name in ("net_proceeds", "profit_threshold"):
            if name not in trees: raise FormulaError(name, "missing_formula", f"missing required formula {name}")
        net = _affine("net_proceeds", self, trees, set())
        if net is None or len(net) != 1 or any(not math.isfinite(value) for value in net[0]) or not net[0][0] > 0 or not net[0][1] < 0:
            raise FormulaError("formulas.net_proceeds", "unsupported_inverse", "net_proceeds must be affine with a > 0 and b < 0")
        threshold = _affine("profit_threshold", self, trees, set())
        if threshold is None or any(not all(math.isfinite(value) for value in (a, b, c)) or a != 0 or b < 0 or c < 0 for a, b, c in threshold):
            raise FormulaError("formulas.profit_threshold", "unsupported_inverse", "profit_threshold must be nondecreasing in cost")
        if self.evaluate("profit_threshold", hammer_eur=1.0, cost_eur=0.0) < net[0][2]:
            raise FormulaError("formulas.net_proceeds", "unsupported_inverse", "break-even hammer must be non-negative")

def profile_from_values(values: Mapping[str, object], *, source: str = "env-derived", updated_at: str | None = None) -> PricingProfile:
    params = []
    for name, (default, unit) in REQUIRED.items():
        raw = values.get(name, default)
        if isinstance(raw, bool): raise ConfigError(f"pricing parameter {name} must be numeric")
        try: value = float(raw)
        except (TypeError, ValueError) as exc: raise ConfigError(f"pricing parameter {name} must be numeric") from exc
        if not math.isfinite(value) or value < 0 or unit == "rate" and value >= 1 or unit == "vnd_per_eur" and value <= 0: raise ConfigError(f"pricing parameter {name} has invalid value")
        params.append(PricingParameter(name, value, unit, True, False))
    profile = PricingProfile(tuple(params), tuple(DEFAULT_HELPERS.items()), tuple(DEFAULT_FORMULAS.items()), source, updated_at)
    profile.validate(); return profile

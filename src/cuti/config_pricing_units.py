"""Small dimensional checker for pricing expressions."""
from __future__ import annotations

import ast
from typing import Mapping

from .config_pricing import _INPUT_UNITS, FormulaError, PricingProfile


def validate_units(profile: PricingProfile, trees: Mapping[str, ast.AST]) -> None:
    units = dict(_INPUT_UNITS)
    units.update({item.name: item.unit for item in profile.parameters})
    resolved: dict[str, str] = {}

    def unit(node: ast.AST, field: str) -> str:
        if isinstance(node, ast.Constant): return "rate"
        if isinstance(node, ast.Name):
            if node.id in units: return units[node.id]
            if node.id in trees:
                if node.id in resolved: return resolved[node.id]
                value = unit(trees[node.id], node.id); resolved[node.id] = value; return value
            raise FormulaError(field, "unknown_name", f"unknown variable {node.id}")
        if isinstance(node, ast.UnaryOp): return unit(node.operand, field)
        if isinstance(node, ast.BinOp):
            left, right = unit(node.left, field), unit(node.right, field)
            if isinstance(node.op, (ast.Add, ast.Sub)):
                if left != right: raise FormulaError(field, "invalid_unit", f"cannot combine {left} and {right}")
                return left
            if isinstance(node.op, ast.Mult):
                if left == "rate": return right
                if right == "rate": return left
                raise FormulaError(field, "invalid_unit", "multiplication creates an unsupported unit")
            if isinstance(node.op, ast.Div):
                if right == "rate": return left
                if left == right: return "rate"
                raise FormulaError(field, "invalid_unit", "division creates an unsupported unit")
        if isinstance(node, ast.Call):
            values = [unit(arg, field) for arg in node.args]
            if len(set(values)) != 1: raise FormulaError(field, "invalid_unit", "min/max arguments must use one unit")
            return values[0]
        raise FormulaError(field, "invalid_unit", "could not infer expression unit")

    for name, tree in trees.items(): resolved[name] = unit(tree, name)
    if resolved.get("net_proceeds") != "eur" or resolved.get("profit_threshold") != "eur":
        raise FormulaError("formulas", "invalid_unit", "required outputs must use eur")

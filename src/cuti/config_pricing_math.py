from __future__ import annotations

import ast
import math
from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:
    from .config_pricing import PricingProfile

_MAX_AFFINE_OPTIONS = 64
_NAME_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789_")


def _error(field: str, code: str, message: str) -> Exception:
    from .config_pricing import FormulaError
    return FormulaError(field, code, message)


def _not_finite(value: object) -> bool:
    try:
        return not math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return True


def _check_ast(node: ast.AST, field: str) -> None:
    nodes = list(ast.walk(node))
    if len(nodes) > 100:
        raise _error(field, "syntax", "expression is too large")

    def depth(item: ast.AST, level: int = 0) -> int:
        return max([level] + [depth(child, level + 1) for child in ast.iter_child_nodes(item)])

    if depth(node) > 20:
        raise _error(field, "syntax", "expression is too deep")
    for item in nodes:
        if isinstance(item, ast.Constant) and (
            isinstance(item.value, bool) or not isinstance(item.value, (int, float)) or _not_finite(item.value)
        ):
            raise _error(field, "syntax", "only finite numeric constants are allowed")
        if isinstance(item, ast.Name) and (not item.id or item.id[0].isdigit() or any(char not in _NAME_CHARS for char in item.id)):
            raise _error(field, "syntax", "names must use snake_case")
        if isinstance(item, ast.Call) and (
            not isinstance(item.func, ast.Name) or item.func.id not in {"min", "max"}
            or len(item.args) < 2 or item.keywords
        ):
            raise _error(field, "syntax", "only min/max with at least two arguments are allowed")
        if isinstance(item, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.UAdd, ast.USub,
                             ast.Expression, ast.Load, ast.BinOp, ast.UnaryOp, ast.Call,
                             ast.Name, ast.Constant)):
            continue
        raise _error(field, "syntax", "unsupported syntax")


def _affine(name: str, profile: PricingProfile, trees: Mapping[str, ast.AST],
            visiting: set[str], memo: dict[str, list[tuple[float, float, float]] | None] | None = None
            ) -> list[tuple[float, float, float]] | None:
    if name in visiting:
        raise _error(name, "cycle", "helper dependency cycle")
    memo = {} if memo is None else memo
    if name in memo:
        return memo[name]
    node = trees[name] if name in trees else ast.parse(name, mode="eval").body
    visiting = visiting | {name}

    def bounded(values: list[tuple[float, float, float]]) -> list[tuple[float, float, float]] | None:
        return values if len(values) <= _MAX_AFFINE_OPTIONS else None

    def walk(item: ast.AST) -> list[tuple[float, float, float]] | None:
        if isinstance(item, ast.Constant):
            return [(0.0, 0.0, float(item.value))]
        if isinstance(item, ast.Name):
            if item.id == "hammer_eur": return [(1.0, 0.0, 0.0)]
            if item.id == "cost_eur": return [(0.0, 1.0, 0.0)]
            if item.id in profile.values: return [(0.0, 0.0, profile.values[item.id])]
            if item.id in trees: return _affine(item.id, profile, trees, visiting, memo)
            return None
        if isinstance(item, ast.UnaryOp):
            values = walk(item.operand)
            return values if isinstance(item.op, ast.UAdd) else [(-a, -b, -c) for a, b, c in values] if values else None
        if isinstance(item, ast.BinOp):
            left, right = walk(item.left), walk(item.right)
            if left is None or right is None: return None
            if isinstance(item.op, (ast.Add, ast.Sub)):
                if len(left) * len(right) > _MAX_AFFINE_OPTIONS: return None
                sign = 1 if isinstance(item.op, ast.Add) else -1
                return bounded([(a + sign * d, b + sign * e, c + sign * f)
                                for a, b, c in left for d, e, f in right])
            if isinstance(item.op, (ast.Mult, ast.Div)):
                left_const = all(not a and not b for a, b, _ in left)
                right_const = all(not a and not b for a, b, _ in right)
                if isinstance(item.op, ast.Div):
                    if not right_const or len(right) != 1 or right[0][2] == 0: return None
                    factor = right[0][2]
                    return bounded([(a / factor, b / factor, c / factor) for a, b, c in left])
                if left_const and len(left) == 1:
                    factor = left[0][2]
                    return bounded([(a * factor, b * factor, c * factor) for a, b, c in right])
                if right_const and len(right) == 1:
                    factor = right[0][2]
                    return bounded([(a * factor, b * factor, c * factor) for a, b, c in left])
        if isinstance(item, ast.Call):
            branches = [walk(arg) for arg in item.args]
            if not all(branches) or sum(len(branch) for branch in branches if branch is not None) > _MAX_AFFINE_OPTIONS:
                return None
            return bounded([option for branch in branches for option in branch])
        return None

    result = walk(node)
    memo[name] = result
    return result

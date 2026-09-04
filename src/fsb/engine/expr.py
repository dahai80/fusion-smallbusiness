import ast
import logging
import operator

logger = logging.getLogger(__name__)

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}

_CMP_OPS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}

_BOOL_OPS = {
    ast.And: all,
    ast.Or: any,
}


def _eval_node(node, ctx: dict) -> object:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, ctx)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return ctx.get(node.id, "")
    if isinstance(node, ast.Attribute):
        attr = node.attr
        if attr.startswith("__"):
            return ""
        base = _eval_node(node.value, ctx)
        if isinstance(base, dict):
            return base.get(attr, "")
        if isinstance(base, (list, str, int, float, bool)):
            return getattr(base, attr, "")
        return ""
    if isinstance(node, ast.Subscript):
        base = _eval_node(node.value, ctx)
        key = _eval_node(node.slice, ctx)
        try:
            return base[key]
        except (KeyError, IndexError, TypeError):
            return ""
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        left = _eval_node(node.left, ctx)
        right = _eval_node(node.right, ctx)
        try:
            return _BIN_OPS[type(node.op)](left, right)
        except (TypeError, ZeroDivisionError) as e:
            logger.warning("binop eval error: %s", e)
            return 0
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, ctx)
        for op, comp in zip(node.ops, node.comparators, strict=True):
            right = _eval_node(comp, ctx)
            if type(op) not in _CMP_OPS:
                return False
            if not _CMP_OPS[type(op)](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.BoolOp) and type(node.op) in _BOOL_OPS:
        values = [_eval_node(v, ctx) for v in node.values]
        if node.op is ast.And:
            return all(values)
        return any(values)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _eval_node(node.operand, ctx)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -_eval_node(node.operand, ctx)
    logger.warning("unsupported expr node: %s", type(node).__name__)
    return False


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        if value.lower() in ("true", "yes", "1"):
            return True
        return value.lower() not in ("", "false", "no", "0")
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return bool(value)


def evaluate_condition(expr: str, ctx: dict) -> bool:
    if not expr or not expr.strip():
        return False
    if expr.strip().lower() in ("default", "else"):
        return False
    try:
        tree = ast.parse(expr.strip(), mode="eval")
        result = _eval_node(tree, ctx)
        return _to_bool(result)
    except SyntaxError as e:
        logger.warning("condition expr syntax error: %s expr=%r", e, expr)
        return False
    except Exception as e:
        logger.warning("condition expr eval error: %s expr=%r", e, expr)
        return False

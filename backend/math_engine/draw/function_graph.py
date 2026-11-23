"""Sample real-valued graphs and build calculus illustrations for the canvas."""

import ast
import math
import operator
import re

import sympy as sp
from mpmath.libmp.libhyper import NoConvergence

from math_engine.draw.Common import common_fields, is_real, make_id, require_dict


X = sp.Symbol("x", real=True)
FUNCTIONS = {
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "cot": sp.cot,
    "sqrt": sp.sqrt, "abs": sp.Abs, "exp": sp.exp,
    "log": sp.log, "ln": sp.log, "log10": sp.log, "log2": sp.log,
}
CONSTANTS = {"x": X, "e": sp.E, "E": sp.E, "pi": sp.pi}
OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul}
TOKEN = re.compile(
    r"(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?"
    r"|[a-zA-Z_][a-zA-Z_0-9]*|\*\*|[+*/().,\-]"
)
MAX_POWER = 32


def _power_depth(node):
    descendants = max((_power_depth(child) for child in ast.iter_child_nodes(node)), default=0)
    return descendants + int(isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow))


def parse_function(expression):
    if not isinstance(expression, str) or not expression.strip() or len(expression) > 200:
        raise ValueError("expression phải là biểu thức theo x, tối đa 200 ký tự.")
    source = (expression.replace("−", "-").replace("×", "*").replace("·", "*")
              .replace("÷", "/").replace("π", "pi").replace("²", "^2")
              .replace("³", "^3").replace("^", "**"))
    source = re.sub(r"^\s*y\s*=\s*", "", source)
    source = re.sub(r"\s+", "", source)
    tokens = TOKEN.findall(source)
    if not tokens or "".join(tokens) != source:
        raise ValueError("Biểu thức hàm số chứa ký tự không hợp lệ.")
    parts = [tokens[0]]
    for previous, current in zip(tokens, tokens[1:]):
        ends_value = previous == ")" or previous in CONSTANTS or previous[-1].isdigit()
        starts_value = current == "(" or current[0].isalnum() or current[0] == "."
        if ends_value and starts_value and previous not in FUNCTIONS:
            parts.append("*")
        parts.append(current)

    # Record domain gaps before simplification. For example, (x²-1)/(x-1)
    # still has a hole at x=1 after SymPy cancels the common factor.
    restrictions = []

    def build(node):
        if isinstance(node, ast.Constant) and is_real(node.value) and abs(node.value) <= 1e12:
            return sp.Rational(str(node.value))
        if isinstance(node, ast.Name) and node.id in CONSTANTS:
            return CONSTANTS[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = build(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.BinOp):
            left, right = build(node.left), build(node.right)
            operation = type(node.op)
            if operation in OPERATORS:
                return OPERATORS[operation](left, right)
            if operation is ast.Div:
                restrictions.append((right, "nonzero"))
                return left / right
            if operation is ast.Pow:
                if (not right.has(X) and right.has(sp.Pow)
                        or right.is_number and (right.is_real is not True or abs(right) > MAX_POWER)):
                    raise ValueError("Số mũ ngoài phạm vi vẽ.")
                if left.has(sp.Pow) and right.is_number and abs(right) > 4:
                    raise ValueError("Lũy thừa lồng nhau ngoài phạm vi vẽ.")
                if right.is_negative:
                    restrictions.append((left, "nonzero"))
                if right.is_Rational and right.q != 1:
                    restrictions.append((left, "nonnegative"))
                if not right.is_number:
                    restrictions.append((left, "positive"))
                return sp.Pow(left, right, evaluate=False)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            name = node.func.id
            arities = (1, 2) if name == "log" else (1,)
            if name in FUNCTIONS and len(node.args) in arities and not node.keywords:
                args = [build(arg) for arg in node.args]
                arg = args[0]
                if name in {"log", "ln", "log2", "log10"}:
                    restrictions.append((arg, "positive"))
                    if name in {"log2", "log10"}:
                        args.append(sp.Integer(2 if name == "log2" else 10))
                    if len(args) == 2 and (not args[1].is_number or args[1].is_positive is not True or args[1] == 1):
                        raise ValueError("Cơ số logarit phải dương và khác 1.")
                elif name == "sqrt":
                    restrictions.append((arg, "nonnegative"))
                elif name in {"tan", "cot"}:
                    restrictions.append(((sp.cos if name == "tan" else sp.sin)(arg), "nonzero"))
                return FUNCTIONS[name](*args)
        raise ValueError("Dùng biến x, số, phép toán và các hàm toán học được hỗ trợ.")

    try:
        tree = ast.parse("".join(parts), mode="eval")
        if sum(isinstance(node, ast.Pow) for node in ast.walk(tree)) > 8 or _power_depth(tree) > 2:
            raise ValueError("Biểu thức có quá nhiều phép lũy thừa.")
        expr = build(tree.body)
    except (SyntaxError, TypeError, OverflowError, RecursionError) as exc:
        raise ValueError("Biểu thức hàm số không hợp lệ.") from exc
    return expr, restrictions


def _range(input_data):
    bounds = input_data.get("x_range", [-5, 5])
    if not isinstance(bounds, (list, tuple)) or len(bounds) != 2 or not all(is_real(v) for v in bounds):
        raise ValueError("x_range phải gồm hai số hữu hạn.")
    lo, hi = map(float, bounds)
    if not lo < hi or not math.isfinite(hi - lo):
        raise ValueError("x_min phải nhỏ hơn x_max và khoảng vẽ phải hữu hạn.")
    count = input_data.get("num_points", 240)
    if isinstance(count, bool) or not isinstance(count, int) or not 2 <= count <= 5000:
        raise ValueError("num_points phải nằm trong khoảng 2–5000.")
    if (hi - lo) / count == 0:
        raise ValueError("Khoảng vẽ quá nhỏ để lấy mẫu.")
    return lo, hi, count


def _roots(expr, lo, hi):
    """Find the polynomial and affine trigonometric roots used in THPT graphs."""
    trig_factors = {sp.sin: 0, sp.cos: math.pi / 2}
    if expr.func in (sp.Mul, sp.Pow):
        if expr.func is sp.Pow:
            return _roots(expr.base, lo, hi) if expr.exp.is_positive else []
        return sorted({root for arg in expr.args for root in _roots(arg, lo, hi)})
    if expr.func in trig_factors:
        argument = expr.args[0]
        slope = argument.diff(X)
        offset = argument.subs(X, 0)
        if slope.is_real and slope.is_number and slope != 0 and offset.is_real:
            a, b = float(slope), float(offset)
            phase = trig_factors[expr.func]
            t0, t1 = sorted((a * lo + b - phase, a * hi + b - phase))
            if not math.isfinite(t0) or not math.isfinite(t1) or t1 - t0 > 200 * math.pi:
                raise ValueError("Hãy chọn khoảng vẽ nhỏ hơn cho hàm lượng giác.")
            return sorted((phase + k * math.pi - b) / a
                          for k in range(math.ceil(t0 / math.pi), math.floor(t1 / math.pi) + 1))
    if not expr.has(X) or expr.is_polynomial(X) is not True:
        return []
    poly = sp.Poly(expr, X)
    if not 1 <= poly.degree() <= 8 or any(coefficient.is_real is not True for coefficient in poly.all_coeffs()):
        return []
    try:
        roots = poly.real_roots()
    except NotImplementedError:
        try:
            roots = [root for root in poly.nroots(maxsteps=100) if abs(sp.im(root)) < 1e-10]
        except (ValueError, ArithmeticError, NoConvergence, sp.polys.polyerrors.PolynomialError):
            return []
    values = {float(sp.re(root)) for root in roots}
    return sorted(value for value in values if lo <= value <= hi)


def _evaluate(function, value):
    try:
        result = float(function(value))
    except (ValueError, OverflowError, ZeroDivisionError, TypeError):
        return None
    return result if math.isfinite(result) else None


class FunctionGraph:
    def __init__(self, expression, lo, hi):
        self.expr, restrictions = parse_function(expression)
        self.function = sp.lambdify(X, self.expr, modules="math", cse=True)
        self.boundaries = set()
        self.excluded = set()
        self.checks = []
        for argument, rule in restrictions:
            self.checks.append((sp.lambdify(X, argument, modules="math"), rule))
            roots = _roots(argument, lo, hi)
            self.boundaries.update(roots)
            if rule != "nonnegative":
                self.excluded.update(roots)

    def value(self, x):
        if x in self.excluded:
            return None
        for check, rule in self.checks:
            result = _evaluate(check, x)
            if result is None or (rule == "nonzero" and result == 0):
                return None
            if (rule == "positive" and result <= 0) or (rule == "nonnegative" and result < 0):
                return None
        return _evaluate(self.function, x)


def _sample(graphs, lo, hi, count, extra=()):
    step = (hi - lo) / count
    cuts = sorted({lo, hi, *extra, *(x for graph in graphs for x in graph.boundaries)})
    excluded = set.union(*(graph.excluded for graph in graphs))
    segments = []
    current = []
    for left, right in zip(cuts, cuts[1:]):
        n = max(2, math.ceil((right - left) / step))
        start = left + (right - left) * 0.002 if left in excluded else left
        stop = right - (right - left) * 0.002 if right in excluded else right
        for index in range(n + 1):
            x = stop if index == n else start + (stop - start) * index / n
            if current and x == current[-1][0]:
                continue
            ys = [graph.value(x) for graph in graphs]
            if None in ys:
                if len(current) >= 2:
                    segments.append(current)
                current = []
            else:
                current.append([x, *ys])
        if right in excluded:
            if len(current) >= 2:
                segments.append(current)
            current = []
    if len(current) >= 2:
        segments.append(current)
    return segments


def _rational_parts(expr):
    if expr.is_rational_function(X):
        return sp.fraction(sp.cancel(expr))
    return None


def _asymptotes(expr, lo, hi):
    parts = _rational_parts(expr)
    if parts is None:
        return []
    numerator, denominator = parts
    if not denominator.has(X):
        return []
    guides = [{"x": x} for x in _roots(denominator, lo, hi)]
    quotient, _ = sp.div(numerator, denominator, X)
    if quotient.is_polynomial(X) and sp.degree(quotient, X) <= 1:
        guides.append({"slope": float(quotient.coeff(X)), "intercept": float(quotient.subs(X, 0))})
    return guides


def _markers(graph, lo, hi, intercepts, extrema):
    markers = {}
    if intercepts:
        parts = _rational_parts(graph.expr)
        if lo <= 0 <= hi and graph.value(0) is not None:
            markers[0] = {"position": [0, graph.value(0)], "label": "Giao Oy"}
        if parts:
            for x in _roots(parts[0], lo, hi):
                y = graph.value(x)
                if y is not None and abs(y) < 1e-7:
                    markers[x] = {"position": [x, 0], "label": "Giao Ox" if x else "O"}
    if extrema:
        derivative = graph.expr.diff(X)
        derivative_parts = _rational_parts(derivative)
        if derivative_parts:
            roots = _roots(derivative_parts[0], lo, hi)
            cuts = sorted({lo, hi, *roots, *graph.boundaries})
            slope = sp.lambdify(X, derivative, modules="math")
            for index, x in enumerate(cuts[1:-1], 1):
                y = graph.value(x)
                if x not in roots or y is None:
                    continue
                left = _evaluate(slope, (cuts[index - 1] + x) / 2)
                right = _evaluate(slope, (cuts[index + 1] + x) / 2)
                if left is not None and right is not None and left * right < 0:
                    markers[x] = {"position": [x, y], "label": "Cực đại" if left > 0 else "Cực tiểu"}
    return list(markers.values())


def draw_function(input_data, state=None):
    input_data = require_dict(input_data)
    lo, hi, count = _range(input_data)
    expression = input_data.get("expression")
    graph = FunctionGraph(expression, lo, hi)
    markers = _markers(graph, lo, hi, input_data.get("show_intercepts"), input_data.get("show_extrema"))
    guides = _asymptotes(graph.expr, lo, hi) if input_data.get("show_asymptotes") else []
    if "tangent_at" in input_data:
        x = input_data["tangent_at"]
        if not is_real(x) or not lo <= x <= hi:
            raise ValueError("tangent_at phải là số nằm trong khoảng vẽ.")
        y = graph.value(x)
        derivative = graph.expr.diff(X)
        slope = _evaluate(sp.lambdify(X, derivative, modules="math"), x) if y is not None else None
        # SymPy's sign(0) convention is not the derivative of |x| at zero.
        if derivative.has(sp.sign, sp.Heaviside) and any(x in _roots(term.args[0], lo, hi)
                                                       for term in derivative.atoms(sp.sign, sp.Heaviside)):
            slope = None
        if slope is None or not math.isfinite(y - slope * x):
            raise ValueError("Không xác định được tiếp tuyến có hệ số góc hữu hạn tại hoành độ này.")
        markers = [marker for marker in markers if marker["position"][0] != x]
        markers.append({"position": [x, y], "label": str(input_data.get("tangent_label") or "Tiếp điểm")})
        guides.append({"slope": slope, "intercept": y - slope * x, "role": "tangent"})

    segments = _sample([graph], lo, hi, count, (marker["position"][0] for marker in markers))
    if not segments:
        raise ValueError("Không đủ điểm hợp lệ để vẽ đồ thị.")
    if graph.excluded:
        parts = _rational_parts(graph.expr)
        if parts:
            numerator, denominator = parts
            poles = set(_roots(denominator, lo, hi))
            simplified = sp.lambdify(X, numerator / denominator, modules="math")
            for x in sorted(graph.excluded - poles):
                y = _evaluate(simplified, x)
                if y is not None:
                    markers.append({"position": [x, y], "label": "Điểm khuyết", "open": True})
    return {
        "id": make_id("function"), "kind": "function", "dimension": "2d",
        "label": str(input_data.get("name") or f"y = {re.sub(r'^\s*y\s*=\s*', '', expression).strip()}"),
        "expression": expression, "x_range": [lo, hi],
        "segments": segments, "guides": guides, "markers": markers,
        **common_fields(input_data, style_default_color="#2563eb"),
    }


def draw_area_between(input_data, state=None):
    input_data = require_dict(input_data)
    if "x_range" not in input_data:
        raise ValueError("Cần xác định hai cận x để tô miền diện tích.")
    lo, hi, count = _range(input_data)
    f, g = input_data.get("expression"), input_data.get("other_expression", "0")
    graphs = [FunctionGraph(f, lo, hi), FunctionGraph(g, lo, hi)]
    difference = graphs[0].expr - graphs[1].expr
    if difference == 0:
        raise ValueError("Hai đường trùng nhau nên không tạo miền diện tích.")
    parts = _rational_parts(difference)
    roots = _roots(parts[0], lo, hi) if parts else []
    segments = _sample(graphs, lo, hi, count, roots)
    if (len(segments) != 1 or segments[0][0][0] != lo or segments[0][-1][0] != hi
            or any(graph.excluded for graph in graphs)):
        raise ValueError("Cần một khoảng liên tục của cả hai hàm để tô miền diện tích.")

    # Close a separate polygon on either side of each crossing to avoid a
    # self-intersecting fill when f and g switch which one is above the other.
    bands = []
    current = []
    for row in segments[0]:
        if row[0] in roots:
            x, y, _ = row
            row = [x, y, y]
        if current:
            x0, f0, g0 = current[-1]
            x, f1, g1 = row
            d0, d1 = f0 - g0, f1 - g1
            if d0 != 0 and d1 != 0 and (d0 < 0) != (d1 < 0):
                t = abs(d0) / (abs(d0) + abs(d1))
                y = (1 - t) * f0 + t * f1
                crossing = [(1 - t) * x0 + t * x, y, y]
                bands.append([*current, crossing])
                current = [crossing]
        current.append(row)
        if len(current) > 1 and row[1] == row[2]:
            bands.append(current)
            current = [row]
    if len(current) > 1:
        bands.append(current)
    return {
        "id": make_id("area_between"), "kind": "area_between", "dimension": "2d",
        "label": str(input_data.get("name") or "Miền diện tích"),
        "expression": f, "other_expression": g, "x_range": [lo, hi], "bands": bands,
        **common_fields(input_data, style_default_color="#0f766e"),
    }

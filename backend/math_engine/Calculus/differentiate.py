import sympy as sp
def differentiate(
    expression: str,
    variable: str = "x",
    order: int = 1
):
    """
    Tính đạo hàm cấp order.

    Ví dụ:
        differentiate("x**4 + 2*x**2", "x", 2)
    """

    try:
        if order < 1:
            raise ValueError("Bậc đạo hàm phải >= 1")

        x = sp.Symbol(variable)

        expr = sp.sympify(expression)

        derivative = sp.diff(expr, x, order)

        derivative = sp.simplify(derivative)

        return {
            "success": True,
            "operation": "differentiate",
            "input": {
                "expression": expression,
                "variable": variable,
                "order": order
            },
            "result": str(derivative),
            "latex": sp.latex(derivative)
        }

    except Exception as e:
        return {
            "success": False,
            "operation": "differentiate",
            "error": str(e)
        }
    
def code_giai_differentiate():
    return """def differentiate(
    expression: str,
    variable: str = "x",
    order: int = 1
):
    

    try:
        if order < 1:
            raise ValueError("Bậc đạo hàm phải >= 1")

        x = sp.Symbol(variable)

        expr = sp.sympify(expression)

        derivative = sp.diff(expr, x, order)

        derivative = sp.simplify(derivative)

        return {
            "success": True,
            "operation": "differentiate",
            "input": {
                "expression": expression,
                "variable": variable,
                "order": order
            },
            "result": str(derivative),
            "latex": sp.latex(derivative)
        }

    except Exception as e:
        return {
            "success": False,
            "operation": "differentiate",
            "error": str(e)
        }"""


def tangent_line(
    expression: str,
    variable: str = "x",
    x_value: float = 1
):
    x = sp.Symbol(variable)

    # Hàm số
    expr = sp.sympify(expression)

    # Đạo hàm
    derivative = sp.diff(expr, x)

    # Tính hệ số góc
    slope = derivative.subs(x, x_value)

    # Tính y tại điểm
    y_value = expr.subs(x, x_value)

    # Phương trình tiếp tuyến
    tangent = sp.expand(
        y_value + slope * (x - x_value)
    )

    return {
        "point": [x_value, y_value],
        "derivative": derivative,
        "slope": slope,
        "equation_tangent": tangent,

        "steps": [
            {
                "step": 1,
                "title": "Tính đạo hàm",
                "expression": f"f'({variable}) = {sp.latex(derivative)}"
            },
            {
                "step": 2,
                "title": "Tính tọa độ điểm tiếp xúc",
                "expression": (
                    f"{variable}_0 = {x_value}, "
                    f"y_0 = f({x_value}) = {sp.latex(y_value)}"
                )
            },
            {
                "step": 3,
                "title": "Tính hệ số góc tiếp tuyến",
                "expression": (
                    f"m = f'({x_value}) = {sp.latex(slope)}"
                )
            },
            {
                "step": 4,
                "title": "Lập phương trình tiếp tuyến",
                "expression": (
                    f"y - {sp.latex(y_value)} = "
                    f"{sp.latex(slope)}(x - {x_value})"
                )
            },
            {
                "step": 5,
                "title": "Kết quả",
                "expression": (
                    f"y = {sp.latex(tangent)}"
                )
            }
        ]
    }

def code_giai_tangent_line():
    return """def tangent_line(expression: str, variable: str = "x", x_value: float = 1):
    x = sp.Symbol(variable)

    # Hàm số
    expr = sp.sympify(expression)

    # Đạo hàm
    derivative = sp.diff(expr, x)

    # Tính hệ số góc
    slope = derivative.subs(x, x_value)

    # Tính y tại điểm
    y_value = expr.subs(x, x_value)

    # Phương trình tiếp tuyến
    tangent = sp.expand(
        y_value + slope * (x - x_value)
    )

    return {
        "point": [x_value, y_value],
        "slope": slope,
        "derivative": derivative,
        "equation": tangent
    }
"""

from sympy import (
    symbols,
    sympify,
    solve,
    factor,
    expand,
    simplify
)


def solve_equation(equation: str, variable: str):
    """
    Giải phương trình tổng quát bằng SymPy.

    Math Engine:
    - Không tự viết lời giải bằng từng trường hợp bậc 2, bậc 3,...
    - Thực hiện các phép biến đổi tổng quát.
    - Trả về kết quả tính toán + thông tin cấu trúc.
    - Tutor LLM sẽ dùng dữ liệu này để giải thích cho người dùng.
    """

    # =========================================================
    # 1. Kiểm tra input
    # =========================================================

    if not equation :
        return {
            "operation": "solve_equation",
            "status": "error",
            "message": "Phương trình không hợp lệ"
        }

    try:
        x = symbols(variable)

        # Tách hai vế
        if "=" not in equation:
            left=equation
            right="0"
        else:
            left, right = equation.split("=", 1)

        lhs = sympify(left.strip())
        rhs = sympify(right.strip())

    except Exception as e:
        return {
            "operation": "solve_equation",
            "status": "error",
            "message": f"Không thể phân tích phương trình: {str(e)}"
        }

    # =========================================================
    # 2. Đưa về dạng F(x) = 0
    # =========================================================

    expr_before = lhs - rhs
    expr = expand(expr_before)

    steps = []

    steps.append({
        "step": 1,
        "operation": "normalize",
        "input": equation,
        "output": f"{expr} = 0",
        "reason": (
            "Chuyển tất cả các hạng tử về một vế "
            "để đưa phương trình về dạng F(x) = 0."
        )
    })

    # =========================================================
    # 3. Rút gọn
    # =========================================================

    simplified = simplify(expr)

    if simplified != expr:
        steps.append({
            "step": len(steps) + 1,
            "operation": "simplify",
            "input": f"{expr} = 0",
            "output": f"{simplified} = 0",
            "reason": (
                "Rút gọn biểu thức nhưng vẫn giữ nguyên tập nghiệm "
                "của phương trình."
            )
        })

        expr = simplified

    # =========================================================
    # 4. Phân tích nhân tử
    # =========================================================

    factored = factor(expr)

    if factored != expr:
        steps.append({
            "step": len(steps) + 1,
            "operation": "factor",
            "input": f"{expr} = 0",
            "output": f"{factored} = 0",
            "reason": (
                "Phân tích biểu thức thành nhân tử để có thể "
                "đưa phương trình về các phương trình đơn giản hơn."
            )
        })

    # =========================================================
    # 5. Giải phương trình
    # =========================================================

    try:
        solutions = solve(expr, x)
    except Exception as e:
        return {
            "operation": "solve_equation",
            "status": "unsolved",
            "input": {
                "equation": equation,
                "variable": variable
            },
            "analysis": {
                "expression": str(expr),
                "factored": str(factored)
            },
            "steps": steps,
            "message": f"Không thể giải phương trình: {str(e)}"
        }

    solution_strings = [
        str(simplify(solution))
        for solution in solutions
    ]

    # =========================================================
    # 6. Bước nghiệm cuối
    # =========================================================

    steps.append({
        "step": len(steps) + 1,
        "operation": "solve",
        "input": f"{factored} = 0",
        "output": solution_strings,
        "reason": (
            "Tìm các giá trị của biến thỏa mãn phương trình."
        )
    })

    # =========================================================
    # 7. Phân tích cấu trúc phương trình
    # =========================================================

    try:
        polynomial = expr.as_poly(x)

        if polynomial is not None:
            degree = polynomial.degree()
        else:
            degree = None

    except Exception:
        degree = None

    # =========================================================
    # 8. Kết quả
    # =========================================================

    return {
        "operation": "solve_equation",

        "status": "success",

        "input": {
            "equation": equation,
            "variable": variable
        },

        "analysis": {
            "expression": str(expr),
            "factored": str(factored),
            "degree": degree,
            "variable": variable
        },

        "result": {
            "solutions": solution_strings
        },

        "steps": steps
    }

def code_giai_function():
    return """def solve_equation(equation: str, variable: str):


    # =========================================================
    # 1. Kiểm tra input
    # =========================================================

    if not equation or "=" not in equation:
        return {
            "operation": "solve_equation",
            "status": "error",
            "message": "Phương trình phải có dạng A = B."
        }

    try:
        x = symbols(variable)

        # Tách hai vế
        left, right = equation.split("=", 1)

        lhs = sympify(left.strip())
        rhs = sympify(right.strip())

    except Exception as e:
        return {
            "operation": "solve_equation",
            "status": "error",
            "message": f"Không thể phân tích phương trình: {str(e)}"
        }

    # =========================================================
    # 2. Đưa về dạng F(x) = 0
    # =========================================================

    expr_before = lhs - rhs
    expr = expand(expr_before)

    steps = []

    steps.append({
        "step": 1,
        "operation": "normalize",
        "input": equation,
        "output": f"{expr} = 0",
        "reason": (
            "Chuyển tất cả các hạng tử về một vế "
            "để đưa phương trình về dạng F(x) = 0."
        )
    })

    # =========================================================
    # 3. Rút gọn
    # =========================================================

    simplified = simplify(expr)

    if simplified != expr:
        steps.append({
            "step": len(steps) + 1,
            "operation": "simplify",
            "input": f"{expr} = 0",
            "output": f"{simplified} = 0",
            "reason": (
                "Rút gọn biểu thức nhưng vẫn giữ nguyên tập nghiệm "
                "của phương trình."
            )
        })

        expr = simplified

    # =========================================================
    # 4. Phân tích nhân tử
    # =========================================================

    factored = factor(expr)

    if factored != expr:
        steps.append({
            "step": len(steps) + 1,
            "operation": "factor",
            "input": f"{expr} = 0",
            "output": f"{factored} = 0",
            "reason": (
                "Phân tích biểu thức thành nhân tử để có thể "
                "đưa phương trình về các phương trình đơn giản hơn."
            )
        })

    # =========================================================
    # 5. Giải phương trình
    # =========================================================

    try:
        solutions = solve(expr, x)
    except Exception as e:
        return {
            "operation": "solve_equation",
            "status": "unsolved",
            "input": {
                "equation": equation,
                "variable": variable
            },
            "analysis": {
                "expression": str(expr),
                "factored": str(factored)
            },
            "steps": steps,
            "message": f"Không thể giải phương trình: {str(e)}"
        }

    solution_strings = [
        str(simplify(solution))
        for solution in solutions
    ]

    # =========================================================
    # 6. Bước nghiệm cuối
    # =========================================================

    steps.append({
        "step": len(steps) + 1,
        "operation": "solve",
        "input": f"{factored} = 0",
        "output": solution_strings,
        "reason": (
            "Tìm các giá trị của biến thỏa mãn phương trình."
        )
    })

    # =========================================================
    # 7. Phân tích cấu trúc phương trình
    # =========================================================

    try:
        polynomial = expr.as_poly(x)

        if polynomial is not None:
            degree = polynomial.degree()
        else:
            degree = None

    except Exception:
        degree = None

    # =========================================================
    # 8. Kết quả
    # =========================================================

    return {
        "operation": "solve_equation",

        "status": "success",

        "input": {
            "equation": equation,
            "variable": variable
        },

        "analysis": {
            "expression": str(expr),
            "factored": str(factored),
            "degree": degree,
            "variable": variable
        },

        "result": {
            "solutions": solution_strings
        },

        "steps": steps
    }
"""
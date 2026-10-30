import sympy as sp


def simplify(expression: str):
    """
    Rút gọn biểu thức đại số.

    Parameters
    ----------
    expression : str
        Biểu thức cần rút gọn.

    Returns
    -------
    dict
        Kết quả và các bước biến đổi để LLM giải thích.
    """

    try:
        # =========================
        # 1. Parse biểu thức
        # =========================
        expr = sp.sympify(expression)

        # =========================
        # 2. Rút gọn
        # =========================
        result = sp.simplify(expr)

        # =========================
        # 3. Tạo các bước biến đổi
        # =========================
        steps = []

        # Bước ban đầu
        steps.append({
            "step": 1,
            "expression": str(expr),
            "description": "Biểu thức ban đầu."
        })

        # expand
        expanded = sp.expand(expr)

        if expanded != expr:
            steps.append({
                "step": len(steps) + 1,
                "expression": str(expanded),
                "description": "Khai triển và thu gọn các hạng tử."
            })

        # cancel
        cancelled = sp.cancel(expr)

        if cancelled != expr and cancelled != expanded:
            steps.append({
                "step": len(steps) + 1,
                "expression": str(cancelled),
                "description": "Rút gọn các phân thức."
            })

        # factor
        factored = sp.factor(expr)

        if factored != expr and factored != expanded and factored != cancelled:
            steps.append({
                "step": len(steps) + 1,
                "expression": str(factored),
                "description": "Phân tích và thu gọn biểu thức."
            })

        # Kết quả cuối
        if str(result) != str(steps[-1]["expression"]):
            steps.append({
                "step": len(steps) + 1,
                "expression": str(result),
                "description": "Kết quả rút gọn."
            })

        return {
            "success": True,
            "operation": "simplify",
            "input": expression,
            "result": str(result),
            "steps": steps
        }

    except Exception as e:
        return {
            "success": False,
            "operation": "simplify",
            "input": expression,
            "error": str(e)
        }
    
def code_simplify():
    return """import sympy as sp


def simplify(expression: str):

    try:
        # =========================
        # 1. Parse biểu thức
        # =========================
        expr = sp.sympify(expression)

        # =========================
        # 2. Rút gọn
        # =========================
        result = sp.simplify(expr)

        # =========================
        # 3. Tạo các bước biến đổi
        # =========================
        steps = []

        # Bước ban đầu
        steps.append({
            "step": 1,
            "expression": str(expr),
            "description": "Biểu thức ban đầu."
        })

        # expand
        expanded = sp.expand(expr)

        if expanded != expr:
            steps.append({
                "step": len(steps) + 1,
                "expression": str(expanded),
                "description": "Khai triển và thu gọn các hạng tử."
            })

        # cancel
        cancelled = sp.cancel(expr)

        if cancelled != expr and cancelled != expanded:
            steps.append({
                "step": len(steps) + 1,
                "expression": str(cancelled),
                "description": "Rút gọn các phân thức."
            })

        # factor
        factored = sp.factor(expr)

        if factored != expr and factored != expanded and factored != cancelled:
            steps.append({
                "step": len(steps) + 1,
                "expression": str(factored),
                "description": "Phân tích và thu gọn biểu thức."
            })

        # Kết quả cuối
        if str(result) != str(steps[-1]["expression"]):
            steps.append({
                "step": len(steps) + 1,
                "expression": str(result),
                "description": "Kết quả rút gọn."
            })

        return {
            "success": True,
            "operation": "simplify",
            "input": expression,
            "result": str(result),
            "steps": steps
        }

    except Exception as e:
        return {
            "success": False,
            "operation": "simplify",
            "input": expression,
            "error": str(e)
        }"""
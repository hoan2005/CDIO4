import sympy as sp


def simplify_trig(expression: str):
    """
    Rút gọn biểu thức lượng giác.

    Parameters
    ----------
    expression : str
        Biểu thức lượng giác cần rút gọn.

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

        steps = []

        # =========================
        # 2. Biểu thức ban đầu
        # =========================
        steps.append({
            "step": 1,
            "operation": "input",
            "expression": str(expr),
            "description": "Biểu thức lượng giác ban đầu."
        })

        current = expr

        # =========================
        # 3. Khai triển công thức lượng giác
        # =========================
        trig_expanded = sp.expand_trig(current)

        if trig_expanded != current:
            current = trig_expanded

            steps.append({
                "step": len(steps) + 1,
                "operation": "trig_expand",
                "expression": str(current),
                "description": (
                    "Khai triển các hàm lượng giác bằng "
                    "các công thức lượng giác tương ứng."
                )
            })

        # =========================
        # 4. Khai triển đại số
        # =========================
        expanded = sp.expand(current)

        if expanded != current:
            current = expanded

            steps.append({
                "step": len(steps) + 1,
                "operation": "expand",
                "expression": str(current),
                "description": (
                    "Khai triển các tích và thu gọn "
                    "các hạng tử đại số."
                )
            })

        # =========================
        # 5. Phân tích nhân tử
        # =========================
        factored = sp.factor(current)

        if factored != current:
            current = factored

            steps.append({
                "step": len(steps) + 1,
                "operation": "factor",
                "expression": str(current),
                "description": (
                    "Phân tích biểu thức thành các nhân tử "
                    "để tìm các nhân tử chung."
                )
            })

        # =========================
        # 6. Rút gọn phân thức
        # =========================
        cancelled = sp.cancel(current)

        if cancelled != current:
            current = cancelled

            steps.append({
                "step": len(steps) + 1,
                "operation": "cancel",
                "expression": str(current),
                "description": (
                    "Triệt tiêu các nhân tử chung "
                    "ở tử số và mẫu số."
                )
            })

        # =========================
        # 7. Rút gọn lượng giác
        # =========================
        trig_simplified = sp.trigsimp(current)

        if trig_simplified != current:
            current = trig_simplified

            steps.append({
                "step": len(steps) + 1,
                "operation": "trig_simplify",
                "expression": str(current),
                "description": (
                    "Áp dụng các hằng đẳng thức và "
                    "quan hệ lượng giác để rút gọn biểu thức."
                )
            })

        # =========================
        # 8. Thử simplify cuối cùng
        # =========================
        final_result = sp.simplify(current)

        if final_result != current:
            current = final_result

            steps.append({
                "step": len(steps) + 1,
                "operation": "simplify",
                "expression": str(current),
                "description": (
                    "Thực hiện bước rút gọn cuối cùng "
                    "để đưa biểu thức về dạng đơn giản hơn."
                )
            })

        # =========================
        # 9. Kết quả
        # =========================
        return {
            "success": True,
            "operation": "simplify_trig",
            "input": expression,
            "result": str(current),
            "steps": steps
        }

    except Exception as e:
        return {
            "success": False,
            "operation": "simplify_trig",
            "input": expression,
            "error": str(e)
        }
def code_simplify_trig():
    return """
import sympy as sp


def simplify_trig(expression: str):


    try:
        # =========================
        # 1. Parse biểu thức
        # =========================
        expr = sp.sympify(expression)

        steps = []

        # =========================
        # 2. Biểu thức ban đầu
        # =========================
        steps.append({
            "step": 1,
            "operation": "input",
            "expression": str(expr),
            "description": "Biểu thức lượng giác ban đầu."
        })

        current = expr

        # =========================
        # 3. Khai triển công thức lượng giác
        # =========================
        trig_expanded = sp.expand_trig(current)

        if trig_expanded != current:
            current = trig_expanded

            steps.append({
                "step": len(steps) + 1,
                "operation": "trig_expand",
                "expression": str(current),
                "description": (
                    "Khai triển các hàm lượng giác bằng "
                    "các công thức lượng giác tương ứng."
                )
            })

        # =========================
        # 4. Khai triển đại số
        # =========================
        expanded = sp.expand(current)

        if expanded != current:
            current = expanded

            steps.append({
                "step": len(steps) + 1,
                "operation": "expand",
                "expression": str(current),
                "description": (
                    "Khai triển các tích và thu gọn "
                    "các hạng tử đại số."
                )
            })

        # =========================
        # 5. Phân tích nhân tử
        # =========================
        factored = sp.factor(current)

        if factored != current:
            current = factored

            steps.append({
                "step": len(steps) + 1,
                "operation": "factor",
                "expression": str(current),
                "description": (
                    "Phân tích biểu thức thành các nhân tử "
                    "để tìm các nhân tử chung."
                )
            })

        # =========================
        # 6. Rút gọn phân thức
        # =========================
        cancelled = sp.cancel(current)

        if cancelled != current:
            current = cancelled

            steps.append({
                "step": len(steps) + 1,
                "operation": "cancel",
                "expression": str(current),
                "description": (
                    "Triệt tiêu các nhân tử chung "
                    "ở tử số và mẫu số."
                )
            })

        # =========================
        # 7. Rút gọn lượng giác
        # =========================
        trig_simplified = sp.trigsimp(current)

        if trig_simplified != current:
            current = trig_simplified

            steps.append({
                "step": len(steps) + 1,
                "operation": "trig_simplify",
                "expression": str(current),
                "description": (
                    "Áp dụng các hằng đẳng thức và "
                    "quan hệ lượng giác để rút gọn biểu thức."
                )
            })

        # =========================
        # 8. Thử simplify cuối cùng
        # =========================
        final_result = sp.simplify(current)

        if final_result != current:
            current = final_result

            steps.append({
                "step": len(steps) + 1,
                "operation": "simplify",
                "expression": str(current),
                "description": (
                    "Thực hiện bước rút gọn cuối cùng "
                    "để đưa biểu thức về dạng đơn giản hơn."
                )
            })

        # =========================
        # 9. Kết quả
        # =========================
        return {
            "success": True,
            "operation": "simplify_trig",
            "input": expression,
            "result": str(current),
            "steps": steps
        }

    except Exception as e:
        return {
            "success": False,
            "operation": "simplify_trig",
            "input": expression,
            "error": str(e)
        }
"""
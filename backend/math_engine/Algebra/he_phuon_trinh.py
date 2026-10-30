import sympy as sp
import numpy as np
from scipy.optimize import root, least_squares



# ============================================================
# HỖ TRỢ GIẢI HỆ PHI TUYẾN BẰNG PHƯƠNG PHÁP SỐ
# ============================================================

def _safe_float(value):
    """Chuyển giá trị SymPy/numpy sang float an toàn."""
    try:
        value = complex(value)
        if abs(value.imag) > 1e-10:
            return None
        value = float(value.real)
        return value if np.isfinite(value) else None
    except Exception:
        return None


def _numerical_solve_system(
    expressions,
    variables,
    symbols,
    equations,
    search_range=(-10, 10),
    grid_size=15,
    residual_tolerance=1e-7,
    dedup_tolerance=1e-5,
):
    """
    Tìm nghiệm thực bằng multi-start numerical solver.

    - n phương trình = n biến: scipy.optimize.root
    - n phương trình > n biến: scipy.optimize.least_squares
    - n phương trình < n biến: báo underdetermined
    - Nhiều điểm khởi đầu giúp tìm nhiều nghiệm khác nhau.

    Lưu ý: nghiệm số "tất cả nghiệm" chỉ có ý nghĩa trong miền tìm kiếm
    được chọn và không thể đảm bảo tuyệt đối trên miền vô hạn.
    """
    n_eq = len(expressions)
    n_var = len(symbols)

    if n_eq < n_var:
        return {
            "success": False,
            "type": "system_of_equations",
            "system_type": "nonlinear",
            "method": "numerical",
            "status": "underdetermined",
            "message": "Hệ có ít phương trình hơn số biến, chưa thể xác định tập nghiệm rời rạc.",
            "variables": variables,
            "equations": equations,
            "solutions": [],
        }

    try:
        low, high = float(search_range[0]), float(search_range[1])
        if low >= high:
            raise ValueError("search_range phải có dạng (min, max), với min < max.")

        grid_size = max(3, int(grid_size))
        n_starts = grid_size ** n_var

        # Tránh tạo grid quá lớn.
        if n_starts <= 10000:
            axes = [
                np.linspace(low, high, grid_size)
                for _ in range(n_var)
            ]
            starts = np.array(np.meshgrid(*axes, indexing="ij")).reshape(n_var, -1).T
        else:
            rng = np.random.default_rng(42)
            starts = rng.uniform(low, high, size=(min(10000, n_starts), n_var))

        # Lambdify thành hàm numpy.
        numeric_functions = [
            sp.lambdify(symbols, expr, modules=["numpy"])
            for expr in expressions
        ]

        def residual_vector(point):
            try:
                values = []
                for func in numeric_functions:
                    value = func(*point)
                    value = np.real_if_close(value)
                    value = float(np.asarray(value).item())
                    if not np.isfinite(value):
                        return np.full(n_eq, 1e100)
                    values.append(value)
                return np.asarray(values, dtype=float)
            except Exception:
                return np.full(n_eq, 1e100)

        solutions = []

        for start in starts:
            try:
                if n_eq == n_var:
                    result = root(residual_vector, start, method="hybr")
                    candidate = np.asarray(result.x, dtype=float)
                else:
                    # Overdetermined: dùng least_squares có bounds.
                    result = least_squares(
                        residual_vector,
                        start,
                        bounds=(low, high),
                        xtol=1e-12,
                        ftol=1e-12,
                        gtol=1e-12,
                        max_nfev=3000,
                    )
                    candidate = np.asarray(result.x, dtype=float)

                if candidate.shape != (n_var,) or not np.all(np.isfinite(candidate)):
                    continue

                # Với root(), lọc nghiệm nằm ngoài miền tìm kiếm.
                if np.any(candidate < low - 1e-8) or np.any(candidate > high + 1e-8):
                    continue

                residual = residual_vector(candidate)
                residual_norm = float(np.linalg.norm(residual))

                if not np.isfinite(residual_norm):
                    continue

                if residual_norm <= residual_tolerance:
                    if not any(
                        np.linalg.norm(candidate - old_candidate) <= dedup_tolerance
                        for old_candidate in solutions
                    ):
                        solutions.append(candidate)

            except Exception:
                continue

        solutions.sort(key=lambda p: tuple(float(v) for v in p))

        formatted_solutions = []
        for candidate in solutions:
            formatted_solutions.append({
                variable: float(candidate[i])
                for i, variable in enumerate(variables)
            })

        return {
            "success": True,
            "type": "system_of_equations",
            "system_type": "nonlinear",
            "method": "numerical",
            "status": (
                "multiple_solutions" if len(formatted_solutions) > 1
                else "unique_solution" if len(formatted_solutions) == 1
                else "no_solution"
            ),
            "message": (
                f"Tìm thấy {len(formatted_solutions)} nghiệm thực bằng phương pháp số."
                if formatted_solutions
                else "Không tìm thấy nghiệm thực trong miền tìm kiếm bằng phương pháp số."
            ),
            "variables": variables,
            "equations": equations,
            "solutions": formatted_solutions,
            "search_range": [low, high],
            "grid_size": grid_size,
            "residual_tolerance": residual_tolerance,
        }

    except Exception as e:
        return {
            "success": False,
            "type": "system_of_equations",
            "system_type": "nonlinear",
            "method": "numerical",
            "status": "numerical_error",
            "message": f"Lỗi nghiệm số: {str(e)}",
            "variables": variables,
            "equations": equations,
            "solutions": [],
        }


def solve_system(equations, variables, search_range=(-10, 10), grid_size=15, residual_tolerance=1e-7):
    """
    Giải hệ phương trình bằng SymPy.

    Hỗ trợ:
        - Hệ tuyến tính
        - Hệ phi tuyến
        - Vô nghiệm
        - Một nghiệm
        - Nhiều nghiệm
        - Vô số nghiệm / nghiệm có tham số
        - Nghiệm phức

    Parameters
    ----------
    equations : list[str]
        Danh sách phương trình.
        Ví dụ:
            [
                "2*x + y = 5",
                "x - y = 1"
            ]

    variables : list[str]
        Danh sách biến.
        Ví dụ:
            ["x", "y"]

    Returns
    -------
    dict
        JSON-serializable dictionary.
    """

    # ============================================================
    # 1. KIỂM TRA INPUT
    # ============================================================

    if not equations:
        return {
            "success": False,
            "type": "system_of_equations",
            "status": "invalid_input",
            "message": "Danh sách phương trình rỗng.",
            "variables": [],
            "equations": [],
            "solutions": []
        }

    if not variables:
        return {
            "success": False,
            "type": "system_of_equations",
            "status": "invalid_input",
            "message": "Danh sách biến rỗng.",
            "variables": [],
            "equations": equations,
            "solutions": []
        }

    # ============================================================
    # 2. TẠO SYMBOL
    # ============================================================

    try:
        symbols = sp.symbols(" ".join(variables))

        # Trường hợp chỉ có 1 biến
        if len(variables) == 1:
            symbols = (symbols,)

        local_dict = {
            name: symbol
            for name, symbol in zip(variables, symbols)
        }

        # Các hàm thường xuất hiện trong input từ LLM / người dùng.
        local_dict.update({
            "sin": sp.sin,
            "cos": sp.cos,
            "tan": sp.tan,
            "asin": sp.asin,
            "acos": sp.acos,
            "atan": sp.atan,
            "sqrt": sp.sqrt,
            "exp": sp.exp,
            "log": sp.log,
            "ln": sp.log,
            "pi": sp.pi,
            "E": sp.E,
        })

    except Exception as e:
        return {
            "success": False,
            "type": "system_of_equations",
            "status": "invalid_variables",
            "message": f"Không thể tạo biến: {str(e)}",
            "variables": variables,
            "equations": equations,
            "solutions": []
        }

    # ============================================================
    # 3. CHUYỂN PHƯƠNG TRÌNH -> BIỂU THỨC = 0
    # ============================================================

    expressions = []

    try:

        for equation in equations:

            if not isinstance(equation, str):
                raise ValueError(
                    f"Phương trình phải là chuỗi: {equation}"
                )

            equation = equation.strip()

            # Có dấu "="
            if "=" in equation:

                parts = equation.split("=")

                if len(parts) != 2:
                    raise ValueError(
                        f"Phương trình không hợp lệ: {equation}"
                    )

                left = parts[0].strip()
                right = parts[1].strip()

                left_expr = sp.parse_expr(
                    left,
                    local_dict=local_dict,
                    transformations=(
                        sp.parsing.sympy_parser.standard_transformations
                        + (sp.parsing.sympy_parser.implicit_multiplication_application,)
                        + (sp.parsing.sympy_parser.convert_xor,)
                    ),
                    evaluate=True,
                )

                right_expr = sp.parse_expr(
                    right,
                    local_dict=local_dict,
                    transformations=(
                        sp.parsing.sympy_parser.standard_transformations
                        + (sp.parsing.sympy_parser.implicit_multiplication_application,)
                        + (sp.parsing.sympy_parser.convert_xor,)
                    ),
                    evaluate=True,
                )

                expr = left_expr - right_expr

            # Không có dấu "="
            else:

                expr = sp.parse_expr(
                    equation,
                    local_dict=local_dict,
                    transformations=(
                        sp.parsing.sympy_parser.standard_transformations
                        + (sp.parsing.sympy_parser.implicit_multiplication_application,)
                        + (sp.parsing.sympy_parser.convert_xor,)
                    ),
                    evaluate=True,
                )

            expressions.append(sp.expand(expr))

    except Exception as e:

        return {
            "success": False,
            "type": "system_of_equations",
            "status": "parse_error",
            "message": f"Không thể phân tích phương trình: {str(e)}",
            "variables": variables,
            "equations": equations,
            "solutions": []
        }

    # ============================================================
    # 4. KIỂM TRA HỆ TUYẾN TÍNH / PHI TUYẾN
    # ============================================================

    try:

        is_linear = all(
            sp.Poly(expr, *symbols).total_degree() <= 1
            for expr in expressions
        )

    except Exception:
        is_linear = False

    system_type = (
        "linear"
        if is_linear
        else "nonlinear"
    )

    # ============================================================
    # 5. GIẢI HỆ
    # ============================================================

    try:

        if is_linear:

            # Hệ tuyến tính
            solution_set = sp.linsolve(
                expressions,
                symbols
            )

        else:

            # Hệ phi tuyến
            solution_set = sp.solve(
                expressions,
                symbols,
                dict=True
            )

    except Exception as e:
        # SymPy có thể không giải được một số hệ phi tuyến/transcendental
        # dù hệ vẫn có nghiệm thực. Khi đó tự động chuyển sang nghiệm số.
        numerical_result = _numerical_solve_system(
            expressions=expressions,
            variables=variables,
            symbols=symbols,
            equations=equations,
            search_range=search_range,
            grid_size=grid_size,
            residual_tolerance=residual_tolerance,
        )

        if numerical_result["success"]:
            numerical_result["symbolic_error"] = str(e)
            return numerical_result

        return {
            "success": False,
            "type": "system_of_equations",
            "system_type": system_type,
            "status": "solve_error",
            "message": f"Không thể giải hệ bằng SymPy và nghiệm số: {str(e)}",
            "variables": variables,
            "equations": equations,
            "solutions": [],
            "numerical_result": numerical_result,
        }

    # ============================================================
    # 6. XỬ LÝ HỆ TUYẾN TÍNH
    # ============================================================

    if is_linear:

        # --------------------------------------------------------
        # Vô nghiệm
        # --------------------------------------------------------

        if solution_set == sp.EmptySet:

            return {
                "success": True,
                "type": "system_of_equations",
                "system_type": "linear",
                "status": "no_solution",
                "message": "Hệ phương trình vô nghiệm.",
                "variables": variables,
                "equations": equations,
                "solutions": []
            }

        # --------------------------------------------------------
        # Có nghiệm
        # --------------------------------------------------------

        solution_tuple = next(iter(solution_set))

        solutions = []

        has_parameter = False

        for variable, value in zip(
            variables,
            solution_tuple
        ):

            value = sp.simplify(value)

            # Kiểm tra có tham số hay không
            free_symbols = value.free_symbols

            parameter_symbols = [
                s for s in free_symbols
                if s not in symbols
            ]

            if parameter_symbols:
                has_parameter = True

            solutions.append({
                "variable": variable,
                "value": str(value)
            })

        # --------------------------------------------------------
        # Vô số nghiệm
        # --------------------------------------------------------

        if has_parameter:

            return {
                "success": True,
                "type": "system_of_equations",
                "system_type": "linear",
                "status": "infinite_solutions",
                "message": "Hệ có vô số nghiệm.",
                "variables": variables,
                "equations": equations,
                "solutions": solutions
            }

        # --------------------------------------------------------
        # Nghiệm duy nhất
        # --------------------------------------------------------

        return {
            "success": True,
            "type": "system_of_equations",
            "system_type": "linear",
            "status": "unique_solution",
            "message": "Hệ có nghiệm duy nhất.",
            "variables": variables,
            "equations": equations,
            "solutions": solutions
        }

    # ============================================================
    # 7. XỬ LÝ HỆ PHI TUYẾN
    # ============================================================

    # solve(..., dict=True) trả về list
    if not solution_set:
        # Không kết luận vô nghiệm ngay với hệ phi tuyến.
        # Thử tìm nghiệm thực bằng phương pháp số trước.
        numerical_result = _numerical_solve_system(
            expressions=expressions,
            variables=variables,
            symbols=symbols,
            equations=equations,
            search_range=search_range,
            grid_size=grid_size,
            residual_tolerance=residual_tolerance,
        )

        if numerical_result["success"] and numerical_result["solutions"]:
            numerical_result["symbolic_status"] = "no_solution"
            return numerical_result

        return {
            "success": True,
            "type": "system_of_equations",
            "system_type": "nonlinear",
            "status": "no_solution",
            "message": "Không tìm thấy nghiệm. Đã thử cả SymPy và tìm nghiệm số trong miền tìm kiếm.",
            "variables": variables,
            "equations": equations,
            "solutions": [],
            "search_range": list(search_range),
        }

    solutions = []

    for solution in solution_set:

        current_solution = {}

        for variable in variables:

            if variable in solution:

                value = sp.simplify(
                    solution[variable]
                )

                current_solution[variable] = str(value)

        solutions.append(current_solution)

    # ============================================================
    # 8. KIỂM TRA NGHIỆM CÓ THAM SỐ
    # ============================================================

    has_parameter = False

    for solution in solutions:

        for value in solution.values():

            try:

                expr = sp.sympify(
                    value,
                    locals=local_dict
                )

                free_symbols = expr.free_symbols

                if any(
                    s not in symbols
                    for s in free_symbols
                ):
                    has_parameter = True

            except Exception:
                pass

    if has_parameter:

        status = "infinite_solutions"

        message = "Hệ có vô số nghiệm."

    elif len(solutions) == 1:

        status = "unique_solution"

        message = "Hệ có một nghiệm."

    else:

        status = "multiple_solutions"

        message = f"Hệ có {len(solutions)} nghiệm."

    # ============================================================
    # 9. KIỂM TRA NGHIỆM PHỨC
    # ============================================================

    has_complex_solution = False

    for solution in solutions:

        for value in solution.values():

            try:

                expr = sp.sympify(
                    value,
                    locals=local_dict
                )

                if expr.has(sp.I):

                    has_complex_solution = True

            except Exception:
                pass

    # ============================================================
    # 10. KẾT QUẢ CUỐI
    # ============================================================

    return {
        "success": True,
        "type": "system_of_equations",
        "system_type": system_type,
        "status": status,
        "message": message,
        "variables": variables,
        "equations": equations,
        "solutions": solutions,
        "has_complex_solution": has_complex_solution
    }
def code_giai_he():
    return """import sympy as sp


def solve_system(equations, variables):
   
   

    # ============================================================
    # 1. KIỂM TRA INPUT
    # ============================================================

    if not equations:
        return {
            "success": False,
            "type": "system_of_equations",
            "status": "invalid_input",
            "message": "Danh sách phương trình rỗng.",
            "variables": [],
            "equations": [],
            "solutions": []
        }

    if not variables:
        return {
            "success": False,
            "type": "system_of_equations",
            "status": "invalid_input",
            "message": "Danh sách biến rỗng.",
            "variables": [],
            "equations": equations,
            "solutions": []
        }

    # ============================================================
    # 2. TẠO SYMBOL
    # ============================================================

    try:
        symbols = sp.symbols(" ".join(variables))

        # Trường hợp chỉ có 1 biến
        if len(variables) == 1:
            symbols = (symbols,)

        local_dict = {
            name: symbol
            for name, symbol in zip(variables, symbols)
        }

    except Exception as e:
        return {
            "success": False,
            "type": "system_of_equations",
            "status": "invalid_variables",
            "message": f"Không thể tạo biến: {str(e)}",
            "variables": variables,
            "equations": equations,
            "solutions": []
        }

    # ============================================================
    # 3. CHUYỂN PHƯƠNG TRÌNH -> BIỂU THỨC = 0
    # ============================================================

    expressions = []

    try:

        for equation in equations:

            if not isinstance(equation, str):
                raise ValueError(
                    f"Phương trình phải là chuỗi: {equation}"
                )

            equation = equation.strip()

            # Có dấu "="
            if "=" in equation:

                parts = equation.split("=")

                if len(parts) != 2:
                    raise ValueError(
                        f"Phương trình không hợp lệ: {equation}"
                    )

                left = parts[0].strip()
                right = parts[1].strip()

                left_expr = sp.sympify(
                    left,
                    locals=local_dict
                )

                right_expr = sp.sympify(
                    right,
                    locals=local_dict
                )

                expr = left_expr - right_expr

            # Không có dấu "="
            else:

                expr = sp.sympify(
                    equation,
                    locals=local_dict
                )

            expressions.append(sp.expand(expr))

    except Exception as e:

        return {
            "success": False,
            "type": "system_of_equations",
            "status": "parse_error",
            "message": f"Không thể phân tích phương trình: {str(e)}",
            "variables": variables,
            "equations": equations,
            "solutions": []
        }

    # ============================================================
    # 4. KIỂM TRA HỆ TUYẾN TÍNH / PHI TUYẾN
    # ============================================================

    try:

        is_linear = all(
            sp.Poly(expr, *symbols).total_degree() <= 1
            for expr in expressions
        )

    except Exception:
        is_linear = False

    system_type = (
        "linear"
        if is_linear
        else "nonlinear"
    )

    # ============================================================
    # 5. GIẢI HỆ
    # ============================================================

    try:

        if is_linear:

            # Hệ tuyến tính
            solution_set = sp.linsolve(
                expressions,
                symbols
            )

        else:

            # Hệ phi tuyến
            solution_set = sp.solve(
                expressions,
                symbols,
                dict=True
            )

    except Exception as e:

        return {
            "success": False,
            "type": "system_of_equations",
            "system_type": system_type,
            "status": "solve_error",
            "message": f"Không thể giải hệ: {str(e)}",
            "variables": variables,
            "equations": equations,
            "solutions": []
        }

    # ============================================================
    # 6. XỬ LÝ HỆ TUYẾN TÍNH
    # ============================================================

    if is_linear:

        # --------------------------------------------------------
        # Vô nghiệm
        # --------------------------------------------------------

        if solution_set == sp.EmptySet:

            return {
                "success": True,
                "type": "system_of_equations",
                "system_type": "linear",
                "status": "no_solution",
                "message": "Hệ phương trình vô nghiệm.",
                "variables": variables,
                "equations": equations,
                "solutions": []
            }

        # --------------------------------------------------------
        # Có nghiệm
        # --------------------------------------------------------

        solution_tuple = next(iter(solution_set))

        solutions = []

        has_parameter = False

        for variable, value in zip(
            variables,
            solution_tuple
        ):

            value = sp.simplify(value)

            # Kiểm tra có tham số hay không
            free_symbols = value.free_symbols

            parameter_symbols = [
                s for s in free_symbols
                if s not in symbols
            ]

            if parameter_symbols:
                has_parameter = True

            solutions.append({
                "variable": variable,
                "value": str(value)
            })

        # --------------------------------------------------------
        # Vô số nghiệm
        # --------------------------------------------------------

        if has_parameter:

            return {
                "success": True,
                "type": "system_of_equations",
                "system_type": "linear",
                "status": "infinite_solutions",
                "message": "Hệ có vô số nghiệm.",
                "variables": variables,
                "equations": equations,
                "solutions": solutions
            }

        # --------------------------------------------------------
        # Nghiệm duy nhất
        # --------------------------------------------------------

        return {
            "success": True,
            "type": "system_of_equations",
            "system_type": "linear",
            "status": "unique_solution",
            "message": "Hệ có nghiệm duy nhất.",
            "variables": variables,
            "equations": equations,
            "solutions": solutions
        }

    # ============================================================
    # 7. XỬ LÝ HỆ PHI TUYẾN
    # ============================================================

    # solve(..., dict=True) trả về list
    if not solution_set:

        return {
            "success": True,
            "type": "system_of_equations",
            "system_type": "nonlinear",
            "status": "no_solution",
            "message": "Hệ phương trình vô nghiệm.",
            "variables": variables,
            "equations": equations,
            "solutions": []
        }

    solutions = []

    for solution in solution_set:

        current_solution = {}

        for variable in variables:

            if variable in solution:

                value = sp.simplify(
                    solution[variable]
                )

                current_solution[variable] = str(value)

        solutions.append(current_solution)

    # ============================================================
    # 8. KIỂM TRA NGHIỆM CÓ THAM SỐ
    # ============================================================

    has_parameter = False

    for solution in solutions:

        for value in solution.values():

            try:

                expr = sp.sympify(
                    value,
                    locals=local_dict
                )

                free_symbols = expr.free_symbols

                if any(
                    s not in symbols
                    for s in free_symbols
                ):
                    has_parameter = True

            except Exception:
                pass

    if has_parameter:

        status = "infinite_solutions"

        message = "Hệ có vô số nghiệm."

    elif len(solutions) == 1:

        status = "unique_solution"

        message = "Hệ có một nghiệm."

    else:

        status = "multiple_solutions"

        message = f"Hệ có {len(solutions)} nghiệm."

    # ============================================================
    # 9. KIỂM TRA NGHIỆM PHỨC
    # ============================================================

    has_complex_solution = False

    for solution in solutions:

        for value in solution.values():

            try:

                expr = sp.sympify(
                    value,
                    locals=local_dict
                )

                if expr.has(sp.I):

                    has_complex_solution = True

            except Exception:
                pass

    # ============================================================
    # 10. KẾT QUẢ CUỐI
    # ============================================================

    return {
        "success": True,
        "type": "system_of_equations",
        "system_type": system_type,
        "status": status,
        "message": message,
        "variables": variables,
        "equations": equations,
        "solutions": solutions,
        "has_complex_solution": has_complex_solution
    }"""
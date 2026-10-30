
from typing import Dict, List, Any
import sympy as sp


class ConstraintParser:

    def __init__(self):
        self.variables = {}
        self.equations = []

        # Đăng ký các loại constraint được hỗ trợ
        self.handlers = {
            "square": self.parse_square,
            "perpendicular_line_plane": self.parse_perpendicular_line_plane,
            "perpendicular_lines": self.parse_perpendicular_lines,
            "parallel_lines": self.parse_parallel_lines,
            "equal_length": self.parse_equal_length,
            "isosceles_triangle": self.parse_isosceles_triangle,
            "equilateral_triangle": self.parse_equilateral_triangle,
            "right_triangle": self.parse_right_triangle,
        }

    # ==========================================
    # 1. Tạo biến tọa độ cho một điểm
    # ==========================================
    def get_point(self, name: str, dimension: int = 3):

        if name not in self.variables:
            self.variables[name] = sp.symbols(
                f"{name}_x:{dimension}"
            )

        return sp.Matrix(self.variables[name])

    # ==========================================
    # 2. Thêm phương trình
    # ==========================================
    def add_equation(self, expression):

        expression = sp.expand(expression)

        self.equations.append(expression)

    # ==========================================
    # 3. Hình vuông
    # ==========================================
    def parse_square(self, constraint):

        A, B, C, D = [
            self.get_point(name)
            for name in constraint["points"]
        ]

        AB = B - A
        BC = C - B

        # AB = BC (độ dài)
        self.add_equation(
            AB.dot(AB) - BC.dot(BC)
        )

        # AB vuông góc BC
        self.add_equation(
            AB.dot(BC)
        )

        # ABCD là hình bình hành
        self.add_equation(
            A + C - B - D
        )

    # ==========================================
    # 4. Đường thẳng vuông góc mặt phẳng
    # ==========================================
    def parse_perpendicular_line_plane(self, constraint):

        P1, P2 = [
            self.get_point(name)
            for name in constraint["line"]
        ]

        A, B, C = [
            self.get_point(name)
            for name in constraint["plane"]
        ]

        line_vector = P2 - P1

        plane_vector_1 = B - A
        plane_vector_2 = C - A

        # Vector đường thẳng vuông góc
        # với hai vector độc lập của mặt phẳng
        self.add_equation(
            line_vector.dot(plane_vector_1)
        )

        self.add_equation(
            line_vector.dot(plane_vector_2)
        )

    # ==========================================
    # 5. Hai đường thẳng vuông góc
    # ==========================================
    def parse_perpendicular_lines(self, constraint):

        A, B = [
            self.get_point(name)
            for name in constraint["line1"]
        ]

        C, D = [
            self.get_point(name)
            for name in constraint["line2"]
        ]

        AB = B - A
        CD = D - C

        self.add_equation(
            AB.dot(CD)
        )

    # ==========================================
    # 6. Hai đường thẳng song song
    # ==========================================
    def parse_parallel_lines(self, constraint):

        A, B = [
            self.get_point(name)
            for name in constraint["line1"]
        ]

        C, D = [
            self.get_point(name)
            for name in constraint["line2"]
        ]

        AB = B - A
        CD = D - C

        # Hai vector cùng phương
        cross = AB.cross(CD)

        for component in cross:
            self.add_equation(component)

    # ==========================================
    # 7. Hai đoạn thẳng bằng nhau
    # ==========================================
    def parse_equal_length(self, constraint):

        A, B = [
            self.get_point(name)
            for name in constraint["line1"]
        ]

        C, D = [
            self.get_point(name)
            for name in constraint["line2"]
        ]

        AB = B - A
        CD = D - C

        self.add_equation(
            AB.dot(AB) - CD.dot(CD)
        )

    # ==========================================
    # 8. Tam giác cân
    # ==========================================
    def parse_isosceles_triangle(self, constraint):

        A, B, C = [
            self.get_point(name)
            for name in constraint["points"]
        ]

        # Mặc định: AB = AC, tức A là đỉnh
        # Có thể chỉ định apex để chọn đỉnh cân.
        apex = constraint.get("apex", "A")

        if apex == "A":
            v1 = B - A
            v2 = C - A
        elif apex == "B":
            v1 = A - B
            v2 = C - B
        elif apex == "C":
            v1 = A - C
            v2 = B - C
        else:
            raise ValueError(
                "apex của tam giác cân phải là A, B hoặc C"
            )

        # Hai cạnh bên bằng nhau
        self.add_equation(
            v1.dot(v1) - v2.dot(v2)
        )

    # ==========================================
    # 9. Tam giác đều
    # ==========================================
    def parse_equilateral_triangle(self, constraint):

        A, B, C = [
            self.get_point(name)
            for name in constraint["points"]
        ]

        AB = B - A
        BC = C - B
        CA = A - C

        # AB = BC
        self.add_equation(
            AB.dot(AB) - BC.dot(BC)
        )

        # BC = CA
        self.add_equation(
            BC.dot(BC) - CA.dot(CA)
        )

    # ==========================================
    # 10. Tam giác vuông
    # ==========================================
    def parse_right_triangle(self, constraint):

        A, B, C = [
            self.get_point(name)
            for name in constraint["points"]
        ]

        # Mặc định tam giác vuông tại A
        right_at = constraint.get("right_at", "A")

        if right_at == "A":
            v1 = B - A
            v2 = C - A
        elif right_at == "B":
            v1 = A - B
            v2 = C - B
        elif right_at == "C":
            v1 = A - C
            v2 = B - C
        else:
            raise ValueError(
                "right_at của tam giác vuông phải là A, B hoặc C"
            )

        # Hai cạnh tạo góc vuông vuông góc nhau
        self.add_equation(
            v1.dot(v2)
        )

    # ==========================================
    # 8. Hàm tổng quát xử lý JSON
    # ==========================================
    def parse(self, data: Dict[str, Any]):

        self.variables = {}
        self.equations = []

        constraints = data.get("constraints", [])

        for constraint in constraints:

            constraint_type = constraint.get("type")

            handler = self.handlers.get(constraint_type)

            if handler is None:
                raise ValueError(
                    f"Constraint không được hỗ trợ: {constraint_type}"
                )

            handler(constraint)

        return {
            "variables": self.variables,
            "equations": self.equations,
            "points": list(self.variables.keys())
        }



class CoordinateConvention:

    def __init__(self):
        self.equations = []

    # ==========================================================
    # Cố định một điểm
    # ==========================================================
    def fix_point(
        self,
        variables,
        point_name,
        position
    ):

        point = variables[point_name]

        for i in range(3):

            self.equations.append(
                point[i] - position[i]
            )

    # ==========================================================
    # Cố định hai điểm trên trục X
    # ==========================================================
    def fix_segment_on_x(
        self,
        variables,
        point_a,
        point_b,
        length
    ):

        A = variables[point_a]
        B = variables[point_b]

        # A = (0,0,0)
        self.fix_point(
            variables,
            point_a,
            [0, 0, 0]
        )

        # B = (length,0,0)
        self.fix_point(
            variables,
            point_b,
            [length, 0, 0]
        )

    # ==========================================================
    # Trả về các phương trình quy ước
    # ==========================================================
    def get_equations(self):

        return self.equations
class CoordinateSolver:

    def __init__(self):
        pass

    # ==========================================================
    # 1. Lấy toàn bộ biến từ Parser
    # ==========================================================
    def get_symbols(self, variables: Dict[str, Any]):

        symbols = []

        for point_variables in variables.values():
            symbols.extend(point_variables)

        return symbols

    # ==========================================================
    # 2. Solve hệ phương trình
    # ==========================================================
    def solve(self, parsed_data: Dict[str, Any]):

        variables = parsed_data["variables"]
        equations = parsed_data["equations"]

        symbols = self.get_symbols(variables)

        if not equations:
            raise ValueError(
                "Không có constraint để giải"
            )

        # Solve hệ phương trình
        solutions = sp.solve(
            equations,
            symbols,
            dict=True
        )

        if not solutions:
            raise ValueError(
                "Không tìm được nghiệm cho hệ constraint"
            )

        return self._format_solution(
            variables,
            solutions[0]
        )

    # ==========================================================
    # 3. Chuyển nghiệm SymPy thành tọa độ
    # ==========================================================
    def _format_solution(
        self,
        variables: Dict[str, Any],
        solution: Dict
    ):

        result = {}

        for point_name, point_variables in variables.items():

            coordinates = []

            for variable in point_variables:

                value = solution.get(variable, variable)

                coordinates.append(
                    float(value)
                )

            result[point_name] = coordinates

        return result
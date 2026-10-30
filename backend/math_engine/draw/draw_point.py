
from typing import Dict, List, Any
import sympy as sp


# ============================================================
# 0. DRAW POINT
# ============================================================

def draw_point(
    name: str,
    position: List[float],
) -> dict:

    # 1. Kiểm tra tên điểm
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Tên điểm không hợp lệ")

    # 2. Kiểm tra tọa độ
    if not isinstance(position, (list, tuple)) or len(position) < 2:
        raise ValueError(
            "Tọa độ điểm phải có ít nhất 2 chiều"
        )

    try:
        position = [float(value) for value in position]
    except (TypeError, ValueError):
        raise ValueError("Tọa độ phải là số")

    # 3. Xác định số chiều
    dimension = f"{len(position)}d"

    # 4. Tạo object điểm
    return {
        "id": f"point_{name}",
        "kind": "point",
        "dimension": dimension,
        "label": name,
        "position": position
    }


# ============================================================
# 1. CONSTRAINT PARSER
# ============================================================

class ConstraintParser:

    def __init__(self):

        self.variables = {}
        self.equations = []

        self.handlers = {
            "square": self.parse_square,
            "perpendicular_line_plane":
                self.parse_perpendicular_line_plane,
            "perpendicular_lines":
                self.parse_perpendicular_lines,
            "parallel_lines":
                self.parse_parallel_lines,
            "equal_length":
                self.parse_equal_length,
            "isosceles_triangle":
                self.parse_isosceles_triangle,
            "equilateral_triangle":
                self.parse_equilateral_triangle,
            "right_triangle":
                self.parse_right_triangle,
        }

    # ==========================================================
    # Tạo biến tọa độ
    # ==========================================================

    def get_point(
        self,
        name: str,
        dimension: int = 3
    ):

        if name not in self.variables:

            self.variables[name] = sp.symbols(
                f"{name}_x:{dimension}"
            )

        return sp.Matrix(
            self.variables[name]
        )

    # ==========================================================
    # Thêm phương trình
    # ==========================================================

    def add_equation(self, expression):

        expression = sp.expand(expression)

        if isinstance(
            expression,
            sp.MatrixBase
        ):

            for value in expression:

                self.equations.append(
                    sp.expand(value)
                )

        else:

            self.equations.append(
                expression
            )

    # ==========================================================
    # Hình vuông
    # ==========================================================

    def parse_square(self, constraint):

        A, B, C, D = [
            self.get_point(name)
            for name in constraint["points"]
        ]

        AB = B - A
        BC = C - B

        self.add_equation(
            AB.dot(AB) - BC.dot(BC)
        )

        self.add_equation(
            AB.dot(BC)
        )

        self.add_equation(
            A + C - B - D
        )

    # ==========================================================
    # Đường thẳng vuông góc mặt phẳng
    # ==========================================================

    def parse_perpendicular_line_plane(
        self,
        constraint
    ):

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

        self.add_equation(
            line_vector.dot(plane_vector_1)
        )

        self.add_equation(
            line_vector.dot(plane_vector_2)
        )

    # ==========================================================
    # Hai đường thẳng vuông góc
    # ==========================================================

    def parse_perpendicular_lines(
        self,
        constraint
    ):

        A, B = [
            self.get_point(name)
            for name in constraint["line_1"]
        ]

        C, D = [
            self.get_point(name)
            for name in constraint["line_2"]
        ]

        AB = B - A
        CD = D - C

        self.add_equation(
            AB.dot(CD)
        )

    # ==========================================================
    # Hai đường thẳng song song
    # ==========================================================

    def parse_parallel_lines(
        self,
        constraint
    ):

        A, B = [
            self.get_point(name)
            for name in constraint["line_1"]
        ]

        C, D = [
            self.get_point(name)
            for name in constraint["line_2"]
        ]

        AB = B - A
        CD = D - C

        cross = AB.cross(CD)

        for component in cross:

            self.add_equation(
                component
            )

    # ==========================================================
    # Hai đoạn thẳng bằng nhau
    # ==========================================================

    def parse_equal_length(
        self,
        constraint
    ):

        A, B = [
            self.get_point(name)
            for name in constraint["line_1"]
        ]

        C, D = [
            self.get_point(name)
            for name in constraint["line_2"]
        ]

        AB = B - A
        CD = D - C

        self.add_equation(
            AB.dot(AB) - CD.dot(CD)
        )

    # ==========================================================
    # Tam giác cân
    # ==========================================================

    def parse_isosceles_triangle(
        self,
        constraint
    ):

        A, B, C = [
            self.get_point(name)
            for name in constraint["points"]
        ]

        apex = constraint.get(
            "apex",
            "A"
        )

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

        self.add_equation(
            v1.dot(v1) - v2.dot(v2)
        )

    # ==========================================================
    # Tam giác đều
    # ==========================================================

    def parse_equilateral_triangle(
        self,
        constraint
    ):

        A, B, C = [
            self.get_point(name)
            for name in constraint["points"]
        ]

        AB = B - A
        BC = C - B
        CA = A - C

        self.add_equation(
            AB.dot(AB) - BC.dot(BC)
        )

        self.add_equation(
            BC.dot(BC) - CA.dot(CA)
        )

    # ==========================================================
    # Tam giác vuông
    # ==========================================================

    def parse_right_triangle(
        self,
        constraint
    ):

        points = constraint["points"]

        if len(points) != 3:

            raise ValueError(
                "right_triangle phải có đúng 3 điểm"
            )

        A, B, C = [
            self.get_point(name)
            for name in points
        ]

        right_at = constraint.get(
            "right_at"
        )

        if right_at is None:

            raise ValueError(
                "right_triangle bắt buộc phải có right_at"
            )

        if right_at in points:

            right_point_name = right_at

        elif right_at in ["A", "B", "C"]:

            index = {
                "A": 0,
                "B": 1,
                "C": 2
            }[right_at]

            right_point_name = points[index]

        else:

            raise ValueError(
                f"right_at không hợp lệ: {right_at}"
            )

        if right_point_name == points[0]:

            v1 = B - A
            v2 = C - A

        elif right_point_name == points[1]:

            v1 = A - B
            v2 = C - B

        elif right_point_name == points[2]:

            v1 = A - C
            v2 = B - C

        else:

            raise ValueError(
                "Không xác định được đỉnh vuông"
            )

        self.add_equation(
            v1.dot(v2)
        )

    # ==========================================================
    # PARSE
    # ==========================================================

    def parse(
        self,
        data: Dict[str, Any]
    ):

        self.variables = {}
        self.equations = []

        constraints = data.get(
            "constraints",
            []
        )

        for constraint in constraints:

            constraint_type = constraint.get(
                "type"
            )

            handler = self.handlers.get(
                constraint_type
            )

            if handler is None:

                raise ValueError(
                    f"Constraint không được hỗ trợ: "
                    f"{constraint_type}"
                )

            handler(constraint)

        return {
            "variables": self.variables,
            "equations": self.equations,
            "points": list(
                self.variables.keys()
            )
        }


# ============================================================
# 2. COORDINATE CONVENTION
# ============================================================

class CoordinateConvention:

    def __init__(self):

        self.equations = []

    def reset(self):

        self.equations = []

    def fix_point(
        self,
        variables,
        point_name,
        position
    ):

        if point_name not in variables:

            raise ValueError(
                f"Không tìm thấy điểm: {point_name}"
            )

        point = variables[point_name]

        if len(position) != len(point):

            raise ValueError(
                f"Tọa độ của {point_name} không đúng số chiều"
            )

        for i in range(len(point)):

            self.equations.append(
                point[i] - position[i]
            )

    def set_right_triangle(
        self,
        variables,
        points,
        right_at,
        side1=4,
        side2=3
    ):

        if len(points) != 3:

            raise ValueError(
                "Tam giác vuông phải có 3 điểm"
            )

        A_name, B_name, C_name = points

        if right_at in points:

            right_point = right_at

        elif right_at in ["A", "B", "C"]:

            index = {
                "A": 0,
                "B": 1,
                "C": 2
            }[right_at]

            right_point = points[index]

        else:

            raise ValueError(
                f"right_at không hợp lệ: {right_at}"
            )

        if right_point == A_name:

            self.fix_point(
                variables,
                A_name,
                [0, 0, 0]
            )

            self.fix_point(
                variables,
                B_name,
                [side1, 0, 0]
            )

            self.fix_point(
                variables,
                C_name,
                [0, side2, 0]
            )

        elif right_point == B_name:

            self.fix_point(
                variables,
                B_name,
                [0, 0, 0]
            )

            self.fix_point(
                variables,
                A_name,
                [side1, 0, 0]
            )

            self.fix_point(
                variables,
                C_name,
                [0, side2, 0]
            )

        elif right_point == C_name:

            self.fix_point(
                variables,
                C_name,
                [0, 0, 0]
            )

            self.fix_point(
                variables,
                A_name,
                [side1, 0, 0]
            )

            self.fix_point(
                variables,
                B_name,
                [0, side2, 0]
            )

    def set_apex_above_point(
        self,
        variables,
        apex_name,
        base_point_name,
        height=5
    ):

        if apex_name not in variables:

            raise ValueError(
                f"Không tìm thấy apex: {apex_name}"
            )

        if base_point_name not in variables:

            raise ValueError(
                f"Không tìm thấy điểm đáy: {base_point_name}"
            )

        base_point = variables[
            base_point_name
        ]

        position = [
            base_point[0],
            base_point[1],
            base_point[2] + height
        ]

        self.fix_point(
            variables,
            apex_name,
            position
        )

    def get_equations(self):

        return self.equations


# ============================================================
# 3. COORDINATE SOLVER
# ============================================================

class CoordinateSolver:

    def get_symbols(
        self,
        variables: Dict[str, Any]
    ):

        symbols = []

        for point_variables in variables.values():

            symbols.extend(
                point_variables
            )

        return symbols

    def solve(
        self,
        parsed_data: Dict[str, Any]
    ):

        variables = parsed_data["variables"]
        equations = parsed_data["equations"]

        symbols = self.get_symbols(
            variables
        )

        if not equations:

            raise ValueError(
                "Không có constraint để giải"
            )

        solutions = sp.solve(
            equations,
            symbols,
            dict=True
        )

        if not solutions:

            raise ValueError(
                "Không tìm được nghiệm cho hệ constraint"
            )

        solution = solutions[0]

        unresolved = []

        for variable in symbols:

            value = solution.get(
                variable,
                variable
            )

            free_symbols = getattr(
                value,
                "free_symbols",
                set()
            )

            if free_symbols:

                unresolved.append(
                    f"{variable} = {value}"
                )

        if unresolved:

            raise ValueError(
                "Hệ constraint chưa đủ để xác định "
                "tọa độ:\n"
                + "\n".join(unresolved)
            )

        return self._format_solution(
            variables,
            solution
        )

    def _format_solution(
        self,
        variables,
        solution
    ):

        result = {}

        for point_name, point_variables in variables.items():

            coordinates = []

            for variable in point_variables:

                value = solution.get(
                    variable,
                    variable
                )

                try:

                    coordinates.append(
                        float(
                            sp.N(value)
                        )
                    )

                except (TypeError, ValueError):

                    raise ValueError(
                        f"Không thể xác định tọa độ "
                        f"{variable}: {value}"
                    )

            result[point_name] = coordinates

        return result


# ============================================================
# 4. GEOMETRY COORDINATE ENGINE
# ============================================================

class GeometryCoordinateEngine:

    def __init__(self):

        self.parser = ConstraintParser()
        self.convention = CoordinateConvention()
        self.solver = CoordinateSolver()

    # ==========================================================
    # Vẽ điểm trực tiếp
    # ==========================================================

    def _draw_points(
        self,
        coordinates
    ):

        objects = []

        for name, position in coordinates.items():

            objects.append(
                draw_point(
                    name=name,
                    position=position
                )
            )

        return objects

    # ==========================================================
    # Generate
    # ==========================================================

    def generate(
        self,
        data
    ):

        self.convention.reset()

        # ------------------------------------------------------
        # 1. Parse constraint
        # ------------------------------------------------------

        parsed = self.parser.parse(data)

        variables = parsed["variables"]

        constraints = data.get(
            "constraints",
            []
        )

        # ------------------------------------------------------
        # 2. Trường hợp có tọa độ trực tiếp
        #
        # Ví dụ:
        #
        # {
        #     "points": {
        #         "A": [1, 2, 3]
        #     }
        # }
        # ------------------------------------------------------

        direct_points = data.get(
            "points"
        )

        if direct_points:

            coordinates = {}

            for name, position in direct_points.items():

                coordinates[name] = [
                    float(value)
                    for value in position
                ]

            return self._draw_points(
                coordinates
            )

        # ------------------------------------------------------
        # 3. Tìm tam giác vuông
        # ------------------------------------------------------

        right_triangle = None

        for constraint in constraints:

            if constraint.get(
                "type"
            ) == "right_triangle":

                right_triangle = constraint
                break

        # ------------------------------------------------------
        # 4. Xử lý tam giác vuông
        # ------------------------------------------------------

        if right_triangle:

            points = right_triangle["points"]

            right_at = right_triangle[
                "right_at"
            ]

            side1 = data.get(
                "side1",
                4
            )

            side2 = data.get(
                "side2",
                3
            )

            self.convention.set_right_triangle(
                variables=variables,
                points=points,
                right_at=right_at,
                side1=side1,
                side2=side2
            )

        # ------------------------------------------------------
        # 5. Xử lý hình chóp
        # ------------------------------------------------------

        apex_name = data.get(
            "apex_name"
        )

        base_order = data.get(
            "base_order",
            []
        )

        if apex_name and base_order:

            for constraint in constraints:

                if constraint.get(
                    "type"
                ) != "perpendicular_line_plane":

                    continue

                line = constraint.get(
                    "line",
                    []
                )

                if len(line) != 2:

                    continue

                base_point = None

                if (
                    line[0] == apex_name
                    and line[1] in base_order
                ):

                    base_point = line[1]

                elif (
                    line[1] == apex_name
                    and line[0] in base_order
                ):

                    base_point = line[0]

                if base_point:

                    height = data.get(
                        "height",
                        5
                    )

                    self.convention.set_apex_above_point(
                        variables=variables,
                        apex_name=apex_name,
                        base_point_name=base_point,
                        height=height
                    )

                    break

        # ------------------------------------------------------
        # 6. Ghép convention equations
        # ------------------------------------------------------

        parsed["equations"].extend(
            self.convention.get_equations()
        )

        # ------------------------------------------------------
        # 7. Solve
        # ------------------------------------------------------

        coordinates = self.solver.solve(
            parsed
        )

        # ------------------------------------------------------
        # 8. Chuyển tọa độ -> Canvas objects
        # ------------------------------------------------------

        return self._draw_points(
            coordinates
        )

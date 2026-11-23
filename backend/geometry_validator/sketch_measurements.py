"""Validate the visual order of stated measurements on a schematic drawing."""
import math


def check_sketch_measurements(measurements, coordinates):
    groups = {}
    for item in measurements:
        kind = item["type"]
        value = item["value"]
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
            raise ValueError("Số đo minh họa phải là số dương hữu hạn.")
        points = [coordinates[name] for name in item["points"]]
        if kind == "length" and len(points) == 2:
            actual = math.dist(*points)
        elif kind == "angle" and len(points) == 3 and value < 180:
            a, b, c = points
            if not len(a) == len(b) == len(c):
                raise ValueError("Các điểm của góc phải cùng số chiều.")
            u = [x-y for x, y in zip(a, b)]
            v = [x-y for x, y in zip(c, b)]
            product = math.hypot(*u) * math.hypot(*v)
            if product == 0:
                raise ValueError("Góc minh họa có hai điểm trùng nhau.")
            cosine = sum(x*y for x, y in zip(u, v)) / product
            actual = math.degrees(math.acos(max(-1, min(1, cosine))))
            if (actual >= 180 - 1e-7 or
                    (value == 90 and abs(actual - 90) > 0.5) or
                    (value != 90 and (actual - 90) * (value - 90) <= 0)):
                raise ValueError("Hình minh họa phải giữ đúng loại góc nhọn, vuông hoặc tù.")
        else:
            raise ValueError("Số đo cần hai điểm cho cạnh hoặc ba điểm cho góc.")
        if actual <= 1e-7:
            raise ValueError("Cạnh hoặc góc trên hình minh họa bị suy biến.")
        groups.setdefault((kind, len(points[0])), []).append((value, actual))

    for group in groups.values():
        for (v1, a1), (v2, a2) in zip(sorted(group), sorted(group)[1:]):
            equal = math.isclose(a1, a2, rel_tol=1e-5, abs_tol=1e-7)
            if (v1 == v2 and not equal) or (v1 < v2 and (a1 >= a2 or equal)):
                raise ValueError("Thứ tự lớn, bé hoặc bằng nhau trên hình chưa khớp với đề.")

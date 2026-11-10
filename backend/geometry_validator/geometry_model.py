"""Canonical point/object index and dependency propagation for canvas geometry."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from .construction_solver import ConstructionSolver


def object_points(obj: Mapping[str, Any]) -> dict[str, list[float]]:
    points: dict[str, list[float]] = {}
    if obj.get("kind") == "point":
        name = obj.get("label") or obj.get("name")
        position = obj.get("position")
        if isinstance(name, str) and isinstance(position, (list, tuple)):
            points[name] = list(position)

    coordinates = obj.get("coordinates")
    if isinstance(coordinates, Mapping):
        for name, position in coordinates.items():
            if name == "center" and isinstance(obj.get("center_name"), str):
                continue
            if isinstance(name, str) and isinstance(position, (list, tuple)):
                points[name] = list(position)

    center_name = obj.get("center_name")
    center = obj.get("center")
    if isinstance(center_name, str) and isinstance(center, (list, tuple)):
        points.setdefault(center_name, list(center))

    for field in ("vertices",):
        vertices = obj.get(field)
        if isinstance(vertices, Mapping):
            for name, position in vertices.items():
                if isinstance(name, str) and isinstance(position, (list, tuple)):
                    points[name] = list(position)

    point_names = obj.get("point_names")
    line_points = obj.get("points")
    if (
        isinstance(point_names, (list, tuple))
        and isinstance(line_points, (list, tuple))
        and len(point_names) == len(line_points)
    ):
        for name, position in zip(point_names, line_points):
            if isinstance(name, str) and isinstance(position, (list, tuple)):
                points[name] = list(position)
    return points


def build_geometry_model(objects: Mapping[str, Any]) -> dict[str, Any]:
    points: dict[str, dict[str, Any]] = {}
    object_index: dict[str, dict[str, Any]] = {}
    constructions: dict[str, dict[str, Any]] = {}

    for object_id, obj in objects.items():
        if not isinstance(obj, Mapping):
            continue
        names = object_points(obj)
        for name, coordinates in names.items():
            entry = points.setdefault(name, {"coordinates": coordinates, "object_ids": []})
            if object_id not in entry["object_ids"]:
                entry["object_ids"].append(object_id)

        object_index[object_id] = {
            "kind": obj.get("kind"),
            "dimension": obj.get("dimension"),
            "point_names": list(names),
            "dependencies": deepcopy(obj.get("dependencies", [])),
            "constraints": deepcopy(obj.get("constraints", [])),
        }
        specs = obj.get("constructions")
        if isinstance(specs, Mapping):
            for point_name, spec in specs.items():
                if isinstance(point_name, str) and isinstance(spec, Mapping):
                    constructions[point_name] = deepcopy(dict(spec))

    dependents: dict[str, list[str]] = {}
    for point_name, spec in constructions.items():
        dependencies = spec.get("depends_on", [])
        if isinstance(dependencies, (list, tuple)):
            for dependency in dependencies:
                if isinstance(dependency, str):
                    dependents.setdefault(dependency, []).append(point_name)

    return {
        "points": points,
        "objects": object_index,
        "constructions": constructions,
        "dependents": dependents,
    }


def apply_point_coordinates(obj: dict[str, Any], coordinates: Mapping[str, list[float]]) -> bool:
    changed = False
    if obj.get("kind") == "point":
        name = obj.get("label") or obj.get("name")
        if name in coordinates and obj.get("position") != coordinates[name]:
            obj["position"] = list(coordinates[name])
            changed = True

    for field in ("coordinates", "vertices"):
        values = obj.get(field)
        if isinstance(values, dict):
            for name, point in coordinates.items():
                if name in values and values[name] != point:
                    values[name] = list(point)
                    changed = True

    center_name = obj.get("center_name")
    if center_name in coordinates and obj.get("center") != coordinates[center_name]:
        obj["center"] = list(coordinates[center_name])
        changed = True

    point_names = obj.get("point_names")
    points = obj.get("points")
    if isinstance(point_names, (list, tuple)) and isinstance(points, list):
        for index, name in enumerate(point_names):
            if name in coordinates and index < len(points) and points[index] != coordinates[name]:
                points[index] = list(coordinates[name])
                changed = True
    return changed


def recompute_dependents(
    objects: Mapping[str, Any],
    changed_coordinates: Mapping[str, list[float]],
    solver: ConstructionSolver | None = None,
) -> tuple[dict[str, dict], dict[str, list[float]]]:
    model = build_geometry_model(objects)
    constructions = model["constructions"]
    all_points = {
        name: list(entry["coordinates"])
        for name, entry in model["points"].items()
    }
    all_points.update({name: list(point) for name, point in changed_coordinates.items()})

    computed: dict[str, list[float]] = {}
    if constructions:
        base_points = {name: point for name, point in all_points.items() if name not in constructions}
        result = (solver or ConstructionSolver()).solve({
            "coordinates": base_points,
            "constructions": constructions,
            "canvas_objects": objects,
        })
        if not result.get("success"):
            details = "; ".join(result.get("errors") or ["không thể tính lại các điểm phụ thuộc"])
            raise ValueError(f"Không thể cập nhật hình vì phép dựng phụ thuộc không hợp lệ: {details}")
        computed = {
            name: list(point)
            for name, point in (result.get("computed_points") or {}).items()
        }

    propagated_coordinates = {**changed_coordinates, **computed}
    updates: dict[str, dict] = {}
    for object_id, obj in objects.items():
        if not isinstance(obj, dict):
            continue
        updated = deepcopy(obj)
        if apply_point_coordinates(updated, propagated_coordinates):
            updates[object_id] = updated
    return updates, computed

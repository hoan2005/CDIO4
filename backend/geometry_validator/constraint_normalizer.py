"""Normalize the project's ConstraintDispatcher schema for numerical solvers.
Original constraints are preserved by the caller and still validated separately.
"""
from __future__ import annotations
from copy import deepcopy
from math import isfinite
from typing import Any, Dict, List, Mapping, Sequence

class ConstraintNormalizationError(ValueError):
    pass

class ConstraintNormalizer:
    def __init__(self, tolerance: float = 1e-7):
        if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or not isfinite(float(tolerance)) or tolerance <= 0:
            raise ValueError("tolerance phải là số hữu hạn > 0")
        self.tolerance = float(tolerance)

    @staticmethod
    def _name(value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ConstraintNormalizationError(f"Tên điểm không hợp lệ: {value!r}")
        return value.strip().removeprefix("point_")

    @classmethod
    def _pair(cls, value: Any, field: str) -> List[str]:
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise ConstraintNormalizationError(f"{field} phải gồm đúng 2 tên điểm")
        return [cls._name(v) for v in value]

    @staticmethod
    def _number(value: Any, field: str, positive: bool = False) -> float:
        if isinstance(value, bool):
            raise ConstraintNormalizationError(f"{field} phải là số hữu hạn")
        try: n = float(value)
        except (TypeError, ValueError): raise ConstraintNormalizationError(f"{field} phải là số hữu hạn")
        if not isfinite(n) or (positive and n <= 0):
            raise ConstraintNormalizationError(f"{field} không hợp lệ")
        return n

    def normalize(self, constraints: Sequence[Mapping[str, Any]], coordinates: Mapping[str, Sequence[float]],
                  coordinate_control: Mapping[str, Mapping[str, Any]] | None = None,
                  dimension: int | None = None) -> Dict[str, Any]:
        if not isinstance(constraints, (list, tuple)) or not isinstance(coordinates, Mapping):
            raise ConstraintNormalizationError("constraints phải là list và coordinates phải là dict")
        coords: Dict[str, List[float]] = {}; dim = dimension
        for raw_name, raw in coordinates.items():
            name = self._name(raw_name)
            if not isinstance(raw, (list, tuple)) or len(raw) not in (2, 3):
                raise ConstraintNormalizationError(f"Tọa độ {name!r} phải có 2 hoặc 3 thành phần")
            if dim is None: dim = len(raw)
            if len(raw) != dim: raise ConstraintNormalizationError("Không được trộn tọa độ 2D và 3D")
            vals=[]
            for v in raw:
                if isinstance(v, bool): raise ConstraintNormalizationError(f"Tọa độ {name!r} chứa boolean")
                try: n=float(v)
                except (TypeError,ValueError): raise ConstraintNormalizationError(f"Tọa độ {name!r} không phải số")
                if not isfinite(n): raise ConstraintNormalizationError(f"Tọa độ {name!r} không hữu hạn")
                vals.append(n)
            if name in coords and coords[name] != vals: raise ConstraintNormalizationError(f"Alias tọa độ mâu thuẫn tại {name}")
            coords[name]=vals
        dim=dim or 2
        if dim not in (2,3): raise ConstraintNormalizationError("dimension chỉ nhận 2 hoặc 3")
        solver=[]; validation_only=[]; errors=[]

        def add(typ, pts, raw, value=None):
            missing=[n for n in pts if n not in coords]
            if missing: errors.append(f"{typ}: thiếu tọa độ điểm {missing}"); return
            item={"type":typ,"points":pts,"_source_type":raw.get("type")}
            if value is not None: item["value"]=value
            solver.append(item)

        for i, raw in enumerate(constraints):
            if not isinstance(raw, Mapping): errors.append(f"Constraint #{i} không phải object"); continue
            typ=str(raw.get("type",raw.get("constraint_type",""))).strip().lower()
            try:
                if typ=="parallel_lines":
                    if raw.get("line_1") is not None:
                        a,b=self._pair(raw.get("line_1"),"line_1")
                        if raw.get("line_2") is not None:
                            c,d=self._pair(raw.get("line_2"),"line_2"); add("parallel_lines",[a,b,c,d],raw)
                        elif raw.get("tangent_at") is not None and raw.get("circle") is not None:
                            center=self._name(raw.get("circle")); tangent=self._name(raw.get("tangent_at"))
                            add("perpendicular_lines",[a,b,center,tangent],raw)
                        else: raise ConstraintNormalizationError("parallel_lines cần line_2 hoặc tangent_at + circle")
                    else:
                        pp=raw.get("points")
                        if not isinstance(pp,(list,tuple)) or len(pp)!=4: raise ConstraintNormalizationError("parallel_lines cần 4 điểm")
                        add("parallel_lines",[self._name(x) for x in pp],raw)
                elif typ=="perpendicular_lines":
                    if raw.get("line_1") is not None:
                        a,b=self._pair(raw.get("line_1"),"line_1"); c,d=self._pair(raw.get("line_2"),"line_2"); add("perpendicular_lines",[a,b,c,d],raw)
                    else:
                        pp=raw.get("points")
                        if not isinstance(pp,(list,tuple)) or len(pp)!=4: raise ConstraintNormalizationError("perpendicular_lines cần 4 điểm")
                        add("perpendicular_lines",[self._name(x) for x in pp],raw)
                elif typ=="right_triangle":
                    pp=raw.get("points")
                    if not isinstance(pp,(list,tuple)) or len(pp)!=3: raise ConstraintNormalizationError("right_triangle cần 3 điểm")
                    ns=[self._name(x) for x in pp]; apex=self._name(raw.get("right_angle_at"))
                    if apex not in ns: raise ConstraintNormalizationError("right_angle_at không thuộc points")
                    x,y=[n for n in ns if n!=apex]; add("perpendicular_lines",[apex,x,apex,y],raw)
                elif typ in ("isosceles_triangle","equilateral_triangle"):
                    pp=raw.get("points")
                    if not isinstance(pp,(list,tuple)) or len(pp)!=3: raise ConstraintNormalizationError(f"{typ} cần 3 điểm")
                    a,b,c=[self._name(x) for x in pp]
                    if typ=="isosceles_triangle":
                        apex=self._name(raw.get("apex")); base=[x for x in (a,b,c) if x!=apex]
                        if len(base)!=2: raise ConstraintNormalizationError("apex không hợp lệ")
                        add("equal_length",[apex,base[0],apex,base[1]],raw)
                    else:
                        add("equal_length",[a,b,b,c],raw); add("equal_length",[b,c,c,a],raw)
                elif typ=="equal_length":
                    if isinstance(raw.get("points"),(list,tuple)) and len(raw["points"])==4:
                        a,b,c,d=[self._name(x) for x in raw["points"]]
                    else:
                        a,b=self._pair(raw.get("segment_1"),"segment_1"); c,d=self._pair(raw.get("segment_2"),"segment_2")
                    add("equal_length",[a,b,c,d],raw)
                elif typ in ("segment_length","distance","point_distance","distance_between_points"):
                    seg=raw.get("segment",raw.get("points"))
                    a,b=self._pair(seg,"segment")
                    val=raw.get("length",raw.get("distance",raw.get("value"))); add("distance",[a,b],raw,self._number(val,"length"))
                elif typ in ("point_on_line","point_on_segment"):
                    if isinstance(raw.get("points"),(list,tuple)) and len(raw["points"])==3:
                        pt,a,b=[self._name(x) for x in raw["points"]]
                    else:
                        pt=self._name(raw.get("point")); a,b=self._pair(raw.get("line",raw.get("segment")),"line/segment")
                    add("point_on_line",[pt,a,b],raw)
                    if typ=="point_on_segment": validation_only.append(deepcopy(dict(raw)))
                elif typ=="midpoint":
                    if isinstance(raw.get("points"),(list,tuple)) and len(raw["points"])==3:
                        pt,a,b=[self._name(x) for x in raw["points"]]
                    else:
                        pt=self._name(raw.get("point")); a,b=self._pair(raw.get("segment"),"segment")
                    add("midpoint",[pt,a,b],raw)
                elif typ=="perpendicular_line_plane":
                    a,b=self._pair(raw.get("line"),"line"); plane=raw.get("plane")
                    if dim!=3 or not isinstance(plane,(list,tuple)) or len(plane)<3: raise ConstraintNormalizationError("perpendicular_line_plane cần 3D và >=3 điểm mặt phẳng")
                    pp=[self._name(x) for x in plane[:3]]; add("perpendicular_line_plane",[a,b]+pp,raw)
                elif typ=="angle_between_planes":
                    p1,p2=raw.get("plane_1"),raw.get("plane_2")
                    if dim!=3 or not isinstance(p1,(list,tuple)) or len(p1)<3 or not isinstance(p2,(list,tuple)) or len(p2)<3: raise ConstraintNormalizationError("angle_between_planes cần hai mặt phẳng 3D")
                    pp=[self._name(x) for x in list(p1[:3])+list(p2[:3])]; val=self._number(raw.get("angle_degrees"),"angle_degrees")
                    add("angle_between_planes",pp,raw,val)
                elif typ=="circle_radius":
                    center=raw.get("center",raw.get("center_point",raw.get("center_name"))); point=raw.get("point_on_circle",raw.get("point_on_circumference",raw.get("point")))
                    radius=raw.get("radius",raw.get("r"))
                    if center is not None and point is not None and radius is not None: add("distance",[self._name(center),self._name(point)],raw,self._number(radius,"radius",True))
                    else: validation_only.append(deepcopy(dict(raw)))
                else: validation_only.append(deepcopy(dict(raw)))
            except (ConstraintNormalizationError,TypeError,ValueError) as exc: errors.append(f"Constraint #{i} ({typ}): {exc}")

        controls=coordinate_control or {}; hard={}; sources={}
        for name, point in coords.items():
            ctl=controls.get(name,{})
            if not isinstance(ctl,Mapping): ctl={}
            source=str(ctl.get("origin_source",ctl.get("source",""))).lower()
            if source=="user" or ctl.get("fixed") is True or ctl.get("editable") is False:
                hard[name]=list(point); sources[name]=source or "fixed"
        return {"success":not errors,"dimension":dim,"coordinates":coords,"constraints":solver,
                "validation_only_constraints":validation_only,"hard_anchors":hard,"anchor_sources":sources,"errors":errors,"tolerance":self.tolerance}

    def add_minimal_anchors(self, normalized: Dict[str, Any]) -> Dict[str, Any]:
        out=deepcopy(normalized); coords=out.get("coordinates",{}); dim=out.get("dimension",2); gauge={}; names=list(coords)
        if names and not out.get("hard_anchors"):
            gauge[names[0]]=list(coords[names[0]])
            if len(names)>=2: gauge[names[1]]=[coords[names[1]][1]] if dim==2 else [coords[names[1]][1],coords[names[1]][2]]
            if dim==3 and len(names)>=3: gauge[names[2]]=[coords[names[2]][2]]
        out["gauge_anchors"]=gauge
        return out

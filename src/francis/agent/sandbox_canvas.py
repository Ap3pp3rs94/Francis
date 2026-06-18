from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from datetime import UTC, datetime
from html import escape
from pathlib import Path
from typing import Any

from francis.kernel.paths import data_dir

CANVAS_KIND = "francis.sandbox_canvas.mona_lisa"
DEFAULT_CANVAS_SIZE = 512
MIN_CANVAS_SIZE = 128
MAX_CANVAS_SIZE = 2048
RECOGNIZABILITY_FIXTURE_PATH = Path(__file__).with_name("mona_lisa_recognizability_fixture.json")
_PATH_POINT_RE = re.compile(r"(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)")
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$")


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:
        return ""


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = _safe_str(value).lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _safe_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except Exception:
        return default


def _bounded_canvas_size(value: Any, default: int = DEFAULT_CANVAS_SIZE) -> int:
    size = _safe_int(value, default)
    return max(MIN_CANVAS_SIZE, min(MAX_CANVAS_SIZE, size))


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _input_meta(inputs: dict[str, Any]) -> dict[str, Any]:
    return _dict(inputs.get("meta"))


def _mission_meta(inputs: dict[str, Any]) -> dict[str, Any]:
    direct = _dict(inputs.get("mission_meta"))
    if direct:
        return direct
    meta = _input_meta(inputs)
    nested = _dict(meta.get("mission_meta"))
    if nested:
        return nested
    constraints = _dict(inputs.get("constraints"))
    return _dict(constraints.get("mission_meta"))


def _operator_contract(inputs: dict[str, Any], mission_meta: dict[str, Any]) -> dict[str, Any]:
    contract = _dict(inputs.get("operator_contract"))
    if contract:
        return contract
    contract = _dict(mission_meta.get("operator_contract"))
    if contract:
        return contract
    return _dict(_input_meta(inputs).get("operator_contract"))


def _lens_overlay_observation(inputs: dict[str, Any], mission_meta: dict[str, Any]) -> dict[str, Any]:
    observation = _dict(inputs.get("lens_overlay_observation"))
    if observation:
        return observation
    observation = _dict(mission_meta.get("lens_overlay_observation"))
    if observation:
        return observation
    return _dict(_input_meta(inputs).get("lens_overlay_observation"))


def _structured_observation_receipt(
    *,
    receipt_id: str,
    trace_id: str,
    run_id: str,
    mission_id: str,
    requested_region: dict[str, Any],
    mapped_region: dict[str, Any],
    actual_region: dict[str, Any],
    manifest_path: Path,
    manifest_hash: str,
    action_path: Path,
    action_hash: str,
    svg_path: Path,
    svg_hash: str,
    primitive_count: int,
    dry_run: bool,
) -> dict[str, Any]:
    status = "planned" if dry_run else "observed"
    return {
        "kind": "francis.lens.overlay.structured_observation_receipt",
        "schema_version": 1,
        "receipt_id": receipt_id,
        "trace_id": trace_id,
        "run_id": run_id,
        "mission_id": mission_id,
        "decision": "observed",
        "status": status,
        "requested_region": requested_region,
        "mapped_overlay_region": mapped_region,
        "actual_inspected_region": actual_region,
        "source": {
            "name": "sandbox_canvas_coordinate_model",
            "status": "sandbox_model_used",
            "mode": "sandbox_replayable_artifact",
            "live_simulated_fixture_or_replay": "sandbox",
            "read_only": True,
        },
        "evidence_reference": {
            "status": "sandbox_artifact_manifest",
            "manifest_ref": str(manifest_path),
            "manifest_hash": manifest_hash,
            "actions_ref": str(action_path),
            "actions_hash": action_hash,
            "artifact_ref": str(svg_path) if svg_hash else "",
            "artifact_hash": svg_hash,
            "content_included": False,
        },
        "inferred_information": {
            "canvas_bounds": actual_region,
            "primitive_count": primitive_count,
            "artifact_created": not dry_run,
            "live_desktop_action": False,
            "image_imported": False,
        },
        "confidence": 1.0 if not dry_run else 0.8,
        "unknowns": [
            "desktop_pixels",
            "external_app_canvas_bounds",
            "accessibility_tree",
            "ocr_text",
            "visual_similarity_to_external_screenshot",
        ],
        "failure_or_refusal_reason": "",
        "governance": {
            "read_only": True,
            "sandbox_only": True,
            "desktop_control": False,
            "screenshots": False,
            "pixels": False,
            "ocr": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }


def _canvas_dimensions(inputs: dict[str, Any]) -> tuple[int, int]:
    canvas = _dict(inputs.get("canvas"))
    width = _bounded_canvas_size(canvas.get("width") or inputs.get("width"))
    height = _bounded_canvas_size(canvas.get("height") or inputs.get("height"))
    return width, height


def _scale_path(path: str, *, sx: float, sy: float) -> str:
    parts: list[str] = []
    for token in path.split():
        if "," not in token:
            parts.append(token)
            continue
        x_text, y_text = token.split(",", 1)
        try:
            x = float(x_text) * sx
            y = float(y_text) * sy
        except ValueError:
            parts.append(token)
            continue
        parts.append(f"{x:.2f},{y:.2f}")
    return " ".join(parts)


def _scale_primitive(primitive: dict[str, Any], *, width: int, height: int) -> dict[str, Any]:
    sx = width / DEFAULT_CANVAS_SIZE
    sy = height / DEFAULT_CANVAS_SIZE
    out = dict(primitive)
    for key in ("x", "cx", "rx", "width", "stroke_width"):
        if key in out:
            out[key] = round(float(out[key]) * sx, 2)
    for key in ("y", "cy", "ry", "height"):
        if key in out:
            out[key] = round(float(out[key]) * sy, 2)
    if "path" in out:
        out["path"] = _scale_path(_safe_str(out["path"]), sx=sx, sy=sy)
    return out


def _primitive_catalog() -> list[dict[str, Any]]:
    return [
        {
            "action": "fill_rect",
            "label": "warm muted background",
            "x": 0,
            "y": 0,
            "width": 512,
            "height": 512,
            "fill": "#786f57",
            "opacity": 1.0,
        },
        {
            "action": "fill_path",
            "label": "dark landscape wedge",
            "path": "M 0,190 C 120,145 235,168 512,126 L 512,512 L 0,512 Z",
            "fill": "#2f3b34",
            "opacity": 0.56,
        },
        {
            "action": "fill_path",
            "label": "distant ochre valley",
            "path": "M 0,225 C 160,190 330,225 512,178 L 512,315 C 370,282 165,300 0,278 Z",
            "fill": "#a99162",
            "opacity": 0.48,
        },
        {
            "action": "fill_ellipse",
            "label": "hair mass left",
            "cx": 232,
            "cy": 176,
            "rx": 82,
            "ry": 112,
            "fill": "#241b17",
            "opacity": 0.96,
        },
        {
            "action": "fill_ellipse",
            "label": "hair mass right",
            "cx": 286,
            "cy": 178,
            "rx": 84,
            "ry": 118,
            "fill": "#261d18",
            "opacity": 0.96,
        },
        {
            "action": "fill_ellipse",
            "label": "face oval",
            "cx": 258,
            "cy": 170,
            "rx": 58,
            "ry": 78,
            "fill": "#cbb18c",
            "opacity": 1.0,
        },
        {
            "action": "fill_ellipse",
            "label": "left cheek tone",
            "cx": 237,
            "cy": 178,
            "rx": 22,
            "ry": 28,
            "fill": "#d5bd96",
            "opacity": 0.42,
        },
        {
            "action": "fill_ellipse",
            "label": "right cheek tone",
            "cx": 279,
            "cy": 178,
            "rx": 22,
            "ry": 28,
            "fill": "#b99676",
            "opacity": 0.36,
        },
        {
            "action": "stroke_path",
            "label": "brow and nose line",
            "path": "M 228,150 C 245,144 270,145 292,151 M 262,154 C 256,178 253,190 259,207",
            "stroke": "#5c4435",
            "stroke_width": 4,
            "opacity": 0.56,
        },
        {
            "action": "stroke_path",
            "label": "soft eyes",
            "path": "M 225,166 C 236,160 246,162 253,168 M 269,168 C 279,162 290,162 299,168",
            "stroke": "#312822",
            "stroke_width": 3,
            "opacity": 0.78,
        },
        {
            "action": "stroke_path",
            "label": "small smile",
            "path": "M 236,215 C 252,225 274,225 290,214",
            "stroke": "#5c342d",
            "stroke_width": 4,
            "opacity": 0.72,
        },
        {
            "action": "fill_path",
            "label": "neck shadow",
            "path": "M 232,239 C 250,258 275,258 292,238 L 304,305 L 220,305 Z",
            "fill": "#8c6f55",
            "opacity": 0.86,
        },
        {
            "action": "fill_path",
            "label": "dark dress body",
            "path": "M 152,510 C 165,348 203,282 250,268 C 300,282 348,352 368,510 Z",
            "fill": "#1f221c",
            "opacity": 1.0,
        },
        {
            "action": "fill_path",
            "label": "left sleeve",
            "path": "M 120,510 C 134,390 174,310 226,290 C 211,354 201,430 204,510 Z",
            "fill": "#2c2b22",
            "opacity": 0.98,
        },
        {
            "action": "fill_path",
            "label": "right sleeve",
            "path": "M 390,510 C 372,390 335,312 288,290 C 305,360 313,432 309,510 Z",
            "fill": "#2a2a22",
            "opacity": 0.98,
        },
        {
            "action": "stroke_path",
            "label": "folded hands upper",
            "path": "M 166,386 C 211,367 266,373 310,395 C 274,405 217,407 166,386",
            "stroke": "#c5a27c",
            "stroke_width": 16,
            "opacity": 0.9,
        },
        {
            "action": "stroke_path",
            "label": "folded hands lower",
            "path": "M 190,421 C 236,405 291,411 334,433 C 297,443 237,444 190,421",
            "stroke": "#b8916d",
            "stroke_width": 15,
            "opacity": 0.82,
        },
        {
            "action": "stroke_path",
            "label": "veil edge",
            "path": "M 196,91 C 162,146 167,225 210,280 M 319,92 C 355,148 351,232 304,285",
            "stroke": "#141312",
            "stroke_width": 5,
            "opacity": 0.6,
        },
        {
            "action": "stroke_path",
            "label": "dress neckline",
            "path": "M 205,300 C 237,326 278,329 312,302",
            "stroke": "#95805d",
            "stroke_width": 5,
            "opacity": 0.58,
        },
        {
            "action": "stroke_path",
            "label": "atmospheric contour pass",
            "path": "M 188,113 C 204,74 295,70 324,118 C 363,189 337,266 300,303 C 264,326 220,315 196,282 C 161,232 160,170 188,113",
            "stroke": "#e1d4bd",
            "stroke_width": 2,
            "opacity": 0.24,
        },
    ]


def _mona_lisa_primitives(width: int, height: int) -> list[dict[str, Any]]:
    return [
        {"seq": index + 1, **_scale_primitive(primitive, width=width, height=height)}
        for index, primitive in enumerate(_primitive_catalog())
    ]


def _primitive_svg(primitive: dict[str, Any]) -> str:
    action = _safe_str(primitive.get("action"))
    opacity = float(primitive.get("opacity", 1.0) or 1.0)
    if action == "fill_rect":
        return (
            f'<rect x="{primitive["x"]}" y="{primitive["y"]}" width="{primitive["width"]}" '
            f'height="{primitive["height"]}" fill="{escape(_safe_str(primitive.get("fill")))}" '
            f'opacity="{opacity:.3f}" />'
        )
    if action == "fill_ellipse":
        return (
            f'<ellipse cx="{primitive["cx"]}" cy="{primitive["cy"]}" rx="{primitive["rx"]}" '
            f'ry="{primitive["ry"]}" fill="{escape(_safe_str(primitive.get("fill")))}" '
            f'opacity="{opacity:.3f}" />'
        )
    if action == "fill_path":
        return (
            f'<path d="{escape(_safe_str(primitive.get("path")))}" '
            f'fill="{escape(_safe_str(primitive.get("fill")))}" opacity="{opacity:.3f}" />'
        )
    if action == "stroke_path":
        return (
            f'<path d="{escape(_safe_str(primitive.get("path")))}" fill="none" '
            f'stroke="{escape(_safe_str(primitive.get("stroke")))}" '
            f'stroke-width="{primitive["stroke_width"]}" stroke-linecap="round" '
            f'stroke-linejoin="round" opacity="{opacity:.3f}" />'
        )
    return ""


def _svg_document(primitives: list[dict[str, Any]], *, width: int, height: int) -> str:
    body = "\n  ".join(line for primitive in primitives if (line := _primitive_svg(primitive)))
    return "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
                f'viewBox="0 0 {width} {height}" role="img" '
                'aria-label="Sandbox primitive Mona Lisa painting">'
            ),
            f"  {body}",
            "</svg>",
            "",
        ]
    )


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".tmp_{uuid.uuid4().hex[:12]}.json"
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, default=str), encoding="utf-8")
    tmp.replace(path)


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".tmp_{uuid.uuid4().hex[:12]}.jsonl"
    tmp.write_text(
        "\n".join(json.dumps(row, sort_keys=True, ensure_ascii=True, default=str) for row in rows), encoding="utf-8"
    )
    tmp.replace(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except Exception:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def _sandbox_root() -> Path:
    return (data_dir() / "sandbox_canvas" / "mona_lisa").resolve()


def _safe_run_segment(value: Any) -> str:
    text = _safe_str(value)
    if not text or "/" in text or "\\" in text:
        return ""
    return text if _RUN_ID_RE.fullmatch(text) else ""


def _trusted_artifact_dir(path: Path, root: Path) -> Path | None:
    try:
        resolved = path.resolve()
        resolved.relative_to(root)
    except Exception:
        return None
    return resolved if resolved.is_dir() else None


def _artifact_dir_candidates(root: Path) -> list[Path]:
    if not root.exists():
        return []
    candidates: list[Path] = []
    for path in root.iterdir():
        artifact_dir = _trusted_artifact_dir(path, root)
        if artifact_dir is None:
            continue
        if (
            (artifact_dir / "receipt.json").exists()
            or (artifact_dir / "manifest.json").exists()
            or (artifact_dir / "operator_actions.jsonl").exists()
        ):
            candidates.append(artifact_dir)
    return candidates


def _matches_artifact_selector(candidate: Path, selector: str, root: Path) -> bool:
    text = _safe_str(selector).rstrip("/\\")
    if not text:
        return False
    normalized_text = text.replace("\\", "/")
    options = {candidate.name, str(candidate), str(candidate).replace("\\", "/")}
    try:
        relative_to_root = candidate.relative_to(root)
        options.add(str(relative_to_root))
        options.add(str(relative_to_root).replace("\\", "/"))
    except Exception:
        pass
    try:
        relative_to_data = candidate.relative_to(data_dir().resolve())
        options.add(str(relative_to_data))
        options.add(str(relative_to_data).replace("\\", "/"))
    except Exception:
        pass
    return normalized_text in options or text in options


def _resolve_artifact_dir(value: str | None = None, *, run_id: str | None = None) -> Path | None:
    root = _sandbox_root()
    candidate_text = _safe_str(value)
    run_text = _safe_str(run_id)
    if run_text:
        run_segment = _safe_run_segment(run_text)
        if not run_segment:
            return None
        for candidate in _artifact_dir_candidates(root):
            if candidate.name == run_segment:
                return candidate
        return None
    elif candidate_text:
        for candidate in _artifact_dir_candidates(root):
            if _matches_artifact_selector(candidate, candidate_text, root):
                return candidate
        return None
    else:
        candidates = _artifact_dir_candidates(root)
        if not candidates:
            return None
        return max(candidates, key=lambda path: path.stat().st_mtime)


def _safe_segment(value: Any, fallback: str) -> str:
    text = _safe_str(value)
    segment = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in text).strip("._-")
    return (segment[:96] or fallback).strip("._-") or fallback


def _record_hash(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _read_json_records(directory_name: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for artifact_dir in _artifact_dir_candidates(_sandbox_root()):
        directory = artifact_dir / directory_name
        if not directory.exists():
            continue
        for path in directory.glob("*.json"):
            row = _read_json(path)
            if row:
                row.setdefault("record_path", str(path))
                rows.append(row)
    rows.sort(key=lambda item: (_safe_str(item.get("created_at")), _safe_str(item.get("record_path"))), reverse=True)
    return rows


def _hash_match(path: Path, expected_hash: Any) -> dict[str, Any]:
    expected = _safe_str(expected_hash)
    if not path.exists():
        return {"path": str(path), "exists": False, "sha256": "", "expected_sha256": expected, "matches": False}
    actual = _sha256(path)
    return {
        "path": str(path),
        "exists": True,
        "sha256": actual,
        "expected_sha256": expected,
        "matches": bool(expected and actual == expected),
    }


def _primitive_labels(actions: list[dict[str, Any]]) -> set[str]:
    return {_safe_str(row.get("label")).lower() for row in actions}


def _keyword_match(label: str, keywords: list[Any]) -> bool:
    return any(_safe_str(keyword).lower() in label for keyword in keywords)


def _primitive_center(primitive: dict[str, Any]) -> tuple[float, float] | None:
    cx = primitive.get("cx")
    cy = primitive.get("cy")
    if cx is not None and cy is not None:
        try:
            return float(cx), float(cy)
        except (TypeError, ValueError):
            return None

    x = primitive.get("x")
    y = primitive.get("y")
    width = primitive.get("width")
    height = primitive.get("height")
    if x is not None and y is not None and width is not None and height is not None:
        try:
            return float(x) + (float(width) / 2.0), float(y) + (float(height) / 2.0)
        except (TypeError, ValueError):
            return None

    points: list[tuple[float, float]] = []
    for match in _PATH_POINT_RE.finditer(_safe_str(primitive.get("path"))):
        try:
            points.append((float(match.group(1)), float(match.group(2))))
        except ValueError:
            continue
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return (min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0


def _inside_zone(center: tuple[float, float] | None, zone: dict[str, Any]) -> bool:
    if center is None:
        return False
    x, y = center
    return float(zone.get("x_min", 0)) <= x <= float(zone.get("x_max", 0)) and float(
        zone.get("y_min", 0)
    ) <= y <= float(zone.get("y_max", 0))


def _offline_fixture_evidence(actions: list[dict[str, Any]]) -> dict[str, Any]:
    fixture_path = RECOGNIZABILITY_FIXTURE_PATH
    fixture = _read_json(fixture_path)
    if not fixture:
        return {
            "status": "fixture_unavailable",
            "fixture_ref": str(fixture_path),
            "score": 0.0,
            "passed": False,
            "pixel_evidence": False,
            "visual_similarity_claim": False,
            "reference_image_used": False,
            "limitations": ["Offline fixture file was not available; no fixture evidence was claimed."],
        }

    feature_keywords = _dict(fixture.get("feature_keywords"))
    labels = _primitive_labels(actions)
    feature_matches = {
        feature: any(_keyword_match(label, list(keywords or [])) for label in labels)
        for feature, keywords in feature_keywords.items()
    }
    feature_count = sum(1 for value in feature_matches.values() if value)
    required_feature_count = max(1, _safe_int(fixture.get("required_feature_count"), 1))

    zone_results: list[dict[str, Any]] = []
    for zone in fixture.get("geometry_zones") or []:
        if not isinstance(zone, dict):
            continue
        keywords = list(zone.get("keywords") or [])
        matched_labels: list[str] = []
        for primitive in actions:
            label = _safe_str(primitive.get("label")).lower()
            if not _keyword_match(label, keywords):
                continue
            if _inside_zone(_primitive_center(primitive), zone):
                matched_labels.append(label)
        zone_results.append(
            {
                "id": _safe_str(zone.get("id")),
                "matched": bool(matched_labels),
                "matched_labels": sorted(set(matched_labels)),
            }
        )
    zone_count = sum(1 for item in zone_results if item["matched"])
    required_zone_count = max(1, _safe_int(fixture.get("required_zone_count"), 1))

    feature_component = min(1.0, feature_count / required_feature_count)
    zone_component = min(1.0, zone_count / required_zone_count)
    primitive_component = min(1.0, len(actions) / 20.0)
    score = round((feature_component * 0.45) + (zone_component * 0.45) + (primitive_component * 0.10), 3)
    minimum_score = float(fixture.get("minimum_score") or 0.0)
    passed = score >= minimum_score and feature_count >= required_feature_count and zone_count >= required_zone_count

    return {
        "status": "evaluated",
        "fixture_ref": str(fixture_path),
        "fixture_hash": _sha256(fixture_path),
        "fixture_kind": _safe_str(fixture.get("kind")),
        "source": _safe_str(fixture.get("source")),
        "target": _safe_str(fixture.get("target")),
        "evidence_mode": _safe_str(fixture.get("evidence_mode")),
        "score": score,
        "minimum_score": minimum_score,
        "passed": passed,
        "feature_count": feature_count,
        "required_feature_count": required_feature_count,
        "feature_matches": feature_matches,
        "zone_count": zone_count,
        "required_zone_count": required_zone_count,
        "zone_matches": zone_results,
        "pixel_evidence": bool(fixture.get("pixel_evidence")) is True,
        "visual_similarity_claim": bool(fixture.get("visual_similarity_claim")) is True,
        "reference_image_used": bool(fixture.get("reference_image_used")) is True,
        "limitations": [
            "Offline fixture evaluates SVG/operator geometry and labels only.",
            "No screenshot, pixel, OCR, accessibility, or human visual-similarity evidence was used.",
        ],
    }


def _recognizability_evidence(actions: list[dict[str, Any]], svg_text: str) -> dict[str, Any]:
    labels = _primitive_labels(actions)
    features = {
        "background": any("background" in label or "landscape" in label or "valley" in label for label in labels),
        "hair": any("hair" in label for label in labels),
        "face": any("face" in label or "cheek" in label for label in labels),
        "eyes": any("eye" in label or "brow" in label for label in labels),
        "smile": any("smile" in label for label in labels),
        "dress": any("dress" in label or "sleeve" in label for label in labels),
        "hands": any("hand" in label for label in labels),
        "contour": any("contour" in label or "veil" in label or "neckline" in label for label in labels),
    }
    feature_count = sum(1 for value in features.values() if value)
    primitive_count = len(actions)
    svg_shape_count = svg_text.count("<path") + svg_text.count("<ellipse") + svg_text.count("<rect")
    primitive_component = min(1.0, primitive_count / 20.0)
    feature_component = feature_count / max(1, len(features))
    svg_component = min(1.0, svg_shape_count / 20.0)
    primitive_score = round((feature_component * 0.55) + (primitive_component * 0.30) + (svg_component * 0.15), 3)
    offline_fixture = _offline_fixture_evidence(actions)
    fixture_score = float(offline_fixture.get("score") or 0.0)
    score = (
        round((primitive_score * 0.55) + (fixture_score * 0.45), 3)
        if offline_fixture.get("status") == "evaluated"
        else primitive_score
    )
    fixture_passed = bool(offline_fixture.get("passed"))
    return {
        "score": score,
        "basis": "operator_primitive_replay_plus_offline_svg_geometry_fixture_not_pixel_similarity",
        "primitive_replay_score": primitive_score,
        "offline_fixture_evidence": offline_fixture,
        "feature_count": feature_count,
        "expected_feature_count": len(features),
        "features": features,
        "primitive_count": primitive_count,
        "svg_shape_count": svg_shape_count,
        "recognizable_lower_complexity_target": (
            score >= 0.72 and feature_count >= 6 and primitive_count >= 12 and fixture_passed
        ),
        "limitations": [
            "No live screenshot, pixel, OCR, accessibility, or external visual similarity evidence was used.",
            "Score blends deterministic primitive replay with an offline SVG geometry fixture.",
            "This is not proof of human recognizability.",
        ],
    }


def _improvement_proposals(evaluation: dict[str, Any]) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    recognizability = _dict(evaluation.get("recognizability"))
    if float(recognizability.get("score") or 0.0) < 0.85:
        proposals.append(
            {
                "proposal_id": "sandbox_canvas_refine_mona_lisa_primitives",
                "kind": "bounded_improvement_proposal",
                "status": "proposed_not_promoted",
                "summary": "Add a second primitive refinement pass for facial proportions, hands, and tonal transitions.",
                "requires_validation": [
                    "primitive replay evaluation does not regress",
                    "visual lock tests remain unchanged",
                    "no image import or paste action appears",
                ],
            }
        )
    offline_fixture = _dict(recognizability.get("offline_fixture_evidence"))
    if not bool(offline_fixture.get("passed")):
        proposals.append(
            {
                "proposal_id": "sandbox_canvas_repair_offline_recognizability_fixture",
                "kind": "bounded_improvement_proposal",
                "status": "proposed_not_promoted",
                "summary": "Repair or extend the offline SVG geometry fixture so sandbox output has labeled evidence.",
                "requires_validation": [
                    "fixture source is safe and recorded",
                    "evaluation labels fixture/replay status explicitly",
                    "no live desktop perception claim is introduced",
                ],
            }
        )
    proposals.append(
        {
            "proposal_id": "sandbox_canvas_add_pixel_or_multi_run_review",
            "kind": "bounded_improvement_proposal",
            "status": "proposed_not_promoted",
            "summary": "Add optional truth-labeled pixel evidence or multi-run failure scoring for sandbox output.",
            "requires_validation": [
                "pixel evidence is labeled fixture, replay, sandbox, or live",
                "visual similarity is not claimed unless a real pixel path returns evidence",
                "proposal promotion remains separate and approval-gated",
            ],
        }
    )
    return proposals


def evaluate_mona_lisa_sandbox_artifact(
    *,
    artifact_dir: str | None = None,
    run_id: str | None = None,
    operation_id: str | None = None,
) -> dict[str, Any]:
    resolved_dir = _resolve_artifact_dir(artifact_dir, run_id=run_id)
    if resolved_dir is None:
        return {
            "kind": f"{CANVAS_KIND}.evaluation",
            "ok": False,
            "status": "blocked",
            "error": "sandbox_artifact_dir_not_found_or_out_of_bounds",
            "operation_id": _safe_str(operation_id),
            "run_id": _safe_str(run_id),
            "artifact_dir": _safe_str(artifact_dir),
            "governance": {
                "read_only": True,
                "writes_files": False,
                "runs_operation": False,
                "desktop_control": False,
                "visual_similarity_claim": False,
            },
        }

    actions_path = resolved_dir / "operator_actions.jsonl"
    manifest_path = resolved_dir / "manifest.json"
    receipt_path = resolved_dir / "receipt.json"
    svg_path = resolved_dir / "mona_lisa_sandbox.svg"

    actions = _read_jsonl(actions_path)
    manifest = _read_json(manifest_path)
    receipt = _read_json(receipt_path)
    svg_text = svg_path.read_text(encoding="utf-8", errors="replace") if svg_path.exists() else ""

    primitive_count = len(actions)
    receipt_count = _safe_int(receipt.get("operator_primitives_count"), 0)
    manifest_count = _safe_int(manifest.get("operator_primitives_count"), 0)
    seq_values = [_safe_int(row.get("seq"), -1) for row in actions]
    expected_seq = list(range(1, primitive_count + 1))
    action_kinds = {_safe_str(row.get("kind")) for row in actions}
    action_types = sorted({_safe_str(row.get("action")) for row in actions if _safe_str(row.get("action"))})
    live_desktop_flags = [row.get("live_desktop_action") for row in actions]
    structured_observation_receipts = [
        item for item in receipt.get("structured_observation_receipts") or [] if isinstance(item, dict)
    ]
    if not structured_observation_receipts:
        nested_observation = _dict(_dict(receipt.get("lens_overlay_observation")).get("structured_observation_receipt"))
        if nested_observation:
            structured_observation_receipts.append(nested_observation)
    first_observation = structured_observation_receipts[0] if structured_observation_receipts else {}
    observation_evidence = _dict(first_observation.get("evidence_reference"))
    no_image_import = "<image" not in svg_text.lower()
    created_through_primitives = (
        primitive_count > 0
        and seq_values == expected_seq
        and action_kinds == {"sandbox.canvas.operator_primitive"}
        and all(value is False for value in live_desktop_flags)
        and no_image_import
    )

    artifact_hash = _hash_match(svg_path, receipt.get("artifact_hash") or manifest.get("artifact_hash"))
    actions_hash = _hash_match(actions_path, receipt.get("actions_hash"))
    manifest_hash = _hash_match(manifest_path, receipt.get("manifest_hash"))
    recognizability = _recognizability_evidence(actions, svg_text)
    offline_fixture = _dict(recognizability.get("offline_fixture_evidence"))
    checks = {
        "artifact_dir_within_sandbox_root": True,
        "actions_exist": actions_path.exists(),
        "manifest_exists": manifest_path.exists(),
        "receipt_exists": receipt_path.exists(),
        "svg_exists": svg_path.exists(),
        "primitive_count_matches_receipt": primitive_count == receipt_count and primitive_count > 0,
        "primitive_count_matches_manifest": primitive_count == manifest_count and primitive_count > 0,
        "primitive_sequence_contiguous": seq_values == expected_seq,
        "all_rows_are_operator_primitives": action_kinds == {"sandbox.canvas.operator_primitive"},
        "no_live_desktop_actions": all(value is False for value in live_desktop_flags),
        "svg_has_no_image_import": no_image_import,
        "artifact_hash_matches_receipt": bool(artifact_hash["matches"]),
        "actions_hash_matches_receipt": bool(actions_hash["matches"]),
        "manifest_hash_matches_receipt": bool(manifest_hash["matches"]),
        "structured_observation_receipt_present": bool(structured_observation_receipts),
        "structured_observation_evidence_references_manifest": _safe_str(observation_evidence.get("manifest_ref"))
        == str(manifest_path),
        "structured_observation_unknowns_live_desktop_pixels": "desktop_pixels"
        in list(first_observation.get("unknowns") or []),
        "recognizability_offline_fixture_evidence_present": offline_fixture.get("status") == "evaluated",
        "recognizability_offline_fixture_no_pixel_claim": bool(offline_fixture.get("pixel_evidence")) is False,
        "recognizability_offline_fixture_no_visual_similarity_claim": bool(
            offline_fixture.get("visual_similarity_claim")
        )
        is False,
    }
    passed = all(checks.values()) and bool(recognizability["recognizable_lower_complexity_target"])
    evaluation = {
        "kind": f"{CANVAS_KIND}.evaluation",
        "ok": True,
        "status": "evaluated",
        "evaluation_mode": "read_only_replay",
        "operation_id": _safe_str(operation_id),
        "run_id": _safe_str(receipt.get("run_id") or manifest.get("run_id") or run_id),
        "trace_id": _safe_str(receipt.get("trace_id") or manifest.get("trace_id")),
        "mission_id": _safe_str(receipt.get("mission_id")),
        "artifact_dir": str(resolved_dir),
        "artifact_paths": {
            "actions": str(actions_path),
            "manifest": str(manifest_path),
            "receipt": str(receipt_path),
            "svg": str(svg_path),
        },
        "checks": checks,
        "passed": passed,
        "created_through_operator_primitives": created_through_primitives,
        "operator_primitives_count": primitive_count,
        "action_types": action_types,
        "hashes": {
            "artifact": artifact_hash,
            "actions": actions_hash,
            "manifest": manifest_hash,
        },
        "recognizability": recognizability,
        "structured_observation_receipts": structured_observation_receipts,
        "failure_classification": []
        if passed
        else [key for key, value in checks.items() if not value]
        + (
            ["recognizability_threshold_not_met"] if not recognizability["recognizable_lower_complexity_target"] else []
        ),
        "improvement_proposals": [],
        "governance": {
            "read_only": True,
            "writes_files": False,
            "writes_receipts": False,
            "runs_operation": False,
            "desktop_control": False,
            "clipboard_paste": False,
            "imports_finished_image": False,
            "approves_proposals": False,
            "promotes_changes": False,
            "visual_similarity_claim": False,
            "live_desktop_perception_claim": False,
        },
        "limitations": [
            "Evaluation replays local sandbox artifacts only.",
            "No live desktop window, screenshot, pixel, OCR, or accessibility evidence was captured.",
            "Improvement proposals are read-only suggestions and are not promoted automatically.",
        ],
    }
    evaluation["improvement_proposals"] = _improvement_proposals(evaluation)
    return evaluation


def record_mona_lisa_sandbox_evaluation(
    *,
    artifact_dir: str | None = None,
    run_id: str | None = None,
    operation_id: str | None = None,
    actor: str | None = None,
    reason: str | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evaluation = evaluate_mona_lisa_sandbox_artifact(
        artifact_dir=artifact_dir,
        run_id=run_id,
        operation_id=operation_id,
    )
    if not evaluation.get("ok"):
        return {
            "kind": f"{CANVAS_KIND}.evaluation_record",
            "ok": False,
            "status": "blocked",
            "error": evaluation.get("error") or "evaluation_not_recordable",
            "evaluation": evaluation,
            "governance": {
                "writes_files": False,
                "writes_evaluation_record": False,
                "writes_queue_item": False,
                "writes_proposal_records": False,
                "runs_operation": False,
                "desktop_control": False,
                "approves_proposals": False,
                "promotes_changes": False,
            },
        }

    resolved_dir = _resolve_artifact_dir(_safe_str(evaluation.get("artifact_dir")))
    if resolved_dir is None:
        return {
            "kind": f"{CANVAS_KIND}.evaluation_record",
            "ok": False,
            "status": "blocked",
            "error": "evaluation_artifact_dir_not_found_or_out_of_bounds",
            "evaluation": evaluation,
            "governance": {
                "writes_files": False,
                "writes_evaluation_record": False,
                "writes_queue_item": False,
                "writes_proposal_records": False,
                "runs_operation": False,
                "desktop_control": False,
                "approves_proposals": False,
                "promotes_changes": False,
            },
        }

    now = _now_iso()
    run_segment = _safe_segment(evaluation.get("run_id"), "run")
    correlation_seed = {
        "artifact_dir": evaluation.get("artifact_dir"),
        "operation_id": evaluation.get("operation_id"),
        "run_id": evaluation.get("run_id"),
        "trace_id": evaluation.get("trace_id"),
    }
    fingerprint = _record_hash(correlation_seed)[:12]
    evaluation_id = f"eval_{run_segment}_{fingerprint}"
    queue_item_id = f"queue_{run_segment}_{fingerprint}"

    failure_classification = list(evaluation.get("failure_classification") or [])
    proposal_inputs = [item for item in evaluation.get("improvement_proposals") or [] if isinstance(item, dict)]
    queue_status = "queued_for_review" if failure_classification or proposal_inputs else "recorded_no_followup_needed"

    record_dir = resolved_dir / "evaluation_records"
    queue_dir = resolved_dir / "review_queue"
    proposal_dir = resolved_dir / "improvement_proposals"
    evaluation_path = record_dir / f"{evaluation_id}.json"
    queue_path = queue_dir / f"{queue_item_id}.json"

    queue_item = {
        "kind": f"{CANVAS_KIND}.evaluation_queue_item",
        "queue": "sandbox_canvas.mona_lisa.evaluation_review",
        "queue_item_id": queue_item_id,
        "evaluation_id": evaluation_id,
        "status": queue_status,
        "created_at": now,
        "actor": _safe_str(actor),
        "reason": _safe_str(reason) or "record_sandbox_canvas_evaluation",
        "operation_id": evaluation.get("operation_id"),
        "mission_id": evaluation.get("mission_id"),
        "trace_id": evaluation.get("trace_id"),
        "run_id": evaluation.get("run_id"),
        "artifact_dir": evaluation.get("artifact_dir"),
        "evaluation_record_path": str(evaluation_path),
        "passed": bool(evaluation.get("passed")),
        "failure_classification": failure_classification,
        "improvement_proposal_count": len(proposal_inputs),
        "next_recommended_action": "review_bounded_improvement_proposals"
        if proposal_inputs
        else "retain_record_as_passed_replay_evidence",
        "acceptance_criteria": [
            "replay evaluation stays read-only",
            "proposal promotion requires a separate governed approval path",
            "no live desktop perception or visual similarity claim is introduced by this record",
        ],
    }

    proposal_records: list[dict[str, Any]] = []
    proposal_paths: list[str] = []
    for index, proposal in enumerate(proposal_inputs, start=1):
        base_proposal_id = _safe_segment(proposal.get("proposal_id"), f"proposal_{index}")
        proposal_id_hash = hashlib.sha256(base_proposal_id.encode("utf-8")).hexdigest()[:8]
        proposal_record_id = f"proposal_{index}_{fingerprint}_{proposal_id_hash}"
        proposal_path = proposal_dir / f"{proposal_record_id}.json"
        proposal_record = {
            **proposal,
            "kind": f"{CANVAS_KIND}.improvement_proposal",
            "proposal_record_id": proposal_record_id,
            "source_proposal_id": proposal.get("proposal_id"),
            "status": "proposed_not_promoted",
            "created_at": now,
            "evaluation_id": evaluation_id,
            "queue_item_id": queue_item_id,
            "operation_id": evaluation.get("operation_id"),
            "mission_id": evaluation.get("mission_id"),
            "trace_id": evaluation.get("trace_id"),
            "run_id": evaluation.get("run_id"),
            "artifact_dir": evaluation.get("artifact_dir"),
            "evaluation_record_path": str(evaluation_path),
            "queue_item_path": str(queue_path),
            "promotion": {
                "approved": False,
                "promoted": False,
                "requires_governed_validation": True,
                "silent_self_promotion_allowed": False,
            },
        }
        _atomic_write_json(proposal_path, proposal_record)
        proposal_records.append(proposal_record)
        proposal_paths.append(str(proposal_path))

    _atomic_write_json(queue_path, queue_item)

    record = {
        "kind": f"{CANVAS_KIND}.evaluation_record",
        "evaluation_id": evaluation_id,
        "status": "recorded",
        "created_at": now,
        "actor": _safe_str(actor),
        "reason": _safe_str(reason) or "record_sandbox_canvas_evaluation",
        "meta": _dict(meta),
        "evaluation": evaluation,
        "queue_item": queue_item,
        "improvement_proposals": proposal_records,
        "paths": {
            "evaluation_record": str(evaluation_path),
            "queue_item": str(queue_path),
            "improvement_proposals": proposal_paths,
        },
        "governance": {
            "writes_files": True,
            "writes_evaluation_record": True,
            "writes_queue_item": True,
            "writes_proposal_records": bool(proposal_records),
            "writes_receipts": False,
            "runs_operation": False,
            "desktop_control": False,
            "clipboard_paste": False,
            "imports_finished_image": False,
            "approves_proposals": False,
            "promotes_changes": False,
            "visual_similarity_claim": False,
            "live_desktop_perception_claim": False,
        },
    }
    _atomic_write_json(evaluation_path, record)
    record_hash = _sha256(evaluation_path)

    return {
        "kind": f"{CANVAS_KIND}.evaluation_record.result",
        "ok": True,
        "status": "recorded",
        "evaluation_id": evaluation_id,
        "queue_item_id": queue_item_id,
        "record_hash": record_hash,
        "artifact_dir": evaluation.get("artifact_dir"),
        "operation_id": evaluation.get("operation_id"),
        "mission_id": evaluation.get("mission_id"),
        "run_id": evaluation.get("run_id"),
        "trace_id": evaluation.get("trace_id"),
        "paths": record["paths"],
        "queue_item": queue_item,
        "improvement_proposals": proposal_records,
        "governance": record["governance"],
    }


def _review_scoring(rows: list[dict[str, Any]]) -> dict[str, Any]:
    failure_counts: dict[str, int] = {}
    passed_count = 0
    failed_count = 0
    proposal_count = 0
    latest_failure_classes: list[str] = []
    for row in rows:
        if bool(row.get("passed")):
            passed_count += 1
        else:
            failed_count += 1
        proposal_count += _safe_int(row.get("improvement_proposal_count"), 0)
        classes = [_safe_str(item) for item in row.get("failure_classification") or [] if _safe_str(item)]
        if classes and not latest_failure_classes:
            latest_failure_classes = classes
        for failure_class in classes:
            failure_counts[failure_class] = failure_counts.get(failure_class, 0) + 1

    repeated = [
        {"failure_class": failure_class, "count": count}
        for failure_class, count in sorted(failure_counts.items())
        if count >= 2
    ]
    if not rows:
        classification = "no_records"
        next_action = "record_evaluations_before_review_scoring"
    elif repeated:
        classification = "repeated_failure_pattern"
        next_action = "review_repeated_failures_before_new_proposals"
    elif failed_count:
        classification = "single_run_failure_review"
        next_action = "review_latest_failure_before_repeating_run"
    elif proposal_count:
        classification = "passed_with_proposals"
        next_action = "review_bounded_improvement_proposals"
    else:
        classification = "stable_pass"
        next_action = "retain_record_as_passed_replay_evidence"

    return {
        "kind": f"{CANVAS_KIND}.evaluation_review_scoring",
        "status": "read_only",
        "classification": classification,
        "total_records": len(rows),
        "passed_count": passed_count,
        "failed_count": failed_count,
        "improvement_proposal_count": proposal_count,
        "failure_class_counts": failure_counts,
        "repeated_failure_classes": repeated,
        "latest_failure_classes": latest_failure_classes,
        "next_recommended_action": next_action,
        "thresholds": {
            "repeated_failure_min_count": 2,
            "source": "evaluation_queue_records",
        },
        "governance": {
            "read_only": True,
            "writes_files": False,
            "runs_operation": False,
            "approves_proposals": False,
            "promotes_changes": False,
        },
    }


def list_mona_lisa_sandbox_evaluation_queue(*, limit: int = 50, status: str | None = None) -> dict[str, Any]:
    bounded_limit = max(1, min(200, _safe_int(limit, 50)))
    status_filter = _safe_str(status)
    rows = _read_json_records("review_queue")
    if status_filter:
        rows = [row for row in rows if _safe_str(row.get("status")) == status_filter]
    return {
        "kind": f"{CANVAS_KIND}.evaluation_queue",
        "ok": True,
        "status": "read_only",
        "count": len(rows),
        "items": rows[:bounded_limit],
        "review_scoring": _review_scoring(rows),
        "governance": {
            "read_only": True,
            "writes_files": False,
            "runs_operation": False,
            "desktop_control": False,
            "approves_proposals": False,
            "promotes_changes": False,
        },
    }


def list_mona_lisa_sandbox_improvement_proposals(*, limit: int = 50, status: str | None = None) -> dict[str, Any]:
    bounded_limit = max(1, min(200, _safe_int(limit, 50)))
    status_filter = _safe_str(status)
    rows = _read_json_records("improvement_proposals")
    if status_filter:
        rows = [row for row in rows if _safe_str(row.get("status")) == status_filter]
    return {
        "kind": f"{CANVAS_KIND}.improvement_proposals",
        "ok": True,
        "status": "read_only",
        "count": len(rows),
        "items": rows[:bounded_limit],
        "governance": {
            "read_only": True,
            "writes_files": False,
            "runs_operation": False,
            "desktop_control": False,
            "approves_proposals": False,
            "promotes_changes": False,
        },
    }


def _new_trace_id() -> str:
    return f"trace_{uuid.uuid4().hex[:16]}"


def _new_run_id() -> str:
    return f"run_{int(time.time())}_{uuid.uuid4().hex[:8]}"


def _result_blocked(*, reason: str, objective: str, mission_meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "sandbox.canvas.paint_mona_lisa.result",
        "ok": False,
        "status": "blocked",
        "error": reason,
        "objective": objective,
        "mission_meta_present": bool(mission_meta),
        "execution_mode": "sandbox",
        "live_desktop_execution": False,
        "operator_primitives_required": True,
        "claim_completed_painting": False,
        "governance": {
            "sandbox_only": True,
            "desktop_control": False,
            "clipboard_paste": False,
            "imports_finished_image": False,
            "bounded_canvas_required": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "completion_claim_authority": False,
        },
        "verification": {
            "status": "failed",
            "hook_type": "sandbox_canvas_contract",
            "summary": reason,
            "checked": ["live desktop not allowed", "sandbox contract required"],
        },
    }


def paint_mona_lisa_sandbox(inputs: dict[str, Any], objective: str) -> dict[str, Any]:
    mission_meta = _mission_meta(inputs)
    operator_contract = _operator_contract(inputs, mission_meta)
    lens_observation = _lens_overlay_observation(inputs, mission_meta)

    requested_live_desktop = _safe_bool(inputs.get("live_desktop_execution"), default=False) or _safe_bool(
        mission_meta.get("live_desktop_execution"), default=False
    )
    if requested_live_desktop:
        return _result_blocked(
            reason="live_desktop_execution_not_supported_by_sandbox_adapter",
            objective=objective,
            mission_meta=mission_meta,
        )

    if _safe_bool(inputs.get("paste_image"), default=False) or _safe_bool(inputs.get("import_image"), default=False):
        return _result_blocked(
            reason="pasted_or_imported_finished_image_refused",
            objective=objective,
            mission_meta=mission_meta,
        )

    dry_run = _safe_bool(inputs.get("dry_run"), default=False)
    width, height = _canvas_dimensions(inputs)
    primitives = _mona_lisa_primitives(width, height)
    trace_id = _new_trace_id()
    run_id = _new_run_id()
    artifact_root = data_dir() / "sandbox_canvas" / "mona_lisa" / run_id
    artifact_root.mkdir(parents=True, exist_ok=True)

    action_path = artifact_root / "operator_actions.jsonl"
    manifest_path = artifact_root / "manifest.json"
    svg_path = artifact_root / "mona_lisa_sandbox.svg"
    receipt_path = artifact_root / "receipt.json"

    action_rows = [
        {
            **primitive,
            "kind": "sandbox.canvas.operator_primitive",
            "coordinate_space": "sandbox.logical_pixels",
            "bounded_canvas": True,
            "live_desktop_action": False,
            "source": "procedural_mona_lisa_low_complexity_pass",
        }
        for primitive in primitives
    ]
    _write_jsonl(action_path, action_rows)

    svg_written = False
    svg_hash = ""
    if not dry_run:
        svg_path.write_text(_svg_document(primitives, width=width, height=height), encoding="utf-8")
        svg_hash = _sha256(svg_path)
        svg_written = True

    action_hash = _sha256(action_path)
    requested_region = _dict(lens_observation.get("requested_region"))
    mapped_region = _dict(lens_observation.get("mapped_overlay_region"))
    actual_region = {
        "coordinate_space": "sandbox.logical_pixels",
        "x": 0,
        "y": 0,
        "width": width,
        "height": height,
    }
    manifest = {
        "kind": f"{CANVAS_KIND}.manifest",
        "status": "planned" if dry_run else "sandbox_artifact_created",
        "trace_id": trace_id,
        "run_id": run_id,
        "objective": objective,
        "canvas": actual_region,
        "operator_primitives_count": len(primitives),
        "actions_path": str(action_path),
        "svg_path": str(svg_path) if svg_written else "",
        "dry_run": dry_run,
        "created_at": _now_iso(),
        "no_pasted_image": True,
        "imports_finished_image": False,
        "live_desktop_execution": False,
    }
    _atomic_write_json(manifest_path, manifest)
    manifest_hash = _sha256(manifest_path)
    receipt_id = f"sandbox_canvas_{uuid.uuid4().hex[:16]}"
    mission_id = _safe_str(inputs.get("mission_id") or mission_meta.get("mission_id"))
    structured_observation = _structured_observation_receipt(
        receipt_id=f"{receipt_id}.observation.1",
        trace_id=trace_id,
        run_id=run_id,
        mission_id=mission_id,
        requested_region=requested_region,
        mapped_region=mapped_region,
        actual_region=actual_region,
        manifest_path=manifest_path,
        manifest_hash=manifest_hash,
        action_path=action_path,
        action_hash=action_hash,
        svg_path=svg_path,
        svg_hash=svg_hash,
        primitive_count=len(primitives),
        dry_run=dry_run,
    )

    receipt = {
        "kind": f"{CANVAS_KIND}.receipt",
        "receipt_id": receipt_id,
        "trace_id": trace_id,
        "run_id": run_id,
        "status": "planned" if dry_run else "sandbox_completed",
        "created_at": _now_iso(),
        "execution_mode": "dry_run" if dry_run else "sandbox",
        "mission_id": mission_id,
        "mission_meta_present": bool(mission_meta),
        "intent_kind": _safe_str(mission_meta.get("intent_kind")),
        "operator_contract": {
            "target": _safe_str(operator_contract.get("target")) or "francis_owned_sandbox_canvas",
            "discrete_primitives_required": True,
            "bounded_canvas": True,
            "live_desktop_execution": False,
            "paste_or_import_finished_image": False,
        },
        "lens_overlay_observation": {
            "requested_region": requested_region,
            "mapped_overlay_region": mapped_region,
            "actual_inspected_region": actual_region,
            "observation_source": "sandbox_canvas_coordinate_model",
            "status": "sandbox_model_used",
            "live_simulated_fixture_or_replay": "sandbox",
            "evidence_artifact": str(manifest_path),
            "inferred_information": ["canvas bounds", "primitive bounds", "artifact paths"],
            "confidence": 1.0,
            "unknown_information": [
                "desktop pixels",
                "external app canvas bounds",
                "accessibility tree",
                "visual similarity to external screenshot",
            ],
            "failure_or_refusal_reason": "",
            "structured_observation_receipt": structured_observation,
        },
        "structured_observation_receipts": [structured_observation],
        "orb_embodiment": {
            "truth_source": "operation_result",
            "semantic_state": "acting" if not dry_run else "planning",
            "movement_mode": "precision" if not dry_run else "precision_pending",
            "visual_change": False,
            "visual_lock_preserved": True,
            "claims_live_desktop_action": False,
        },
        "artifact_dir": str(artifact_root),
        "artifact_path": str(svg_path) if svg_written else "",
        "actions_path": str(action_path),
        "manifest_path": str(manifest_path),
        "artifact_hash": svg_hash,
        "actions_hash": action_hash,
        "manifest_hash": manifest_hash,
        "operator_primitives_count": len(primitives),
        "created_through_operator_primitives": True,
        "recognizable_lower_complexity_target": "mona_lisa",
        "claim_completed_painting": bool(svg_written),
        "truthful_limitations": [
            "sandbox artifact only; no live desktop paint program was controlled",
            "procedural low-complexity representation; no reference image was pasted or imported",
            "desktop screenshot, pixel, OCR, and accessibility evidence were not captured by this adapter",
        ],
        "governance": {
            "sandbox_only": True,
            "desktop_control": False,
            "clipboard_paste": False,
            "imports_finished_image": False,
            "bounded_canvas": True,
            "stop_cancel_boundary": "operation_cancel_before_run_or_short_sandbox_run",
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "live_desktop_authority": False,
        },
    }
    _atomic_write_json(receipt_path, receipt)
    receipt_hash = _sha256(receipt_path)

    return {
        "kind": "sandbox.canvas.paint_mona_lisa.result",
        "ok": True,
        "status": "planned" if dry_run else "sandbox_completed",
        "objective": objective,
        "execution_mode": "dry_run" if dry_run else "sandbox",
        "trace_id": trace_id,
        "run_id": run_id,
        "artifact_dir": str(artifact_root),
        "artifact_path": str(svg_path) if svg_written else "",
        "actions_path": str(action_path),
        "manifest_path": str(manifest_path),
        "receipt_path": str(receipt_path),
        "artifact_hash": svg_hash,
        "actions_hash": action_hash,
        "manifest_hash": manifest_hash,
        "receipt_hash": receipt_hash,
        "canvas": actual_region,
        "operator_primitives_count": len(primitives),
        "created_through_operator_primitives": True,
        "structured_observation_receipts": [structured_observation],
        "no_pasted_image": True,
        "imports_finished_image": False,
        "live_desktop_execution": False,
        "sandbox": {
            "trace_id": trace_id,
            "run_id": run_id,
            "artifact_dir": str(artifact_root),
            "artifact_path": str(svg_path) if svg_written else "",
            "execution_mode": "dry_run" if dry_run else "sandbox",
            "operator_primitives_count": len(primitives),
        },
        "receipt": receipt,
        "verification": {
            "status": "passed",
            "hook_type": "sandbox_canvas_artifact_contract",
            "summary": "Sandbox Mona Lisa artifact was generated from discrete operator primitives.",
            "checked": [
                "bounded canvas dimensions",
                "operator primitive action list written",
                "no image import or paste action present",
                "sandbox/live boundary declared",
                "artifact receipt written",
            ],
        },
        "governance": receipt["governance"],
    }


__all__ = [
    "evaluate_mona_lisa_sandbox_artifact",
    "list_mona_lisa_sandbox_evaluation_queue",
    "list_mona_lisa_sandbox_improvement_proposals",
    "paint_mona_lisa_sandbox",
    "record_mona_lisa_sandbox_evaluation",
]

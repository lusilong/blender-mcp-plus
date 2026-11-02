# SPDX-FileCopyrightText: 2026 Blender Authors
#
# SPDX-License-Identifier: GPL-3.0-or-later

# pylint: disable=C0114  # See tool doc-strings.

"""
Poly Haven asset library tools.

These tools run the HTTP side in the MCP server process and only send a small
"import this file" snippet to Blender, keeping the Blender side minimal.
"""

__all__ = (
    "register",
)

import json
import os
import re
import tempfile
import time
import urllib.parse
import urllib.request
from typing import Any

from blender_mcp_plus.tools_helpers.connection import send_code
from mcp.server.fastmcp import FastMCP  # pylint: disable=import-error,no-name-in-module
from mcp.types import ToolAnnotations  # pylint: disable=import-error,no-name-in-module

_API_BASE = "https://api.polyhaven.com"
_USER_AGENT = "blender-mcp-plus/0.1 (Poly Haven asset bridge)"
_TIMEOUT = 60.0
_CACHE_TTL = 300.0
_SEARCH_LIMIT_MAX = 50

_ASSET_TYPES = ("models", "hdris", "textures")

# Cheap in-process cache: Poly Haven's asset list is ~0.5MB per type and the
# model rarely needs two identical fetches inside one session.
_cache: dict[str, tuple[float, list[Any]]] = {}


def _http_get_json(url: str) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def _cached(key: str, loader: Any) -> Any:
    now = time.monotonic()
    hit = _cache.get(key)
    if hit is not None and hit[0] > now:
        return hit[1]
    value = loader()
    _cache[key] = (now + _CACHE_TTL, value)
    return value


def _assets(asset_type: str) -> dict[str, Any]:
    """Return ``{slug: metadata}`` for an asset type, cached."""
    return _cached("assets:" + asset_type, lambda: _http_get_json(
        "{:s}/assets?t={:s}".format(_API_BASE, urllib.parse.quote(asset_type))
    ))


def _files(asset_id: str) -> dict[str, Any]:
    return _cached("files:" + asset_id, lambda: _http_get_json(
        "{:s}/files/{:s}".format(_API_BASE, urllib.parse.quote(asset_id))
    ))


def _download(url: str, destination: str) -> int:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
    total = 0
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response, open(destination, "wb") as fh:
        while True:
            chunk = response.read(1024 * 256)
            if not chunk:
                break
            fh.write(chunk)
            total += len(chunk)
    return total


def _asset_url(asset_id: str, asset_type: str) -> str:
    kind = {"models": "models", "hdris": "hdris", "textures": "textures"}.get(asset_type, "models")
    return "https://polyhaven.com/a/{:s}".format(asset_id) if kind != "hdris" else "https://polyhaven.com/hdris"


def _summarize(asset_id: str, record: dict[str, Any], asset_type: str) -> dict[str, Any]:
    dimensions = record.get("dimensions") or []
    return {
        "id": asset_id,
        "name": record.get("name") or asset_id,
        "type": asset_type,
        "category": record.get("category"),
        "categories": record.get("categories") or [],
        "tags": (record.get("tags") or [])[:10],
        "dimensions_m": [round(float(v) / 1000.0, 3) for v in dimensions] if dimensions else None,
        "polycount": record.get("polycount"),
        "download_count": record.get("download_count"),
        "thumbnail_url": record.get("thumbnail_url"),
        "url": _asset_url(asset_id, asset_type),
    }


def _matches(asset_id: str, record: dict[str, Any], query: str) -> bool:
    if not query:
        return True
    haystack = " ".join([
        asset_id,
        str(record.get("name") or ""),
        " ".join(record.get("tags") or []),
        str(record.get("category") or ""),
        " ".join(record.get("categories") or []),
    ]).lower()
    return all(word in haystack for word in query.lower().split())


def _resolution_key(available: Any, resolution: str) -> str:
    if isinstance(available, dict):
        keys = list(available.keys())
        if resolution in available:
            return resolution
        for candidate in ("1k", "2k", "4k", "8k", "512"):
            if candidate in available:
                return candidate
        if keys:
            return keys[0]
    return resolution


def _download_model_files(asset_id: str, resolution: str) -> tuple[str, str, dict[str, Any]]:
    files = _files(asset_id)
    tree = files.get("gltf") or {}
    res = _resolution_key(tree, resolution)
    entry = tree.get(res, {}).get("gltf")
    if not entry:
        raise RuntimeError("No glTF download is published for '{:s}'".format(asset_id))

    work_dir = tempfile.mkdtemp(prefix="blmcp_ph_{:s}_".format(asset_id))
    gltf_name = os.path.basename(urllib.parse.urlparse(entry["url"]).path)
    gltf_path = os.path.join(work_dir, gltf_name)
    _download(entry["url"], gltf_path)

    includes = entry.get("include") or {}
    for relative, info in includes.items():
        relative_path = relative.replace("/", os.sep).replace("\\", os.sep)
        target = os.path.join(work_dir, relative_path)
        _download(info["url"], target)

    summary = {"resolution": res, "files": 1 + len(includes), "directory": work_dir}
    return work_dir, gltf_path, summary


def _import_model_code(gltf_path: str, target_size: float) -> str:
    return """import bpy, json
from mathutils import Vector

before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath={gltf!r})
bpy.context.view_layer.update()
new_objects = [obj for obj in bpy.data.objects if obj not in before]

def _bounds(objects):
    low = [1.0e18, 1.0e18, 1.0e18]
    high = [-1.0e18, -1.0e18, -1.0e18]
    for obj in objects:
        if obj.type not in {{'MESH', 'CURVE', 'SURFACE', 'FONT', 'META'}}:
            continue
        for corner in obj.bound_box:
            point = obj.matrix_world @ Vector(corner)
            for index in range(3):
                low[index] = min(low[index], point[index])
                high[index] = max(high[index], point[index])
    if low[0] > high[0]:
        return None, None
    return low, high

low, high = _bounds(new_objects)
scale_factor = 1.0
target_size = {size!r}
if target_size and target_size > 0.0 and low is not None:
    extent = max(high[index] - low[index] for index in range(3))
    if extent > 0.0:
        scale_factor = float(target_size) / extent
        for obj in new_objects:
            if obj.parent is None:
                obj.scale = tuple(value * scale_factor for value in obj.scale)
        bpy.context.view_layer.update()
        low, high = _bounds(new_objects)

result = {{
    "imported": sorted(obj.name for obj in new_objects),
    "object_count": len(new_objects),
    "scale_factor": round(scale_factor, 5),
    "dimensions_m": [round(high[index] - low[index], 4) for index in range(3)] if low is not None else None,
}}
""".format(gltf=gltf_path, size=float(target_size or 0.0))


def _import_hdri_code(hdri_path: str, strength: float) -> str:
    return """import bpy
from mathutils import Vector

scene = bpy.context.scene
world = scene.world
if world is None:
    world = bpy.data.worlds.new("World")
    scene.world = world
world.use_nodes = True
nodes = world.node_tree.nodes
links = world.node_tree.links
background = next((node for node in nodes if node.type == 'BACKGROUND'), None)
if background is None:
    background = nodes.new('ShaderNodeBackground')
    output = next((node for node in nodes if node.type == 'OUTPUT_WORLD'), None)
    if output is not None:
        links.new(background.outputs['Background'], output.inputs['Surface'])
environment = next((node for node in nodes if node.type == 'TEX_ENVIRONMENT'), None)
if environment is None:
    environment = nodes.new('ShaderNodeTexEnvironment')
image = bpy.data.images.load({path!r}, check_existing=True)
environment.image = image
if not environment.outputs['Color'].is_linked:
    links.new(environment.outputs['Color'], background.inputs['Color'])
background.inputs['Strength'].default_value = {strength!r}

result = {{
    "world": world.name,
    "image": image.name,
    "size": list(image.size),
    "strength": {strength!r},
}}
""".format(path=hdri_path, strength=float(strength))


def _download_texture(asset_id: str, resolution: str) -> tuple[str, str, dict[str, Any]]:
    files = _files(asset_id)
    for map_name in ("Diffuse", "diffuse", "Diff", "diff"):
        map_tree = files.get(map_name)
        if isinstance(map_tree, dict):
            res = _resolution_key(map_tree, resolution)
            formats = map_tree.get(res) or {}
            for extension in ("jpg", "png", "exr"):
                info = formats.get(extension)
                if isinstance(info, dict) and info.get("url"):
                    work_dir = tempfile.mkdtemp(prefix="blmcp_ph_{:s}_".format(asset_id))
                    suffix = "." + extension
                    path = os.path.join(work_dir, asset_id + "_diffuse_" + res + suffix)
                    _download(info["url"], path)
                    return path, res, {"map": map_name, "resolution": res}
    raise RuntimeError("No diffuse texture is published for '{:s}'".format(asset_id))


def _import_texture_code(texture_path: str, asset_id: str, apply_to: str) -> str:
    return """import bpy

asset_id = {asset_id!r}
material = bpy.data.materials.new(name=asset_id + "_mat")
material.use_nodes = True
nodes = material.node_tree.nodes
links = material.node_tree.links
bsdf = next((node for node in nodes if node.type == 'BSDF_PRINCIPLED'), None)
if bsdf is None:
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    output = next((node for node in nodes if node.type == 'OUTPUT_MATERIAL'), None)
    if output is not None:
        links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])
image = bpy.data.images.load({path!r}, check_existing=True)
texture = nodes.new('ShaderNodeTexImage')
texture.image = image
links.new(texture.outputs['Color'], bsdf.inputs['Base Color'])

target = bpy.data.objects.get({apply_to!r}) if {apply_to!r} else bpy.context.active_object
applied_to = None
if target is not None and target.type == 'MESH':
    target.data.materials.clear()
    target.data.materials.append(material)
    applied_to = target.name

result = {{
    "material": material.name,
    "image": image.name,
    "size": list(image.size),
    "applied_to": applied_to,
}}
""".format(path=texture_path, asset_id=asset_id, apply_to=apply_to)


def _response_result(response: dict[str, Any]) -> dict[str, Any]:
    if response.get("status") != "ok":
        raise RuntimeError(str(response.get("message", "Blender returned an error")))
    result = response.get("result")
    if not isinstance(result, dict):
        return {"value": result}
    if result.get("status") == "error":
        raise RuntimeError(str(result.get("message", "Blender returned an error")))
    return result


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        annotations=ToolAnnotations(
            title="Search Poly Haven Assets",
            readOnlyHint=True,
        )
    )
    def search_assets(
        query: str = "",
        source: str = "polyhaven",
        asset_type: str = "models",
        category: str = "",
        limit: int = 12,
        min_size_m: float = 0.0,
    ) -> dict[str, Any]:
        """
        Search the Poly Haven library for free CC0 models, HDRIs and textures.

        *asset_type* is one of ``models``, ``hdris``, ``textures`` or ``all``.
        *query* matches words in the asset id, name, tags and category
        (all words must match). *category* filters on Poly Haven's taxonomy
        path (for example ``Furniture`` or ``Metal/Sheet & Corrugated``).
        *min_size_m* drops assets whose largest real-world dimension is smaller
        than this value in meters (models and textures only).
        """
        if source and source.lower() not in ("polyhaven", "poly_haven", "poly-haven"):
            return {
                "error": "This build of the Blender MCP server only implements the Poly Haven "
                         "asset source. Sketchfab and Poly Pizza need their own API keys and are "
                         "not wired in here.",
                "source": source,
            }
        if asset_type not in _ASSET_TYPES + ("all",):
            return {"error": "asset_type must be one of: models, hdris, textures, all"}
        try:
            types = list(_ASSET_TYPES) if asset_type == "all" else [asset_type]
            found: list[dict[str, Any]] = []
            for one_type in types:
                for asset_id, record in _assets(one_type).items():
                    if category and category.lower() not in str(record.get("category") or "").lower():
                        continue
                    if not _matches(asset_id, record, query):
                        continue
                    dimensions = record.get("dimensions") or []
                    if min_size_m and dimensions and max(dimensions) / 1000.0 < float(min_size_m):
                        continue
                    found.append(_summarize(asset_id, record, one_type))
            found.sort(key=lambda item: item.get("download_count") or 0, reverse=True)
            limit_int = max(1, min(int(limit or 12), _SEARCH_LIMIT_MAX))
            return {
                "assets": found[:limit_int],
                "total_count": len(found),
                "returned_count": min(limit_int, len(found)),
                "query": query or None,
                "note": None,
            }
        except Exception as ex:  # pylint: disable=broad-exception-caught
            return {"error": "{:s}: {:s}".format(type(ex).__name__, str(ex))}

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Import Poly Haven Asset",
            destructiveHint=True,
        )
    )
    def import_asset(
        id: str,
        asset_type: str = "models",
        resolution: str = "1k",
        target_size: float = 0.0,
        apply_to: str = "",
        strength: float = 1.0,
        source: str = "polyhaven",
    ) -> dict[str, Any]:
        """
        Download a Poly Haven asset and import it into the connected Blender scene.

        *id* is the asset id returned by ``search_assets`` (for example
        ``ArmChair_01``). For ``models`` the glTF version is imported; for
        ``hdris`` the HDRI becomes the world environment at *strength*; for
        ``textures`` the diffuse map is put on a new material applied to
        *apply_to* (or the active mesh object). *target_size* > 0 scales the
        imported model so its largest dimension is that many meters.
        """
        if not id:
            return {"error": "id is required (use search_assets to find one)"}
        if source and source.lower() not in ("polyhaven", "poly_haven", "poly-haven"):
            return {"error": "Only the Poly Haven source is implemented in this server."}
        if asset_type not in _ASSET_TYPES:
            return {"error": "asset_type must be one of: models, hdris, textures"}
        try:
            if asset_type == "models":
                work_dir, gltf_path, info = _download_model_files(id, resolution)
                result = _response_result(send_code(_import_model_code(gltf_path, target_size), strict_json=True))
                return {"ok": True, "asset_id": id, "asset_type": asset_type,
                        "download": info, "blender": result}
            if asset_type == "hdris":
                files = _files(id)
                tree = files.get("hdri") or {}
                res = _resolution_key(tree, resolution)
                formats = tree.get(res) or {}
                entry = formats.get("hdr") or formats.get("exr")
                if not entry:
                    raise RuntimeError("No HDR/EXR download is published for '{:s}'".format(id))
                work_dir = tempfile.mkdtemp(prefix="blmcp_ph_{:s}_".format(id))
                extension = ".hdr" if "hdr" in entry else ".exr"
                path = os.path.join(work_dir, id + extension)
                _download(entry["url"], path)
                result = _response_result(send_code(_import_hdri_code(path, strength), strict_json=True))
                return {"ok": True, "asset_id": id, "asset_type": asset_type,
                        "download": {"resolution": res, "file": path}, "blender": result}
            texture_path, res, info = _download_texture(id, resolution)
            result = _response_result(send_code(
                _import_texture_code(texture_path, id, apply_to), strict_json=True))
            return {"ok": True, "asset_id": id, "asset_type": asset_type,
                    "download": dict(info, file=texture_path, resolution=res), "blender": result}
        except Exception as ex:  # pylint: disable=broad-exception-caught
            return {"error": "{:s}: {:s}".format(type(ex).__name__, str(ex))}


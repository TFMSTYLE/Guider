# SPDX-FileCopyrightText: 2025-2026 The French Monkey
# SPDX-License-Identifier: GPL-3.0-or-later

bl_info = {
    "name": "Guider",
    "author": "The French Monkey",
    "version": (1, 0, 1),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Guider",
    "description": "Overlay guides with Main/Sub grids and labels",
    "category": "3D View",
    "license": "GPL-3.0-or-later",
}

import bpy, gpu, math
from math import sin, cos, pi, radians, degrees, atan2, asin
from mathutils import Vector
from gpu_extras.batch import batch_for_shader
import bpy_extras.view3d_utils as v3d
import blf

# ------------------------------------------------------------------------
# Globals
# ------------------------------------------------------------------------

_H3D = None
_H2D = None
_SHADER_NAME = "UNIFORM_COLOR"  
_GEOM_CACHE = {}
_LABEL_CACHE = {}
_LAST_VIEW_MATRIX_HASH = None

# ------------------------------------------------------------------------
# Draw handlers (3D/2D)
# ------------------------------------------------------------------------

def _tag_redraw_all():
    wm = bpy.context.window_manager if hasattr(bpy.context, "window_manager") else None
    if not wm:
        return
    for window in wm.windows:
        screen = getattr(window, "screen", None)
        if not screen:
            continue
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

def _enable_handlers():
    global _H3D, _H2D
    if _H3D is None:
        _H3D = bpy.types.SpaceView3D.draw_handler_add(_draw_3d, (), 'WINDOW', 'POST_VIEW')
    if _H2D is None:
        _H2D = bpy.types.SpaceView3D.draw_handler_add(_draw_2d_labels, (), 'WINDOW', 'POST_PIXEL')
    _tag_redraw_all()

def _disable_handlers():
    global _H3D, _H2D
    if _H3D is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_H3D, 'WINDOW'); _H3D = None
    if _H2D is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_H2D, 'WINDOW'); _H2D = None
    _tag_redraw_all()
    
def _cache_key(p, grid_type, sub=False):
    return (
        "SUB" if sub else "MAIN",
        grid_type,
        p.spacing,
        p.count,
        p.segments,
        p.radial_divisions,
        p.sub_divisions,
        p.main_label_step if not sub else p.sub_label_step,
        p.main_style if not sub else p.sub_style,
    )

def _get_cached_geom(p, grid_type, sub=False):
    key = _cache_key(p, grid_type, sub)
    if key in _GEOM_CACHE:
        return _GEOM_CACHE[key]

    spacing = p.spacing if not sub else p.spacing / p.sub_divisions
    count = p.count * (p.sub_divisions if sub else 1)
    divs = p.sub_divisions
    segs = p.segments
    rdiv = p.radial_divisions

    if grid_type == 'FLAT':
        lines = build_flat_lines(spacing, count)
        pts = intersections_flat(spacing, count, step=1)

    elif grid_type == 'CIRCULAR':
        lines = build_circular_lines(spacing, count, rdiv, segs)
        pts = intersections_circular(spacing, count, rdiv, step=1)

    elif grid_type == 'CUBE':
        lines = build_cube_lines(spacing, count)
        pts = intersections_cube(spacing, count, step=1)

    else: 
        lines = build_spherical_lines(spacing, count, segs)
        pts = intersections_spherical(spacing, count, segs, step=1)

    _GEOM_CACHE[key] = (lines, pts)
    return lines, pts

def _invalidate_cache(filter_prefix=None):
    if not filter_prefix:
        _GEOM_CACHE.clear()
        return
    for k in list(_GEOM_CACHE.keys()):
        if k[0].startswith(filter_prefix):
            del _GEOM_CACHE[k]

def _invalidate_label_cache():
    global _LABEL_CACHE
    _LABEL_CACHE.clear()

# ------------------------------------------------------------------------
# Geometry generators
# ------------------------------------------------------------------------

def build_flat_lines(spacing, count):
    ext = count * spacing
    coords = []
    for i in range(-count, count + 1):
        y = i * spacing
        coords += [(-ext, y, 0.0), (ext, y, 0.0)]
        x = i * spacing
        coords += [(x, -ext, 0.0), (x, ext, 0.0)]
    return coords

def build_circular_lines(spacing, rings, radial_divs, segments):
    coords = []
    for r in range(1, rings + 1):
        prev = None
        for i in range(segments + 1):
            a = (i / segments) * 2 * pi
            p = (cos(a)*r*spacing, sin(a)*r*spacing, 0.0)
            if prev is not None:
                coords += [prev, p]
            prev = p
    radial_divs = max(1, radial_divs)
    R = rings * spacing
    for k in range(radial_divs):
        a = (k / radial_divs) * 2 * pi
        coords += [(0.0, 0.0, 0.0), (cos(a)*R, sin(a)*R, 0.0)]
    return coords

def build_cube_lines(spacing, count):
    coords = []
    ext = count * spacing
    for z in range(-count, count + 1):
        zval = z * spacing
        for i in range(-count, count + 1):
            coords += [(-ext, i * spacing, zval), (ext, i * spacing, zval)]
            coords += [(i * spacing, -ext, zval), (i * spacing, ext, zval)]
    for x in range(-count, count + 1):
        for y in range(-count, count + 1):
            if abs(x) == count or abs(y) == count:
                coords += [(x*spacing, y*spacing, -ext), (x*spacing, y*spacing, ext)]
    return coords

def build_spherical_lines(spacing, rings, segments):
    coords = []
    R = max(spacing, rings * spacing)
    lat_steps = max(4, rings * 2)
    for j in range(1, lat_steps):
        phi = pi * (j / lat_steps)
        r = R * sin(phi); z = R * cos(phi)
        prev = None
        for i in range(segments + 1):
            a = (i / segments) * 2 * pi
            p = (r * cos(a), r * sin(a), z)
            if prev is not None:
                coords += [prev, p]
            prev = p
    for k in range(segments):
        a = (k / segments) * 2 * pi
        prev = None
        for i in range(segments + 1):
            t = -pi/2 + pi * (i / segments)
            p = (R * math.cos(t) * math.cos(a), R * math.cos(t) * math.sin(a), R * math.sin(t))
            if prev is not None:
                coords += [prev, p]
            prev = p
    return coords

def intersections_flat(spacing, count, step):
    pts = []
    step = max(1, step)
    for ix in range(-count, count + 1):
        if ix % step != 0: continue
        x = ix * spacing
        for iy in range(-count, count + 1):
            if iy % step != 0: continue
            y = iy * spacing
            pts.append((x, y, 0.0))
    return pts

def intersections_circular(spacing, rings, radial_divs, step):
    pts = []
    radial_divs = max(1, radial_divs)
    step = max(1, step)
    for r in range(1, rings + 1):
        if r % step != 0: continue
        for k in range(radial_divs):
            a = (k / radial_divs) * 2 * pi
            pts.append((cos(a)*r*spacing, sin(a)*r*spacing, 0.0))
    return pts

def intersections_cube(spacing, count, step):
    pts = []
    step = max(1, step)
    for z in range(-count, count + 1):
        if z % step != 0: continue
        zval = z * spacing
        for ix in range(-count, count + 1):
            if ix % step != 0: continue
            x = ix * spacing
            for iy in range(-count, count + 1):
                if iy % step != 0: continue
                y = iy * spacing
                pts.append((x, y, zval))
    return pts

def intersections_spherical(spacing, rings, segments, step):
    pts = []
    step = max(1, step)
    R = max(spacing, rings * spacing)
    lat_steps = max(4, rings * 2)
    long_steps = max(8, segments)
    for j in range(1, lat_steps):
        if j % step != 0: continue
        phi = pi * (j / lat_steps)
        for k in range(long_steps):
            if k % step != 0: continue
            a = (k / long_steps) * 2 * pi
            x = R * math.sin(phi) * math.cos(a)
            y = R * math.sin(phi) * math.sin(a)
            z = R * math.cos(phi)
            pts.append((x, y, z))
    return pts

# ------------------------------------------------------------------------
# Units formatting
# ------------------------------------------------------------------------

def _unit_convert(val_m, mode):
    if mode == 'MM': return val_m * 1000.0, "mm"
    if mode == 'CM': return val_m * 100.0, "cm"
    if mode == 'M':  return val_m, "m"
    if mode == 'KM': return val_m / 1000.0, "km"
    return val_m, "" 

# ------------------------------------------------------------------------
# Draw helpers
# ------------------------------------------------------------------------

def _draw_lines(coords, color):
    if not coords:
        return
    shader = gpu.shader.from_builtin(_SHADER_NAME)
    batch = batch_for_shader(shader, "LINES", {"pos": coords})
    gpu.state.blend_set("ALPHA")
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)
    gpu.state.blend_set("NONE")

def _draw_crosses(points, color, world_size, three_d=False):
    if not points:
        return
    d = world_size
    coords = []
    for (x, y, z) in points:
        coords += [(x - d, y, z), (x + d, y, z)]
        coords += [(x, y - d, z), (x, y + d, z)]
        if three_d:
            coords += [(x, y, z - d), (x, y, z + d)]
    _draw_lines(coords, color)

def _draw_gl_points(points, color, pixel_size):
    if not points:
        return
    shader = gpu.shader.from_builtin(_SHADER_NAME)
    batch = batch_for_shader(shader, "POINTS", {"pos": points})
    gpu.state.blend_set("ALPHA")
    gpu.state.program_point_size_set(True)
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)
    gpu.state.program_point_size_set(False)
    gpu.state.blend_set("NONE")

def _project_draw_text(text, world_pos, size_px, color, offset):
    region = bpy.context.region
    rv3d = bpy.context.region_data
    if not (region and rv3d):
        return
    x, y, z = world_pos
    ox, oy, oz = offset
    p2 = v3d.location_3d_to_region_2d(region, rv3d, Vector((x + ox, y + oy, z + oz)))
    if p2 is None:
        return
    fid = 0
    blf.color(fid, *color)
    blf.size(fid, int(max(6, size_px)))
    line_h = size_px + 2  
    for i, line in enumerate(text.split("\n")):
        blf.position(fid, p2.x, p2.y - i * line_h, 0)
        blf.draw(fid, line)

def _label_is_visible(_):
    return True

def _pts_key(pt, tol=1e-4):
    return (round(pt[0] / tol), round(pt[1] / tol), round(pt[2] / tol))

# ------------------------------------------------------------------------
# Main draw passes
# ------------------------------------------------------------------------

def _draw_3d():
    scene = bpy.context.scene if hasattr(bpy.context, "scene") else None
    if not scene:
        return
    p = getattr(scene, "guider_props", None)
    if not p or not p.preview_enabled:
        return

    gpu.state.depth_test_set('NONE' if p.show_through else 'LESS_EQUAL')

    if p.main_enabled:
        main_lines, main_pts = _get_cached_geom(p, p.grid_type, sub=False)
        style = p.main_style
        if style == 'LINES':
            _draw_lines(main_lines, p.main_color)
        elif style == 'CROSS':
            _draw_crosses(main_pts, p.main_color, p.main_point_size * p.spacing, three_d=(p.grid_type in {'CUBE', 'SPHERICAL'}))
        elif style == 'POINTS':
            _draw_gl_points(main_pts, p.main_color, p.main_point_pixel_size)

    if p.sub_enabled and p.sub_divisions > 1:
        sub_lines, sub_pts = _get_cached_geom(p, p.grid_type, sub=True)
        style = p.sub_style
        sub_spacing = p.spacing / p.sub_divisions
        if style == 'LINES':
            _draw_lines(sub_lines, p.sub_color)
        elif style == 'CROSS':
            _draw_crosses(sub_pts, p.sub_color, p.sub_point_size * sub_spacing, three_d=(p.grid_type in {'CUBE', 'SPHERICAL'}))
        elif style == 'POINTS':
            _draw_gl_points(sub_pts, p.sub_color, p.sub_point_pixel_size)

    gpu.state.depth_test_set('NONE')

def _draw_2d_labels():
    global _LAST_VIEW_MATRIX_HASH, _LABEL_CACHE
    scene = bpy.context.scene if hasattr(bpy.context, "scene") else None
    if not scene:
        return
    p = getattr(scene, "guider_props", None)
    if not p or not p.preview_enabled:
        return

    region = getattr(bpy.context, "region", None)
    rv3d = getattr(bpy.context, "region_data", None)
    if not (region and rv3d):
        return

    def stable_hash_matrix(mat):
        return tuple(round(v, 3) for row in mat for v in row)

    view_hash = hash(stable_hash_matrix(rv3d.view_matrix) + stable_hash_matrix(rv3d.perspective_matrix))
    if view_hash != _LAST_VIEW_MATRIX_HASH:
        _LABEL_CACHE.clear()
        _LAST_VIEW_MATRIX_HASH = view_hash

    fid = 0
    blf.size(fid, 12)
    MAX_LABELS = 1000

    def get_label_cache_key(sub):
        return (
            "SUB" if sub else "MAIN",
            p.grid_type,
            p.spacing,
            p.count,
            p.sub_divisions,
            p.main_label_step if not sub else p.sub_label_step,
            p.main_label_layout if not sub else p.sub_label_layout,
            p.main_unit if not sub else p.sub_unit,
            p.main_axis_tag if not sub else p.sub_axis_tag,
        )

    def build_label_cache(points, color, size_px, off, unit_mode, axis_tag, layout, key):
        from mathutils import Vector as Vec
        cached = []
        ox, oy, oz = off
        for (x, y, z) in points:
            world = Vec((x + ox, y + oy, z + oz))
            p2 = v3d.location_3d_to_region_2d(region, rv3d, world)
            if not p2 or p2.x < 0 or p2.x > region.width or p2.y < 0 or p2.y > region.height:
                continue

            vx, ux = _unit_convert(x, unit_mode)
            vy, uy = _unit_convert(y, unit_mode)
            vz, uz = _unit_convert(z, unit_mode)

            if p.grid_type in {'FLAT', 'CIRCULAR'}:
                comps = [("X", vx, ux), ("Y", vy, uy)]
            else: 
                comps = [("X", vx, ux), ("Y", vy, uy), ("Z", vz, uz)]

            if axis_tag:
                lines = [f"{lbl}: {abs(val):.3g}{unit}" for lbl, val, unit in comps]
            else:
                lines = [f"{abs(val):.3g}{unit}" for _, val, unit in comps]

            txt = "  ".join(lines) if layout == "INLINE" else "\n".join(lines)
            cached.append((p2.x, p2.y, txt))

        if len(cached) > MAX_LABELS:
            step = max(1, len(cached) // MAX_LABELS)
            cached = cached[::step]

        _LABEL_CACHE[key] = cached
        return cached

    def draw_cached_labels(cached, color, size_px):
        if not cached:
            return
        blf.color(0, *color)
        blf.size(0, int(size_px))
        for x, y, txt in cached:
            for i, line in enumerate(txt.split("\n")):
                blf.position(0, x, y - i * (size_px + 2), 0)
                blf.draw(0, line)

    # ─────────── MAIN LABELS
    if p.main_enabled and p.main_labels:
        key = get_label_cache_key(False)
        cached = _LABEL_CACHE.get(key)
        if cached is None:
            _, all_pts = _get_cached_geom(p, p.grid_type, sub=False)
            step = max(1, p.main_label_step)
            pts = all_pts[::step]
            cached = build_label_cache(
                pts, p.main_label_color, p.main_label_size_px,
                (p.main_label_offx, p.main_label_offy, p.main_label_offz),
                p.main_unit, p.main_axis_tag, p.main_label_layout, key
            )
        draw_cached_labels(cached, p.main_label_color, p.main_label_size_px)

    # ─────────── SUB LABELS
    if p.sub_enabled and p.sub_labels:
        key = get_label_cache_key(True)
        cached = _LABEL_CACHE.get(key)
        if cached is None:
            _, all_pts = _get_cached_geom(p, p.grid_type, sub=True)
            step = max(1, p.sub_label_step)
            pts = all_pts[::step]
            cached = build_label_cache(
                pts, p.sub_label_color, p.sub_label_size_px,
                (p.sub_label_offx, p.sub_label_offy, p.sub_label_offz),
                p.sub_unit, p.sub_axis_tag, p.sub_label_layout, key
            )
        draw_cached_labels(cached, p.sub_label_color, p.sub_label_size_px)

# ------------------------------------------------------------------------
# Properties
# ------------------------------------------------------------------------

class GuiderOverlayProps(bpy.types.PropertyGroup):
    # ───────────── General ─────────────
    preview_enabled: bpy.props.BoolProperty(name="Preview (Overlay)", default=False, description="Draw guider as overlay (no scene objects)", update=lambda s, c: (_enable_handlers() if s.preview_enabled else _disable_handlers()))
    show_through: bpy.props.BoolProperty(name="Always Visible (Ignore Depth)", default=True, description="If off, guides and labels will be hidden by geometry", update=lambda s, c: _tag_redraw_all())

    # ───────────── Grid Base ─────────────
    grid_type: bpy.props.EnumProperty(name="Grid Type", items=[('FLAT', "Flat", "2D grid on XY"), ('CIRCULAR', "Circular", "Rings + radials"), ('CUBE', "Cube", "Volumetric grid"), ('SPHERICAL', "Spherical", "Lat/Long sphere")], default='FLAT', update=lambda s, c: (_invalidate_cache(), _tag_redraw_all()))
    spacing: bpy.props.FloatProperty(name="Spacing", default=1.0, min=0.001, subtype='DISTANCE', update=lambda s, c: (_invalidate_cache(), _tag_redraw_all()))
    count: bpy.props.IntProperty(name="Count / Rings", default=10, min=1, max=1000, update=lambda s, c: (_invalidate_cache(), _tag_redraw_all()))
    segments: bpy.props.IntProperty(name="Segments", default=96, min=16, max=4096, update=lambda s, c: (_invalidate_cache(), _tag_redraw_all()))
    radial_divisions: bpy.props.IntProperty(name="Radials", default=16, min=1, max=720, update=lambda s, c: (_invalidate_cache(), _tag_redraw_all()))

    # ───────────── Main Grid ─────────────
    main_enabled: bpy.props.BoolProperty(name="Enable Main Grid", default=True, update=lambda s, c: _tag_redraw_all())
    main_style: bpy.props.EnumProperty(name="Main Style", items=[('LINES', "Lines", "Continuous lines"), ('CROSS', "Crosses", "Small crosses at intersections"), ('POINTS', "Points", "GL points at intersections")], default='LINES', update=lambda s, c: (_invalidate_cache(), _tag_redraw_all()))
    main_color: bpy.props.FloatVectorProperty(name="Main Color", subtype='COLOR_GAMMA', size=4, min=0.0, max=1.0, default=(0.8, 0.8, 0.8, 0.9), update=lambda s, c: _tag_redraw_all())
    main_point_size: bpy.props.FloatProperty(name="Cross Size (World)", default=0.03, min=0.0001, max=10.0, update=lambda s, c: _tag_redraw_all())
    main_point_pixel_size: bpy.props.FloatProperty(name="Point Size (px)", default=4.0, min=1.0, max=32.0, update=lambda s, c: _tag_redraw_all())

    # ───────────── Main Labels ─────────────
    main_labels: bpy.props.BoolProperty(name="Main Labels", default=True, update=lambda s, c: _tag_redraw_all())
    main_label_step: bpy.props.IntProperty(name="Main Label Step", default=2, min=1, max=200, update=lambda s, c: (_invalidate_cache(), _invalidate_label_cache(), _tag_redraw_all()))
    main_label_size_px: bpy.props.IntProperty(name="Main Label Size (px)", default=14, min=6, max=72, update=lambda s, c: _tag_redraw_all())
    main_label_color: bpy.props.FloatVectorProperty(name="Main Label Color", subtype='COLOR_GAMMA', size=4, min=0.0, max=1.0, default=(1.0, 1.0, 1.0, 1.0), update=lambda s, c: (_invalidate_label_cache(), _tag_redraw_all()))
    main_label_offx: bpy.props.FloatProperty(name="Main Label Offset X", default=0.06, min=-10.0, max=10.0, update=lambda s, c: _tag_redraw_all())
    main_label_offy: bpy.props.FloatProperty(name="Main Label Offset Y", default=0.06, min=-10.0, max=10.0, update=lambda s, c: _tag_redraw_all())
    main_label_offz: bpy.props.FloatProperty(name="Main Label Offset Z", default=0.0, min=-10.0, max=10.0, update=lambda s, c: _tag_redraw_all())
    main_unit: bpy.props.EnumProperty(name="Main Units", items=[('NONE','None','No unit'),('MM','mm','Millimeters'),('CM','cm','Centimeters'),('M','m','Meters'),('KM','km','Kilometers')], default='NONE', update=lambda s, c: (_invalidate_label_cache(), _tag_redraw_all()))
    main_show_unit: bpy.props.BoolProperty(name="Show Unit Suffix", default=True, update=lambda s, c: _tag_redraw_all())
    main_axis_tag: bpy.props.BoolProperty(name="Axis Tags (X/Y/Z)", default=False, update=lambda s, c: (_invalidate_label_cache(), _tag_redraw_all()))
    main_label_layout: bpy.props.EnumProperty(name="Main Label Layout", items=[('INLINE','INLINE','Single line'),('STACKED','STACKED','Multi line')], default='INLINE', update=lambda s, c: (_invalidate_label_cache(), _tag_redraw_all()))

    # ───────────── Subgrid ─────────────
    sub_enabled: bpy.props.BoolProperty(name="Enable Subgrid", default=False, update=lambda s, c: _tag_redraw_all())
    sub_divisions: bpy.props.IntProperty(name="Sub Divisions", default=5, min=2, max=200, update=lambda s, c: (_invalidate_cache(), _tag_redraw_all()))
    sub_style: bpy.props.EnumProperty(name="Sub Style", items=[('LINES', "Lines", "Continuous lines"), ('CROSS', "Crosses", "Small crosses at intersections"), ('POINTS', "Points", "GL points at intersections")], default='LINES', update=lambda s, c: (_invalidate_cache(), _tag_redraw_all()))
    sub_color: bpy.props.FloatVectorProperty(name="Sub Color", subtype='COLOR_GAMMA', size=4, min=0.0, max=1.0, default=(0.6, 0.6, 0.6, 0.5), update=lambda s, c: _tag_redraw_all())
    sub_point_size: bpy.props.FloatProperty(name="Sub Cross Size (World)", default=0.02, min=0.0001, max=10.0, update=lambda s, c: _tag_redraw_all())
    sub_point_pixel_size: bpy.props.FloatProperty(name="Sub Point Size (px)", default=3.0, min=1.0, max=32.0, update=lambda s, c: _tag_redraw_all())

    # ───────────── Sub Labels ─────────────
    sub_labels: bpy.props.BoolProperty(name="Sub Labels", default=False, update=lambda s, c: _tag_redraw_all())
    sub_label_step: bpy.props.IntProperty(name="Sub Label Step", default=5, min=1, max=400, update=lambda s, c: (_invalidate_cache(), _invalidate_label_cache(), _tag_redraw_all()))
    sub_label_size_px: bpy.props.IntProperty(name="Sub Label Size (px)", default=12, min=6, max=72, update=lambda s, c: _tag_redraw_all())
    sub_label_color: bpy.props.FloatVectorProperty(name="Sub Label Color", subtype='COLOR_GAMMA', size=4, min=0.0, max=1.0, default=(0.9, 0.9, 0.9, 0.9), update=lambda s, c: (_invalidate_label_cache(), _tag_redraw_all()))
    sub_label_offx: bpy.props.FloatProperty(name="Sub Label Offset X", default=0.04, min=-10.0, max=10.0, update=lambda s, c: _tag_redraw_all())
    sub_label_offy: bpy.props.FloatProperty(name="Sub Label Offset Y", default=0.04, min=-10.0, max=10.0, update=lambda s, c: _tag_redraw_all())
    sub_label_offz: bpy.props.FloatProperty(name="Sub Label Offset Z", default=0.0, min=-10.0, max=10.0, update=lambda s, c: _tag_redraw_all())
    sub_unit: bpy.props.EnumProperty(name="Sub Units", items=[('NONE','None','No unit'),('MM','mm','Millimeters'),('CM','cm','Centimeters'),('M','m','Meters'),('KM','km','Kilometers')], default='NONE', update=lambda s, c: (_invalidate_label_cache(), _tag_redraw_all()))
    sub_show_unit: bpy.props.BoolProperty(name="Show Unit Suffix", default=True, update=lambda s, c: _tag_redraw_all())
    sub_axis_tag: bpy.props.BoolProperty(name="Axis Tags (X/Y/Z)", default=False, update=lambda s, c: (_invalidate_label_cache(), _tag_redraw_all()))
    sub_label_layout: bpy.props.EnumProperty(name="Sub Label Layout", items=[('INLINE','INLINE','Single line'),('STACKED','STACKED','Multi line')], default='INLINE', update=lambda s, c: (_invalidate_label_cache(), _tag_redraw_all()))

# ------------------------------------------------------------------------
# Operators
# ------------------------------------------------------------------------

class GUIDER_OT_preview_on(bpy.types.Operator):
    bl_idname = "guider.preview_on"
    bl_label = "Enable Preview"
    bl_description = "Enable overlay drawing"
    bl_options = {"REGISTER", "UNDO"}
    def execute(self, ctx):
        ctx.scene.guider_props.preview_enabled = True
        _enable_handlers()
        return {'FINISHED'}

class GUIDER_OT_preview_off(bpy.types.Operator):
    bl_idname = "guider.preview_off"
    bl_label = "Disable Preview"
    bl_description = "Disable overlay drawing"
    bl_options = {"REGISTER", "UNDO"}
    def execute(self, ctx):
        ctx.scene.guider_props.preview_enabled = False
        _disable_handlers()
        return {'FINISHED'}
    
# ------------------------------------------------------------------------
# UI
# ------------------------------------------------------------------------

class VIEW3D_PT_guider(bpy.types.Panel):
    bl_label = "Guider"
    bl_idname = "VIEW3D_PT_guider"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Guider'

    def draw(self, context):
        layout = self.layout
        p = context.scene.guider_props

        row = layout.row(align=True)
        if p.preview_enabled:
            row.operator("guider.preview_off", icon="EMPTY_AXIS", text="Disable Guides")
        else:
            row.operator("guider.preview_on", icon="EMPTY_AXIS", text="Enable Guides")

        row = layout.row(align=True)
        row.prop(p, "show_through", toggle=True, text="X-Ray Mode", icon="XRAY")

        layout.separator(factor=0.5)

        layout.row(align=True).prop(p, "grid_type", expand=True)

        col = layout.column(align=False)
        col.prop(p, "spacing")
        col.prop(p, "count", slider=True)

        if p.grid_type in {'CIRCULAR', 'SPHERICAL'}:
            col.prop(p, "segments", slider=True)
        if p.grid_type == 'CIRCULAR':
            col.prop(p, "radial_divisions", slider=True)

        layout.separator(factor=0.5)

        # MAIN GRID
        col = layout.column(align=False)
        col.prop(p, "main_enabled", toggle=True)

        if p.main_enabled:
            row = col.row(align=True)
            row.prop(p, "main_style", expand=True)

            col.prop(p, "main_color", text="")
            if p.main_style == 'CROSS':
                col.prop(p, "main_point_size", slider=True)

            col.prop(p, "main_labels", toggle=True)

            if p.main_labels:
                col.prop(p, "main_label_color", text="")
                col.prop(p, "main_label_step", slider=True)
                col.prop(p, "main_label_size_px", slider=True)
                col.prop(p, "main_label_offz")

                col.label(text="Units:")
                row = col.row(align=True)
                row.prop(p, "main_unit", expand=True)

                col.prop(p, "main_axis_tag", toggle=True, text="Axis Tags (X/Y/Z)")

                row = col.row(align=True)
                row.prop(p, "main_label_layout", expand=True)

        # SUBGRID
        col = layout.column(align=False)
        col.prop(p, "sub_enabled", toggle=True)

        if p.sub_enabled:
            col.prop(p, "sub_divisions", slider=True)

            row = col.row(align=True)
            row.prop(p, "sub_style", expand=True)

            col.prop(p, "sub_color", text="")
            if p.sub_style == 'CROSS':
                col.prop(p, "sub_point_size", slider=True)

            col.prop(p, "sub_labels", toggle=True)

            if p.sub_labels:
                col.prop(p, "sub_label_color", text="")
                col.prop(p, "sub_label_step", slider=True)
                col.prop(p, "sub_label_size_px", slider=True)
                col.prop(p, "sub_label_offz")

                col.label(text="Units:")
                row = col.row(align=True)
                row.prop(p, "sub_unit", expand=True)

                col.prop(p, "sub_axis_tag", toggle=True, text="Axis Tags (X/Y/Z)")

                row = col.row(align=True)
                row.prop(p, "sub_label_layout", expand=True)

# ------------------------------------------------------------------------
# Register
# ------------------------------------------------------------------------

_CLASSES = (
    GuiderOverlayProps,
    GUIDER_OT_preview_on,
    GUIDER_OT_preview_off,
    VIEW3D_PT_guider,
)

def register():
    for c in _CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.guider_props = bpy.props.PointerProperty(type=GuiderOverlayProps)
    _enable_handlers()

def unregister():
    _disable_handlers()
    for c in reversed(_CLASSES):
        bpy.utils.unregister_class(c)
    del bpy.types.Scene.guider_props

if __name__ == "__main__":
    register()

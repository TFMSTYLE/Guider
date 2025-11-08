# Guider

![guider-thumb](https://github.com/user-attachments/assets/e9112f7e-9dce-48d7-b193-90800fc00e49)

**Author:** The French Monkey (TFMSTYLE)  
**Version:** 1.0.0  

---

## Overview

**Guider** is an advanced **viewport overlay system** for Blender that displays visual grid guides, sub-grids, and measurement labels directly in the 3D Viewport.  
It provides artists with precise geometric reference frameworks — flat, circular, cubic, or spherical — useful for composition, modeling alignment, and spatial visualization.

Guider supports **main and sub-grids**, **custom colors**, **labels with units**, and **depth-aware visibility**.  
It is fully dynamic and lightweight, updating interactively as parameters are adjusted.

---

## Parameters

### General
Controls overlay visibility and depth drawing behavior.

- **Preview (Overlay):**  
  Enables or disables the visual grid overlay in the viewport.

- **Always Visible (Ignore Depth):**  
  When enabled, guides and labels are drawn through all geometry.  
  When disabled, they respect scene depth and can be occluded.

---

### Grid Base
Defines the **grid structure** and global geometry generation.

- **Grid Type:**  
  Selects the guide topology:
  - `FLAT`: 2D XY grid.
  - `CIRCULAR`: Concentric rings with radial divisions.
  - `CUBE`: 3D volumetric lattice.
  - `SPHERICAL`: Latitude-longitude sphere grid.

- **Spacing:**  
  Distance between major grid divisions.  
  *(Default: 1.0)*

- **Count / Rings:**  
  Number of primary grid divisions or rings.  
  *(Default: 10)*

- **Segments:**  
  Used for circular and spherical modes. Determines segment resolution.  
  *(Default: 96)*

- **Radials:**  
  Number of radial lines for circular grids.  
  *(Default: 16)*

---

### Main Grid
Primary grid layer controls.

- **Enable Main Grid:**  
  Toggles the visibility of the main grid.

- **Main Style:**  
  Visual style for main grid intersections:
  - `LINES`: Continuous grid lines.
  - `CROSS`: Cross markers.
  - `POINTS`: GL points.

- **Main Color:**  
  RGBA color of the main grid lines.

- **Cross Size (World):**  
  World-space size of crosses (for `CROSS` style).  
  *(Default: 0.03)*

- **Point Size (px):**  
  Pixel size for `POINTS` style.  
  *(Default: 4.0)*

---

### Main Labels
Displays coordinate or unit labels for main grid intersections.

- **Main Labels:**  
  Toggles main grid labels on/off.

- **Main Label Step:**  
  Step frequency for labeling intersections.  
  *(Default: 2)*

- **Main Label Size (px):**  
  Font size in pixels.  
  *(Default: 14)*

- **Main Label Color:**  
  RGBA color for text labels.

- **Main Label Offset (X/Y/Z):**  
  Spatial offset for label placement relative to grid points.

- **Main Units:**  
  Defines which measurement unit to display:  
  `None`, `mm`, `cm`, `m`, `km`.

- **Show Unit Suffix:**  
  Toggles visibility of unit suffix text.

- **Axis Tags (X/Y/Z):**  
  Adds axis identifiers to labels.

- **Main Label Layout:**  
  Text format:
  - `INLINE`: Single-line layout.
  - `STACKED`: Multiline layout.

---

### Subgrid
Secondary grid layer for finer divisions between main lines.

- **Enable Subgrid:**  
  Toggles sub-grid visibility.

- **Sub Divisions:**  
  Number of subdivisions between main grid lines.  
  *(Default: 5)*

- **Sub Style:**  
  Visual style for sub-grid intersections:
  - `LINES`, `CROSS`, or `POINTS`.

- **Sub Color:**  
  RGBA color of sub-grid elements.

- **Sub Cross Size (World):**  
  World-space size for sub crosses.  
  *(Default: 0.02)*

- **Sub Point Size (px):**  
  Pixel size for sub points.  
  *(Default: 3.0)*

---

### Sub Labels
Displays optional coordinate or unit labels for sub-grid intersections.

- **Sub Labels:**  
  Toggles sub-grid label visibility.

- **Sub Label Step:**  
  Step frequency for sub-grid labels.  
  *(Default: 5)*

- **Sub Label Size (px):**  
  Font size in pixels.  
  *(Default: 12)*

- **Sub Label Color:**  
  RGBA color for sub labels.

- **Sub Label Offset (X/Y/Z):**  
  Positional offsets for label placement.

- **Sub Units:**  
  Measurement unit for sub-grid labels.

- **Show Unit Suffix:**  
  Enables unit display next to values.

- **Axis Tags (X/Y/Z):**  
  Adds coordinate identifiers to label text.

- **Sub Label Layout:**  
  Text layout mode: `INLINE` or `STACKED`.

---

## Operators

### Enable Preview
Activates overlay drawing in the 3D Viewport.  
**Operator:** `guider.preview_on`

### Disable Preview
Disables overlay rendering and removes draw handlers.  
**Operator:** `guider.preview_off`

---

## Drawing Modes

Guider supports two draw passes:

- **3D Pass:**  
  Draws geometric elements (lines, crosses, points) in 3D space.

- **2D Pass:**  
  Draws projected labels in screen space, respecting viewport camera movement.

---

## Cache & Performance

- Geometry and label data are **cached** for efficient redrawing.  
- Cache invalidation occurs automatically when parameters change.  
- Depth rendering, transparency, and color blending are optimized for overlay stability.  
- Guider maintains performance even at high subdivision or segment counts.

---

## Usage Notes

- Ideal for modeling, composition guides, or precision alignment.  
- Works seamlessly in **orthographic** and **perspective** views.  
- Can be used as a non-destructive overlay — it doesn’t modify scene geometry.  
- Compatible with **Blender 4.2+** and GPU-based drawing.  
- Supports all grid types simultaneously through parameter adjustments.

Guider provides a **clean, professional overlay system** for spatial visualization, technical design, and compositional reference — empowering artists to work with clarity and precision.

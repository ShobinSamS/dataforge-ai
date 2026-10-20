# Create documents and reusable assets from scratch

In Dashboard or Template library, choose **Create from scratch**. A4 at 150 DPI
is the default. Choose A5, US Letter or a custom size in millimeters/pixels,
portrait/landscape orientation and a white, colored or transparent canvas.
Choose an optional starter signature, seal, text, photo, stamp or code.

The template opens in the editor. **Add element** inserts a movable/resizable
element. The **+** tool draws a box for the selected element type; the **pen**
draws a freehand stroke. Each stroke can be selected, resized, recolored or
deleted like other elements. **Bring forward** / **Send backward** change the
layer order. Later elements appear on top. Existing uploaded templates still
require non-overlapping replacement regions.

Select an element to edit its exact content, font family, font weight, size,
colors and generation options. Signatures retain independent content, style,
boldness and opacity options. Blank exact content means generate a value.
Choose an element background color to put a colored rectangle behind it, or
leave it on the canvas background.

**Preview canvas** renders the current unsaved elements with the selected seed.
**Download PNG** exports that composition, including transparency and DPI.
Changing elements or seed clears the previous preview/download, so the download
always corresponds to the rendered settings. Checkerboard is editor decoration,
not image content. Save the final combined review and use Generation studio
when you want a batch and annotation ZIPs. Transparent canvas PNGs retain alpha
in generated samples and exports. Canvas generation starts with one clean sample
and the saved region styles; increase the count or enable augmentations as needed.
Rotation keeps transparent corners; QR
validation uses a white decoder matte without changing the exported image.

For photos, upload an approved image or transparent PNG in the existing image
pool. **Photo background** can keep the original, remove it, replace it with a
fixed color or choose a background color from selected swatches per sample.
Existing PNG edges are preserved. Automatic background removal is local and
approximate; busy backgrounds and hair may need an externally prepared cutout.
Use the preview to inspect edges. Original image pool files remain intact.

API: `POST /api/templates/blank` and
`POST /api/templates/{id}/preview`. MCP: `create_blank_template` and
`preview_canvas`; see [MCP options](mcp.md).

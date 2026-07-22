import os
import math
from datetime import datetime

def generate_svg_for_block_side(block, side_name, highlight_scrap=None, draw_prisms=True):
    L, W, H = block.size
    
    # Get global view size
    if side_name in ['Front', 'Back']:
        view_w, view_h = L, H
    elif side_name in ['Left', 'Right']:
        view_w, view_h = W, H
    elif side_name in ['Top', 'Bottom']:
        view_w, view_h = L, W
    else:
        view_w, view_h = L, H
        
    # Block global min coordinates (to offset prisms)
    block_x_min = min(v[0] for v in block.box_coordinate)
    block_y_min = min(v[1] for v in block.box_coordinate)
    block_z_min = min(v[2] for v in block.box_coordinate)
    
    # Padding
    pad = max(view_w, view_h) * 0.05
    if pad < 15: 
        pad = 15
        
    # SVG size in output (use viewBox for scaling, and specify aspect-aware size)
    svg_h = 240
    svg_w = int((view_w + 2*pad) / (view_h + 2*pad) * svg_h)
    
    block_id_safe = str(block.unique_code).replace('-', '_').replace(' ', '_')
    
    # SVG header
    svg_str = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-pad} {-pad} {view_w + 2*pad} {view_h + 2*pad}" width="{svg_w}" height="{svg_h}" style="font-family: inherit; max-width: 100%; height: auto;">'
    
    # Definitions
    svg_str += f"""
    <defs>
        <pattern id="grid_{block_id_safe}_{side_name}" width="50" height="50" patternUnits="userSpaceOnUse">
            <path d="M 50 0 L 0 0 0 50" fill="none" stroke="rgba(0,0,0,0.03)" stroke-width="1" />
        </pattern>
    </defs>
    """
    
    # 1. Draw block background grid
    svg_str += f'<rect x="0" y="0" width="{view_w}" height="{view_h}" fill="#fafafa" stroke="none" />'
    svg_str += f'<rect x="0" y="0" width="{view_w}" height="{view_h}" fill="url(#grid_{block_id_safe}_{side_name})" rx="3" />'
    
    # Faces list (vertex indices mapping to 6 faces)
    faces_indices = [
        [0, 1, 2, 3], # Bottom
        [4, 5, 6, 7], # Top
        [0, 1, 5, 4], # Side 1
        [1, 2, 6, 5], # Side 2
        [2, 3, 7, 6], # Side 3
        [3, 0, 4, 7]  # Side 4
    ]
    
    colors = ["#4F46E5", "#10B981", "#F59E0B", "#EC4899", "#3B82F6", "#8B5CF6", "#EF4444", "#06B6D4"]
    
    def project_vertex(v):
        x_raw = v[0] - block_x_min
        y_raw = v[1] - block_y_min
        z_raw = v[2] - block_z_min
        
        if side_name == 'Front':
            return x_raw, H - z_raw
        elif side_name == 'Back':
            return L - x_raw, H - z_raw
        elif side_name == 'Left':
            return y_raw, H - z_raw
        elif side_name == 'Right':
            return W - y_raw, H - z_raw
        elif side_name == 'Top':
            return x_raw, W - y_raw
        elif side_name == 'Bottom':
            return x_raw, y_raw
        return x_raw, z_raw
        
    def get_poly_area(pts):
        n = len(pts)
        if n < 3:
            return 0.0
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += float(pts[i][0]) * float(pts[j][1])
            area -= float(pts[j][0]) * float(pts[i][1])
        return abs(area) / 2.0

    def get_cam_depth(v3d_list):
        if not v3d_list: return 0
        cx = sum(v[0] for v in v3d_list) / float(len(v3d_list))
        cy = sum(v[1] for v in v3d_list) / float(len(v3d_list))
        cz = sum(v[2] for v in v3d_list) / float(len(v3d_list))
        if side_name == 'Front': return cy
        if side_name == 'Back': return -cy
        if side_name == 'Left': return cx
        if side_name == 'Right': return -cx
        if side_name == 'Top': return -cz
        if side_name == 'Bottom': return cz
        return 0

    polygons_drawn = 0
    render_elements = []  # tuple of (depth, svg_string)
    
    # 2. Draw placed prisms
    if draw_prisms and block.prism_details:
        # Deterministic global color map by hashing the mark code
        color_map = {}
        for detail in block.prism_details:
            prism = detail['prism']
            p_code = getattr(prism, 'code', getattr(prism, 'unique_code', 'Part'))
            p_code_clean = str(p_code).strip()
            if p_code_clean not in color_map:
                sum_chars = sum((i + 1) * ord(c) for i, c in enumerate(p_code_clean))
                color_map[p_code_clean] = colors[sum_chars % len(colors)]
        
        prism_idx = 0
        for detail in block.prism_details:
            prism = detail['prism']
            p_code = getattr(prism, 'code', getattr(prism, 'unique_code', 'Part'))
            p_code_clean = str(p_code).strip()
            p_size_str = "x".join(f"{s:.0f}" for s in prism.size) if hasattr(prism, 'size') else ""
            title_tooltip = f"Part: {p_code_clean} | Size: {p_size_str} mm"
            color = color_map.get(p_code_clean, "#4F46E5")
            
            for coords in detail['coordinates']:
                for face in faces_indices:
                    pts = [project_vertex(coords[v_idx]) for v_idx in face]
                    if get_poly_area(pts) > 0.1:
                        pts_str = " ".join(f"{pt[0]:.1f},{pt[1]:.1f}" for pt in pts)
                        poly_svg = f'<polygon points="{pts_str}" fill="{color}" stroke="rgba(255,255,255,0.75)" stroke-width="1" stroke-linejoin="round">'
                        poly_svg += f'<title>{title_tooltip}</title>'
                        poly_svg += '</polygon>'
                        
                        v3d_list = [coords[v_idx] for v_idx in face]
                        depth = get_cam_depth(v3d_list)
                        render_elements.append((depth, poly_svg))
                        polygons_drawn += 1
                
                # Concise labeling for G14, G15, G17, G18, G19, G20, G21 component blocks
                p_code_upper = p_code_clean.upper()
                if any(x in p_code_upper for x in ['G14', 'G15', 'G17', 'G18', 'G19', 'G20', 'G21']) or (p_code_upper.startswith('G') and len(p_code_upper) <= 5):
                    projected_pts = [project_vertex(v) for v in coords]
                    xs = [pt[0] for pt in projected_pts]
                    ys = [pt[1] for pt in projected_pts]
                    min_x, max_x = min(xs), max(xs)
                    min_y, max_y = min(ys), max(ys)
                    width = max_x - min_x
                    height = max_y - min_y
                    
                    if width > 8.0 and height > 8.0:
                        cx = (min_x + max_x) / 2.0
                        cy = (min_y + max_y) / 2.0
                        # Adaptive text sizing based on the projected prism dimensions with no hardcoded small maximum
                        font_sz = max(10.0, min(height * 0.35, width * 0.25))
                        txt_el = f'<text x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" dominant-baseline="central" ' \
                                 f'font-size="{font_sz:.1f}px" font-weight="700" fill="#ffffff" ' \
                                 f'style="paint-order: stroke; stroke: #000000; stroke-width: 2px; stroke-linejoin: round; pointer-events: none;">' \
                                 f'{p_code_clean}</text>'
                        
                        # Depth positioning for the label (just in front of the front-most part of the prism)
                        text_depth = min(get_cam_depth([v]) for v in coords) - 0.001
                        render_elements.append((text_depth, txt_el))
                prism_idx += 1
                
        # Draw z-sorted polygons and labels via Painter's algorithm
        render_elements.sort(key=lambda x: x[0], reverse=True)
        for _, svg_element in render_elements:
            svg_str += svg_element
            
    # 3. Draw scraps (only if a specific scrap is being highlighted, to match 3D behavior)
    if highlight_scrap is not None:
        for scrap in block.scraps:
            if getattr(scrap, 'unique_code', '') != getattr(highlight_scrap, 'unique_code', ''):
                continue
                
            scrap_code = getattr(scrap, 'unique_code', 'Scrap')
            scrap_size_str = "x".join(f"{s:.0f}" for s in scrap.size) if hasattr(scrap, 'size') else ""
        title_tooltip = f"Scrap | Size: {scrap_size_str} mm"
        
        for face in faces_indices:
            pts = [project_vertex(scrap.box_coordinate[v_idx]) for v_idx in face]
            if get_poly_area(pts) > 0.1:
                pts_str = " ".join(f"{pt[0]:.1f},{pt[1]:.1f}" for pt in pts)
                
                if highlight_scrap is not None:
                    fill_col = "rgba(239, 68, 68, 0.35)"
                    stroke_col = "#EF4444"
                    stroke_w = "2"
                    stroke_dash = "none"
                else:
                    fill_col = "rgba(254, 226, 226, 0.5)"
                    stroke_col = "#EF4444"
                    stroke_w = "1"
                    stroke_dash = "2,2"
                    
                svg_str += f'<polygon points="{pts_str}" fill="{fill_col}" stroke="{stroke_col}" stroke-width="{stroke_w}" stroke-dasharray="{stroke_dash}">'
                svg_str += f'<title>{title_tooltip}</title>'
                svg_str += '</polygon>'
                polygons_drawn += 1
                
    # Check if empty
    if polygons_drawn == 0:
        svg_str += f'<text x="{view_w/2}" y="{view_h/2}" font-size="16px" fill="#94A3B8" font-family="sans-serif" font-weight="600" text-anchor="middle" dominant-baseline="middle">Empty View</text>'
                
    # 4. Draw outer border of the block
    svg_str += f'<rect x="0" y="0" width="{view_w}" height="{view_h}" fill="none" stroke="#1E293B" stroke-width="2.5" rx="3" />'
    
    # 5. Add direct label overlay with sizes
    svg_str += f'<text x="5" y="{view_h - 6}" font-size="max(8px, {view_h * 0.05:.1f}px)" fill="#475569" font-weight="600" opacity="0.85">{view_w:.0f}×{view_h:.0f} mm</text>'
    
    svg_str += '</svg>'
    return svg_str


def get_block_svg_html(block, block_code):
    L, W, H = block.size
    efficiency = block.get_efficiency()
    volume = block.volume
    
    sides = ['Front', 'Back', 'Left', 'Right', 'Top', 'Bottom']
    svgs = {side: generate_svg_for_block_side(block, side) for side in sides}
    
    colors_palette = ["#4F46E5", "#10B981", "#F59E0B", "#EC4899", "#3B82F6", "#8B5CF6", "#EF4444", "#06B6D4"]
    legend_items = []
    seen_codes = set()
    if block.prism_details:
        for detail in block.prism_details:
            prism_code = getattr(detail['prism'], 'code', 'Part')
            prism_code_clean = str(prism_code).strip()
            if prism_code_clean not in seen_codes:
                seen_codes.add(prism_code_clean)
                sum_chars = sum((i + 1) * ord(c) for i, c in enumerate(prism_code_clean))
                color = colors_palette[sum_chars % len(colors_palette)]
                legend_items.append((prism_code_clean, color))
                
    has_scraps = len(block.scraps) > 0
    legend_html = ""
    if legend_items or has_scraps:
        legend_html = '<div class="legend-container" style="display: flex; gap: 16px; margin: 0 auto 24px auto; max-width: 1400px; flex-wrap: wrap; align-items: center; justify-content: center; background: #ffffff; padding: 12px 24px; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">'
        legend_html += '<span style="font-size: 12px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-right: 4px;">Color Legend:</span>'
        for code, color in legend_items:
            legend_html += f"""
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="width: 16px; height: 16px; background-color: {color}; border-radius: 4px; display: inline-block; border: 1px solid rgba(0,0,0,0.15);"></span>
                <span style="font-size: 13px; font-weight: 600; color: #334155;">{code}</span>
            </div>
            """
        if has_scraps:
            legend_html += """
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="width: 16px; height: 16px; background-color: rgba(239, 68, 68, 0.35); border: 1.5px dashed #EF4444; border-radius: 4px; display: inline-block;"></span>
                <span style="font-size: 13px; font-weight: 600; color: #334155;">Scrap</span>
            </div>
            """
        legend_html += '</div>'

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Block {block_code} - 6-Side Views</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: #f8fafc;
            margin: 0;
            padding: 20px;
            color: #1e293b;
        }}
        .header {{
            text-align: center;
            margin-bottom: 24px;
        }}
        .header h1 {{
            font-size: 24px;
            font-weight: 700;
            color: #0f172a;
            margin: 0 0 6px 0;
        }}
        .header p {{
            font-size: 14px;
            color: #64748b;
            margin: 0;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }}
        .card {{
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 16px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .title {{
            font-size: 14px;
            font-weight: 600;
            color: #475569;
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .plot-container {{
            width: 100%;
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        @media (max-width: 900px) {{
            .grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}
        @media (max-width: 600px) {{
            .grid {{
                grid-template-columns: 1fr;
            }}
        }}
        .zoom-controls {{
            position: fixed;
            bottom: 30px;
            right: 30px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            z-index: 1000;
        }}
        .zoom-btn {{
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: white;
            border: none;
            border-radius: 50%;
            width: 44px;
            height: 44px;
            font-size: 20px;
            cursor: pointer;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
        }}
        .zoom-btn:hover {{ background: #334155; transform: scale(1.1); }}
        @media print {{
            .zoom-controls {{ display: none !important; }}
        }}
    </style>
</head>
<body>
    <div class="zoom-controls">
        <button class="zoom-btn" onclick="zoomPage(0.1)" title="Zoom In">➕</button>
        <button class="zoom-btn" onclick="resetZoom()" title="Reset Zoom">🏠</button>
        <button class="zoom-btn" onclick="zoomPage(-0.1)" title="Zoom Out">➖</button>
    </div>
    
    <div id="zoomable-content" style="transform-origin: top left; transition: transform 0.1s; will-change: transform;">
    
    <div class="header">
        <h1>Block {block_code} - 6-Side Views</h1>
        <p>Size: {L:.0f} × {W:.0f} × {H:.0f} mm | Efficiency: {efficiency:.2f}% | Volume: {volume:,.0f} mm³</p>
    </div>
    {legend_html}
    <div class="grid">
"""
    for side in sides:
        html += f"""
        <div class="card">
            <div class="title">{side} View</div>
            <div class="plot-container">
                {svgs[side]}
            </div>
        </div>
"""
    
    html += """
    </div>
    </div>
    <script>
        let currentZoom = 1;
        let pannedX = 0;
        let pannedY = 0;
        let isDragging = false;
        let startX, startY;
        
        const el = document.getElementById('zoomable-content');
        
        function updateTransform() {
            el.style.transform = `translate(${pannedX}px, ${pannedY}px) scale(${currentZoom})`;
        }
        
        function zoomPage(delta) {
            currentZoom += delta;
            if (currentZoom < 0.2) currentZoom = 0.2;
            updateTransform();
        }
        
        function resetZoom() {
            currentZoom = 1;
            pannedX = 0;
            pannedY = 0;
            updateTransform();
        }
        
        document.addEventListener('mousedown', (e) => {
            if (e.target.closest('.zoom-btn') || e.target.closest('.print-button')) return;
            isDragging = true;
            startX = e.clientX - pannedX;
            startY = e.clientY - pannedY;
            document.body.style.cursor = 'grabbing';
            // Optional: prevent default if you don't want text selection while dragging
            // e.preventDefault(); 
        });
        
        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            pannedX = e.clientX - startX;
            pannedY = e.clientY - startY;
            updateTransform();
        });
        
        document.addEventListener('mouseup', () => {
            isDragging = false;
            document.body.style.cursor = 'auto';
        });
        
        document.addEventListener('mouseleave', () => {
            isDragging = false;
            document.body.style.cursor = 'auto';
        });
    </script>
</body>
</html>
"""
    return html


def get_scrap_svg_html(scrap, scrap_code):
    parent = scrap.parent_block
    L, W, H = parent.size
    
    sides = ['Front', 'Back', 'Left', 'Right', 'Top', 'Bottom']
    svgs = {side: generate_svg_for_block_side(parent, side, highlight_scrap=scrap, draw_prisms=False) for side in sides}
    
    legend_html = f"""
    <div class="legend-container" style="display: flex; gap: 16px; margin: 0 auto 24px auto; max-width: 1400px; flex-wrap: wrap; align-items: center; justify-content: center; background: #ffffff; padding: 12px 24px; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">
        <div style="display: flex; align-items: center; gap: 8px;">
            <span style="width: 16px; height: 16px; background-color: rgba(239, 68, 68, 0.5); border: 2px solid #EF4444; border-radius: 4px; display: inline-block;"></span>
            <span style="font-size: 13px; font-weight: 600; color: #334155;">Selected Scrap</span>
        </div>
    </div>
    """

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Scrap {scrap_code} - Parent Block Views</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: #f8fafc;
            margin: 0;
            padding: 20px;
            color: #1e293b;
        }}
        .header {{
            text-align: center;
            margin-bottom: 24px;
        }}
        .header h1 {{
            font-size: 24px;
            font-weight: 700;
            color: #0f172a;
            margin: 0 0 6px 0;
        }}
        .header p {{
            font-size: 14px;
            color: #64748b;
            margin: 0;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }}
        .card {{
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 16px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .title {{
            font-size: 14px;
            font-weight: 600;
            color: #475569;
            margin-bottom: 12px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .plot-container {{
            width: 100%;
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        @media (max-width: 900px) {{
            .grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
        }}
        @media (max-width: 600px) {{
            .grid {{
                grid-template-columns: 1fr;
            }}
        }}
        .zoom-controls {{
            position: fixed;
            bottom: 30px;
            right: 30px;
            display: flex;
            flex-direction: column;
            gap: 12px;
            z-index: 1000;
        }}
        .zoom-btn {{
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: white;
            border: none;
            border-radius: 50%;
            width: 44px;
            height: 44px;
            font-size: 20px;
            cursor: pointer;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s;
        }}
        .zoom-btn:hover {{ background: #334155; transform: scale(1.1); }}
        @media print {{
            .zoom-controls {{ display: none !important; }}
        }}
    </style>
</head>
<body>
    <div class="zoom-controls">
        <button class="zoom-btn" onclick="zoomPage(0.1)" title="Zoom In">➕</button>
        <button class="zoom-btn" onclick="resetZoom()" title="Reset Zoom">🏠</button>
        <button class="zoom-btn" onclick="zoomPage(-0.1)" title="Zoom Out">➖</button>
    </div>
    
    <div id="zoomable-content" style="transform-origin: top left; transition: transform 0.1s; will-change: transform;">
    
    <div class="header">
        <h1>Scrap {scrap_code} Location in Parent Block</h1>
        <p>Parent Block Size: {L:.0f} × {W:.0f} × {H:.0f} mm | Scrap Volume: {scrap.volume:,.0f} mm³</p>
    </div>
    {legend_html}
    <div class="grid">
"""
    for side in sides:
        html += f"""
        <div class="card">
            <div class="title">{side} View</div>
            <div class="plot-container">
                {svgs[side]}
            </div>
        </div>
"""
    
    html += """
    </div>
    </div>
    <script>
        let currentZoom = 1;
        let pannedX = 0;
        let pannedY = 0;
        let isDragging = false;
        let startX, startY;
        
        const el = document.getElementById('zoomable-content');
        
        function updateTransform() {
            el.style.transform = `translate(${pannedX}px, ${pannedY}px) scale(${currentZoom})`;
        }
        
        function zoomPage(delta) {
            currentZoom += delta;
            if (currentZoom < 0.2) currentZoom = 0.2;
            updateTransform();
        }
        
        function resetZoom() {
            currentZoom = 1;
            pannedX = 0;
            pannedY = 0;
            updateTransform();
        }
        
        document.addEventListener('mousedown', (e) => {
            if (e.target.closest('.zoom-btn') || e.target.closest('.print-button')) return;
            isDragging = true;
            startX = e.clientX - pannedX;
            startY = e.clientY - pannedY;
            document.body.style.cursor = 'grabbing';
            // Optional: prevent default if you don't want text selection while dragging
            // e.preventDefault(); 
        });
        
        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            pannedX = e.clientX - startX;
            pannedY = e.clientY - startY;
            updateTransform();
        });
        
        document.addEventListener('mouseup', () => {
            isDragging = false;
            document.body.style.cursor = 'auto';
        });
        
        document.addEventListener('mouseleave', () => {
            isDragging = false;
            document.body.style.cursor = 'auto';
        });
    </script>
</body>
</html>
"""
    return html


def get_block_svg_3d_html(block, block_code, highlight_scrap=None, only_scrap=False):
    # Ensure block size
    L, W, H = block.size
    
    # Block global min coordinates (to offset prisms)
    block_x_min = min(v[0] for v in block.box_coordinate)
    block_y_min = min(v[1] for v in block.box_coordinate)
    block_z_min = min(v[2] for v in block.box_coordinate)
    
    # Isometric scale factor
    # Translate and scale to view space.
    # Camera is situated looking from (1.5, -1.8, 1.2) direction down along (1, -1.2, 1) vector.
    # Let's project vertex:
    def project_vertex_3d(v_coord):
        x_raw = v_coord[0] - block_x_min
        y_raw = v_coord[1] - block_y_min
        z_raw = v_coord[2] - block_z_min
        
        # Orthographic projections
        # u = x_raw * cos(30) - y_raw * cos(30)
        # v = x_raw * sin(30) + y_raw * sin(30) - z_raw
        cos_30 = 0.866025
        sin_30 = 0.5
        u = cos_30 * x_raw - cos_30 * y_raw
        v = sin_30 * x_raw + sin_30 * y_raw - z_raw
        
        # depth along view direction (1.5, -1.8, 1.2) -> larger value is closer
        depth = 1.5 * x_raw - 1.8 * y_raw + 1.2 * z_raw
        return u, v, depth

    # We want to find the min and max u, v coordinates of the container (to set the viewBox)
    container_coords = [
        [0, 0, 0], [L, 0, 0], [L, W, 0], [0, W, 0],
        [0, 0, H], [L, 0, H], [L, W, H], [0, W, H]
    ]
    projected_container = [project_vertex_3d(vc) for vc in container_coords]
    u_vals = [p[0] for p in projected_container]
    v_vals = [p[1] for p in projected_container]
    
    u_min, u_max = min(u_vals), max(u_vals)
    v_min, v_max = min(v_vals), max(v_vals)
    
    u_span = u_max - u_min
    v_span = v_max - v_min
    
    pad_u = u_span * 0.08 if u_span > 0 else 20
    pad_v = v_span * 0.08 if v_span > 0 else 20
    
    view_x = u_min - pad_u
    view_y = v_min - pad_v
    view_w = u_span + 2 * pad_u
    view_h = v_span + 2 * pad_v
    
    svg_h = 560
    svg_w = int(view_w / view_h * svg_h) if view_h > 0 else 800
    if svg_w > 900:
        svg_w = 900
        svg_h = int(view_h / view_w * svg_w)

    # Faces indices mapping
    faces_indices = [
        [0, 1, 2, 3], # Bottom
        [4, 5, 6, 7], # Top
        [0, 1, 5, 4], # Side 1 (Front-Left)
        [1, 2, 6, 5], # Side 2 (Front-Right)
        [2, 3, 7, 6], # Side 3 (Back-Right)
        [3, 0, 4, 7]  # Side 4 (Back-Left)
    ]
    
    # We will compute the projected coordinates for all parts, scraps and container
    faces_to_draw = []
    
    # Helper to calculate hex color shading
    def shade_color(hex_color, factor):
        hex_color = hex_color.lstrip('#')
        if len(hex_color) != 6:
            return f"#{hex_color}"
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            r = min(255, max(0, int(r * factor)))
            g = min(255, max(0, int(g * factor)))
            b = min(255, max(0, int(b * factor)))
            return f"#{r:02X}{g:02X}{b:02X}"
        except:
            return f"#{hex_color}"

    # 1. ADD PARTS FACES
    colors = ["#4F46E5", "#10B981", "#F59E0B", "#EC4899", "#3B82F6", "#8B5CF6", "#EF4444", "#06B6D4"]
    
    # Gather colors per prism type
    unique_codes = []
    if block.prism_details:
        unique_codes = sorted(list(set(getattr(p_detail['prism'], 'code', 'Part') for p_detail in block.prism_details)))
    color_map = {code: colors[idx % len(colors)] for idx, code in enumerate(unique_codes)}
    
    # Opacity settings
    has_highlight = highlight_scrap is not None
    part_opacity = 0.15 if only_scrap else (0.25 if has_highlight else 0.85)

    if not only_scrap and block.prism_details:
        for detail in block.prism_details:
            prism = detail['prism']
            p_code = getattr(prism, 'code', 'Part')
            p_size_str = "x".join(f"{s:.0f}" for s in prism.size) if hasattr(prism, 'size') else ""
            title_tooltip = f"Part: {p_code} | Size: {p_size_str} mm"
            base_color = color_map.get(p_code, "#4F46E5")
            
            # Shaded colors for faces
            shaded_colors = {
                1: shade_color(base_color, 0.75),  # Side 1 (Front-Left)
                2: shade_color(base_color, 0.88),  # Side 2 (Front-Right)
                3: shade_color(base_color, 0.88),  # Side 3
                4: shade_color(base_color, 0.75),  # Side 4
                0: shade_color(base_color, 0.65),  # Bottom
                5: base_color                      # Top (Top faces unshaded)
            }
            
            for coords in detail['coordinates']:
                # Draw visible faces: Top face (5), Side 1 (2), Side 2 (3) (Wait, map face_idx from faces_indices list mapping above)
                # Bottom (0), Top (1), Side 1 (2), Side 2 (3), Side 3 (4), Side 4 (5)
                # Let's render visible faces: Top (1), Side 1 (2), Side 2 (3) page-facing
                visible_face_indices = [1, 2, 3] # top and front faces
                
                for face_idx in visible_face_indices:
                    face_vertex_indices = faces_indices[face_idx]
                    pts_proj = [project_vertex_3d(coords[vi]) for vi in face_vertex_indices]
                    
                    # Calculate center depth for sorting
                    avg_depth = sum(p[2] for p in pts_proj) / 4.0
                    pts_str = " ".join(f"{p[0]:.2f},{p[1]:.2f}" for p in pts_proj)
                    
                    # Shading based on face type
                    fill_color = shaded_colors.get(face_idx, base_color)
                    
                    faces_to_draw.append({
                        'depth': avg_depth,
                        'pts_str': pts_str,
                        'fill': fill_color,
                        'stroke': "rgba(255, 255, 255, 0.6)",
                        'stroke_width': "0.75",
                        'stroke_dasharray': "none",
                        'tooltip': title_tooltip,
                        'opacity': part_opacity
                    })

    # 2. ADD SCRAPS FACES
    for scrap in block.scraps:
        scrap_code = getattr(scrap, 'unique_code', 'Scrap')
        scrap_size_str = "x".join(f"{s:.0f}" for s in scrap.size) if hasattr(scrap, 'size') else ""
        title_tooltip = f"Scrap: {scrap_code} | Size: {scrap_size_str} mm"
        
        is_this_highlighted = has_highlight and (getattr(scrap, 'unique_code', '') == getattr(highlight_scrap, 'unique_code', ''))
        
        # Scraps are semi-transparent red
        if is_this_highlighted:
            scrap_fill = "rgba(239, 68, 68, 0.5)"
            scrap_stroke = "#EF4444"
            scrap_stroke_width = "2"
            scrap_stroke_dash = "none"
            scrap_op = 0.85
        else:
            scrap_fill = "rgba(239, 68, 68, 0.18)"
            scrap_stroke = "#EF4444"
            scrap_stroke_width = "1.2"
            scrap_stroke_dash = "2,2"
            scrap_op = 0.2 if has_highlight else (0.8 if only_scrap else 0.5)
            
        # Draw visible faces: Top (1), Side 1 (2), Side 2 (3)
        for face_idx in [1, 2, 3]:
            face_vertex_indices = faces_indices[face_idx]
            pts_proj = [project_vertex_3d(scrap.box_coordinate[vi]) for vi in face_vertex_indices]
            
            avg_depth = sum(p[2] for p in pts_proj) / 4.0
            pts_str = " ".join(f"{p[0]:.2f},{p[1]:.2f}" for p in pts_proj)
            
            faces_to_draw.append({
                'depth': avg_depth,
                'pts_str': pts_str,
                'fill': scrap_fill,
                'stroke': scrap_stroke,
                'stroke_width': scrap_stroke_width,
                'stroke_dasharray': scrap_stroke_dash,
                'tooltip': title_tooltip,
                'opacity': scrap_op
            })

    # Sort faces by depth back-to-front
    faces_to_draw.sort(key=lambda x: x['depth'])

    # Build container boundaries:
    # We project the container box vertices
    proj_container_pts = [project_vertex_3d(vc) for vc in container_coords]
    
    # Helper to generate SVG poly string from container indices
    def get_container_face_pts(indices):
        return " ".join(f"{proj_container_pts[i][0]:.2f},{proj_container_pts[i][1]:.2f}" for i in indices)
        
    # The back-facing container walls (rendered in background of everything)
    # Bottom: 0,1,2,3; Side 3 (back-right): 2,3,7,6; Side 4 (back-left): 3,0,4,7
    container_bg_svg = ""
    container_bg_svg += f'  <polygon points="{get_container_face_pts([0, 1, 2, 3])}" fill="#1e293b" stroke="#334155" stroke-dasharray="none" stroke-width="1.5" />\n'
    container_bg_svg += f'  <polygon points="{get_container_face_pts([3, 0, 4, 7])}" fill="#0f172a" stroke="#334155" stroke-width="1.5" />\n'
    container_bg_svg += f'  <polygon points="{get_container_face_pts([2, 3, 7, 6])}" fill="#0f172a" stroke="#334155" stroke-width="1.5" />\n'
    
    # Optional grid floor lines to give scale/depth
    grid_lines_svg = ""
    # Parallel lines in X direction along bottom face
    for pos in range(100, int(L), 100):
        p_start = project_vertex_3d([pos, 0, 0])
        p_end = project_vertex_3d([pos, W, 0])
        grid_lines_svg += f'  <line x1="{p_start[0]:.2f}" y1="{p_start[1]:.2f}" x2="{p_end[0]:.2f}" y2="{p_end[1]:.2f}" stroke="#334155" stroke-dasharray="2,2" stroke-width="0.75" />\n'
    # Parallel lines in Y direction along bottom face
    for pos in range(100, int(W), 100):
        p_start = project_vertex_3d([0, pos, 0])
        p_end = project_vertex_3d([L, pos, 0])
        grid_lines_svg += f'  <line x1="{p_start[0]:.2f}" y1="{p_start[1]:.2f}" x2="{p_end[0]:.2f}" y2="{p_end[1]:.2f}" stroke="#334155" stroke-dasharray="2,2" stroke-width="0.75" />\n'

    # Build the main faces SVG string
    faces_svg_markup = ""
    for face in faces_to_draw:
        faces_svg_markup += f'  <polygon points="{face["pts_str"]}" fill="{face["fill"]}" stroke="{face["stroke"]}" stroke-width="{face["stroke_width"]}" stroke-dasharray="{face["stroke_dasharray"]}" opacity="{face["opacity"]}">\n'
        faces_svg_markup += f'    <title>{face["tooltip"]}</title>\n'
        faces_svg_markup += f'  </polygon>\n'

    # The front outline of the container (drawn OVER everything to encapsulate/frame the active contents)
    container_fg_svg = ""
    
    # Front wireframes
    front_edges = [
        (0, 1), (1, 2), # bottom edges
        (0, 4), (1, 5), (2, 6), # verticals
        (4, 5), (5, 6)  # top edges
    ]
    for e in front_edges:
        start_pt = proj_container_pts[e[0]]
        end_pt = proj_container_pts[e[1]]
        container_fg_svg += f'  <line x1="{start_pt[0]:.2f}" y1="{start_pt[1]:.2f}" x2="{end_pt[0]:.2f}" y2="{end_pt[1]:.2f}" stroke="#64748b" stroke-width="2" stroke-linecap="round" />\n'

    # Generate final self-contained SVG
    svg_str = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view_x} {view_y} {view_w} {view_h}" width="{svg_w}" height="{svg_h}" style="max-width: 100%; height: auto;">\n'
    svg_str += f'  <!-- Container Background Walls -->\n'
    svg_str += container_bg_svg
    svg_str += f'  <!-- Grid lines on Floor -->\n'
    svg_str += grid_lines_svg
    svg_str += f'  <!-- Packed Parts & Scraps sorted back-to-front -->\n'
    svg_str += faces_svg_markup
    svg_str += f'  <!-- Container Front Wireframe Outline -->\n'
    svg_str += container_fg_svg
    svg_str += '</svg>\n'

    # Generate HTML content wrapper
    efficiency = block.get_efficiency()
    volume = block.volume
    
    legend_html = ""
    if not only_scrap and unique_codes:
        legend_html += '<div class="legend-container">'
        for code in unique_codes:
            col = color_map.get(code, "#4F46E5")
            legend_html += f'<div class="legend-item"><span class="legend-color" style="background-color: {col};"></span><span class="legend-text">{code}</span></div>'
        legend_html += '<div class="legend-item"><span class="legend-color" style="background-color: rgba(239, 68, 68, 0.45); border: 1px dashed #EF4444;"></span><span class="legend-text">Scrap</span></div>'
        legend_html += '</div>'
    elif only_scrap:
        legend_html += '<div class="legend-container">'
        legend_html += '<div class="legend-item"><span class="legend-color" style="background-color: rgba(239, 68, 68, 0.6); border: 1.5px solid #EF4444;"></span><span class="legend-text">Selected Scrap</span></div>'
        legend_html += '</div>'

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>3D Orthographic View - Block {block_code}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: #0f172a;
            margin: 0;
            padding: 16px;
            color: #f8fafc;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            box-sizing: border-box;
        }}
        .card {{
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 16px;
            width: 100%;
            max-width: 950px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5);
            padding: 24px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .header {{
            width: 100%;
            text-align: center;
            margin-bottom: 20px;
            border-bottom: 1px solid #334155;
            padding-bottom: 16px;
        }}
        .header h1 {{
            font-size: 20px;
            font-weight: 700;
            margin: 0 0 6px 0;
            color: #f8fafc;
            letter-spacing: -0.025em;
        }}
        .header p {{
            font-size: 13px;
            color: #94a3b8;
            margin: 0;
        }}
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            background: #3b82f633;
            color: #60a5fa;
            margin-top: 6px;
        }}
        .badge-efficiency {{
            background: #10b98133;
            color: #34d399;
        }}
        .plot-wrapper {{
            width: 100%;
            background: #1e293b;
            border-radius: 12px;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 10px;
        }}
        .legend-container {{
            display: flex;
            flex-wrap: wrap;
            gap: 16px;
            justify-content: center;
            margin-top: 20px;
            padding-top: 16px;
            border-top: 1px solid #334155;
            width: 100%;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .legend-color {{
            width: 14px;
            height: 14px;
            border-radius: 4px;
            display: inline-block;
        }}
        .legend-text {{
            font-size: 12px;
            color: #cbd5e1;
            font-weight: 500;
        }}
        @media print {{
            body {{
                background: white;
                color: black;
                padding: 0;
            }}
            .card {{
                background: white;
                border: none;
                box-shadow: none;
                padding: 0;
                color: black;
            }}
            .header h1 {{
                color: black;
            }}
            .header p {{
                color: #475569;
            }}
            .badge {{
                border: 1px solid #cbd5e1;
                background: transparent;
                color: black;
            }}
            .legend-text {{
                color: black;
            }}
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="header">
            <h1>{"Scrap Location View" if only_scrap else "Block Packing 3D Isometric View"} (Block {block_code})</h1>
            <p>Size: {L:.0f} &times; {W:.0f} &times; {H:.0f} mm &nbsp;|&nbsp; Volume: {volume:,.0f} mm&sup3;</p>
            <span class="badge badge-efficiency">Efficiency: {efficiency:.2f}%</span>
        </div>
        <div class="plot-wrapper">
            {svg_str}
        </div>
        {legend_html}
    </div>
</body>
</html>
"""
    return html

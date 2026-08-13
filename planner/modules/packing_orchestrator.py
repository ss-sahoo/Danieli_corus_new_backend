"""
Complete Packing Orchestrator Module
Converts Jupyter notebook logic into production-ready Python code
"""

import math
import numpy as np
import pandas as pd
import json
from contextlib import contextmanager
from typing import List, Dict, Tuple, Optional, Any

# Import from fill module (ensure this exists in your project)
from .fill import fill_the_box, draw, get_scrap_vol

# Tolerance for treating two solids as touching rather than overlapping (mm).
OVERLAP_TOL = 1e-4


# ---------------------------------------------------------------------------
# Part-type processing order
# ---------------------------------------------------------------------------
# run_optimization_with_retries processes part types largest-volume-first. That single
# choice is worth about 13 points of efficiency on Sample_data_03 - volume-ascending
# scores 66.8% where volume-descending scores 80.4% - so it is the most sensitive knob
# in the pipeline, and it has never been varied.
#
# Volume-descending is the best of the obvious orderings, but it is not optimal: small
# perturbations of it beat it by up to +0.3 points. The deep optimisation searches those
# perturbations. A perturbation is identified by an integer seed so the winning order can
# be reproduced exactly on the final run; seed 0 (or None) is plain volume-descending.

PRISM_ORDER_SEED = None


# ---------------------------------------------------------------------------
# Lookahead block selection
# ---------------------------------------------------------------------------
# check_which_block_to_add scores a candidate stock size by how many of the ONE part
# triggering the block fit in it. That is myopic: most of a block's value is in what its
# leftover slab is worth to the part types packed after it, and the plain metric cannot
# see that. It is the reason offering an extra size can make a result worse - a 12%
# smaller block that packs the same count wins on paper while giving up the headroom a
# later part needed.
#
# With lookahead on, a candidate is scored by the total part volume it is expected to
# yield: the current part, plus what the other outstanding part types can take out of the
# scrap this packing would leave. Measured on Sample_data_03 with all five sizes offered:
# 78.67% -> 80.59%, 796 -> 706 blocks, for about 2.3x the packing time.
#
# Off by default. The deep optimisation turns it on; the quick endpoint is unchanged.

LOOKAHEAD_SELECTION = False
LOOKAHEAD_TOP_K = 6        # how many other pending part types to try in the leftovers
LOOKAHEAD_MAX_SCRAPS = 6   # how many of the largest leftover boxes to try them in


@contextmanager
def lookahead_selection(enabled: bool = True, top_k: int = None, max_scraps: int = None):
    """
    Score candidate blocks by total yield rather than by the current part alone.

    Module state for the same reason as prism_order and fill.exhaustive_decomposition:
    the decision happens deep inside the packing loop. Not thread-safe.
    """
    global LOOKAHEAD_SELECTION, LOOKAHEAD_TOP_K, LOOKAHEAD_MAX_SCRAPS
    previous = (LOOKAHEAD_SELECTION, LOOKAHEAD_TOP_K, LOOKAHEAD_MAX_SCRAPS)
    LOOKAHEAD_SELECTION = enabled
    if top_k is not None:
        LOOKAHEAD_TOP_K = top_k
    if max_scraps is not None:
        LOOKAHEAD_MAX_SCRAPS = max_scraps
    try:
        yield
    finally:
        LOOKAHEAD_SELECTION, LOOKAHEAD_TOP_K, LOOKAHEAD_MAX_SCRAPS = previous

# Largest number of adjacent transpositions a perturbation may apply. Past roughly this
# many the order stops resembling volume-descending and the result degrades toward the
# random-shuffle score (77%).
MAX_ORDER_SWAPS = 8


def prioritise_constrained_parts(prisms: List['Prisms'],
                                 parent_block_sizes: List[List[float]],
                                 parent_block_quantities: List[Optional[int]],
                                 rotation_axis: List[List[str]] = None) -> List['Prisms']:
    """
    Move parts that depend entirely on quota-limited stock to the front of the queue.

    Without this, a part with no alternative can be starved by a part that had one.
    `check_which_block_to_add` prefers limited sizes (tier 0) so that owned stock is used
    before more is bought, and parts are processed largest-volume-first. Together those two
    rules let a big, flexible part spend a scarce size it merely *likes* before a smaller
    part that can use nothing else ever gets a turn:

        A, B unlimited; C limited to 2. BIG fits A, B and C. G2 fits only C.
        BIG is larger, so it goes first, takes both C blocks, and G2 packs 2 of 40.

    The test is "has no unlimited fitting size", not "fits exactly one size": a part that
    fits two limited sizes is equally exposed, while a part that fits a limited size and an
    unlimited one is not exposed at all.

    The sort is stable and only lifts the exposed parts, so volume-descending order is
    preserved within both groups. When no size carries a quantity, nothing is exposed and
    the order is returned untouched - which is why this cannot affect an ordinary run.
    """
    if not parent_block_quantities or all(q is None for q in parent_block_quantities):
        return prisms

    unlimited = [i for i, q in enumerate(parent_block_quantities) if q is None]

    def depends_on_scarce_stock(prism):
        fits_unlimited = False
        fits_anything = False
        for i, size in enumerate(parent_block_sizes):
            block = Block('probe', list(size), start_coord=[0, 0, 0])
            if not block.can_fit_with_rotation(prism, rotation_axis)[0]:
                continue
            fits_anything = True
            if i in unlimited:
                fits_unlimited = True
                break
        # A part that fits nothing is not competing for stock; it is reported as a
        # shortfall either way, and promoting it would only reorder the queue for nothing.
        return fits_anything and not fits_unlimited

    exposed = [p for p in prisms if depends_on_scarce_stock(p)]
    if not exposed:
        return prisms

    exposed_ids = {id(p) for p in exposed}
    rest = [p for p in prisms if id(p) not in exposed_ids]
    print(f"[ORDER] {len(exposed)} part type(s) depend only on limited stock, "
          f"packing first: {[p.code for p in exposed]}")

    return exposed + rest


def perturb_prism_order(prisms: List['Prisms'], seed: Optional[int]) -> List['Prisms']:
    """
    Nudge a volume-descending ordering without destroying it.

    Adjacent transpositions only: they reorder neighbours of similar volume and leave the
    big-parts-first structure intact. A full shuffle is a different, much worse ordering,
    not a perturbation of this one.
    """
    if not seed:
        return prisms

    import random
    rnd = random.Random(seed)
    out = list(prisms)
    if len(out) < 2:
        return out

    for _ in range(rnd.randint(1, MAX_ORDER_SWAPS)):
        i = rnd.randrange(len(out) - 1)
        out[i], out[i + 1] = out[i + 1], out[i]

    return out


@contextmanager
def prism_order(seed: Optional[int]):
    """
    Run the packer with a specific ordering perturbation.

    Module state rather than an argument, for the same reason as fill.exhaustive_decomposition:
    the ordering is applied inside run_optimization_with_retries and threading it through
    every caller would touch the whole request path. Not thread-safe.
    """
    global PRISM_ORDER_SEED
    previous = PRISM_ORDER_SEED
    PRISM_ORDER_SEED = seed
    try:
        yield
    finally:
        PRISM_ORDER_SEED = previous


def get_prism_color_mapping(block):
    """
    Generate a deterministic, collision-free color mapping and legend items for a block.
    
    Returns:
        color_map: dict mapping prism_code -> color
        legend_items: list of (legend_label, color, is_scrap)
        label_map: dict mapping prism_code -> label (which is just the prism_code)
    """
    colors_palette = [
        "#4F46E5", "#10B981", "#F59E0B", "#EC4899", "#3B82F6", "#8B5CF6", "#06B6D4", "#F97316",
        "#84CC16", "#14B8A6", "#D946EF", "#0EA5E9", "#A855F7", "#E11D48", "#6366F1", "#059669",
        "#D97706", "#DB2777", "#2563EB", "#7C3AED", "#EA580C", "#65A30D", "#0D9488", "#C084FC",
        "#818CF8", "#34D399", "#FBBF24", "#F472B6", "#60A5FA", "#A78BFA", "#fb923c", "#a3e635",
        "#2dd4bf", "#38bdf8", "#1e1b4b", "#064e3b", "#78350f", "#50072b", "#1e3a8a", "#3b0764",
        "#083344", "#431407"
    ]
    
    # 1. Gather all unique part codes in a deterministic order
    # If parent_helper is present, we loop through all blocks in the job to number globally.
    helper = getattr(block, 'parent_helper', None)
    unique_codes = set()
    
    if helper and getattr(helper, 'all_big_blocks', None):
        for b in helper.all_big_blocks:
            if getattr(b, 'prism_details', None):
                for detail in b.prism_details:
                    p_code = getattr(detail['prism'], 'code', 'Part')
                    unique_codes.add(str(p_code).strip())
    else:
        if getattr(block, 'prism_details', None):
            for detail in block.prism_details:
                p_code = getattr(detail['prism'], 'code', 'Part')
                unique_codes.add(str(p_code).strip())
                
    # Sort the part codes deterministically to make color assignment stable
    def code_sort_key(code):
        try:
            import re
            numeric_part = int(re.search(r'\d+', code).group())
        except:
            numeric_part = 999999
        return (numeric_part, code)
        
    sorted_codes = sorted(list(unique_codes), key=code_sort_key)
    
    # 2. Assign unique color from palette to each part code
    import colorsys
    import random
    
    n_needed = len(sorted_codes)
    assigned_colors = list(colors_palette)
    
    # If we need more than our base premium palette, dynamically generate distinct ones using HSL Golden Ratio spacing
    if n_needed > len(colors_palette):
        h = 0.0
        golden_ratio_conjugate = 0.618033988749895
        while len(assigned_colors) < n_needed:
            h = (h + golden_ratio_conjugate) % 1.0
            l = 0.55 if len(assigned_colors) % 2 == 0 else 0.40
            s = 0.75
            r, g, b_val = colorsys.hls_to_rgb(h, l, s)
            hex_color = f"#{int(r*255):02X}{int(g*255):02X}{int(b_val*255):02X}"
            if hex_color not in assigned_colors:
                assigned_colors.append(hex_color)
                
    # Deterministically shuffle the codes using a fixed seed (101) so that
    # alphabetically-consecutive codes (like T35A vs T39B) do not end up
    # with adjacent and similar colors from the palette.
    shuffled_codes = list(sorted_codes)
    random.Random(101).shuffle(shuffled_codes)
    
    color_map = {}
    label_map = {}
    for i, code in enumerate(shuffled_codes):
        color_map[code] = assigned_colors[i]
        label_map[code] = code
        
    # 3. Generate legend items for this block (only for part codes actually present in this block)
    block_legend_items = []
    seen_codes = set()
    
    if getattr(block, 'prism_details', None):
        for detail in block.prism_details:
            p_code = getattr(detail['prism'], 'code', 'Part')
            p_code_clean = str(p_code).strip()
            if p_code_clean not in seen_codes:
                seen_codes.add(p_code_clean)
                
    # Keep legend ordered by sorted_codes
    for code in sorted_codes:
        if code in seen_codes:
            block_legend_items.append((code, color_map[code], False))
            
    return color_map, block_legend_items, label_map


def aabb(points) -> Tuple[np.ndarray, np.ndarray]:
    """Axis-aligned bounding box of a list of 3D points, as (min_corner, max_corner)."""
    arr = np.asarray(points, dtype=float)
    return arr.min(axis=0), arr.max(axis=0)


def boxes_overlap(lo_a, hi_a, lo_b, hi_b, tol: float = OVERLAP_TOL) -> bool:
    """True if two axis-aligned boxes share interior volume (touching faces do not count)."""
    return bool((np.minimum(hi_a, hi_b) - np.maximum(lo_a, lo_b)).min() > tol)


class Prisms:
    """Represents a trapezoidal prism with dimensions and quantity"""
    
    def __init__(self, code: str, size: List[float], quantity: int, roundingoff: int = 2):
        """
        Initialize a prism
        
        Args:
            code: Prism identifier (e.g., 'G14')
            size: [bottom_length, top_length, width, height] or [length, width, height]
            quantity: Number of prisms needed
            roundingoff: Decimal places for rounding angles
        """
        self.code = code
        self.quantity = quantity
        self.prism_left = quantity
        self.roundingoff = roundingoff
        
        # Handle size array
        if len(size) == 4:
            self.size = size
        elif len(size) == 3:
            # If rectangular (3 dimensions), set bottom = top length
            self.size = [size[0], size[0], size[1], size[2]]
        else:
            raise ValueError(f'Invalid size dimensions for prism {code}: {size}')
        
        self.bottom_length = self.size[0]
        self.top_length = self.size[1]
        self.width = self.size[2]
        self.height = self.size[3]
        self.angle = self.angle_from_height_length()
        
        # Calculate volume: V = 0.5 * (b1 + b2) * w * h
        self.volume = 0.5 * (self.bottom_length + self.top_length) * self.width * self.height
    
    def angle_from_height_length(self) -> float:
        """Calculate the angle of the trapezoid from height and length difference"""
        height = self.height
        length_diff = (self.bottom_length - self.top_length) / 2
        
        if height == 0:
            return 0.0
        
        angle_rad = math.atan(length_diff / height)
        angle_deg = math.degrees(angle_rad)
        return np.round(angle_deg, self.roundingoff)
    
    def update_prism_left(self, used_quantity: int):
        """Update the remaining prism count after packing"""
        self.prism_left = max(0, self.prism_left - used_quantity)
    
    def get_volume(self) -> float:
        """Get the volume of a single prism"""
        return self.volume


def wrap_plotly_fig_with_legend(fig, title, legend_items):
    fig.update_layout(title="")
    plotly_div = fig.to_html(full_html=False, include_plotlyjs='cdn')
    
    legend_html = ""
    if legend_items:
        legend_html = '<div class="legend-container" style="display: flex; gap: 16px; margin: 0 auto 20px auto; max-width: 900px; flex-wrap: wrap; align-items: center; justify-content: center; background: #ffffff; padding: 12px 24px; border-radius: 12px; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);">'
        legend_html += '<span style="font-size: 12px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-right: 4px;">Color Legend:</span>'
        for label, col, is_scrap in legend_items:
            if is_scrap:
                color_style = f"background-color: {col}; border: 1.5px dashed #EF4444; width: 14px; height: 14px; border-radius: 4px; display: inline-block;"
            else:
                color_style = f"background-color: {col}; border: 1px solid rgba(0,0,0,0.15); width: 14px; height: 14px; border-radius: 4px; display: inline-block;"
            legend_html += f"""
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="{color_style}"></span>
                <span style="font-size: 13px; font-weight: 600; color: #334155;">{label}</span>
            </div>
            """
        legend_html += '</div>'
        
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: #f8fafc;
            margin: 0;
            padding: 24px 16px;
            color: #1e293b;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            box-sizing: border-box;
        }}
        .card {{
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 16px;
            width: 100%;
            max-width: 950px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05),  0 8px 10px -6px rgba(0, 0, 0, 0.05);
            padding: 24px;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .header {{
            width: 100%;
            text-align: center;
            margin-bottom: 20px;
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 16px;
        }}
        .header h1 {{
            font-size: 20px;
            font-weight: 700;
            margin: 0 0 6px 0;
            color: #0f172a;
            letter-spacing: -0.025em;
        }}
        .plot-wrapper {{
            width: 100%;
            background: #ffffff;
            border-radius: 12px;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 10px;
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
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="header">
            <h1>{title}</h1>
        </div>
        {legend_html}
        <div class="plot-wrapper">
            {plotly_div}
        </div>
    </div>
</body>
</html>
"""
    return html


class Block:
    """Represents a stock block that can contain prisms"""
    
    def __init__(self, unique_code: str, size: List[float], start_coord: List[float] = None):
        """
        Initialize a block
        
        Args:
            unique_code: Unique identifier (e.g., 'B1')
            size: [length, width, height]
            start_coord: Starting coordinate [x, y, z]
        """
        self.unique_code = unique_code
        self.size = size
        self.start_coord = start_coord or [0, 0, 0]
        self.volume = size[0] * size[1] * size[2]
        self.place_box()
        
        self.scraps = []  # List of Scrap objects
        self.prism_details = []  # List of {prism, coordinates}
        self.all_prisms_coordinates = []

        # A recovered block is a physical offcut pulled back out of ScrapInventory rather
        # than new stock. It packs exactly like a bought block, but it must not be counted
        # as material purchased, so efficiency and block counts exclude it. See
        # People_helper.add_recovered_block.
        self.is_recovered = False
        self.source_scrap_id = None
    
    def add_scrap(self, scrap_obj):
        """Add a scrap piece to this block"""
        scrap_obj.parent_block = self
        self.scraps.append(scrap_obj)
    
    def add_prisms_coordinates(self, prism, coordinates: List):
        """Add prism placement information"""
        prism_detail = {'prism': prism, 'coordinates': coordinates}
        self.prism_details.append(prism_detail)
        self.all_prisms_coordinates.extend(coordinates)

    def occupied_bounds(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Bounding boxes of every prism placed in this block.

        Returns:
            (mins, maxs) as (N, 3) arrays; both are empty when nothing is placed yet.
        """
        if not self.all_prisms_coordinates:
            return np.empty((0, 3)), np.empty((0, 3))

        arr = np.asarray(self.all_prisms_coordinates, dtype=float)
        return arr.min(axis=1), arr.max(axis=1)

    def get_efficiency(self) -> float:
        """Calculate packing efficiency as percentage"""
        prism_volume = 0
        for prism_detail in self.prism_details:
            prism = prism_detail['prism']
            count = len(prism_detail['coordinates'])
            prism_volume += prism.volume * count
        
        if self.volume == 0:
            return 0.0
        
        eff = (prism_volume / self.volume) * 100
        return eff
    
    def can_fit_with_rotation(self, prism, rotation_axis: List[List[str]] = None) -> Tuple[bool, List[List[str]]]:
        """
        Check if prism can fit with various rotations
        
        Args:
            prism: Prism object to check
            rotation_axis: List of rotation sequences to try
        
        Returns:
            (can_fit, valid_rotations)
        """
        if rotation_axis is None:
            rotation_axis = [[], ['z'], ['z', 'x'], ['z', 'y'], ['x'], ['y']]
        
        rotation_axis_new = []
        
        if prism.volume > self.volume:
            return False, rotation_axis_new
        
        for axis_order in rotation_axis:
            if len(axis_order) > 0:
                rot = Rotation(axis_order=axis_order, pivot=self.start_coord)
                size = rot.get_new_lwh(self.size)
            else:
                size = self.size
            
            # Check if prism fits
            if (prism.bottom_length <= size[0] and 
                prism.width <= size[1] and
                prism.height <= size[2]):
                rotation_axis_new.append(axis_order)
        
        return len(rotation_axis_new) > 0, rotation_axis_new
    
    def place_box(self):
        """Calculate the 8 corner coordinates of the block"""
        length, width, height = self.size
        x, y, z = self.start_coord
        
        self.box_coordinate = [
            [x, y, z], 
            [x + length, y, z], 
            [x + length, y + width, z], 
            [x, y + width, z],
            [x, y, z + height], 
            [x + length, y, z + height], 
            [x + length, y + width, z + height], 
            [x, y + width, z + height]
        ]
    
    def draw_it(self, only_scrap=False, save_path=None):
        big_block_coordinate = self.box_coordinate
        co_ordinates_list = self.all_prisms_coordinates
        scrap_volumes = [s.box_coordinate for s in self.scraps]
        
        # Get consistent, collision-free color mapping for the job/block
        color_map, block_legend_items, legend_map = get_prism_color_mapping(self)
        
        prism_colors = []
        for detail in self.prism_details:
            prism_code = getattr(detail['prism'], 'code', 'Part')
            prism_code_clean = str(prism_code).strip()
            color = color_map.get(prism_code_clean, "#4F46E5")
            prism_colors.extend([color] * len(detail['coordinates']))
        
        legend_items = []
        if not only_scrap:
            legend_items.extend(block_legend_items)
                
        if only_scrap:
            legend_items.append(("Selected Scrap", "rgba(239, 68, 68, 0.5)", True))
        elif len(scrap_volumes) > 0:
            legend_items.append(("Scrap", "rgba(239, 68, 68, 0.2)", True))
    
        fig = draw(
            big_block_coordinate,
            [] if only_scrap else co_ordinates_list,
            x_edges=[],
            y_edges=[],
            z_edges=[],
            planes={"xy_planes": [], "zx_planes": [], "yz_planes": []},
            scrap_volumes=scrap_volumes,
            prism_colors=prism_colors
        )
        
        if save_path and fig:
            title = f"{'3D Scrap Location View' if only_scrap else 'Block Packing 3D Isometric View'} (Block {self.unique_code})"
            html_content = wrap_plotly_fig_with_legend(fig, title, legend_items)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(html_content)
                
        return fig


class Scrap(Block):
    """Represents a scrap piece left over from cutting"""
    
    def __init__(self, unique_code: str, size: List[float], start_coord: List[float]):
        super().__init__(unique_code, size, start_coord)
        self.parent_block = None
        # Where this piece came from. 'generated' means it is leftover space this run just
        # cut out of a stock block; 'inventory' means it is a physical offcut pulled off the
        # rack and offered as input stock. The run summary counts only 'inventory' pieces as
        # material consumed - a 'generated' scrap is already inside a stock block that has
        # been counted, so counting it again would double-count the same steel.
        self.origin = 'generated'
        self.inventory_scrap_id = None  # set when origin == 'inventory', matches ScrapInventory.scrap_id


    def delete_scrap(self):
        """Remove this scrap from its parent block"""
        if self.parent_block and self in self.parent_block.scraps:
            self.parent_block.scraps.remove(self)
    

    def draw_scrap(self, save_path=None):
        if not self.parent_block:
            raise RuntimeError("Scrap has no parent block")
            
        fig = draw(
            self.parent_block.box_coordinate,
            co_ordinates_list=[],
            x_edges=[],
            y_edges=[],
            z_edges=[],
            planes={"xy_planes": [], "zx_planes": [], "yz_planes": []},
            scrap_volumes=[self.box_coordinate]
        )
        
        if fig is None:
            raise RuntimeError("draw() returned None for scrap visualization")
            
        fig.update_layout(
            scene=dict(
                aspectmode="data",
                camera=dict(
                    eye=dict(x=1.5, y=-1.8, z=1.2),
                    up=dict(x=0, y=0, z=1),
                ),
                xaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.5)', zeroline=False),
                yaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.5)', zeroline=False),
                zaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.5)', zeroline=False),
            ),
            scene_dragmode='orbit',
            margin=dict(l=0, r=0, t=40, b=0),
            width=900,
            height=700,
            paper_bgcolor='white',
        )
        
        if save_path:
            legend_items = [("Selected Scrap", "rgba(239, 68, 68, 0.5)", True)]
            title = f"Scrap Location View (Block {self.parent_block.unique_code} - Scrap {self.unique_code})"
            html_content = wrap_plotly_fig_with_legend(fig, title, legend_items)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(html_content)
                
        return fig


class Rotation:
    """Handle 3D rotations and coordinate transformations"""
    
    def __init__(self, axis_order: List[str] = None, pivot: Tuple[float, float, float] = (0, 0, 0), 
                 roundingoff: int = 2):
        """
        Initialize rotation handler
        
        Args:
            axis_order: Sequence of axes to rotate around (e.g., ['z', 'x'])
            pivot: Point to rotate around
            roundingoff: Decimal places for rounding
        """
        self.roundingoff = roundingoff
        self.axis_order = axis_order or []
        self.pivot = pivot
    
    def get_new_lwh(self, size: List[float]) -> List[float]:
        """Get new dimensions after rotation"""
        def get_lwh(axis: str, size: List[float]) -> List[float]:
            l, w, h = size
            if axis == 'z':
                return [w, l, h]
            elif axis == 'y':
                return [h, w, l]
            elif axis == 'x':
                return [l, h, w]
            return [l, w, h]
        
        for axis in self.axis_order:
            size = get_lwh(axis, size)
        return size
    
    def get_starting_co_and_size(self, pts: List, after_rotation: bool = True) -> Tuple[List[float], List[float]]:
        """Get bounding box after rotation"""
        if after_rotation:
            pts = self.rotate_in_order(pts)
        
        pts = np.array(pts, dtype=float)
        xs = pts[:, 0]
        ys = pts[:, 1]
        zs = pts[:, 2]
        
        xmin, xmax = xs.min(), xs.max()
        ymin, ymax = ys.min(), ys.max()
        zmin, zmax = zs.min(), zs.max()
        
        starting_point = [xmin, ymin, zmin]
        size = [xmax - xmin, ymax - ymin, zmax - zmin]
        
        return starting_point, size
    
    def rotate_in_order(self, points: List) -> np.ndarray:
        """Apply rotations in sequence"""
        new_pts = points
        for axis in self.axis_order:
            new_pts = self.rotate(new_pts, 90, axis, self.pivot)
        return new_pts
    
    def rotate_in_reverse_order(self, points: List) -> np.ndarray:
        """Apply rotations in reverse sequence"""
        new_pts = points
        for axis in reversed(self.axis_order):
            new_pts = self.rotate(new_pts, -90, axis, self.pivot)
        return new_pts
    
    def rotate(self, points: List, angle_deg: float, axis: str = 'z', 
               pivot: Tuple[float, float, float] = (0, 0, 0)) -> np.ndarray:
        """
        Rotate 3D points around an axis
        
        Args:
            points: Array of 3D points
            angle_deg: Rotation angle in degrees
            axis: Axis to rotate around ('x', 'y', or 'z')
            pivot: Point to rotate around
        
        Returns:
            Rotated points
        """
        pts = np.array(points, dtype=float)
        if pts.ndim == 1:
            # -1, not 1: a bare point is (3,) but an empty list is also 1-D, shape (0,).
            # reshape(1, 3) promotes the former and raises on the latter, and empty is a
            # normal result here - get_scrap_vol returns no boxes when a scrap is packed
            # with zero leftover. -1 maps (3,) -> (1, 3) and (0,) -> (0, 3), which then
            # flows through the transform below unchanged.
            pts = pts.reshape(-1, 3)

        angle = np.radians(angle_deg)
        px, py, pz = pivot
        
        # Shift to origin
        shifted = pts - np.array([px, py, pz])
        
        # Rotation matrices
        if axis == 'x':
            R = np.array([
                [1, 0, 0],
                [0, np.cos(angle), -np.sin(angle)],
                [0, np.sin(angle), np.cos(angle)]
            ])
        elif axis == 'y':
            R = np.array([
                [np.cos(angle), 0, np.sin(angle)],
                [0, 1, 0],
                [-np.sin(angle), 0, np.cos(angle)]
            ])
        elif axis == 'z':
            R = np.array([
                [np.cos(angle), -np.sin(angle), 0],
                [np.sin(angle), np.cos(angle), 0],
                [0, 0, 1]
            ])
        else:
            raise ValueError("axis must be 'x', 'y', or 'z'")
        
        # Apply rotation
        rotated = shifted @ R.T
        
        # Shift back
        rounded = np.round(rotated + np.array([px, py, pz]), self.roundingoff)
        return rounded


class People_helper:
    """Main packing orchestrator"""
    
    def __init__(self, buffer: float = 2, parent_block_sizes: List[List[float]] = None,
                 parent_block_quantities: List[Optional[int]] = None):
        """
        Initialize the packing helper

        Args:
            buffer: Spacing between parts (mm)
            parent_block_sizes: Available stock block dimensions
            parent_block_quantities: How many of each parent size may be opened, parallel to
                parent_block_sizes. An entry of None means unlimited. Omitting the argument
                entirely makes every size unlimited, which is the historical behaviour.
        """
        self.all_scrap = []
        self.scrap_count = 0
        self.big_block_count = 0
        self.recovered_block_count = 0
        self.all_big_blocks = []
        self.rotation_axis = [[], ['z'], ['z', 'x'], ['z', 'y'], ['x'], ['y']]

        self.buffer = buffer
        self.parent_block_sizes = parent_block_sizes or [[1870, 800, 350]]
        self.all_scrap_temp = []
        self.rejected_scrap_count = 0  # scrap boxes discarded as unsound, see add_update_scrap_list
        self.consumed_scraps = []  # scraps that had prisms packed into them, see delete_scrap
        # Every part type in the job, set by run_final_code. Read only by lookahead block
        # selection, which needs to know what the leftovers will have to serve.
        self.pending_prisms = []

        # Mutable per-run stock ledger, parallel to parent_block_sizes. None = unlimited,
        # an int counts down as blocks are opened and is refunded when a fill fails.
        if parent_block_quantities is None:
            self.parent_block_quantities = [None] * len(self.parent_block_sizes)
        else:
            self.parent_block_quantities = list(parent_block_quantities)
            # Never let a short list silently make trailing sizes unlimited or raise later.
            while len(self.parent_block_quantities) < len(self.parent_block_sizes):
                self.parent_block_quantities.append(None)
        self.remaining_quantity = list(self.parent_block_quantities)

        # prism code -> 'stock_exhausted' | 'no_fit', set when a part could not be finished.
        # The view turns this into the status it reports, since the two need different
        # advice: one is fixed by offering more stock, the other only by a bigger size.
        self.shortfall_reasons = {}

    def any_quota_spent(self) -> bool:
        """True when some limited parent size has been used up entirely."""
        return any(q == 0 for q in self.remaining_quantity)

    def add_one_big_block(self, size: List[float], code: str = 'B',
                          size_index: Optional[int] = None) -> Block:
        """
        Create a new stock block, charging it against that size's quota.

        size_index identifies which entry of parent_block_sizes is being consumed. It is
        passed explicitly rather than looked up by dimensions because two entries may share
        dimensions while carrying different quotas.
        """
        self.big_block_count += 1
        starting_point = [0, 0, 0]
        block = Block(code + str(self.big_block_count), size, start_coord=starting_point)
        block.size_index = size_index
        self.all_big_blocks.append(block)

        if size_index is not None and self.remaining_quantity[size_index] is not None:
            self.remaining_quantity[size_index] -= 1

        return block

    def refund_big_block(self, block: Block):
        """
        Undo add_one_big_block after a failed fill.

        Without the quota being handed back, a fill that placed nothing still burns a unit
        of scarce stock, and a size with quantity 1 can end up unavailable having produced
        no parts at all.
        """
        if block in self.all_big_blocks:
            self.all_big_blocks.remove(block)
        self.big_block_count -= 1

        size_index = getattr(block, 'size_index', None)
        if size_index is not None and self.remaining_quantity[size_index] is not None:
            self.remaining_quantity[size_index] += 1

    def add_recovered_block(self, size: List[float], source: Dict[str, Any] = None) -> Block:
        """
        Seed one physical offcut from inventory as packable space (supply stage 1).

        The piece becomes a Block coded R1, R2... carrying a single full-size Scrap over
        itself. run_final_code already tries every prism against all_scrap before opening
        any new stock, so seeding is all that stage 1 needs - no change to the packing loop.

        R-blocks use their own counter so they never disturb B-numbering, and the seed scrap
        is registered through add_update_scrap_list like any other: a fresh block has no
        placed prisms, so it passes the overlap checks, and the chokepoint stays the single
        place scraps enter the system.
        """
        source = source or {}

        self.recovered_block_count += 1
        block = Block('R' + str(self.recovered_block_count), list(size), start_coord=[0, 0, 0])
        block.is_recovered = True
        block.source_scrap_id = source.get('scrap_id')
        block.source_inventory_id = source.get('id')
        block.size_index = None
        self.all_big_blocks.append(block)

        seed = Block('tmp', list(size), start_coord=[0, 0, 0])
        created = self.add_update_scrap_list(block, [seed.box_coordinate])

        # Tag the seed so delete_scrap can report which racked piece a job actually cut
        # into; run_summary keys its inventory reporting off exactly these two attributes.
        for s in created:
            s.origin = 'inventory'
            s.inventory_scrap_id = source.get('scrap_id')
            s.inventory_id = source.get('id')

        return block

    def prune_unused_recovered_blocks(self) -> List[Block]:
        """
        Drop offered inventory pieces that nothing was packed into.

        Required, not cosmetic: auto_save_scraps_from_optimization walks all_scrap and
        writes a ScrapInventory row per entry, so an untouched R-block's seed scrap would
        create a second row for a piece that is already in inventory - the same physical
        offcut counted twice on every run that offers it.
        """
        removed = []
        for block in self.all_big_blocks[:]:
            if not getattr(block, 'is_recovered', False) or block.prism_details:
                continue

            for scrap in block.scraps[:]:
                if scrap in self.all_scrap:
                    self.all_scrap.remove(scrap)
            block.scraps = []

            self.all_big_blocks.remove(block)
            removed.append(block)

        return removed

    def get_a_temp_block(self, size: List[float], code: str = 'Temp') -> Block:
        """Create a temporary block for testing"""
        starting_point = [0, 0, 0]
        block = Block(code, size, start_coord=starting_point)
        return block
    
    def try_to_pack_inside_all_scrap(self, prism, all_scrap: List = None):
        """Attempt to pack prism into existing scrap pieces"""
        if all_scrap is None:
            all_scrap = self.all_scrap
        
        for scrap in all_scrap[:]:
            if prism.prism_left == 0:
                break
            
            result = self.fill_the_prism_optimally(prism, scrap=scrap)
            if result[0] is None:  # Check if packing failed
                continue
    
    def check_which_block_to_add(self, prism) -> Optional[int]:
        """
        Choose which parent block size to open next for this prism, or None.

        Returns the INDEX into parent_block_sizes, not the size: two entries may share
        dimensions while carrying different quotas, so a size alone does not identify what
        is being spent. (An earlier revision returned the size looked up by position in a
        list that skipped non-fitting entries, which silently returned a size the prism did
        not fit.)

        Ranking is (tier, waste_per_part), smallest first:

        - tier 0 is a size with a finite quantity, tier 1 a size with unlimited supply, so
          stock already owned is exhausted before more is bought. This is supply stage 2
          (fixed blocks) taking strict precedence over stage 3 (the open market).
        - within a tier, the size consuming the least stock volume per part packed wins,
          which is what "minimise blocks" means once sizes differ. Measured ~1.2% less
          material than the old raw-count objective on Sample_data_03; see NESTING_AUDIT.md
          issue 8.

        Returns None when nothing is available - either every fitting size is used up or no
        size fits at all. The caller distinguishes the two via any_quota_spent().
        """
        candidates = []  # (tier, waste_per_part, index, parent_size)

        for idx, parent_size in enumerate(self.parent_block_sizes):
            if self.remaining_quantity[idx] == 0:
                continue  # quota spent

            block = self.get_a_temp_block(parent_size, code='Temp')
            cond, rotation_axis_new = block.can_fit_with_rotation(prism, self.rotation_axis)

            if not cond:
                continue

            best_count = 0
            best_size = None
            best_end = None
            for axis_order in rotation_axis_new:
                if len(axis_order) != 0:
                    rot = Rotation(axis_order=axis_order, pivot=block.start_coord)
                    size = rot.get_new_lwh(block.size)
                else:
                    size = block.size

                # Test packing
                co_ordinates_list, big_block_coordinate, end_coordinates, prism_count = fill_the_box(
                    prism,
                    Block_size=size,
                    starting_co=block.start_coord,
                    buffer=self.buffer
                )
                if prism_count > best_count:
                    best_count = prism_count
                    best_size = size
                    best_end = end_coordinates

            # can_fit_with_rotation ignores the buffer, so a size can pass it and still pack
            # nothing. Such a size is not a candidate.
            if best_count == 0:
                continue

            # Part volume this block is expected to produce. Without lookahead that is just
            # the current part type, and dividing by it ranks candidates identically to the
            # old volume/count rule - prism.volume is the same constant for every candidate
            # here, so the default path is unchanged.
            yielded = best_count * prism.volume
            if LOOKAHEAD_SELECTION:
                yielded = self._lookahead_yield(prism, yielded, best_size, best_end)

            tier = 0 if self.remaining_quantity[idx] is not None else 1
            waste_per_part = (parent_size[0] * parent_size[1] * parent_size[2]) / yielded
            candidates.append((tier, waste_per_part, idx, parent_size))

        if not candidates:
            return None

        return min(candidates, key=lambda c: (c[0], c[1]))[2]

    def _lookahead_yield(self, prism, base_yield, size, end_coordinates):
        """
        Add to `base_yield` the part volume the OTHER outstanding part types could take out
        of the scrap this packing would leave.

        Approximate on purpose - it decides which block to open, it does not place anything.
        Only the largest few leftover boxes and the largest few pending part types are
        tried, and each box is credited to the first type that fits it, since a box cannot
        serve two types at once.

        The scrap derivation is forced back to sampled mode: this runs once per candidate
        size per block opened, and the exhaustive decomposition the deep run uses for real
        packing would multiply that by 48 for an estimate that does not need the precision.
        """
        if not end_coordinates:
            return base_yield

        pending = getattr(self, 'pending_prisms', None)
        if not pending:
            return base_yield

        others = [p for p in pending
                  if p is not prism and getattr(p, 'prism_left', 0) > 0][:LOOKAHEAD_TOP_K]
        if not others:
            return base_yield

        from .fill import exhaustive_decomposition

        try:
            with exhaustive_decomposition(False):
                _, boxes = get_scrap_vol(end_coordinates, size, [0, 0, 0], [],
                                         buffer=self.buffer)
        except Exception:
            return base_yield

        boxes = sorted(
            boxes,
            key=lambda b: -(b['Box_size'][0] * b['Box_size'][1] * b['Box_size'][2])
        )[:LOOKAHEAD_MAX_SCRAPS]

        for box in boxes:
            for other in others:
                try:
                    _, _, _, count = fill_the_box(other,
                                                  Block_size=box['Box_size'],
                                                  starting_co=box['starting_co'],
                                                  buffer=self.buffer)
                except Exception:
                    continue
                if count > 0:
                    base_yield += min(count, other.prism_left) * other.volume
                    break  # this box is spoken for

        return base_yield

    def fill_the_prism_optimally(self, prism, scrap) -> Tuple:
        """
        Fill a block/scrap with prisms optimally
        
        Returns:
            (coordinates_list, block_coordinate, scrap_volumes, prism_count, scrap_blocks_list)
        """
        self.all_scrap_temp = []
        size_list = []
        prism_count_list = []
        
        cond, rotation_axis_new = scrap.can_fit_with_rotation(prism, self.rotation_axis)
        
        if not cond:
            return None, None, None, None, None
        
        for axis_order in rotation_axis_new:
            if len(axis_order) != 0:
                rot = Rotation(axis_order=axis_order, pivot=scrap.start_coord)
                size = rot.get_new_lwh(scrap.size)
            else:
                size = scrap.size
            
            size_list.append(size)
            
            # Pack the prism
            co_ordinates_list, big_block_coordinate, end_coordinates, prism_count = fill_the_box(
                prism,
                Block_size=size,
                starting_co=scrap.start_coord,
                buffer=self.buffer
            )
            prism_count_list.append(prism_count)
        
        if not prism_count_list or max(prism_count_list) == 0:
            return None, None, None, None, None
        
        prism_count_max = max(prism_count_list)
        max_index = prism_count_list.index(prism_count_max)
        axis_order_max = rotation_axis_new[max_index]
        size_max = size_list[max_index]
        
        # Apply rotation if needed
        if len(axis_order_max) != 0:
            rot = Rotation(axis_order=axis_order_max, pivot=scrap.start_coord)
            new_starting_point, size = rot.get_starting_co_and_size(scrap.box_coordinate)

            # Pack in an origin-anchored frame: the edge/scrap extraction in
            # fill.py/edges.py hardcodes 0 as the frame anchor, so packing at
            # new_starting_point (which can be negative after rotation, e.g.
            # rotating a block about [0,0,0]) produces an inconsistent edge set
            # and get_type() raises. Fill at [0,0,0], then translate the
            # results to the rotated frame's true position before rotating back.
            co_ordinates_list, big_block_coordinate, end_coordinates, prism_count = fill_the_box(
                prism,
                Block_size=size_max,
                starting_co=[0, 0, 0],
                buffer=self.buffer
            )
            scrap_volumes, scrap_Boxes_new = get_scrap_vol(end_coordinates, size_max, [0, 0, 0], co_ordinates_list,
                                                           buffer=self.buffer)

            # Translate from origin frame to the rotated frame's position
            offset = np.array(new_starting_point, dtype=float)
            if co_ordinates_list:
                co_ordinates_list = (np.array(co_ordinates_list, dtype=float) + offset).tolist()
            big_block_coordinate = (np.array(big_block_coordinate, dtype=float) + offset).tolist()
            scrap_volumes = [(np.array(v, dtype=float) + offset).tolist() for v in scrap_volumes]

            # Rotate back
            co_ordinates_list = rot.rotate_in_reverse_order(co_ordinates_list).tolist()
            big_block_coordinate = rot.rotate_in_reverse_order(big_block_coordinate)
            scrap_volumes = rot.rotate_in_reverse_order(scrap_volumes)
        else:
            co_ordinates_list, big_block_coordinate, end_coordinates, prism_count = fill_the_box(
                prism,
                Block_size=size_max,
                starting_co=scrap.start_coord,
                buffer=self.buffer
            )
            scrap_volumes, scrap_Boxes_new = get_scrap_vol(end_coordinates, size_max, scrap.start_coord, co_ordinates_list,
                                                           buffer=self.buffer)
        
        if prism_count == 0:
            return None, None, None, None, None
        
        # Update block/scrap
        if isinstance(scrap, Block) and not isinstance(scrap, Scrap):
            block = scrap
            prism.update_prism_left(prism_count)
            block.add_prisms_coordinates(prism, co_ordinates_list)
            scrap_blocks_list_temp = self.add_update_scrap_list(block, scrap_volumes)
            self.all_scrap_temp = scrap_blocks_list_temp
        elif isinstance(scrap, Scrap):
            block = scrap.parent_block
            prism.update_prism_left(prism_count)
            block.add_prisms_coordinates(prism, co_ordinates_list)
            # Retire the consumed scrap first: the new scraps are its leftover sub-regions
            # and lie inside it, so they would fail the overlap check while it is still listed.
            self.delete_scrap(scrap)
            scrap_blocks_list_temp = self.add_update_scrap_list(block, scrap_volumes)
        else:
            raise Exception('scrap must be Block or Scrap instance')
        
        return co_ordinates_list, big_block_coordinate, scrap_volumes, prism_count, scrap_blocks_list_temp
    
    def is_small_size(self, size: List[float]) -> bool:
        """Check if a scrap is too small to be useful"""
        volume = size[0] * size[1] * size[2]
        is_small_volume = volume < 10
        is_small_length = size[0] < 2 or size[1] < 2 or size[2] < 2
        return is_small_volume or is_small_length
    
    def add_update_scrap_list(self, block: Block, scrap_volumes: List) -> List[Scrap]:
        """
        Add new scrap pieces to the scrap list.

        A scrap means "free space inside this block", and later passes pack prisms into
        it. get_scrap_vol picks its cutting planes with random.sample and is not
        guaranteed sound, so a small fraction of the boxes it returns cover space that
        already holds a prism. Registering one of those would let the next pass pack a
        part inside solid material, so candidates are checked before being accepted.
        """
        scrap_blocks_list_temp = []
        occ_lo, occ_hi = block.occupied_bounds()
        existing = [aabb(s.box_coordinate) for s in block.scraps]

        for scrap_vol in scrap_volumes:
            self.scrap_count += 1
            rot = Rotation()
            scrap_starting_point, scrap_size = rot.get_starting_co_and_size(scrap_vol, after_rotation=False)

            if self.is_small_size(scrap_size):
                continue

            lo = np.asarray(scrap_starting_point, dtype=float)
            hi = lo + np.asarray(scrap_size, dtype=float)

            if len(occ_lo) and (np.minimum(occ_hi, hi) - np.maximum(occ_lo, lo)).min(axis=1).max() > OVERLAP_TOL:
                self.rejected_scrap_count += 1
                continue

            if any(boxes_overlap(lo, hi, e_lo, e_hi) for e_lo, e_hi in existing):
                self.rejected_scrap_count += 1
                continue

            s = Scrap('s' + str(self.scrap_count), scrap_size, scrap_starting_point)
            block.add_scrap(s)
            existing.append((lo, hi))
            scrap_blocks_list_temp.append(s)

        # Sort by volume (smallest first)
        scrap_blocks_list_temp = sorted(scrap_blocks_list_temp, key=lambda s: s.volume)
        self.all_scrap.extend(scrap_blocks_list_temp)

        return scrap_blocks_list_temp
    
    def delete_scrap(self, scrap: Scrap):
        """
        Remove a scrap from tracking.

        This is the only place a scrap is retired, and it is only ever called after prisms
        have been packed into it (see fill_the_prism_optimally), so a scrap passing through
        here is one that was used. Recording it is what lets the run summary report which
        racked offcuts a job consumed once inventory scraps are offered as input stock;
        without it the piece simply vanishes from all_scrap and the usage is unrecoverable.
        """
        if scrap in self.all_scrap:
            self.all_scrap.remove(scrap)

        self.consumed_scraps.append({
            'code': scrap.unique_code,
            'origin': getattr(scrap, 'origin', 'generated'),
            'inventory_scrap_id': getattr(scrap, 'inventory_scrap_id', None),
            'size': [float(d) for d in scrap.size],
            'volume': float(scrap.volume),
            'parent_block': scrap.parent_block.unique_code if scrap.parent_block else None,
        })

        scrap.delete_scrap()


# Vertex order produced by place_prism_flip: 0-3 bottom face, 4-7 top face.
_PRISM_FACES = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
_PRISM_EDGES = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
                (0, 4), (1, 5), (2, 6), (3, 7)]


def _separating_axes(solid: np.ndarray) -> List[np.ndarray]:
    """Face normals of one trapezoidal prism, normalised."""
    out = []
    for a, b, c, _ in _PRISM_FACES:
        n = np.cross(solid[b] - solid[a], solid[c] - solid[a])
        norm = np.linalg.norm(n)
        if norm > 1e-9:
            out.append(n / norm)
    return out


def solids_overlap(solid_a: List, solid_b: List, tol: float = OVERLAP_TOL) -> float:
    """
    Interpenetration depth of two trapezoidal prisms, via the separating axis theorem.

    Bounding boxes are not usable here: the packer deliberately interlocks alternating
    tapered prisms, so neighbours share bounding-box volume while the solids themselves
    only touch. Both are convex, so SAT over face normals plus pairwise edge cross
    products is exact.

    Returns:
        Depth in mm along the least-overlapping axis, or 0.0 if a separating axis exists.
    """
    a = np.asarray(solid_a, dtype=float)
    b = np.asarray(solid_b, dtype=float)

    axes = _separating_axes(a) + _separating_axes(b)
    edges_a = [a[j] - a[i] for i, j in _PRISM_EDGES]
    edges_b = [b[j] - b[i] for i, j in _PRISM_EDGES]
    for ea in edges_a:
        for eb in edges_b:
            axis = np.cross(ea, eb)
            norm = np.linalg.norm(axis)
            if norm > 1e-9:
                axes.append(axis / norm)

    depth = float('inf')
    for axis in axes:
        pa = a @ axis
        pb = b @ axis
        gap = min(pa.max(), pb.max()) - max(pa.min(), pb.min())
        if gap <= tol:
            return 0.0
        depth = min(depth, gap)

    return depth


def find_overlaps(helper: People_helper, tol: float = OVERLAP_TOL) -> List[Dict[str, Any]]:
    """
    Check the invariant that no two prisms occupy the same space.

    This should always come back empty. A non-empty result means the packing is not
    manufacturable and must not be handed to the caller.

    Returns:
        One entry per offending pair: block code, the two prism codes, and how deep
        they interpenetrate in mm.
    """
    problems = []

    for block in helper.all_big_blocks:
        labels = []
        for entry in block.prism_details:
            code = entry['prism'].code
            labels.extend([code] * len(entry['coordinates']))

        lo, hi = block.occupied_bounds()
        if len(lo) < 2:
            continue

        # Cheap bounding-box pass to shortlist candidates, then an exact test on those.
        overlap = np.minimum(hi[:, None, :], hi[None, :, :]) - np.maximum(lo[:, None, :], lo[None, :, :])
        candidates = overlap.min(axis=2) > tol
        rows, cols = np.triu_indices(len(lo), k=1)
        for i, j in zip(rows[candidates[rows, cols]], cols[candidates[rows, cols]]):
            depth = solids_overlap(block.all_prisms_coordinates[i],
                                   block.all_prisms_coordinates[j], tol)
            if depth > tol:
                problems.append({
                    'block': block.unique_code,
                    'prism_a': labels[i],
                    'prism_b': labels[j],
                    'penetration_mm': round(depth, 3)
                })

    return problems


def get_block_details(helper: People_helper) -> Dict[str, Any]:
    """
    Extract detailed results from packing operation
    
    Returns:
        Dictionary with block details, efficiency, and scrap information
    """
    new_blocks = [b for b in helper.all_big_blocks if not getattr(b, 'is_recovered', False)]

    block_details = {
        "Total_number_of_blocks": len(new_blocks),
        "Total_number_of_recovered_blocks": len(helper.all_big_blocks) - len(new_blocks),
        "Total_stock_volume": 0,
        "Total_prism_volume": 0,
        "Total_eff": 0,
        "blocks": [],
        "scraps": []
    }

    total_eff_sum = 0
    total_stock_volume = 0
    total_prism_volume = 0

    # Process all blocks
    for block in helper.all_big_blocks:
        block_eff = round(block.get_efficiency(), 2)
        size = block.size
        is_recovered = getattr(block, 'is_recovered', False)

        # Recovered blocks are material already paid for, so they are excluded from every
        # aggregate here. Both the stock and the prism term must be excluded together, or
        # efficiency exceeds 100% as soon as much of the demand comes out of scrap.
        if not is_recovered:
            total_stock_volume += size[0] * size[1] * size[2]
            total_eff_sum += block_eff

        # Count prisms by code
        prism_count_dict = {}
        for entry in block.prism_details:
            prism = entry['prism']
            count = len(entry['coordinates'])
            volume = prism.get_volume()
            if not is_recovered:
                total_prism_volume += volume * count

            if prism.code not in prism_count_dict:
                prism_count_dict[prism.code] = 0
            prism_count_dict[prism.code] += count

        prism_list = [
            {"code": code, "number": num}
            for code, num in prism_count_dict.items()
        ]

        block_details["blocks"].append({
            "code": block.unique_code,
            "eff": block_eff,
            "size": size,
            "prisms": prism_list,
            "is_recovered": is_recovered,
            "source_scrap_id": getattr(block, 'source_scrap_id', None)
        })

    # Calculate total efficiency
    if len(new_blocks) > 0:
        block_details["Total_eff"] = round(total_eff_sum / len(new_blocks), 2)
    else:
        block_details["Total_eff"] = 0

    block_details["Total_stock_volume"] = total_stock_volume
    block_details["Total_prism_volume"] = total_prism_volume

    # Add scraps
    for scrap in helper.all_scrap:
        block_details["scraps"].append({
            "code": scrap.unique_code,
            "size": scrap.size,
            "volume": scrap.volume
        })
    
    return block_details


def run_final_code(all_prisms: List[Prisms], buffer: float = 2,
                   parent_block_sizes: List[List[float]] = None,
                   parent_block_quantities: List[Optional[int]] = None,
                   recovered_stock: List[Dict[str, Any]] = None) -> People_helper:
    """
    Main packing algorithm.

    Demand is met from three sources, cheapest first, so the number of new blocks opened is
    as small as the supply allows:

      1. recovered scrap - offcuts pulled back out of inventory, seeded as R-blocks before
         the loop starts. try_to_pack_inside_all_scrap runs before any stock is opened, so
         every prism is offered this material first and costs nothing.
      2. fixed blocks - parent sizes with a finite quantity on hand, preferred by
         check_which_block_to_add's tier-0 rule until their quota is spent.
      3. new stock - parent sizes with no quantity limit, the historical behaviour, applied
         to whatever demand the first two stages could not absorb.

    Args:
        all_prisms: List of Prism objects to pack
        buffer: Spacing between parts
        parent_block_sizes: Available stock block dimensions
        parent_block_quantities: Units available per parent size, parallel to
            parent_block_sizes; None entries (or the whole argument) mean unlimited
        recovered_stock: Inventory offcuts to cut into first, each
            {'id', 'scrap_id', 'size': [l, w, h]}

    Returns:
        People_helper object with packing results
    """
    if parent_block_sizes is None:
        parent_block_sizes = [[2000, 800, 400], [2000, 500, 500]]

    helper = People_helper(buffer, parent_block_sizes, parent_block_quantities)

    # Parts with no unlimited size to fall back on go first, or a flexible part can spend
    # the scarce stock they depend on. No-op when no size carries a quantity.
    all_prisms = prioritise_constrained_parts(
        all_prisms, parent_block_sizes, helper.parent_block_quantities, helper.rotation_axis)

    # Lookahead block selection needs to know what else is still outstanding; the packing
    # loop otherwise only ever hands check_which_block_to_add a single prism. Unused when
    # lookahead is off.
    helper.pending_prisms = all_prisms

    # Stage 1: offer inventory offcuts as packable space before any stock is opened.
    for piece in (recovered_stock or []):
        try:
            size = [float(d) for d in piece['size']]
            if min(size) <= 0:
                continue
            helper.add_recovered_block(size, source=piece)
        except Exception as e:
            print(f"Warning: could not seed recovered scrap {piece!r}: {e}")
            continue

    for prism in all_prisms[:]:
        # Try to pack into existing scraps - recovered inventory on the first part, plus
        # everything earlier parts left behind.
        helper.try_to_pack_inside_all_scrap(prism)

        # Stages 2 and 3: pack whatever is left into fixed then unlimited stock.
        while prism.prism_left > 0:
            # Determine best block size
            size_index = helper.check_which_block_to_add(prism)

            if size_index is None:
                # Expected outcome under a quota, not an error: either the fitting sizes are
                # used up or none fits. Opening a fallback block here (as this once did)
                # would create one that cannot be filled and would spend stock to do it.
                helper.shortfall_reasons[prism.code] = (
                    'stock_exhausted' if helper.any_quota_spent() else 'no_fit')
                print(f"Warning: no stock available for remaining {prism.prism_left} "
                      f"units of {prism.code} ({helper.shortfall_reasons[prism.code]})")
                break

            # Create new block
            b = helper.add_one_big_block(parent_block_sizes[size_index], size_index=size_index)

            # Fill the block
            result = helper.fill_the_prism_optimally(prism, b)

            if result[0] is None:
                # Packing failed - discard the empty block just created so it
                # doesn't inflate block count / deflate reported efficiency,
                # refund its quota so a scarce size is not spent for nothing,
                # and break to avoid an infinite loop. The prism stays in the
                # summary as "remaining" (could not be packed).
                helper.refund_big_block(b)
                helper.shortfall_reasons[prism.code] = 'no_fit'
                print(f"Warning: Could not pack remaining {prism.prism_left} units of {prism.code}")
                break

            co_ordinates_list, big_block_coordinate, scrap_volumes, prism_count, scrap_blocks_list_temp = result

            # Try to pack into newly created scraps
            helper.try_to_pack_inside_all_scrap(prism, scrap_blocks_list_temp)

    # Offered pieces nothing was cut from are not part of this plan, and leaving them in
    # would duplicate them in inventory. See prune_unused_recovered_blocks.
    helper.prune_unused_recovered_blocks()

    return helper


def get_all_prisms(excel_path: str) -> List[Prisms]:
    """
    Load prism data from Excel file
    
    Args:
        excel_path: Path to Excel file with prism specifications
    
    Returns:
        List of Prism objects
    """
    df = pd.read_excel(excel_path)
    
    all_prisms = []
    for _, row in df.iterrows():
        size = [
            row["Bottom Length"],
            row["Top Length"],
            row["Width"],
            row["Height"]
        ]
        
        prism_obj = Prisms(row["MARK"], size, int(row["Nos"]))
        all_prisms.append(prism_obj)
    
    return all_prisms


def run_optimization_with_retries(excel_path: str, parent_block_sizes: List[List[float]] = None,
                                   buffer: float = 2, max_tries: int = 10000,
                                   parent_block_quantities: List[Optional[int]] = None,
                                   recovered_stock: List[Dict[str, Any]] = None,
                                   search_attempts: int = None) -> Tuple[People_helper, Dict]:
    """
    Run optimization with multiple retries to find best solution

    Args:
        excel_path: Path to Excel file
        parent_block_sizes: Stock block dimensions
        buffer: Spacing between parts
        max_tries: Maximum retry attempts
        parent_block_quantities: Units available per parent size, parallel to
            parent_block_sizes; None entries mean unlimited
        recovered_stock: Inventory offcuts to pack into before opening stock
        search_attempts: How many legal packings to generate before returning the best.
            Default 1 (return the first legal one, the historical behaviour), raised to 5
            when quotas or recovered stock are in play - there, what fits varies genuinely
            between attempts because supply is finite, so first-legal under-performs.

    Returns:
        (helper, block_details) tuple
    """
    if parent_block_sizes is None:
        parent_block_sizes = [[1870, 800, 350], [2000, 800, 400]]

    constrained = bool(recovered_stock) or any(
        q is not None for q in (parent_block_quantities or []))
    if search_attempts is None:
        search_attempts = 5 if constrained else 1
    search_attempts = max(1, int(search_attempts))

    tried = 0
    last_error = None
    same_error_count = 0

    best = None  # (parts_packed, -new_material_volume, helper, block_details)
    legal_found = 0

    while tried <= max_tries:
        try:
            # Load prisms
            all_prisms = get_all_prisms(excel_path)

            # Sort by volume (largest first)
            prism_list_sorted = sorted(all_prisms, key=lambda p: p.get_volume(), reverse=True)

            # No-op unless a deep run has set a seed, so the ordinary path is unchanged.
            prism_list_sorted = perturb_prism_order(prism_list_sorted, PRISM_ORDER_SEED)

            # Run packing
            helper = run_final_code(prism_list_sorted, buffer=buffer,
                                    parent_block_sizes=parent_block_sizes,
                                    parent_block_quantities=parent_block_quantities,
                                    recovered_stock=recovered_stock)

            # Get results
            block_details = get_block_details(helper)

            if block_details is not None and helper is not None:
                # Check if any new block has >= 99% efficiency (too good to be true).
                # Recovered blocks are excluded: an offcut is often barely larger than the
                # part cut from it, so a near-perfect fill is the normal case there. Judging
                # them by this rule rejects every attempt of any run that offers inventory,
                # exhausting max_tries and returning nothing.
                has_perfect_block = any(
                    obj['eff'] >= 99 for obj in block_details['blocks']
                    if not obj.get('is_recovered'))

                # Never return a packing where prisms interpenetrate - it cannot be cut.
                overlaps = find_overlaps(helper)
                if overlaps:
                    print(f"Attempt {tried}: rejected, {len(overlaps)} overlapping prism pairs "
                          f"(e.g. {overlaps[0]})")

                if not has_perfect_block and not overlaps:
                    if search_attempts == 1:
                        return helper, block_details

                    # Best-of-N: most parts placed, then least new material bought.
                    packed = sum(p['number'] for b in block_details['blocks']
                                 for p in b['prisms'])
                    score = (packed, -block_details['Total_stock_volume'])
                    if best is None or score > best[0]:
                        best = (score, helper, block_details)

                    legal_found += 1
                    if legal_found >= search_attempts:
                        print(f"Returning best of {legal_found} legal packings: "
                              f"{best[0][0]} parts, {-best[0][1]:.0f} mm^3 new material")
                        return best[1], best[2]

            tried += 1

        except Exception as e:
            print(f"Attempt {tried} failed: {str(e)}")
            tried += 1

            # Bail out early on repeated identical failures: retrying a
            # deterministic error max_tries times hangs the request until the
            # server/proxy timeout kills it, so the client gets an opaque
            # HTML 500 instead of this error message as JSON.
            if str(e) == last_error:
                same_error_count += 1
                if same_error_count >= 5:
                    print('Aborting retries: same error 5 times in a row')
                    raise
            else:
                last_error = str(e)
                same_error_count = 1

            if tried == max_tries:
                print('Max tries exceeded')
                raise

    # Retries exhausted. Under best-of-N a legal packing may already be in hand - returning
    # it beats discarding it and letting the caller raise "optimization failed".
    if best is not None:
        print(f"Max tries exceeded; returning best of {legal_found} legal packings")
        return best[1], best[2]
"""
Complete Packing Orchestrator Module
Converts Jupyter notebook logic into production-ready Python code
"""

import math
import numpy as np
import pandas as pd
import json
from typing import List, Dict, Tuple, Optional, Any

# Import from fill module (ensure this exists in your project)
from .fill import fill_the_box, draw, get_scrap_vol


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
    
    def add_scrap(self, scrap_obj):
        """Add a scrap piece to this block"""
        scrap_obj.parent_block = self
        self.scraps.append(scrap_obj)
    
    def add_prisms_coordinates(self, prism, coordinates: List):
        """Add prism placement information"""
        prism_detail = {'prism': prism, 'coordinates': coordinates}
        self.prism_details.append(prism_detail)
        self.all_prisms_coordinates.extend(coordinates)
    
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
        
        # Color mapping logic matching svg_renderer.py exactly for visual consistency
        colors_palette = [
            "#4F46E5", "#10B981", "#F59E0B", "#EC4899", "#3B82F6", "#8B5CF6", "#06B6D4", "#F97316",
            "#84CC16", "#14B8A6", "#D946EF", "#0EA5E9", "#A855F7", "#E11D48", "#6366F1", "#059669",
            "#D97706", "#DB2777", "#2563EB", "#7C3AED", "#EA580C", "#65A30D", "#0D9488", "#C084FC",
            "#818CF8", "#34D399", "#FBBF24", "#F472B6", "#60A5FA", "#A78BFA", "#fb923c", "#a3e635",
            "#2dd4bf", "#38bdf8", "#1e1b4b", "#064e3b", "#78350f", "#50072b", "#1e3a8a", "#3b0764",
            "#083344", "#431407"
        ]
        
        prism_colors = []
        legend_items = []
        seen_codes = set()
        for detail in self.prism_details:
            prism_code = getattr(detail['prism'], 'code', 'Part')
            prism_code_clean = str(prism_code).strip()
            import zlib
            hash_val = zlib.crc32(prism_code_clean.encode('utf-8'))
            color = colors_palette[hash_val % len(colors_palette)]
            prism_colors.extend([color] * len(detail['coordinates']))
            
            if not only_scrap and prism_code_clean not in seen_codes:
                seen_codes.add(prism_code_clean)
                legend_items.append((prism_code_clean, color, False))
                
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
            pts = pts.reshape(1, 3)
        
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
    
    def __init__(self, buffer: float = 2, parent_block_sizes: List[List[float]] = None):
        """
        Initialize the packing helper
        
        Args:
            buffer: Spacing between parts (mm)
            parent_block_sizes: Available stock block dimensions
        """
        self.all_scrap = []
        self.scrap_count = 0
        self.big_block_count = 0
        self.all_big_blocks = []
        self.rotation_axis = [[], ['z'], ['z', 'x'], ['z', 'y'], ['x'], ['y']]
        
        self.buffer = buffer
        self.parent_block_sizes = parent_block_sizes or [[1870, 800, 350]]
        self.all_scrap_temp = []
    
    def add_one_big_block(self, size: List[float], code: str = 'B') -> Block:
        """Create a new stock block"""
        self.big_block_count += 1
        starting_point = [0, 0, 0]
        block = Block(code + str(self.big_block_count), size, start_coord=starting_point)
        self.all_big_blocks.append(block)
        return block
    
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
    
    def check_which_block_to_add(self, prism) -> List[float]:
        """Determine which parent block size will pack the most prisms"""
        size_list_global = []
        prism_count_list_global = []
        axis_order_list_global = []
        
        for parent_size in self.parent_block_sizes:
            size_list = []
            prism_count_list = []
            
            block = self.get_a_temp_block(parent_size, code='Temp')
            cond, rotation_axis_new = block.can_fit_with_rotation(prism, self.rotation_axis)
            
            if not cond:
                continue
            
            for axis_order in rotation_axis_new:
                if len(axis_order) != 0:
                    rot = Rotation(axis_order=axis_order, pivot=block.start_coord)
                    size = rot.get_new_lwh(block.size)
                else:
                    size = block.size
                
                size_list.append(size)
                
                # Test packing
                co_ordinates_list, big_block_coordinate, end_coordinates, prism_count = fill_the_box(
                    prism,
                    Block_size=size,
                    starting_co=block.start_coord,
                    buffer=self.buffer
                )
                prism_count_list.append(prism_count)
            
            if not prism_count_list:
                continue
            
            prism_count_max = max(prism_count_list)
            max_index = prism_count_list.index(prism_count_max)
            axis_order_max = rotation_axis_new[max_index]
            size_max = size_list[max_index]
            
            prism_count_list_global.append(prism_count_max)
            size_list_global.append(size_max)
            axis_order_list_global.append(axis_order_max)
        
        if not prism_count_list_global:
            # Return first parent block size if none work well
            return self.parent_block_sizes[0]
        
        prism_count_global_max = max(prism_count_list_global)
        max_index = prism_count_list_global.index(prism_count_global_max)
        
        return self.parent_block_sizes[max_index]
    
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
            scrap_volumes, scrap_Boxes_new = get_scrap_vol(end_coordinates, size_max, [0, 0, 0], co_ordinates_list)

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
            scrap_volumes, scrap_Boxes_new = get_scrap_vol(end_coordinates, size_max, scrap.start_coord, co_ordinates_list)
        
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
            scrap_blocks_list_temp = self.add_update_scrap_list(block, scrap_volumes)
            self.delete_scrap(scrap)
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
        """Add new scrap pieces to the scrap list"""
        scrap_blocks_list_temp = []
        
        for scrap_vol in scrap_volumes:
            self.scrap_count += 1
            rot = Rotation()
            scrap_starting_point, scrap_size = rot.get_starting_co_and_size(scrap_vol, after_rotation=False)
            
            if self.is_small_size(scrap_size):
                continue
            
            s = Scrap('s' + str(self.scrap_count), scrap_size, scrap_starting_point)
            block.add_scrap(s)
            scrap_blocks_list_temp.append(s)
        
        # Sort by volume (smallest first)
        scrap_blocks_list_temp = sorted(scrap_blocks_list_temp, key=lambda s: s.volume)
        self.all_scrap.extend(scrap_blocks_list_temp)
        
        return scrap_blocks_list_temp
    
    def delete_scrap(self, scrap: Scrap):
        """Remove a scrap from tracking"""
        if scrap in self.all_scrap:
            self.all_scrap.remove(scrap)
        scrap.delete_scrap()


def get_block_details(helper: People_helper) -> Dict[str, Any]:
    """
    Extract detailed results from packing operation
    
    Returns:
        Dictionary with block details, efficiency, and scrap information
    """
    block_details = {
        "Total_number_of_blocks": len(helper.all_big_blocks),
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
        total_stock_volume += size[0] * size[1] * size[2]
        total_eff_sum += block_eff
        
        # Count prisms by code
        prism_count_dict = {}
        for entry in block.prism_details:
            prism = entry['prism']
            count = len(entry['coordinates'])
            volume = prism.get_volume()
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
            "prisms": prism_list
        })
    
    # Calculate total efficiency
    if len(helper.all_big_blocks) > 0:
        block_details["Total_eff"] = round(total_eff_sum / len(helper.all_big_blocks), 2)
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
                   parent_block_sizes: List[List[float]] = None) -> People_helper:
    """
    Main packing algorithm
    
    Args:
        all_prisms: List of Prism objects to pack
        buffer: Spacing between parts
        parent_block_sizes: Available stock block dimensions
    
    Returns:
        People_helper object with packing results
    """
    if parent_block_sizes is None:
        parent_block_sizes = [[2000, 800, 400], [2000, 500, 500]]
    
    helper = People_helper(buffer, parent_block_sizes)
    
    for prism in all_prisms[:]:
        # Try to pack into existing scraps
        helper.try_to_pack_inside_all_scrap(prism)
        
        # Pack remaining prisms into new blocks
        while prism.prism_left > 0:
            # Determine best block size
            size = helper.check_which_block_to_add(prism)
            
            # Create new block
            b = helper.add_one_big_block(size)
            
            # Fill the block
            result = helper.fill_the_prism_optimally(prism, b)
            
            if result[0] is None:
                # Packing failed - discard the empty block just created so it
                # doesn't inflate block count / deflate reported efficiency,
                # and break to avoid an infinite loop. The prism stays in the
                # summary as "remaining" (could not be packed).
                helper.all_big_blocks.remove(b)
                helper.big_block_count -= 1
                print(f"Warning: Could not pack remaining {prism.prism_left} units of {prism.code}")
                break
            
            co_ordinates_list, big_block_coordinate, scrap_volumes, prism_count, scrap_blocks_list_temp = result
            
            # Try to pack into newly created scraps
            helper.try_to_pack_inside_all_scrap(prism, scrap_blocks_list_temp)
    
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
                                   buffer: float = 2, max_tries: int = 10000) -> Tuple[People_helper, Dict]:
    """
    Run optimization with multiple retries to find best solution
    
    Args:
        excel_path: Path to Excel file
        parent_block_sizes: Stock block dimensions
        buffer: Spacing between parts
        max_tries: Maximum retry attempts
    
    Returns:
        (helper, block_details) tuple
    """
    if parent_block_sizes is None:
        parent_block_sizes = [[1870, 800, 350], [2000, 800, 400]]
    
    tried = 0
    last_error = None
    same_error_count = 0

    while tried <= max_tries:
        try:
            # Load prisms
            all_prisms = get_all_prisms(excel_path)

            # Sort by volume (largest first)
            prism_list_sorted = sorted(all_prisms, key=lambda p: p.get_volume(), reverse=True)

            # Run packing
            helper = run_final_code(prism_list_sorted, buffer=buffer, parent_block_sizes=parent_block_sizes)

            # Get results
            block_details = get_block_details(helper)

            if block_details is not None and helper is not None:
                # Check if any block has >= 99% efficiency (too good to be true)
                has_perfect_block = any(obj['eff'] >= 99 for obj in block_details['blocks'])

                if not has_perfect_block:
                    return helper, block_details

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
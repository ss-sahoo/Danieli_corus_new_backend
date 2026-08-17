# ================================
# GLOBAL OPTIMIZATION STATE (DEV)
# ================================

GLOBAL_OPTIMIZATION_STATE = {
    "helper": None
}
"""
API views for the cutting optimization planner.
"""
from datetime import datetime
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import os
import pandas as pd
import json
import sys
import time

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def generate_block_6_side_images(block, output_dir, block_code):
    """
    Generate a single HTML file with 6-side views of a block using SVGs.
    """
    try:
        from .modules.svg_renderer import get_block_svg_html
        os.makedirs(output_dir, exist_ok=True)
        html_path = os.path.join(output_dir, f"{block_code}_6_sides.html")
        
        html_content = get_block_svg_html(block, block_code)
        
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        if os.path.exists(html_path):
            print(f"  ✓ Generated 6-side SVG HTML for {block_code}: {html_path}")
            return html_path
        else:
            print(f"  ✗ Failed to generate SVG HTML for {block_code}")
            return None
            
    except Exception as e:
        print(f"Error in generate_block_6_side_images: {e}")
        import traceback
        traceback.print_exc()
        return None


def generate_all_blocks_master_html(blocks, output_path, job_label):
    """
    Generate a master HTML file showing all blocks with their 6-side SVG views.
    Optimized for printing.
    """
    try:
        from .modules.svg_renderer import generate_svg_for_block_side
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{job_label} - All Blocks 6-Side Views</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: #f8fafc;
            padding: 15px;
            color: #1e293b;
        }}
        
        .page-header {{
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            color: white;
            padding: 24px;
            border-radius: 12px;
            margin-bottom: 24px;
            text-align: center;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}
        
        .page-header h1 {{
            font-size: 26px;
            font-weight: 700;
            margin-bottom: 8px;
        }}
        
        .page-header p {{
            font-size: 14px;
            opacity: 0.85;
        }}
        
        .block-section {{
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 24px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
            page-break-after: always;
            page-break-inside: avoid;
        }}
        
        .block-section:last-child {{
            page-break-after: auto;
        }}
        
        .block-header {{
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 12px;
            margin-bottom: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        .block-title {{
            font-size: 20px;
            font-weight: 700;
            color: #0f172a;
        }}
        
        .block-info {{
            font-size: 13px;
            color: #64748b;
        }}
        
        .views-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
        }}
        
        .view-item {{
            border: 1px solid #f1f5f9;
            border-radius: 8px;
            padding: 12px;
            background: #ffffff;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        
        .view-label {{
            font-size: 11px;
            font-weight: 600;
            color: #475569;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        .view-plot {{
            width: 100%;
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        
        /* Print-specific styles */
        @media print {{
            body {{
                background: white;
                padding: 0;
            }}
            
            @page {{
                size: A4 landscape;
                margin: 8mm;
            }}
            
            .page-header {{
                background: white !important;
                color: black !important;
                border: 2px solid #0f172a;
                padding: 15px;
                margin-bottom: 20px;
                box-shadow: none;
                page-break-after: avoid;
            }}
            
            .block-section {{
                box-shadow: none;
                border: 2px solid #e2e8f0;
                page-break-after: always;
                padding: 15px;
            }}
            
            .block-section:last-child {{
                page-break-after: auto;
            }}
            
            .print-button {{
                display: none !important;
            }}
            
            .views-grid {{
                grid-template-columns: repeat(3, 1fr) !important;
                gap: 10px !important;
            }}
            
            .view-item {{
                border: 1px solid #e2e8f0 !important;
                page-break-inside: avoid;
            }}
        }}
        
        /* Print button */
        .print-button {{
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: white;
            border: none;
            padding: 14px 28px;
            border-radius: 50px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(15, 23, 42, 0.3);
            z-index: 1000;
            transition: all 0.3s;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .print-button:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(15, 23, 42, 0.5);
        }}
        
        .zoom-controls {{
            position: fixed;
            bottom: 90px;
            right: 36px;
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
    
    <button class="print-button" onclick="window.print()">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 6 2 18 2 18 9"></polyline><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path><rect x="6" y="14" width="12" height="8"></rect></svg>
        Print Report
    </button>
    
    <div id="zoomable-content" style="transform-origin: top left; transition: transform 0.1s; will-change: transform;">
    
    <div class="page-header">
        <h1>{job_label} - Optimization Results</h1>
        <p>Generated: {datetime.now().strftime('%B %d, %Y at %H:%M')} | Total Blocks: {len(blocks)}</p>
    </div>
"""
        
        sides = ['Front', 'Back', 'Left', 'Right', 'Top', 'Bottom']
        colors_palette = [
            "#4F46E5", "#10B981", "#F59E0B", "#EC4899", "#3B82F6", "#8B5CF6", "#06B6D4", "#F97316",
            "#84CC16", "#14B8A6", "#D946EF", "#0EA5E9", "#A855F7", "#E11D48", "#6366F1", "#059669",
            "#D97706", "#DB2777", "#2563EB", "#7C3AED", "#EA580C", "#65A30D", "#0D9488", "#C084FC",
            "#818CF8", "#34D399", "#FBBF24", "#F472B6", "#60A5FA", "#A78BFA", "#fb923c", "#a3e635",
            "#2dd4bf", "#38bdf8", "#1e1b4b", "#064e3b", "#78350f", "#50072b", "#1e3a8a", "#3b0764",
            "#083344", "#431407"
        ]
        
        from .modules.packing_orchestrator import get_prism_color_mapping
        
        for block in blocks:
            efficiency = block.get_efficiency()
            size = block.size
            volume = block.volume
            
            # Retrieve color mapping and legend items for the current block
            color_map, block_legend_items, legend_map = get_prism_color_mapping(block)
            
            legend_items = []
            for label, col, _ in block_legend_items:
                legend_items.append((label, col))
            
            has_scraps = len(getattr(block, 'scraps', [])) > 0
            legend_html = ""
            if legend_items or has_scraps:
                legend_html = '<div class="block-legend" style="display: flex; gap: 16px; margin: -4px 0 16px 0; flex-wrap: wrap; align-items: center; background: #f8fafc; padding: 10px 16px; border-radius: 8px; border: 1px solid #e2e8f0; width: 100%;">'
                legend_html += '<span style="font-size: 11px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; margin-right: 4px;">Color Legend:</span>'
                for code, color in legend_items:
                    legend_html += f"""
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="width: 14px; height: 14px; background-color: {color}; border-radius: 4px; display: inline-block; border: 1px solid rgba(0,0,0,0.15);"></span>
                        <span style="font-size: 12px; font-weight: 600; color: #334155;">{code}</span>
                    </div>
                    """
                if has_scraps:
                    legend_html += """
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <span style="width: 14px; height: 14px; background-color: rgba(239, 68, 68, 0.35); border: 1.5px dashed #EF4444; border-radius: 4px; display: inline-block;"></span>
                        <span style="font-size: 12px; font-weight: 600; color: #334155;">Scrap</span>
                    </div>
                    """
                legend_html += '</div>'
            
            html_content += f"""
    <div class="block-section">
        <div class="block-header">
            <span class="block-title">Block {block.unique_code}</span>
            <span class="block-info">
                <strong>Efficiency:</strong> {efficiency:.2f}% &nbsp;|&nbsp; 
                <strong>Size:</strong> {size[0]:.0f} × {size[1]:.0f} × {size[2]:.0f} mm &nbsp;|&nbsp; 
                <strong>Volume:</strong> {volume:,.0f} mm³
            </span>
        </div>
        {legend_html}
        <div class="views-grid">
"""
            for side in sides:
                svg_markup = generate_svg_for_block_side(block, side)
                html_content += f"""
            <div class="view-item">
                <div class="view-label">{side} view</div>
                <div class="view-plot">
                    {svg_markup}
                </div>
            </div>
"""
            html_content += """
        </div>
    </div>
"""
            
        html_content += """
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
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        print(f"✓ Generated SVG-optimized master HTML: {output_path}")
        return output_path
        
    except Exception as e:
        print(f"Error in generate_all_blocks_master_html: {e}")
        import traceback
        traceback.print_exc()
        return None


from .models import (
    StockBlock,
    PartSpecification,
    CuttingJob,
    Configuration,
    ConfigurationSet
)
from .serializers import (
    StockBlockSerializer,
    PartSpecificationSerializer,
    CuttingJobSerializer,
    CuttingJobCreateSerializer,
    ConfigurationSerializer,
    ConfigurationSetSerializer,
    Top3ConfigurationsRequestSerializer,
    Top3ConfigurationsResponseSerializer,
)
from .services import get_cutting_service
from .run_summary import build_summary, layout_signature, stock_sizes_from, summary_for_history


# ============================================================
# CACHE HELPERS
# ============================================================
# The cache is a Redis instance holding the pickled People_helper so the visualization
# endpoints can read it back. It is a convenience, not the record: every run is also
# persisted to OptimizationHistory and pickled to MEDIA_ROOT/helpers/<id>.pkl, and
# get_helper_for_job falls back to that file.
#
# django-redis raises on a connection failure rather than degrading, so an unguarded
# cache.set turns a finished optimization into a 500 and throws the whole run away -
# minutes of packing lost, no history row written, because a cache was unreachable.
# Route writes and reads that must not do that through these.

def cache_set_safe(key, value, timeout=None, label=None):
    """Write to the cache; on failure log and carry on. Returns True when it landed."""
    try:
        from django.core.cache import cache
        cache.set(key, value, timeout=timeout)
        return True
    except Exception as e:
        print(f"[CACHE] Could not write {label or key}: {e}")
        print(f"[CACHE] Continuing - the result is still saved to history and disk. "
              f"Visualizations may need a job_id until the cache is reachable.")
        return False


def cache_get_safe(key, default=None, label=None):
    """Read from the cache; on failure return default rather than raising."""
    try:
        from django.core.cache import cache
        return cache.get(key)
    except Exception as e:
        print(f"[CACHE] Could not read {label or key}: {e}")
        return default


def cache_delete_safe(key, label=None):
    """Evict a stale entry; on failure log and carry on."""
    try:
        from django.core.cache import cache
        cache.delete(key)
        return True
    except Exception as e:
        print(f"[CACHE] Could not evict {label or key}: {e}")
        return False


# Import from your new modules
try:
    from .modules.packing_module import OptimizationEngine, pack_trapezoidal_prisms as new_pack_trapezoidal_prisms
    from .modules.packing_orchestrator import Prisms, run_final_code, get_block_details, run_optimization_with_retries
except ImportError as e:
    print(f"Warning: Could not import packing modules: {e}")
    OptimizationEngine = None
    new_pack_trapezoidal_prisms = None
    Prisms = None
    run_final_code = None
    get_block_details = None




# ================================
# FILE UPLOAD VIEW FUNCTION
# ================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_excel_file(request):
    """
    Handle Excel file upload and return processed block data.
    
    POST /api/upload/
    Content-Type: multipart/form-data
    Body: file (Excel file with block data)
    
    Returns:
    {
        "success": true,
        "data": [
            {
                "MARK": "G14",
                "Bottom Length": 150.0,
                "Top Length": 100.0,
                "Width": 80.0,
                "Height": 40.0,
                "Nos": 5
            },
            ...
        ],
        "totalRows": 10,
        "message": "Successfully processed 10 blocks"
    }
    """
    try:
        # Check if file was uploaded
        if 'file' not in request.FILES:
            return Response(
                {'success': False, 'error': 'No file uploaded'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES['file']
        
        # Validate file type
        file_name = file.name.lower()
        if not (file_name.endswith('.xlsx') or 
                file_name.endswith('.xls') or 
                file_name.endswith('.csv')):
            return Response(
                {'success': False, 'error': 'Invalid file type. Please upload .xlsx, .xls, or .csv files'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        print(f"[File Upload] Processing file: {file_name}")
        
        # Read the file based on type
        try:
            if file_name.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file, engine='openpyxl')
        except Exception as e:
            return Response(
                {'success': False, 'error': f'Error reading file: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        print(f"[File Upload] DataFrame columns: {df.columns.tolist()}")
        print(f"[File Upload] DataFrame shape: {df.shape}")
        
        # Clean column names (remove whitespace, lowercase for matching)
        df.columns = [str(col).strip() for col in df.columns]
        
        # Define expected columns and their possible variations
        column_variations = {
            'MARK': ['MARK', 'mark', 'Mark', 'Block ID', 'BLOCK ID', 'block_id', 'ID', 'id'],
            'Bottom Length': ['Bottom Length', 'BottomLength', 'Bottom_Length', 'bottom length', 
                             'bottom_length', 'Bottom', 'BLENGTH', 'B Length', 'Base Length', 
                             'base length', 'BASE LENGTH', 'Long Base', 'A(W1)', 'A', 'W1'],
            'Top Length': ['Top Length', 'TopLength', 'Top_Length', 'top length', 'top_length', 
                          'Top', 'TLENGTH', 'T Length', 'Short Base', 'short base', 'SHORT BASE', 
                          'B(W2)', 'B', 'W2'],
            'Width': ['Width', 'width', 'WIDTH', 'W', 'w', 'Breadth', 'breadth', 'BREADTH', 
                     'D(length)', 'D', 'length'],
            'Height': ['Height', 'height', 'HEIGHT', 'H', 'h', 'Thickness', 'thickness', 
                      'THICKNESS', 'Depth', 'depth', 'DEPTH'],
            'Nos': ['Nos', 'nos', 'NOS', 'Quantity', 'quantity', 'QTY', 'qty', 'Count', 
                   'count', 'COUNT', 'Number', 'number', 'NUMBER', 'Units', 'units', 'UNITS']
        }
        
        # Map actual columns to standard names
        column_mapping = {}
        for standard_name, variations in column_variations.items():
            for col in df.columns:
                # Case-insensitive matching
                if str(col).lower() in [v.lower() for v in variations]:
                    column_mapping[col] = standard_name
                    print(f"[File Upload] Mapped column '{col}' -> '{standard_name}'")
                    break
        
        # Apply the mapping
        df.rename(columns=column_mapping, inplace=True)
        
        print(f"[File Upload] After renaming columns: {df.columns.tolist()}")
        
        # Check if we have the essential MARK column
        if 'MARK' not in df.columns:
            return Response(
                {'success': False, 'error': 'File must contain a MARK/Block ID column'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Process each row
        processed_data = []
        for index, row in df.iterrows():
            # Skip empty rows (where MARK is NaN or empty)
            mark_value = row.get('MARK')
            if pd.isna(mark_value) or str(mark_value).strip() == '':
                continue
            
            block_data = {}
            
            # Process each standard column
            standard_columns = ['MARK', 'Bottom Length', 'Top Length', 'Width', 'Height', 'Nos']
            
            for col in standard_columns:
                if col in df.columns:
                    value = row[col]
                    # Convert to appropriate type
                    if pd.isna(value):
                        block_data[col] = None
                    elif col == 'MARK':
                        # Keep MARK as string
                        block_data[col] = str(value).strip()
                    else:
                        # Try to convert numeric columns to float
                        try:
                            if col == 'Nos':
                                block_data[col] = int(float(value))
                            else:
                                block_data[col] = float(value)
                        except (ValueError, TypeError):
                            # If conversion fails, keep as string or None
                            try:
                                block_data[col] = str(value).strip()
                            except:
                                block_data[col] = None
                else:
                    block_data[col] = None
            
            processed_data.append(block_data)
        
        print(f"[File Upload] Processed {len(processed_data)} rows")
        
        if len(processed_data) == 0:
            return Response(
                {'success': False, 'error': 'No valid data found in the file'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Return success response
        return Response({
            'success': True,
            'data': processed_data,
            'totalRows': len(processed_data),
            'message': f'Successfully processed {len(processed_data)} blocks'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        print(f"[File Upload] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return Response(
            {
                'success': False, 
                'error': f'Error processing file: {str(e)}'
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ================================
# VISUALIZATION FUNCTIONS
# ================================

@api_view(['GET', 'HEAD'])
@permission_classes([IsAuthenticated])
def download_block_visualization(request, block_code):
    """
    Generate and download a block visualization HTML file.
    GET /api/visualization/block/<block_code>/download/?job_id=7
    """
    try:
        from django.conf import settings
        from django.core.cache import cache
        import zipfile, io

        # Safe read: with the cache unreachable this reports "not ready" like an expired
        # entry, rather than a 500 with a Redis traceback.
        helper = cache_get_safe("latest_helper", label="latest_helper")
        if helper is None:
            return Response({"success": False, "error": "Optimization data not ready."}, status=400)

        block = next((b for b in helper.all_big_blocks if b.unique_code == block_code), None)
        if block is None:
            return Response({"success": False, "error": f"Block {block_code} not found"}, status=404)

        viz_dir = os.path.join(settings.MEDIA_ROOT, "visualizations")
        os.makedirs(viz_dir, exist_ok=True)

        job_id = request.GET.get("job_id", "OPT")
        job_label = f"OPT-{str(job_id).zfill(4)}" if str(job_id).isdigit() else str(job_id)
        filename = f"{job_label}_{block_code}_3D-Visualization.html"
        filepath = os.path.join(viz_dir, filename)

        block.draw_it(only_scrap=False, save_path=filepath)

        if not os.path.exists(filepath):
            return Response({"success": False, "error": "Failed to generate visualization file."}, status=500)

        response = FileResponse(open(filepath, "rb"), content_type="text/html")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({"success": False, "error": str(e)}, status=500)


def ensure_up_to_date_visualizations(job_id):
    if not job_id or not str(job_id).isdigit():
        return
    try:
        from django.conf import settings
        from django.core.cache import cache
        
        cache_key = f"regen_v3_{job_id}"
        job_label = f"OPT-{int(job_id):04d}"
        master_html_path = os.path.join(settings.MEDIA_ROOT, "block_html", str(job_id), f"{job_label}_All_Blocks_6_Sides.html")
        
        if cache.get(cache_key) and os.path.exists(master_html_path):
            print(f"[REGENERATE] Job {job_id} already generated and files exist, skipping.")
            return
            
        helper = get_helper_for_job(job_id, cache)
        if helper is None:
            print(f"[REGENERATE] Failed to retrieve helper for job {job_id}")
            return
            
        html_base_dir = os.path.join(settings.MEDIA_ROOT, "block_html", str(job_id))
        os.makedirs(html_base_dir, exist_ok=True)
        
        for block in helper.all_big_blocks:
            generate_block_6_side_images(block, html_base_dir, block.unique_code)
            
        generate_all_blocks_master_html(helper.all_big_blocks, master_html_path, job_label)
        cache.set(cache_key, True, timeout=None)
        print(f"[REGENERATE] Successfully regenerated visualizations for job {job_id}")
    except Exception as e:
        print(f"[REGENERATE] Failed to regenerate: {e}")


@api_view(['GET', 'HEAD'])
@permission_classes([IsAuthenticated])
def download_block_images(request, block_code):
    """
    Download 6-side HTML view of a block.
    GET /api/visualization/block/<block_code>/images/?job_id=7
    """
    try:
        from django.conf import settings
        
        job_id = request.GET.get("job_id", "")
        if not job_id:
            return Response({"success": False, "error": "job_id parameter required"}, status=400)
        
        ensure_up_to_date_visualizations(job_id)
        
        # Path where HTML files are stored
        html_dir = os.path.join(settings.MEDIA_ROOT, "block_html", str(job_id))
        html_path = os.path.join(html_dir, f"{block_code}_6_sides.html")
        
        if not os.path.exists(html_path):
            return Response({"success": False, "error": "Block HTML not found. Run optimization first."}, status=404)
        
        job_label = f"OPT-{str(job_id).zfill(4)}"
        filename = f"{job_label}_{block_code}_6-Sides.html"
        
        response = FileResponse(open(html_path, "rb"), content_type="text/html")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({"success": False, "error": str(e)}, status=500)


@api_view(['GET', 'HEAD'])
@permission_classes([IsAuthenticated])
def download_all_blocks_zip(request):
    """
    Download master HTML with ALL blocks and their 6-side views.
    GET /api/visualization/blocks/download-all/?job_id=7
    """
    try:
        from django.conf import settings
        
        job_id = request.GET.get("job_id", "")
        if not job_id:
            return Response({"success": False, "error": "job_id parameter required"}, status=400)
        
        ensure_up_to_date_visualizations(job_id)
        
        job_label = f"OPT-{str(job_id).zfill(4)}" if str(job_id).isdigit() else str(job_id)
        
        # Path to master HTML
        html_dir = os.path.join(settings.MEDIA_ROOT, "block_html", str(job_id))
        master_html_path = os.path.join(html_dir, f"{job_label}_All_Blocks_6_Sides.html")
        
        if not os.path.exists(master_html_path):
            return Response({"success": False, "error": "Master HTML not found. Run optimization first."}, status=404)
        
        filename = f"{job_label}_All_Blocks_6_Sides.html"
        
        response = FileResponse(open(master_html_path, "rb"), content_type="text/html")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({"success": False, "error": str(e)}, status=500)


@api_view(['GET', 'HEAD'])
@permission_classes([AllowAny])
def view_all_blocks(request):
    """
    View master HTML with ALL blocks inline (not as download).
    The browser renders the HTML directly so CDN scripts (Plotly) can load.
    Auth is via ?token= query parameter since this opens in a new browser tab.
    GET /api/visualization/blocks/view-all/?job_id=7&token=<JWT>
    """
    try:
        from django.conf import settings
        from rest_framework_simplejwt.tokens import AccessToken
        
        # Auth via query param (can't send headers when opening in new tab)
        token = request.GET.get("token", "")
        if not token:
            return Response({"error": "Authentication required"}, status=401)
        
        try:
            AccessToken(token)  # Validates the token
        except Exception:
            return Response({"error": "Invalid or expired token"}, status=401)
        
        job_id = request.GET.get("job_id", "")
        if not job_id:
            return Response({"error": "job_id parameter required"}, status=400)
        
        ensure_up_to_date_visualizations(job_id)
        
        job_label = f"OPT-{str(job_id).zfill(4)}" if str(job_id).isdigit() else str(job_id)
        
        html_dir = os.path.join(settings.MEDIA_ROOT, "block_html", str(job_id))
        master_html_path = os.path.join(html_dir, f"{job_label}_All_Blocks_6_Sides.html")
        
        if not os.path.exists(master_html_path):
            return Response({"error": "Master HTML not found. Run optimization first."}, status=404)
        
        # Serve inline (no Content-Disposition: attachment) so browser renders it
        response = FileResponse(open(master_html_path, "rb"), content_type="text/html")
        response["Content-Disposition"] = f'inline; filename="{job_label}_All_Blocks_6_Sides.html"'
        return response
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({"error": str(e)}, status=500)


def get_helper_for_job(job_id, cache):
    helper = None
    if not job_id:
        # No job_id means "whatever ran last", which only the cache knows. With the cache
        # down there is nothing to fall back to, so the caller reports "not ready" rather
        # than surfacing a Redis traceback; passing a job_id works via the disk pickle.
        helper = cache_get_safe("latest_helper", label="latest_helper")
    else:
        helper_cache_key = f"helper_objs_{job_id}"
        cached_helper = cache_get_safe(helper_cache_key, label=helper_cache_key)
        if cached_helper is not None:
            helper = cached_helper
        else:
            # Try loading from pickled helper on disk first for perfect fidelity
            try:
                import pickle
                import os
                from django.conf import settings
                pkl_path = os.path.join(settings.MEDIA_ROOT, "helpers", f"{job_id}.pkl")
                if os.path.exists(pkl_path):
                    with open(pkl_path, "rb") as f:
                        helper = pickle.load(f)
                    cache_set_safe(helper_cache_key, helper, timeout=1800,
                                   label=helper_cache_key)
                    print(f"[GET_HELPER] Successfully loaded pickled helper from disk for job_id={job_id}")
            except Exception as e:
                print(f"[GET_HELPER] Failed to load pickled helper for job {job_id}: {e}")

            if helper is None:
                try:
                    from .models import OptimizationHistory
                    from .modules.packing_orchestrator import Prisms, run_final_code
                    history = OptimizationHistory.objects.get(id=int(job_id))
                    parts_data = history.uploaded_file_data
                    buffer_spacing = history.parameters.get('buffer_spacing', 2)
                    parent_block_sizes = history.parameters.get('parent_blocks_used', [])
                    # Supply constraints have to be replayed too, or the reconstruction packs
                    # against unlimited stock and no scrap, producing a layout that does not
                    # match the plan whose visualization is being requested.
                    parent_block_quantities = history.parameters.get('parent_block_quantities')
                    recovered_stock = history.parameters.get('recovered_stock') or []

                    all_prisms = []
                    for part in parts_data:
                        bottom_len = part.get('Bottom Length', part.get('bottom_length', 0))
                        top_len = part.get('Top Length', part.get('top_length', 0))
                        width = part.get('Width', part.get('width', 0))
                        height = part.get('Height', part.get('height', 0))
                        mark = part.get('MARK', part.get('code', 'Part'))
                        nos = part.get('Nos', part.get('requested', 0))
                        
                        size = [bottom_len, top_len, width, height]
                        all_prisms.append(Prisms(mark, size, int(nos)))
                        
                    prism_list_sorted = sorted(all_prisms, key=lambda p: p.get_volume(), reverse=True)
                    helper = run_final_code(prism_list_sorted, buffer=buffer_spacing,
                                            parent_block_sizes=parent_block_sizes,
                                            parent_block_quantities=parent_block_quantities,
                                            recovered_stock=recovered_stock)

                    cache_set_safe(helper_cache_key, helper, timeout=1800,
                                   label=helper_cache_key)
                except Exception as e:
                    print(f"[GET_HELPER] Error reconstructing helper for job {job_id}: {e}")
                    helper = cache_get_safe("latest_helper", label="latest_helper")

    if helper:
        for b in helper.all_big_blocks:
            b.parent_helper = helper
    return helper


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_block_visualization(request, block_code):
    try:
        from django.conf import settings
        from django.core.cache import cache
        import os
        
        job_id = request.data.get('job_id') or request.GET.get('job_id') or request.query_params.get('job_id')
        helper = get_helper_for_job(job_id, cache)
        if helper is None:
            return Response({
                "success": False,
                "error": "Optimization data not ready. Please run optimization first."
            }, status=400)
        
        # Find the block
        block = None
        for b in helper.all_big_blocks:
            if b.unique_code == block_code:
                block = b
                break
        
        if block is None:
            # Try by index. Only B-codes are positional; an R-code is a recovered block
            # whose number comes from its own counter, so indexing all_big_blocks with it
            # would return an unrelated block (and int('R1'[1:]) is not the same series).
            try:
                if block_code.startswith('B'):
                    block_index = int(block_code.replace("B", "")) - 1
                    if 0 <= block_index < len(helper.all_big_blocks):
                        block = helper.all_big_blocks[block_index]
            except:
                pass
        
        if block is None:
            return Response({
                "success": False,
                "error": f"Block {block_code} not found"
            }, status=404)
        
        # Create visualization directory
        viz_dir = os.path.join(settings.MEDIA_ROOT, "visualizations")
        os.makedirs(viz_dir, exist_ok=True)
        
        # Generate visualization
        filename = f"block_{block.unique_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        filepath = os.path.join(viz_dir, filename)
        try:
            # FIX: Pass save_path parameter to actually save the file
            block.draw_it(only_scrap=False, save_path=filepath)
            
            # Verify the file was created
            if not os.path.exists(filepath):
                raise Exception(f"Visualization file not created at {filepath}")
                
        except Exception as draw_error:
            print(f"Error drawing block: {draw_error}")
            return Response({
                "success": False,
                "error": f"Could not generate visualization: {draw_error}"
            }, status=500)
        
        return Response({
            "success": True,
            "visualization_url": f"/media/visualizations/{filename}",
            "message": f"Visualization generated for block {block.unique_code}"
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({
            "success": False,
            "error": str(e)
        }, status=500)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_scrap_visualization(request, scrap_code):
    try:
        from django.conf import settings
        from django.core.cache import cache
        from datetime import datetime
        import os, time

        job_id = request.data.get('job_id') or request.GET.get('job_id') or request.query_params.get('job_id')
        helper = get_helper_for_job(job_id, cache)
        if helper is None:
            return Response({
                "success": False,
                "error": "Optimization data not ready. Please retry."
            }, status=400)

        scrap = next(
            (s for s in helper.all_scrap if s.unique_code == scrap_code),
            None
        )

        if scrap is None:
            return Response({
                "success": False,
                "error": "Invalid scrap code"
            }, status=404)

        viz_dir = os.path.join(settings.MEDIA_ROOT, "visualizations")
        os.makedirs(viz_dir, exist_ok=True)

        filename = f"scrap_{scrap.unique_code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        filepath = os.path.join(viz_dir, filename)
        scrap.draw_scrap(save_path=filepath)

        for _ in range(30):
            if os.path.exists(filepath) and os.path.getsize(filepath) > 1024:
                break
            time.sleep(0.1)

        return Response({
            "success": True,
            "visualization_url": f"/media/visualizations/{filename}"
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({
            "success": False,
            "error": str(e)
        }, status=500)



@api_view(['GET', 'HEAD'])
def get_visualization_file(request, filename):
    """
    Serve visualization HTML file
    
    GET /api/visualization/file/{filename}/
    """
    try:
        # Construct full path
        from django.conf import settings
        viz_dir = os.path.join(settings.MEDIA_ROOT, 'visualizations')
        filepath = os.path.join(viz_dir, filename)
        
        # Security check
        filepath = os.path.abspath(filepath)
        viz_dir = os.path.abspath(viz_dir)
        
        if not filepath.startswith(viz_dir):
            raise Http404("Invalid file path")
        
        if not os.path.exists(filepath):
            raise Http404("File not found")
        
        # Serve file
        return FileResponse(open(filepath, 'rb'), content_type='text/html')
        
    except Exception as e:
        raise Http404(f"Error serving file: {e}")


# ================================
# MAIN OPTIMIZATION ENDPOINT (UPDATED)
# ================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_and_optimize(request):
    """
    Upload Excel file and run optimization with custom parent blocks and retry logic
    
    POST /api/upload-optimize/
    Content-Type: multipart/form-data
    
    Form Data:
    - file: Excel file
    - selected_blocks: JSON array of selected block IDs (optional)
    - parent_blocks: JSON array of parent block sizes (required)
    - buffer_spacing: float (default: 2.0)
    - max_retries: int (default: 10000, optional)
    - retry_enabled: bool (default: True, optional)
    """
    try:
        from django.utils import timezone
        from django.core.cache import cache
        from django.conf import settings
        import json
        import pandas as pd
        import os
        import tempfile
        import traceback
        import shutil
        
        # ====================
        # 1. VALIDATE INPUTS
        # ====================
        print(f"\n=== OPTIMIZATION REQUEST STARTED ===")
        print(f"User: {request.user.username}")
        print(f"Timestamp: {timezone.now().isoformat()}")
        
        # Get uploaded file
        excel_file = request.FILES.get('file')
        if not excel_file:
            return Response({
                'success': False,
                'error': 'No file uploaded'
            }, status=400)
        
        # Get parameters
        selected_blocks_json = request.POST.get('selected_blocks', '[]')
        parent_blocks_json = request.POST.get('parent_blocks', '[]')
        buffer_spacing = float(request.POST.get('buffer_spacing', '2.0'))
        max_retries = int(request.POST.get('max_retries', '5000'))
        retry_enabled = request.POST.get('retry_enabled', 'true').lower() == 'true'

        # Supply stage 1 controls: cut racked offcuts before opening new stock.
        # Off by default, so a client that does not send these behaves exactly as before.
        use_scrap_inventory = str(
            request.POST.get('use_scrap_inventory', 'false')
        ).strip().lower() in ('true', '1', 'yes')
        scrap_inventory_ids_json = request.POST.get('scrap_inventory_ids', '')

        # How many legal packings to generate before keeping the best. Blank = let the
        # engine decide (1 unconstrained, 5 when supply is limited and outcomes vary).
        search_attempts_raw = str(request.POST.get('search_attempts', '')).strip()
        try:
            search_attempts = int(search_attempts_raw) if search_attempts_raw else None
        except ValueError:
            print(f"Warning: invalid search_attempts {search_attempts_raw!r}, using default")
            search_attempts = None

        try:
            selected_blocks = json.loads(selected_blocks_json)
            parent_blocks_data = json.loads(parent_blocks_json)
        except json.JSONDecodeError as e:
            return Response({
                'success': False,
                'error': f'Invalid JSON in parameters: {str(e)}'
            }, status=400)

        scrap_inventory_ids = None
        if scrap_inventory_ids_json.strip():
            try:
                scrap_inventory_ids = [int(v) for v in json.loads(scrap_inventory_ids_json)]
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                print(f"Warning: invalid scrap_inventory_ids, offering whole inventory: {e}")
                scrap_inventory_ids = None

        if use_scrap_inventory and scrap_inventory_ids:
            # Validate that none of the selected scrap IDs are already consumed by an executed run
            from .models import OptimizationHistory, ScrapInventory
            from rest_framework.exceptions import ValidationError
            
            executed_runs = OptimizationHistory.objects.filter(is_executed=True)
            consumed_ids = set()
            for run in executed_runs:
                c_ids = run.parameters.get('consumed_scrap_inventory_ids') or []
                for cid in c_ids:
                    consumed_ids.add(cid)
            
            conflict_ids = [cid for cid in scrap_inventory_ids if cid in consumed_ids]
            if conflict_ids:
                conflict_scraps = ScrapInventory.objects.filter(id__in=conflict_ids)
                conflict_details = []
                for s in conflict_scraps:
                    c_run = None
                    for run in executed_runs:
                        if s.id in (run.parameters.get('consumed_scrap_inventory_ids') or []):
                            c_run = run
                            break
                    c_run_str = f"'{c_run.job_name}'" if c_run else "an executed run"
                    conflict_details.append(f"#{s.id} ('{s.scrap_id}') is already consumed by optimization {c_run_str}")
                raise ValidationError(
                    "One or more selected scrap pieces are already consumed: " + "; ".join(conflict_details)
                )

        print(f"File: {excel_file.name} ({(excel_file.size/1024):.2f} KB)")
        print(f"Selected blocks: {len(selected_blocks)} items")
        print(f"Parent blocks data count: {len(parent_blocks_data)}")
        print(f"Buffer spacing: {buffer_spacing}")
        print(f"Max retries: {max_retries}")
        print(f"Retry enabled: {retry_enabled}")
        
        # ====================
        # 2. PROCESS PARENT BLOCKS
        # ====================
        parent_block_sizes = []
        parent_labels = []
        # Units of each size on hand, parallel to parent_block_sizes. None = unlimited,
        # which is what an entry without a quantity means and what every existing client
        # sends, so the default path is unchanged.
        parent_quantities = []

        if not parent_blocks_data:
            return Response({
                'success': False,
                'error': 'No parent blocks provided'
            }, status=400)

        for i, block in enumerate(parent_blocks_data):
            try:
                if isinstance(block, dict):
                    # Format: {"label": "800×350×1870", "dimensions": {"length": 1870, "width": 800, "height": 350}}
                    if 'dimensions' in block:
                        dims = block['dimensions']
                        length = float(dims.get('length', 0))
                        width = float(dims.get('width', 0))
                        height = float(dims.get('height', 0))
                    # Format: {"length": 1870, "width": 800, "height": 350}
                    elif 'length' in block and 'width' in block and 'height' in block:
                        length = float(block['length'])
                        width = float(block['width'])
                        height = float(block['height'])
                    else:
                        print(f"Warning: Parent block {i} has invalid format: {block}")
                        continue
                
                elif isinstance(block, list) and len(block) == 3:
                    # Format: [1870, 800, 350]
                    length = float(block[0])
                    width = float(block[1])
                    height = float(block[2])
                else:
                    print(f"Warning: Parent block {i} has invalid format: {block}")
                    continue
                
                # Validate dimensions
                if length <= 0 or width <= 0 or height <= 0:
                    print(f"Warning: Parent block {i} has non-positive dimensions: {length}x{width}x{height}")
                    continue
                
                # Optional stock limit. Only the dict shapes carry it; a bare [l, w, h]
                # stays unlimited. Absent, null or unparseable all mean unlimited rather
                # than rejecting the run, matching the forgiving style of this parser.
                quantity = None
                if isinstance(block, dict) and block.get('quantity') is not None:
                    try:
                        quantity = int(block['quantity'])
                        if quantity <= 0:
                            print(f"Warning: Parent block {i} has non-positive quantity "
                                  f"{block['quantity']}, skipping this size")
                            continue
                    except (TypeError, ValueError):
                        print(f"Warning: Parent block {i} has invalid quantity "
                              f"{block['quantity']!r}, treating as unlimited")
                        quantity = None

                # Add to lists
                parent_block_sizes.append([length, width, height])
                label = block.get('label', f'{length}×{width}×{height}') if isinstance(block, dict) else f'{length}×{width}×{height}'
                parent_labels.append(label)
                parent_quantities.append(quantity)

                print(f"Added parent block: {label} = [{length}, {width}, {height}]"
                      f" (qty: {'unlimited' if quantity is None else quantity})")

            except Exception as e:
                print(f"Error processing parent block {i}: {e}")
                continue

        if not parent_block_sizes:
            return Response({
                'success': False,
                'error': 'No valid parent blocks provided'
            }, status=400)

        print(f"Parent block sizes to use: {parent_block_sizes}")
        print(f"Parent block labels: {parent_labels}")
        print(f"Parent block quantities: {parent_quantities}")

        # ====================
        # 2b. COLLECT RECOVERED SCRAP (supply stage 1)
        # ====================
        # Offcuts racked from previous jobs. These are packed into before any stock is
        # opened, so every part they absorb is a part no new block has to be bought for.
        recovered_stock = []
        scrap_inventory_offered = 0

        if use_scrap_inventory:
            try:
                from .models import ScrapInventory

                # 'manual' rows are real offcuts a user entered by hand; 'usable' ones came
                # out of an executed run. Both are physically on the rack, unlike 'unusable'.
                inv_qs = ScrapInventory.objects.filter(
                    is_in_inventory=True,
                    usability__in=['usable', 'manual']
                )
                if scrap_inventory_ids is not None:
                    inv_qs = inv_qs.filter(id__in=scrap_inventory_ids)

                for s in inv_qs:
                    recovered_stock.append({
                        'id': s.id,
                        'scrap_id': s.scrap_id,
                        'size': [float(s.length), float(s.width), float(s.height)],
                    })

                scrap_inventory_offered = len(recovered_stock)
                print(f"Scrap inventory: offering {scrap_inventory_offered} racked pieces")

            except Exception as e:
                # Non-fatal: a run without recovered stock is still a valid run, it just
                # buys more material than it needed to.
                print(f"Error loading scrap inventory (non-critical): {e}")
                recovered_stock = []
                scrap_inventory_offered = 0

        # ====================
        # 3. PROCESS EXCEL FILE
        # ====================
        print(f"\nProcessing Excel file...")
        
        try:
            # Read the Excel file
            if excel_file.name.lower().endswith('.csv'):
                df = pd.read_csv(excel_file)
            else:
                df = pd.read_excel(excel_file, engine='openpyxl')
            
            print(f"Excel file loaded: {df.shape[0]} rows, {df.shape[1]} columns")
            print(f"Columns: {df.columns.tolist()}")
            
        except Exception as e:
            print(f"Error reading Excel file: {str(e)}")
            traceback.print_exc()
            return Response({
                'success': False,
                'error': f'Error reading Excel file: {str(e)}'
            }, status=400)
        
        # Clean column names
        df.columns = [str(col).strip() for col in df.columns]
        
        # Define expected columns and their possible variations
        column_mapping = {}
        for col in df.columns:
            col_lower = str(col).lower()
            
            if 'mark' in col_lower or 'code' in col_lower:
                column_mapping[col] = 'MARK'
            elif 'bottom' in col_lower and 'length' in col_lower:
                column_mapping[col] = 'Bottom Length'
            elif 'top' in col_lower and 'length' in col_lower:
                column_mapping[col] = 'Top Length'
            elif 'width' in col_lower or 'breadth' in col_lower or 'w' == col_lower:
                column_mapping[col] = 'Width'
            elif 'height' in col_lower or 'thickness' in col_lower or 'depth' in col_lower or 'h' == col_lower:
                column_mapping[col] = 'Height'
            elif 'nos' in col_lower or 'quantity' in col_lower or 'qty' in col_lower or 'count' in col_lower:
                column_mapping[col] = 'Nos'
        
        # Apply mapping
        df.rename(columns=column_mapping, inplace=True)
        
        print(f"After column mapping: {df.columns.tolist()}")
        
        # Check for required columns
        required_columns = ['MARK', 'Bottom Length', 'Top Length', 'Width', 'Height', 'Nos']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            print(f"Missing columns: {missing_columns}")
            return Response({
                'success': False,
                'error': f'Missing required columns: {", ".join(missing_columns)}'
            }, status=400)
        
        # Process each row
        parts_data = []
        for index, row in df.iterrows():
            try:
                # Skip empty rows
                mark_value = row.get('MARK')
                if pd.isna(mark_value) or str(mark_value).strip() == '':
                    continue
                
                # Extract and clean data
                part = {
                    'MARK': str(mark_value).strip(),
                    'Bottom Length': float(row.get('Bottom Length', 0)),
                    'Top Length': float(row.get('Top Length', 0)),
                    'Width': float(row.get('Width', 0)),
                    'Height': float(row.get('Height', 0)),
                    'Nos': int(float(row.get('Nos', 0)))
                }
                
                # Validate data
                if (part['Bottom Length'] <= 0 or part['Top Length'] <= 0 or 
                    part['Width'] <= 0 or part['Height'] <= 0 or part['Nos'] <= 0):
                    print(f"Warning: Row {index} has invalid dimensions or quantity: {part}")
                    continue
                
                parts_data.append(part)
                
            except Exception as e:
                print(f"Warning: Error processing row {index}: {e}")
                continue
        
        if not parts_data:
            return Response({
                'success': False,
                'error': 'No valid data found in Excel file'
            }, status=400)
        
        print(f"Successfully processed {len(parts_data)} parts from Excel")
        
        # Filter selected blocks if specified
        original_part_count = len(parts_data)
        if selected_blocks:
            parts_data = [p for p in parts_data if p['MARK'] in selected_blocks]
            print(f"Filtered to {len(parts_data)} selected parts (from {original_part_count})")
        
        # ====================
        # 4. PREPARE DATA FOR OPTIMIZATION
        # ====================
        print(f"\nPreparing data for optimization...")
        
        # Create a temporary Excel file with filtered data
        temp_file_path = None
        
        try:
            # Create a temporary directory for the Excel file
            temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_uploads')
            os.makedirs(temp_dir, exist_ok=True)
            
            # Generate a unique filename
            import uuid
            temp_filename = f"optimization_{uuid.uuid4().hex[:8]}_{excel_file.name}"
            temp_file_path = os.path.join(temp_dir, temp_filename)
            
            # Save filtered data to Excel
            df_filtered = pd.DataFrame(parts_data)
            if excel_file.name.lower().endswith('.csv'):
                df_filtered.to_csv(temp_file_path, index=False)
            else:
                df_filtered.to_excel(temp_file_path, index=False, engine='openpyxl')
            
            print(f"Created temporary file: {temp_file_path}")
            print(f"Temporary file size: {(os.path.getsize(temp_file_path)/1024):.2f} KB")
            
        except Exception as e:
            print(f"Error creating temporary file: {e}")
            # Continue without temporary file - we'll use direct approach
            
        # ====================
        # 5. RUN OPTIMIZATION WITH RETRY LOGIC
        # ====================
        print(f"\nRunning optimization with retry logic...")
        print(f"- Total prisms: {len(parts_data)}")
        print(f"- Parent block sizes: {len(parent_block_sizes)} options")
        print(f"- Buffer spacing: {buffer_spacing}")
        print(f"- Max retries: {max_retries}")
        print(f"- Retry enabled: {retry_enabled}")
        
        optimization_start_time = timezone.now()
        helper = None
        block_details = None
        
        try:
            if retry_enabled and temp_file_path and os.path.exists(temp_file_path):
                # Use the new run_optimization_with_retries function
                print(f"Using run_optimization_with_retries with max_tries={max_retries}")
                
                # Ensure we have the function imported
                from .modules.packing_orchestrator import run_optimization_with_retries
                
                helper, block_details = run_optimization_with_retries(
                    excel_path=temp_file_path,
                    parent_block_sizes=parent_block_sizes,
                    buffer=buffer_spacing,
                    max_tries=max_retries,
                    parent_block_quantities=parent_quantities,
                    recovered_stock=recovered_stock,
                    search_attempts=search_attempts
                )

                print(f"Optimization completed after retries")
                
            else:
                # Use the original direct approach without retries
                print(f"Using direct optimization approach (no retries)")
                
                # Create prism objects
                all_prisms = []
                for part in parts_data:
                    try:
                        size = [
                            part['Bottom Length'],
                            part['Top Length'],
                            part['Width'],
                            part['Height']
                        ]
                        
                        prism = Prisms(
                            code=part['MARK'],
                            size=size,
                            quantity=part['Nos']
                        )
                        
                        all_prisms.append(prism)
                        
                        print(f"Created prism: {part['MARK']} - {part['Nos']} units, Volume: {prism.get_volume():.2f}")
                        
                    except Exception as e:
                        print(f"Error creating prism {part.get('MARK', 'Unknown')}: {e}")
                        continue
                
                if not all_prisms:
                    raise Exception('No valid prism objects created from the data')
                
                # Sort prisms by volume (largest first for better packing)
                prism_list_sorted = sorted(all_prisms, key=lambda p: p.get_volume(), reverse=True)
                
                # Run the optimization
                helper = run_final_code(
                    all_prisms=prism_list_sorted,
                    buffer=buffer_spacing,
                    parent_block_sizes=parent_block_sizes,
                    parent_block_quantities=parent_quantities,
                    recovered_stock=recovered_stock
                )

                if helper is None:
                    raise Exception("Packing algorithm returned None")
                
                # Get block details
                block_details = get_block_details(helper)
                
            if helper is None:
                raise Exception("Optimization failed - no helper object returned")
            
            print(f"Optimization successful!")
            print(f"- Total blocks created: {len(helper.all_big_blocks)}")
            print(f"- Total scraps generated: {len(helper.all_scrap)}")
            
            # Associate parent_helper to block instances for consistent color mapping
            for b in helper.all_big_blocks:
                b.parent_helper = helper
            
            # Store helper in cache for visualization. Non-fatal: the packing is done and
            # about to be written to history and pickled to disk, so a cache outage must
            # not discard it.
            cache_set_safe(
                "latest_helper",
                helper,
                timeout=60 * 60 * 24 * 7,
                label="latest_helper"
            )

        except Exception as e:
            print(f"ERROR in optimization: {str(e)}")
            traceback.print_exc()
            
            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                    print(f"Cleaned up temporary file: {temp_file_path}")
                except:
                    pass
            
            return Response({
                'success': False,
                'error': f'Optimization failed: {str(e)}'
            }, status=500)
        
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                print(f"Cleaned up temporary file: {temp_file_path}")
            except Exception as e:
                print(f"Warning: Could not delete temporary file: {e}")
        
        # ====================
        # 6. PREPARE RESULTS
        # ====================
        print(f"\nPreparing results...")
        optimization_end_time = timezone.now()
        optimization_duration = (optimization_end_time - optimization_start_time).total_seconds()
        
        try:
            # If block_details wasn't provided by run_optimization_with_retries, generate it
            if block_details is None:
                block_details = get_block_details(helper)
            
            # A recovered block is a racked offcut, not stock this job bought. Efficiency
            # answers "how well did we use what we bought", so it and every volume feeding
            # it are computed over new blocks only. Both the stock term and the prism term
            # have to be restricted together - restricting only the denominator pushes
            # efficiency past 100% as soon as most parts come out of scrap.
            new_blocks = [b for b in helper.all_big_blocks if not getattr(b, 'is_recovered', False)]
            recovered_blocks = [b for b in helper.all_big_blocks if getattr(b, 'is_recovered', False)]
            recovered_codes = {b.unique_code for b in recovered_blocks}

            # Calculate totals
            total_parts_packed = 0
            total_prism_volume = 0       # parts cut from newly bought stock
            recovered_prism_volume = 0   # parts cut from racked offcuts - material saved
            total_requested = 0

            # Calculate total requested from parts_data
            for part in parts_data:
                total_requested += part['Nos']

            # Calculate packed parts and volumes from block_details
            if block_details and 'blocks' in block_details:
                for block in block_details['blocks']:
                    if 'prisms' in block:
                        for prism_info in block['prisms']:
                            # Find the prism in parts_data to get volume
                            for part in parts_data:
                                if part['MARK'] == prism_info['code']:
                                    prism_volume = 0.5 * (part['Bottom Length'] + part['Top Length']) * part['Width'] * part['Height']
                                    count = prism_info.get('number', 0)
                                    total_parts_packed += count
                                    if block.get('code') in recovered_codes:
                                        recovered_prism_volume += prism_volume * count
                                    else:
                                        total_prism_volume += prism_volume * count
                                    break

            print(f"Packing summary:")
            print(f"- Total parts requested: {total_requested}")
            print(f"- Total parts packed: {total_parts_packed}")
            print(f"- Packing rate: {(total_parts_packed/total_requested*100 if total_requested > 0 else 0):.2f}%")

            # Calculate total stock volume (newly bought material only)
            total_stock_volume = 0
            for block in new_blocks:
                total_stock_volume += block.volume

            recovered_volume_used = sum(b.volume for b in recovered_blocks)

            # Calculate efficiency
            if total_stock_volume > 0:
                efficiency = (total_prism_volume / total_stock_volume) * 100
            else:
                efficiency = 0

            # How well all material in play was used, bought and recovered together.
            if (total_stock_volume + recovered_volume_used) > 0:
                overall_efficiency = ((total_prism_volume + recovered_prism_volume) /
                                      (total_stock_volume + recovered_volume_used)) * 100
            else:
                overall_efficiency = 0

            print(f"- New blocks: {len(new_blocks)}, recovered blocks: {len(recovered_blocks)}")
            print(f"- Total stock volume (new): {total_stock_volume:.2f}")
            print(f"- Total prism volume (from new): {total_prism_volume:.2f}")
            print(f"- Material saved from scrap: {recovered_prism_volume:.2f}")
            print(f"- Efficiency: {efficiency:.2f}% (overall {overall_efficiency:.2f}%)")
            print(f"- Optimization duration: {optimization_duration:.2f} seconds")

            # Prepare detailed block information
            blocks_info = []
            for block in helper.all_big_blocks:
                try:
                    # Count prisms in this block
                    prism_counts = {}
                    for entry in block.prism_details:
                        prism = entry['prism']
                        count = len(entry['coordinates'])
                        prism_counts[prism.code] = prism_counts.get(prism.code, 0) + count
                    
                    prism_list = [{"code": code, "count": count} for code, count in prism_counts.items()]
                    
                    blocks_info.append({
                        'code': block.unique_code,
                        'size': [float(dim) for dim in block.size],
                        'efficiency': float(block.get_efficiency()),
                        'prisms': prism_list,
                        'volume': float(block.volume),
                        'start_coord': [float(coord) for coord in block.start_coord],
                        # Fingerprint of the cut layout, stored so the summary can count
                        # distinct saw setups later without re-reading the pickled helper.
                        'pattern_key': layout_signature(block),
                        # An R-block is an offcut off the rack, not stock to buy. The UI
                        # needs to tell the two apart - they are different instructions to
                        # the shop floor.
                        'is_recovered': bool(getattr(block, 'is_recovered', False)),
                        'source_scrap_id': getattr(block, 'source_scrap_id', None)
                    })
                except Exception as e:
                    print(f"Error processing block {block.unique_code}: {e}")
                    continue

            # ---- Stock ledger: what each parent size was allowed and what it cost ----
            stock_usage = []
            for idx, size in enumerate(parent_block_sizes):
                used = sum(1 for b in new_blocks if getattr(b, 'size_index', None) == idx)
                allowed = parent_quantities[idx] if idx < len(parent_quantities) else None
                stock_usage.append({
                    'index': idx,
                    'label': parent_labels[idx] if idx < len(parent_labels) else None,
                    'dimensions': [float(d) for d in size],
                    'quantity_allowed': allowed,
                    'quantity_used': used,
                    'quantity_remaining': None if allowed is None else max(0, allowed - used),
                })

            # ---- Which racked offcuts this plan actually cuts into ----
            scrap_inventory_used = []
            for block in recovered_blocks:
                prism_counts = {}
                for entry in block.prism_details:
                    prism = entry['prism']
                    prism_counts[prism.code] = prism_counts.get(prism.code, 0) + len(entry['coordinates'])

                scrap_inventory_used.append({
                    'inventory_id': getattr(block, 'source_inventory_id', None),
                    'scrap_id': getattr(block, 'source_scrap_id', None),
                    'block_code': block.unique_code,
                    'dimensions': [float(d) for d in block.size],
                    'volume': float(block.volume),
                    'parts': [{'code': c, 'count': n} for c, n in prism_counts.items()],
                    'utilisation': round(float(block.get_efficiency()), 2),
                })

            # Only pieces that received a part are consumed; prune_unused_recovered_blocks
            # has already dropped the rest, so recovered_blocks is exactly the consumed set.
            consumed_scrap_inventory_ids = [
                e['inventory_id'] for e in scrap_inventory_used if e['inventory_id'] is not None
            ]

            has_stock_exhausted = any(
                r == 'stock_exhausted'
                for r in getattr(helper, 'shortfall_reasons', {}).values()
            )

            # Prepare scrap information
            scraps_info = []
            for scrap in helper.all_scrap:
                try:
                    scraps_info.append({
                        'code': scrap.unique_code,
                        'size': [float(dim) for dim in scrap.size],
                        'volume': float(scrap.volume),
                        'start_coord': [float(coord) for coord in scrap.start_coord],
                        'parent_block': scrap.parent_block.unique_code if scrap.parent_block else None
                    })
                except Exception as e:
                    print(f"Error processing scrap {scrap.unique_code}: {e}")
                    continue
            
            # Prepare prism summary
            #
            # Alongside the counts we report which parent blocks each part *could* fit in.
            # Without that, a shortfall is ambiguous: a part may be missing because no
            # selected stock size can ever hold it, or because the optimiser failed to
            # place one that fits. Those need different actions from the user, so the
            # response has to distinguish them rather than just reporting 'remaining'.
            #
            # The packer tries all six orientations, so "fits in some orientation" reduces
            # to comparing sorted dimensions. Clearance is included because fill_the_box
            # offsets the first part by the buffer on every axis.
            def part_envelope(part):
                return sorted([
                    float(part['Bottom Length']) + buffer_spacing,
                    float(part['Width']) + buffer_spacing,
                    float(part['Height']) + buffer_spacing,
                ])

            def which_parents_fit(part):
                need = part_envelope(part)
                fitting = []
                for idx, size in enumerate(parent_block_sizes):
                    have = sorted([float(d) for d in size])
                    if all(n <= h for n, h in zip(need, have)):
                        fitting.append({
                            'index': idx,
                            'label': parent_labels[idx] if idx < len(parent_labels) else None,
                            'dimensions': [float(d) for d in size],
                        })
                return fitting

            def which_scraps_fit(part):
                """
                Offered inventory pieces this part fits in.

                Reported separately because a part can fit no parent block yet still be cut
                from a racked offcut. Without this the row would read
                'does_not_fit_any_parent_block' while showing packed > 0 - self-contradictory.
                """
                need = part_envelope(part)
                fitting = []
                for piece in recovered_stock:
                    have = sorted([float(d) for d in piece['size']])
                    if all(n <= h for n, h in zip(need, have)):
                        fitting.append({
                            'inventory_id': piece['id'],
                            'scrap_id': piece['scrap_id'],
                            'dimensions': [float(d) for d in piece['size']],
                        })
                return fitting

            def name_of(fit):
                return fit['label'] or '{:g}x{:g}x{:g}'.format(*fit['dimensions'])

            shortfall_reasons = getattr(helper, 'shortfall_reasons', {}) or {}

            prism_summary = []
            unpackable_parts = []
            unplaced_parts = []
            for part in parts_data:
                # Find matching prism in helper
                packed_count = 0
                for block_info in blocks_info:
                    for prism_info in block_info['prisms']:
                        if prism_info['code'] == part['MARK']:
                            packed_count += prism_info['count']

                remaining = max(0, part['Nos'] - packed_count)
                fits_in = which_parents_fit(part)
                fits_scrap = which_scraps_fit(part)
                placeable = len(fits_in) > 0
                fit_names = ', '.join(name_of(f) for f in fits_in)

                if remaining == 0:
                    status = 'packed'
                    reason = None
                elif shortfall_reasons.get(part['MARK']) == 'stock_exhausted':
                    # Checked before 'not placeable': the part is fine and so is the size
                    # choice, there is simply none of that stock left. Deliberately worded
                    # without "does not fit" - that phrasing is reserved for the branch
                    # below, and confusing the two sends the user to change the part when
                    # they only need to raise a quantity.
                    status = 'stock_exhausted'
                    reason = (
                        "{} fits {}, but every available block of {} was used. Increase the "
                        "quantity, add another stock size, or supply more scrap.".format(
                            part['MARK'],
                            fit_names or 'the available scrap',
                            'that size' if len(fits_in) == 1 else 'those sizes')
                    )
                elif not placeable and not fits_scrap:
                    status = 'does_not_fit_any_parent_block'
                    reason = (
                        "{} is {:g}x{:g}x{:g} mm and, with {:g} mm clearance, is larger than "
                        "every selected parent block in all orientations. Add a bigger stock "
                        "size or reduce the part.".format(
                            part['MARK'], float(part['Bottom Length']), float(part['Width']),
                            float(part['Height']), float(buffer_spacing))
                    )
                elif not placeable:
                    # Fits no bought size but does fit an offered offcut, so it is cuttable
                    # from what is on the rack - a warning, not a dead end.
                    status = 'not_placed' if packed_count == 0 else 'partially_placed'
                    reason = (
                        "{} fits no selected parent block, but does fit {} offered scrap "
                        "piece{}. {} of {} could not be placed.".format(
                            part['MARK'], len(fits_scrap),
                            '' if len(fits_scrap) == 1 else 's', remaining, part['Nos'])
                    )
                elif packed_count == 0:
                    status = 'not_placed'
                    reason = ("{} fits {} but the optimiser placed none of the {} required."
                              .format(part['MARK'], fit_names, part['Nos']))
                else:
                    status = 'partially_placed'
                    reason = ("{} of {} could not be placed, although {} fits {}."
                              .format(remaining, part['Nos'], part['MARK'], fit_names))

                prism_summary.append({
                    'code': part['MARK'],
                    'requested': part['Nos'],
                    'packed': packed_count,
                    'remaining': remaining,
                    'bottom_length': part['Bottom Length'],
                    'top_length': part['Top Length'],
                    'width': part['Width'],
                    'height': part['Height'],
                    'volume': 0.5 * (part['Bottom Length'] + part['Top Length']) * part['Width'] * part['Height'],
                    'packing_rate': (packed_count / part['Nos'] * 100) if part['Nos'] > 0 else 0,
                    'placeable': placeable or len(fits_scrap) > 0,
                    'fits_parent_blocks': fits_in,
                    'fits_scrap_inventory': fits_scrap,
                    'status': status,
                    'reason': reason
                })

                if status == 'does_not_fit_any_parent_block':
                    unpackable_parts.append({
                        'code': part['MARK'],
                        'requested': part['Nos'],
                        'bottom_length': part['Bottom Length'],
                        'top_length': part['Top Length'],
                        'width': part['Width'],
                        'height': part['Height'],
                        'reason': reason
                    })
                elif status in ('not_placed', 'partially_placed', 'stock_exhausted'):
                    # stock_exhausted is a warning class like the other two: the part fits,
                    # so it never belongs in unpackable_parts.
                    unplaced_parts.append({
                        'code': part['MARK'],
                        'requested': part['Nos'],
                        'packed': packed_count,
                        'remaining': remaining,
                        'fits_parent_blocks': fits_in,
                        'fits_scrap_inventory': fits_scrap,
                        'status': status,
                        'reason': reason
                    })

            print(f"- Parts that fit NO parent block: {len(unpackable_parts)}"
                  + (f" ({', '.join(p['code'] for p in unpackable_parts)})"
                     if unpackable_parts else ""))
            print(f"- Parts that fit but were not fully placed: {len(unplaced_parts)}"
                  + (f" ({', '.join(p['code'] for p in unplaced_parts)})"
                     if unplaced_parts else ""))

        except Exception as e:
            print(f"Error preparing results: {e}")
            traceback.print_exc()
            # Create minimal results
            blocks_info = []
            scraps_info = []
            prism_summary = []
            unpackable_parts = []
            unplaced_parts = []
            total_stock_volume = 0
            total_prism_volume = 0
            total_parts_packed = 0
            total_requested = sum(part['Nos'] for part in parts_data)
            efficiency = 0
            overall_efficiency = 0
            recovered_prism_volume = 0
            recovered_volume_used = 0
            new_blocks = []
            recovered_blocks = []
            stock_usage = []
            scrap_inventory_used = []
            consumed_scrap_inventory_ids = []
            has_stock_exhausted = False

        # ====================
        # 6b. RUN SUMMARY (for the person doing the cutting)
        # ====================
        # Aggregates only - what stock to pull, how many saw setups, how many offcuts to
        # rack, and the settings the run used. Per-block detail stays in 'blocks'/'scraps'.
        stock_sizes_selected = stock_sizes_from(parent_block_sizes, parent_labels)

        scrap_inventory_enabled = use_scrap_inventory

        # Only inventory pieces are kept: a scrap generated during this run sits inside a
        # stock block that is already counted, and the list of those runs to thousands.
        consumed_from_inventory = [
            c for c in getattr(helper, 'consumed_scraps', [])
            if c.get('origin') == 'inventory'
        ]

        # build_summary counts every block it is given as stock to pull. Recovered blocks
        # are offcuts already on the rack, so passing them would put steel on the pull list
        # that nobody has to fetch, and add an unlabelled size entry per offcut. They are
        # reported instead through consumed_scraps, as scrap_pieces_used.
        new_blocks_info = [b for b in blocks_info if not b.get('is_recovered')]

        try:
            run_summary = build_summary(
                blocks=new_blocks_info,
                scraps=scraps_info,
                prism_summary=prism_summary,
                stock_sizes=stock_sizes_selected,
                blade_thickness=buffer_spacing,
                source_file=excel_file.name,
                run_by=request.user.username,
                run_at=timezone.now().isoformat(),
                scrap_inventory_enabled=scrap_inventory_enabled,
                consumed_scraps=consumed_from_inventory,
            )
            print(f"- Stock pulled: " + ", ".join(
                f"{s['quantity']}x {s['label'] or 'unlabelled'}"
                for s in run_summary['stock_used']['by_size']))
            print(f"- Distinct cutting patterns: {run_summary['cutting']['distinct_patterns']}")
            print(f"- Offcuts: {run_summary['offcuts']['to_rack']} to rack, "
                  f"{run_summary['offcuts']['to_discard']} to discard")
        except Exception as e:
            print(f"Error building run summary (non-critical): {e}")
            traceback.print_exc()
            run_summary = None

        # ====================
        # 7. SAVE TO HISTORY
        # ====================
        history_saved = False
        history_id = None
        
        try:
            # Check if OptimizationHistory model exists
            from django.apps import apps
            
            if apps.is_installed('planner'):
                from .models import OptimizationHistory
                
                # Create a meaningful job name
                timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
                job_name = f"{os.path.splitext(excel_file.name)[0]} - {timestamp}"
                
                # Prepare optimization results
                optimization_results = {
                    'blocks': blocks_info,
                    'scraps': scraps_info,
                    'summary': {
                        'efficiency': round(efficiency, 2),
                        'total_parts_packed': total_parts_packed,
                        'total_parts_requested': total_requested,
                        'packing_percentage': round(total_parts_packed / total_requested * 100, 2) if total_requested > 0 else 0,
                        'total_blocks_created': len(helper.all_big_blocks),
                        'total_stock_volume': round(total_stock_volume, 2),
                        'total_prism_volume': round(total_prism_volume, 2),
                        'waste_percentage': round(100 - efficiency, 2),
                        'optimization_duration_seconds': round(optimization_duration, 2)
                    }
                }
                # Merged into the existing summary rather than parked under a new key, so
                # the history page finds the new sections next to the totals it already
                # reads. No key overlaps with the ones above.
                if run_summary:
                    optimization_results['summary'].update(run_summary)

                # Save to history
                history = OptimizationHistory.objects.create(
                    user=request.user,
                    job_name=job_name,
                    uploaded_file_name=excel_file.name,
                    uploaded_file_data=parts_data,
                    selected_blocks=selected_blocks,
                    selected_parents=parent_labels,
                    parameters={
                        'buffer_spacing': buffer_spacing,
                        'parent_blocks_used': parent_block_sizes,
                        'parent_labels': parent_labels,
                        'max_retries': max_retries,
                        'retry_enabled': retry_enabled,
                        'original_part_count': original_part_count,
                        'filtered_part_count': len(parts_data),
                        'optimization_duration_seconds': optimization_duration,
                        # Kept so the summary can be rebuilt from the row alone
                        'scrap_inventory_enabled': scrap_inventory_enabled,
                        'consumed_scraps': consumed_from_inventory,
                        # Needed to reproduce this exact plan: get_helper_for_job re-runs
                        # run_final_code from these values, and a reconstruction without
                        # them would pack against different supply than the saved plan.
                        'parent_block_quantities': parent_quantities,
                        'stock_usage': stock_usage,
                        'recovered_stock': recovered_stock,
                        # Read on execute to retire the racked pieces this job cuts up.
                        'consumed_scrap_inventory_ids': consumed_scrap_inventory_ids
                    },
                    optimization_results=optimization_results,
                    efficiency=round(efficiency, 2),
                    total_blocks_created=len(new_blocks),
                    total_parts_packed=total_parts_packed,
                    total_parts_requested=total_requested,
                    prism_summary=prism_summary
                )
                
                # Save the original uploaded file copy to media/uploaded_files
                try:
                    uploaded_files_dir = os.path.join(settings.MEDIA_ROOT, "uploaded_files")
                    os.makedirs(uploaded_files_dir, exist_ok=True)
                    excel_file.seek(0)
                    dest_path = os.path.join(uploaded_files_dir, f"{history.id}_{excel_file.name}")
                    with open(dest_path, 'wb+') as destination:
                        for chunk in excel_file.chunks():
                            destination.write(chunk)
                    print(f"✓ Saved original upload copy to {dest_path}")
                except Exception as f_err:
                    print(f"⚠ Failed to save original upload copy: {f_err}")
                
                # Build a professional, industry-style job name:
                # e.g. "OPT-0007 · SteelParts Jul11" instead of "Run #7 - sample_data"
                raw_stem = os.path.splitext(excel_file.name)[0]          # e.g. "sample_data"
                clean_stem = raw_stem.replace('_', ' ').replace('-', ' ').strip().title()  # "Sample Data"
                date_tag = timezone.now().strftime("%d %b %y")            # "11 Jul 26"
                history.job_name = f"OPT-{history.id:04d} \u00b7 {clean_stem} \u00b7 {date_tag}"
                history.save(update_fields=['job_name'])
                
                # Save pickled helper to disk for perfect fidelity dynamic requests
                try:
                    import pickle
                    helpers_dir = os.path.join(settings.MEDIA_ROOT, "helpers")
                    os.makedirs(helpers_dir, exist_ok=True)
                    pkl_path = os.path.join(helpers_dir, f"{history.id}.pkl")
                    with open(pkl_path, "wb") as f:
                        pickle.dump(helper, f)
                    print(f"✓ Saved pickled helper for job {history.id} to {pkl_path}")
                except Exception as pkl_err:
                    print(f"⚠ Failed to save pickled helper: {pkl_err}")

                history_id = history.id
                history_saved = True
                print(f"[HISTORY] Saved optimization #{history.id} for user {request.user.username}")

                # ====================
                # 8. GENERATE 6-SIDE HTML FOR ALL BLOCKS (FAST!)
                # ====================
                print(f"\n{'='*80}")
                print("GENERATING 6-SIDE HTML FILES FOR ALL BLOCKS")
                print(f"{'='*80}")
                
                html_base_dir = os.path.join(settings.MEDIA_ROOT, "block_html", str(history.id))
                os.makedirs(html_base_dir, exist_ok=True)
                
                # Generate individual block HTML files
                for block in helper.all_big_blocks:
                    try:
                        print(f"\nGenerating HTML for block {block.unique_code}...")
                        html_path = generate_block_6_side_images(block, html_base_dir, block.unique_code)
                        
                        if html_path:
                            print(f"✓ Successfully generated HTML for {block.unique_code}")
                        else:
                            print(f"⚠ Failed to generate HTML for {block.unique_code}")
                    except Exception as e:
                        print(f"✗ Error generating HTML for {block.unique_code}: {e}")
                        continue
                
                # Generate master HTML with all blocks
                job_label = f"OPT-{history.id:04d}"
                master_html_path = os.path.join(html_base_dir, f"{job_label}_All_Blocks_6_Sides.html")
                generate_all_blocks_master_html(helper.all_big_blocks, master_html_path, job_label)
                
                print(f"\n{'='*80}\n")

                # Auto-save scraps to database (initially not in inventory)
                try:
                    from .inventory_views import auto_save_scraps_from_optimization
                    auto_save_scraps_from_optimization(helper, history, request.user)
                except Exception as inv_err:
                    print(f"[INVENTORY] Error saving scraps (non-critical): {inv_err}")

        except ImportError as ie:
            print(f"[HISTORY] OptimizationHistory model not found: {ie}")
        except Exception as history_error:
            print(f"[HISTORY] Error saving history (non-critical): {history_error}")
            traceback.print_exc()
            # Don't fail the main request if history saving fails
        
        # ====================
        # 8. PREPARE FINAL RESPONSE
        # ====================
        # The headline message must not read as a clean success when parts were left out,
        # otherwise a shortfall is only discoverable by scanning prism_summary by hand.
        summary_message = (
            f'Successfully packed {total_parts_packed} out of {total_requested} parts '
            f'({total_parts_packed/total_requested*100:.1f}%) into {len(new_blocks)} '
            f'stock blocks with {efficiency:.2f}% efficiency in {optimization_duration:.2f} seconds.'
            if total_requested > 0 else 'No parts to pack.'
        )
        if recovered_blocks:
            summary_message += (
                ' {} racked scrap piece{} reused, saving {:.0f} mm³ of new material.'.format(
                    len(recovered_blocks), '' if len(recovered_blocks) == 1 else 's',
                    recovered_prism_volume)
            )
        if has_stock_exhausted:
            summary_message += (
                ' Some parts were left short because the available stock ran out, '
                'not because they are too large.'
            )
        if unpackable_parts:
            summary_message += (
                ' {} part type{} ({}) do{} not fit any selected parent block and could not be '
                'packed at all.'.format(
                    len(unpackable_parts), '' if len(unpackable_parts) == 1 else 's',
                    ', '.join(p['code'] for p in unpackable_parts),
                    'es' if len(unpackable_parts) == 1 else '')
            )
        if unplaced_parts:
            summary_message += (
                ' {} part type{} ({}) fit a selected parent block but were left short.'.format(
                    len(unplaced_parts), '' if len(unplaced_parts) == 1 else 's',
                    ', '.join(p['code'] for p in unplaced_parts))
            )

        results = {
            'success': True,
            'efficiency': round(efficiency, 2),
            'total_parts_packed': total_parts_packed,
            'total_parts_requested': total_requested,
            'packing_percentage': round(total_parts_packed / total_requested * 100, 2) if total_requested > 0 else 0,
            # New stock only. A recovered block is material already on the rack, so counting
            # it here would report the job as buying blocks it did not buy.
            'total_blocks_created': len(new_blocks),
            'total_stock_volume': round(total_stock_volume, 2),
            'total_prism_volume': round(total_prism_volume, 2),
            'waste_percentage': round(100 - efficiency, 2),
            # Recovered-material view. overall_efficiency counts bought and racked material
            # together, material_saved_volume is the part volume that came out of scrap and
            # is the headline number for the reuse feature.
            'total_recovered_blocks': len(recovered_blocks),
            'recovered_volume_used': round(recovered_volume_used, 2),
            'material_saved_volume': round(recovered_prism_volume, 2),
            'overall_efficiency': round(overall_efficiency, 2),
            'blocks': blocks_info,
            'scraps': scraps_info,
            'parent_blocks_used': parent_block_sizes,
            'parent_labels': parent_labels,
            'parent_block_quantities': parent_quantities,
            # Per-size ledger: what was allowed, what the plan spent, what is left.
            'stock_usage': stock_usage,
            # Racked offcuts this plan cuts into, and how many were on offer.
            'scrap_inventory_used': scrap_inventory_used,
            'scrap_inventory_offered': scrap_inventory_offered,
            'scrap_inventory_enabled': scrap_inventory_enabled,
            # True when a part was left short purely because stock ran out. Distinct from
            # has_unpackable_parts: this one is fixed by raising a quantity, not by
            # choosing a bigger size.
            'has_stock_exhausted': has_stock_exhausted,
            # Shop-floor view of the run: stock to pull, parts produced, offcuts to rack,
            # saw setups, and the settings used. Aggregates only.
            'summary': run_summary,
            'prism_summary': prism_summary,
            # Parts no selected stock size can hold in any orientation. Non-empty means the
            # user must change the stock selection - re-running will not help.
            'unpackable_parts': unpackable_parts,
            'has_unpackable_parts': len(unpackable_parts) > 0,
            # Parts that DO fit a selected stock size but the optimiser left short.
            'unplaced_parts': unplaced_parts,
            'has_unplaced_parts': len(unplaced_parts) > 0,
            'optimization_parameters': {
                'buffer_spacing': buffer_spacing,
                'max_retries': max_retries,
                'retry_enabled': retry_enabled,
                'use_scrap_inventory': use_scrap_inventory,
                'scrap_inventory_ids': scrap_inventory_ids,
                'search_attempts': search_attempts,
                'optimization_duration_seconds': round(optimization_duration, 2)
            },
            'history_saved': history_saved,
            'history_id': history_id,
            'message': summary_message,
            'timestamp': timezone.now().isoformat(),
            'user': request.user.username,
            'file_processed': {
                'name': excel_file.name,
                'size_kb': round(excel_file.size / 1024, 2),
                'rows_processed': len(parts_data)
            }
        }
        
        print(f"\n=== OPTIMIZATION COMPLETED SUCCESSFULLY ===")
        print(f"Returning results with {len(blocks_info)} blocks")
        print(f"Total optimization time: {optimization_duration:.2f} seconds")
        
        return Response(results)
        
    except Exception as e:
        from rest_framework.exceptions import ValidationError
        if isinstance(e, ValidationError):
            print(f"\n=== OPTIMIZATION VALIDATION FAILED ===")
            print(f"Error: {str(e)}")
            err_msg = e.detail if hasattr(e, 'detail') else str(e)
            if isinstance(err_msg, dict) and 'detail' in err_msg:
                err_msg = err_msg['detail']
            if isinstance(err_msg, list):
                err_msg = " ".join([str(x) for x in err_msg])
            return Response({
                'success': False,
                'error': f"Validation error: {err_msg}"
            }, status=400)

        print(f"\n=== OPTIMIZATION FAILED ===")
        print(f"Error: {str(e)}")
        traceback.print_exc()
        
        # Try to save failed optimization to history
        try:
            from .models import OptimizationHistory
            from django.utils import timezone
            
            OptimizationHistory.objects.create(
                user=request.user,
                job_name=f"Failed Optimization - {timezone.now().strftime('%Y-%m-%d %H:%M')}",
                uploaded_file_name=excel_file.name if 'excel_file' in locals() else "Unknown",
                optimization_results={'error': str(e)},
                efficiency=0.0,
                total_blocks_created=0,
                total_parts_packed=0,
                total_parts_requested=0,
                error_message=str(e),
                status='failed'
            )
        except Exception as history_err:
            print(f"[HISTORY] Error saving failed optimization: {history_err}")
        
        return Response({
            'success': False,
            'error': f"Optimization failed: {str(e)}",
            'traceback': traceback.format_exc() if settings.DEBUG else None
        }, status=500)


# ================================
# DEEP OPTIMIZATION
# ================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_and_optimize_deep(request):
    """
    POST /api/upload-optimize-deep/

    The slow, thorough sibling of /api/upload-optimize/. Same payload, same response,
    plus a 'deep_search' section describing what it explored.

    It does two things the quick endpoint does not:

    1. Searches over SUBSETS of the offered parent sizes instead of handing all of them
       to the greedy at once. The greedy scores a size by how well it packs the current
       part only, so offering more sizes can make the result worse - measured at -1.1
       points on Sample_data_03. Searching subsets makes that impossible, because the
       smaller set is always still a candidate. Worth about +2.5 points there.
    2. Repacks the winning subset with exhaustive scrap decomposition (all 48 merge
       orders rather than 8 sampled). Worth about +0.15 points for ~3x the time, which is
       why it runs once at the end rather than on every candidate.

    Deliberately structured as search-then-delegate: once the subset is chosen, the real
    run goes through upload_and_optimize unchanged, so history, visualisations, scrap
    inventory and the response shape cannot drift between the two endpoints.

    Runtime is minutes, not seconds. Callers should expect to wait or run it in the
    background.
    """
    import time
    import traceback
    from django.conf import settings
    from .deep_search import (DEFAULT_ORDER_ATTEMPTS, search_parent_subsets,
                              search_prism_order)

    started = time.time()
    print(f"\n{'='*80}\n=== DEEP OPTIMIZATION REQUEST ===\n{'='*80}")

    try:
        excel_file = request.FILES.get('file')
        if not excel_file:
            return Response({'success': False, 'error': 'No file uploaded'}, status=400)

        try:
            parent_blocks_data = json.loads(request.POST.get('parent_blocks', '[]'))
            selected_blocks = json.loads(request.POST.get('selected_blocks', '[]'))
        except json.JSONDecodeError as e:
            return Response({'success': False,
                             'error': f'Invalid JSON in parameters: {str(e)}'}, status=400)

        if not parent_blocks_data:
            return Response({'success': False, 'error': 'No parent blocks provided'}, status=400)

        buffer_spacing = float(request.POST.get('buffer_spacing', '2.0'))
        strategy = str(request.POST.get('search_strategy', 'auto')).strip().lower()
        try:
            time_budget = float(request.POST.get('search_time_budget', '') or 0) or None
        except ValueError:
            time_budget = None
        try:
            order_attempts = int(request.POST.get('order_attempts', '')
                                 or DEFAULT_ORDER_ATTEMPTS)
        except ValueError:
            order_attempts = DEFAULT_ORDER_ATTEMPTS
        order_attempts = max(0, order_attempts)

        # ---- parse the offered sizes exactly as the quick endpoint does ----
        sizes, labels, quantities = [], [], []
        for i, block in enumerate(parent_blocks_data):
            try:
                if isinstance(block, dict):
                    if 'dimensions' in block:
                        d = block['dimensions']
                        length, width, height = (float(d.get('length', 0)),
                                                 float(d.get('width', 0)),
                                                 float(d.get('height', 0)))
                    elif all(k in block for k in ('length', 'width', 'height')):
                        length, width, height = (float(block['length']), float(block['width']),
                                                 float(block['height']))
                    else:
                        print(f"Warning: Parent block {i} has invalid format: {block}")
                        continue
                elif isinstance(block, list) and len(block) == 3:
                    length, width, height = float(block[0]), float(block[1]), float(block[2])
                else:
                    print(f"Warning: Parent block {i} has invalid format: {block}")
                    continue

                if length <= 0 or width <= 0 or height <= 0:
                    continue

                quantity = None
                if isinstance(block, dict) and block.get('quantity') is not None:
                    try:
                        quantity = int(block['quantity'])
                        if quantity <= 0:
                            continue
                    except (TypeError, ValueError):
                        quantity = None

                sizes.append([length, width, height])
                labels.append(block.get('label', f'{length}×{width}×{height}')
                              if isinstance(block, dict) else f'{length}×{width}×{height}')
                quantities.append(quantity)
            except Exception as e:
                print(f"Error processing parent block {i}: {e}")
                continue

        if not sizes:
            return Response({'success': False,
                             'error': 'No valid parent blocks provided'}, status=400)

        # ---- recovered scrap, same rules as the quick endpoint ----
        use_scrap_inventory = str(
            request.POST.get('use_scrap_inventory', 'false')
        ).strip().lower() in ('true', '1', 'yes')
        recovered_stock = []
        if use_scrap_inventory:
            try:
                from .models import ScrapInventory
                inv = ScrapInventory.objects.filter(
                    is_in_inventory=True, usability__in=['usable', 'manual'])
                ids_raw = request.POST.get('scrap_inventory_ids', '')
                if ids_raw.strip():
                    inv = inv.filter(id__in=[int(v) for v in json.loads(ids_raw)])
                recovered_stock = [{'id': s.id, 'scrap_id': s.scrap_id,
                                    'size': [float(s.length), float(s.width), float(s.height)]}
                                   for s in inv]
            except Exception as e:
                print(f"Error loading scrap inventory for deep search (non-critical): {e}")
                recovered_stock = []

        # ---- build the search's own copy of the parts ----
        # Same filtering the quick endpoint applies, so the subset is chosen against the
        # parts that will actually be packed.
        search_path, demand = _write_search_workbook(excel_file, selected_blocks)
        if search_path is None:
            return Response({'success': False,
                             'error': 'Could not read parts from the uploaded file'}, status=400)

        print(f"[DEEP] {len(sizes)} sizes offered, {demand} parts, "
              f"{len(recovered_stock)} scrap pieces, strategy={strategy}")

        try:
            search = search_parent_subsets(
                excel_path=search_path,
                parent_block_sizes=sizes,
                parent_labels=labels,
                parent_quantities=quantities,
                demand=demand,
                buffer=buffer_spacing,
                recovered_stock=recovered_stock,
                strategy=strategy,
                time_budget=time_budget,
            )

            print(f"[DEEP] chose {search['chosen_labels']} "
                  f"({search['chosen_efficiency']}%, {search['chosen_blocks']} blocks) "
                  f"from {search['candidates_evaluated']} candidates "
                  f"in {search['search_seconds']}s")

            # ---- second stage: processing order, on the winning subset only ----
            # The order part types are packed in moves efficiency far more than anything
            # else here, and volume-descending - the hardcoded default - is good but not
            # best. Searched after the subset rather than jointly, so it costs
            # order_attempts packings rather than multiplying the subset scan.
            chosen = set(search['chosen_indices'])
            order = None
            if order_attempts > 1:
                remaining = (time_budget - search['search_seconds']) if time_budget else None
                if remaining is None or remaining > 0:
                    order = search_prism_order(
                        excel_path=search_path,
                        parent_block_sizes=[sizes[i] for i in sorted(chosen)],
                        parent_quantities=[quantities[i] for i in sorted(chosen)],
                        demand=demand,
                        buffer=buffer_spacing,
                        recovered_stock=recovered_stock,
                        attempts=order_attempts,
                        time_budget=remaining,
                    )
                    print(f"[DEEP] order seed {order['seed']} "
                          f"({order['improvement_points']:+} points over volume-descending) "
                          f"from {order['attempts']} attempts in {order['search_seconds']}s")
                else:
                    print("[DEEP] skipping order search, time budget already spent")
            search['prism_order'] = order
        finally:
            try:
                os.remove(search_path)
            except Exception:
                pass

        # ---- final run: winning subset only, through the untouched quick endpoint ----
        winning_payload = [
            {'label': labels[i], 'quantity': quantities[i],
             'dimensions': {'length': sizes[i][0], 'width': sizes[i][1], 'height': sizes[i][2]}}
            for i in range(len(sizes)) if i in chosen
        ]

        # The uploaded file was consumed building the search workbook; rewind so the
        # delegate can read it again.
        try:
            excel_file.seek(0)
        except Exception:
            pass

        # Swap in the winning subset before delegating. DRF's Request.POST is a read-only
        # property over the parsed form data, so the parsed data itself is what has to be
        # replaced - and _full_data, DRF's merged view of data + files, has to be rebuilt
        # the same way _load_data_and_files does it or the delegate sees stale values.
        post = request.POST.copy()
        post['parent_blocks'] = json.dumps(winning_payload)
        post._mutable = False
        request._data = post
        if request._files:
            request._full_data = post.copy()
            request._full_data.update(request._files)
        else:
            request._full_data = post
        request._request._post = post

        # Delegate to the underlying HttpRequest, not this DRF Request: upload_and_optimize
        # is wrapped in @api_view, which builds its own Request and rejects one that is
        # already wrapped. The multipart stream is spent by now, so DRF re-reads the parsed
        # _post/_files set above - which is exactly the substitution we want it to see.
        from .modules.fill import exhaustive_decomposition
        from .modules.packing_orchestrator import (lookahead_selection,
                                                   prism_order as prism_order_ctx)
        order_seed = (search.get('prism_order') or {}).get('seed') or None
        # Same three settings the search ran under, so the final plan is the one that was
        # actually measured rather than a different packer given the winning inputs.
        with exhaustive_decomposition(), prism_order_ctx(order_seed), lookahead_selection():
            response = upload_and_optimize(request._request)

        if response.status_code == 200 and isinstance(response.data, dict):
            search['total_seconds'] = round(time.time() - started, 1)
            response.data['optimization_mode'] = 'deep'
            response.data['deep_search'] = search
            response.data['message'] = (
                f"{response.data.get('message', '')} Deep optimisation evaluated "
                f"{search['candidates_evaluated']} combinations of your "
                f"{len(sizes)} stock sizes and used {', '.join(search['chosen_labels'])}."
            ).strip()

            # Record the search on the history row too. upload_and_optimize only ever sees
            # the winning subset, so without this the stored run says "3 sizes" when the
            # user selected 5, with nothing to explain the difference - which reads as the
            # backend quietly ignoring input. Keep the sizes as offered alongside the
            # verdict so the record is self-contained.
            _persist_deep_search(response.data.get('history_id'), search, sizes, labels,
                                 quantities)

        return response

    except Exception as e:
        print(f"=== DEEP OPTIMIZATION FAILED ===\n{e}")
        traceback.print_exc()
        return Response({
            'success': False,
            'error': f'Deep optimization failed: {str(e)}',
            'traceback': traceback.format_exc() if settings.DEBUG else None
        }, status=500)


def _persist_deep_search(history_id, search, sizes, labels, quantities):
    """
    Attach the deep search to its OptimizationHistory row.

    Non-fatal: the plan itself is already saved and correct without this. What is lost on
    failure is only the explanation of why some offered sizes went unused.
    """
    if not history_id:
        return

    try:
        from .models import OptimizationHistory

        history = OptimizationHistory.objects.get(id=history_id)
        params = history.parameters or {}
        params['optimization_mode'] = 'deep'
        params['deep_search'] = search
        # What the caller actually offered, before the search narrowed it. parent_blocks_used
        # holds the winning subset, so on its own it cannot show what was rejected.
        params['parent_blocks_offered'] = [[float(d) for d in s] for s in sizes]
        params['parent_labels_offered'] = list(labels)
        params['parent_quantities_offered'] = list(quantities)
        history.parameters = params
        history.save(update_fields=['parameters'])

        print(f"[DEEP] recorded search on optimization #{history_id}")

    except Exception as e:
        print(f"[DEEP] could not record search on history {history_id} (non-critical): {e}")


def _write_search_workbook(excel_file, selected_blocks):
    """
    Standardise the uploaded BOM to a temp workbook the search can re-read cheaply.

    Mirrors the column mapping and part filtering in upload_and_optimize. Duplicated
    rather than extracted so the quick endpoint stays untouched; if that parser ever
    changes, this has to change with it.

    Returns (path, total_quantity) or (None, 0).
    """
    import uuid
    from django.conf import settings

    try:
        if excel_file.name.lower().endswith('.csv'):
            df = pd.read_csv(excel_file)
        else:
            df = pd.read_excel(excel_file, engine='openpyxl')
    except Exception as e:
        print(f"[DEEP] could not read uploaded file: {e}")
        return None, 0

    df.columns = [str(c).strip() for c in df.columns]
    mapping = {}
    for col in df.columns:
        low = str(col).lower()
        if 'mark' in low or 'code' in low:
            mapping[col] = 'MARK'
        elif 'bottom' in low and 'length' in low:
            mapping[col] = 'Bottom Length'
        elif 'top' in low and 'length' in low:
            mapping[col] = 'Top Length'
        elif 'width' in low or 'breadth' in low or low == 'w':
            mapping[col] = 'Width'
        elif 'height' in low or 'thickness' in low or 'depth' in low or low == 'h':
            mapping[col] = 'Height'
        elif 'nos' in low or 'quantity' in low or 'qty' in low or 'count' in low:
            mapping[col] = 'Nos'
    df.rename(columns=mapping, inplace=True)

    required = ['MARK', 'Bottom Length', 'Top Length', 'Width', 'Height', 'Nos']
    if any(c not in df.columns for c in required):
        print(f"[DEEP] missing columns: {[c for c in required if c not in df.columns]}")
        return None, 0

    rows = []
    for _, row in df.iterrows():
        mark = row.get('MARK')
        if pd.isna(mark) or str(mark).strip() == '':
            continue
        try:
            part = {
                'MARK': str(mark).strip(),
                'Bottom Length': float(row.get('Bottom Length', 0)),
                'Top Length': float(row.get('Top Length', 0)),
                'Width': float(row.get('Width', 0)),
                'Height': float(row.get('Height', 0)),
                'Nos': int(float(row.get('Nos', 0))),
            }
        except (TypeError, ValueError):
            continue
        if part['Nos'] <= 0 or min(part['Bottom Length'], part['Width'], part['Height']) <= 0:
            continue
        if selected_blocks and part['MARK'] not in selected_blocks:
            continue
        rows.append(part)

    if not rows:
        return None, 0

    temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_uploads')
    os.makedirs(temp_dir, exist_ok=True)
    path = os.path.join(temp_dir, f"deep_search_{uuid.uuid4().hex[:8]}.xlsx")
    pd.DataFrame(rows).to_excel(path, index=False, engine='openpyxl')

    return path, sum(r['Nos'] for r in rows)


# ================================
# NEW ENDPOINT FOR RETRY SETTINGS
# ================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_optimization_settings(request):
    """
    Set optimization settings for the user
    
    POST /api/optimization-settings/
    
    Body:
    {
        "max_retries": 10000,
        "default_buffer_spacing": 2.0,
        "enable_retry": true,
        "default_parent_blocks": [
            {"label": "Standard 1", "dimensions": {"length": 2000, "width": 800, "height": 400}},
            {"label": "Standard 2", "dimensions": {"length": 1870, "width": 800, "height": 350}}
        ]
    }
    """
    try:
        data = request.data
        
        # Validate input
        max_retries = data.get('max_retries', 10000)
        if max_retries < 1 or max_retries > 10000:
            return Response({
                'success': False,
                'error': 'max_retries must be between 1 and 10000'
            }, status=400)
        
        buffer_spacing = data.get('default_buffer_spacing', 2.0)
        if buffer_spacing < 0 or buffer_spacing > 50:
            return Response({
                'success': False,
                'error': 'buffer_spacing must be between 0 and 50'
            }, status=400)
        
        # Save to user profile or cache
        from django.core.cache import cache
        settings_key = f"optimization_settings_{request.user.id}"
        
        settings = {
            'max_retries': max_retries,
            'default_buffer_spacing': buffer_spacing,
            'enable_retry': data.get('enable_retry', True),
            'default_parent_blocks': data.get('default_parent_blocks', []),
            'updated_at': timezone.now().isoformat()
        }
        
        cache.set(settings_key, settings, timeout=60*60*24*7)  # 1 week
        
        return Response({
            'success': True,
            'message': 'Optimization settings saved',
            'settings': settings
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

# ================================
# TEST ENDPOINTS
# ================================


# Add these new views to your views.py

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_optimization_history(request):
    """
    GET /api/optimization-history/
    - Normal users: see only their own history
    - Superadmin/staff: see all users' history (pass all_users=true)
    - Search: ?search=<id or job name>
    - Executed only: ?executed_only=true (filters the whole history, not just this page)
    """
    try:
        from .models import OptimizationHistory
        from django.db.models import Q

        page = max(1, int(request.GET.get('page', 1)))
        page_size = min(100, max(1, int(request.GET.get('page_size', 50))))
        search = request.GET.get('search', '').strip()
        show_all = request.GET.get('all_users', 'false').lower() == 'true'
        executed_only = request.GET.get('executed_only', 'false').lower() == 'true'

        # Superadmin/staff can see everyone's history
        if show_all and (request.user.is_superuser or request.user.is_staff):
            history = OptimizationHistory.objects.select_related('user').all()
        else:
            history = OptimizationHistory.objects.filter(user=request.user)

        # Search by numeric ID or job name
        if search:
            clean_search = search.lstrip('#').strip()
            if clean_search.isdigit():
                history = history.filter(
                    Q(id=clean_search) | Q(job_name__icontains=search)
                )
            else:
                history = history.filter(job_name__icontains=search)

        # "Show Executed Only" toggle. Applied before the count and the slice so the
        # frontend pages over executed runs across the whole history, not over whichever
        # of them happen to land on the page it already downloaded.
        if executed_only:
            history = history.filter(is_executed=True)

        total_count = history.count()
        start = (page - 1) * page_size
        end = start + page_size
        paginated_history = history[start:end]

        history_list = []
        for item in paginated_history:
            summary = item.summary
            summary['id'] = item.id
            summary['username'] = item.user.username if hasattr(item, 'user') else None
            history_list.append(summary)

        return Response({
            'success': True,
            'data': history_list,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total_count,
                'total_pages': max(1, (total_count + page_size - 1) // page_size),
                'has_next': end < total_count,
                'has_previous': page > 1,
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({'success': False, 'error': str(e), 'data': []}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_optimization_details(request, history_id):
    """
    Get full details of a specific optimization
    
    GET /api/optimization-history/<id>/
    Returns complete optimization data
    """
    try:
        from .models import OptimizationHistory
        
        # Get the history item
        if request.user.is_superuser or request.user.is_staff:
            history = OptimizationHistory.objects.get(id=history_id)
        else:
            history = OptimizationHistory.objects.get(id=history_id, user=request.user)

        # Runs saved before the summary existed still hold their full blocks/scraps lists,
        # so the summary is rebuilt on read rather than leaving those pages blank until
        # someone re-runs the job. Computed only, never written back.
        optimization_results = history.optimization_results or {}
        if 'settings' not in (optimization_results.get('summary') or {}):
            try:
                optimization_results = dict(optimization_results)
                optimization_results['summary'] = dict(optimization_results.get('summary') or {})
                optimization_results['summary'].update(summary_for_history(history))
            except Exception as e:
                print(f"[HISTORY] Could not rebuild summary for #{history.id} (non-critical): {e}")

        return Response({
            'success': True,
            'data': {
                'id': history.id,
                'job_name': history.job_name,
                'created_at': history.created_at,
                'efficiency': history.efficiency,
                'uploaded_file_name': history.uploaded_file_name,
                'uploaded_file_data': history.uploaded_file_data,
                'selected_blocks': history.selected_blocks,
                'selected_parents': history.selected_parents,
                'parameters': history.parameters,
                'optimization_results': optimization_results,
                'is_executed': history.is_executed,
                'label': history.label,
                'label_color': history.label_color,
                'username': history.user.username,
                'prism_summary': history.prism_summary,
                # Carries the same sections as optimization_results['summary'], so the page
                # does not have to know which of the two to read.
                'summary': dict({
                    'total_blocks_created': history.total_blocks_created,
                    'total_parts_packed': history.total_parts_packed,
                    'total_parts_requested': history.total_parts_requested,
                    'is_successful': history.is_successful
                }, **(optimization_results.get('summary') or {}))
            }
        })
        
    except OptimizationHistory.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Optimization not found or access denied'
        }, status=404)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_uploaded_file(request, history_id):
    """
    Download the original uploaded file or dynamically regenerate it from uploaded_file_data if it is not saved on disk.
    """
    try:
        from .models import OptimizationHistory
        from django.http import HttpResponse
        import os
        import pandas as pd
        import io
        from django.conf import settings
        import urllib.parse
        
        # Get the history item
        if request.user.is_superuser or request.user.is_staff:
            history = OptimizationHistory.objects.get(id=history_id)
        else:
            history = OptimizationHistory.objects.get(id=history_id, user=request.user)
            
        filename = history.uploaded_file_name or "uploaded_parts.xlsx"
        
        # First, check if the original file exists in media/uploaded_files
        uploaded_file_path = os.path.join(settings.MEDIA_ROOT, "uploaded_files", f"{history.id}_{filename}")
        
        if os.path.exists(uploaded_file_path):
            try:
                with open(uploaded_file_path, 'rb') as f:
                    file_content = f.read()
                    
                if filename.lower().endswith('.csv'):
                    content_type = 'text/csv'
                elif filename.lower().endswith('.xlsx'):
                    content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                elif filename.lower().endswith('.xls'):
                    content_type = 'application/vnd.ms-excel'
                else:
                    content_type = 'application/octet-stream'
                    
                response = HttpResponse(file_content, content_type=content_type)
                quoted_filename = urllib.parse.quote(filename)
                response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quoted_filename}"
                return response
            except Exception as read_err:
                print(f"Error reading saved file (generating fallback): {read_err}")
        
        # Dynamic generation fallback
        data = history.uploaded_file_data
        if not data:
            return Response({'success': False, 'error': 'No file data stored for this run.'}, status=400)
            
        df = pd.DataFrame(data)
        
        # Format columns appropriately for the Excel columns expected
        expected_cols = ['MARK', 'Bottom Length', 'Top Length', 'Width', 'Height', 'Nos']
        existing_cols = [c for c in expected_cols if c in df.columns]
        if existing_cols:
            df = df[existing_cols]
            
        if filename.lower().endswith('.csv'):
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            response = HttpResponse(csv_buffer.getvalue(), content_type='text/csv')
        else:
            if not filename.lower().endswith('.xlsx') and not filename.lower().endswith('.xls'):
                filename += '.xlsx'
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Parts')
            response = HttpResponse(excel_buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            
        quoted_filename = urllib.parse.quote(filename)
        response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quoted_filename}"
        return response
        
    except OptimizationHistory.DoesNotExist:
        return Response({'success': False, 'error': 'Optimization history entry not found.'}, status=404)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_optimization_history(request):
    """
    Delete optimization history items
    
    POST /api/optimization-history/delete/
    Body: {"ids": [1, 2, 3]} or {"delete_all": true}
    """
    try:
        from .models import OptimizationHistory
        
        data = request.data
        ids_to_delete = data.get('ids', [])
        delete_all = data.get('delete_all', False)
        
        # Validate
        if not ids_to_delete and not delete_all:
            return Response({
                'success': False,
                'error': 'No IDs provided and delete_all is false'
            }, status=400)
        
        # Build query
        query = OptimizationHistory.objects.filter(user=request.user)
        
        if delete_all:
            count = query.count()
            query.delete()
            message = f"Deleted all {count} optimization records"
        else:
            query = query.filter(id__in=ids_to_delete)
            count = query.count()
            query.delete()
            message = f"Deleted {count} optimization record(s)"
        
        return Response({
            'success': True,
            'message': message,
            'deleted_count': count
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def rename_optimization(request, history_id):
    """
    Rename an optimization job
    
    POST /api/optimization-history/<id>/rename/
    Body: {"new_name": "Production Run 2024"}
    """
    try:
        from .models import OptimizationHistory
        
        history = OptimizationHistory.objects.get(id=history_id, user=request.user)
        new_name = request.data.get('new_name', '').strip()
        
        if not new_name:
            return Response({
                'success': False,
                'error': 'New name is required'
            }, status=400)
        
        if len(new_name) > 255:
            return Response({
                'success': False,
                'error': 'Name too long (max 255 characters)'
            }, status=400)
        
        old_name = history.job_name
        history.job_name = new_name
        history.save()
        
        return Response({
            'success': True,
            'message': f'Renamed from "{old_name}" to "{new_name}"'
        })
        
    except OptimizationHistory.DoesNotExist:
        return Response({
            'success': False,
            'error': 'Optimization not found'
        }, status=404)
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def toggle_executed(request, history_id):
    """
    Toggle the is_executed status of an optimization
    
    PATCH /api/optimization-history/<id>/toggle-executed/
    Body: {"is_executed": true}
    """
    try:
        from .models import OptimizationHistory, ScrapInventory
        
        # Get the history item
        if request.user.is_superuser or request.user.is_staff:
            history = OptimizationHistory.objects.get(id=history_id)
        else:
            history = OptimizationHistory.objects.get(id=history_id, user=request.user)
        
        # Get new status from request
        new_status = request.data.get('is_executed', False)
        
        if new_status:
            if history.is_executed:
                return Response({
                    'success': False,
                    'detail': 'This optimization has already been executed and cannot be reverted.'
                }, status=400)

            # Check if any consumed scrap is already consumed by another executed optimization
            consumed_ids = history.parameters.get('consumed_scrap_inventory_ids') or []
            if consumed_ids:
                scraps = ScrapInventory.objects.filter(id__in=consumed_ids)
                scraps_dict = {s.id: s.scrap_id for s in scraps}
                
                # Check overlap in executed optimizations
                executed_runs = OptimizationHistory.objects.filter(is_executed=True).exclude(id=history.id)
                for run in executed_runs:
                    run_consumed_ids = run.parameters.get('consumed_scrap_inventory_ids') or []
                    overlap_ids = set(consumed_ids).intersection(set(run_consumed_ids))
                    if overlap_ids:
                        conflict_scrap_ids = [scraps_dict.get(oid, f"ID {oid}") for oid in overlap_ids]
                        conflict_scrap_str = ", ".join(conflict_scrap_ids)
                        error_detail = (
                            f'The scrap "{conflict_scrap_str}" is used in different optimization "{run.job_name}" '
                            f'(ID: {run.id}) that is already executed. We cannot use this used scrap in any other optimization.'
                        )
                        return Response({
                            'success': False,
                            'error': error_detail,
                            'detail': error_detail
                        }, status=400)

            history.is_executed = True
            history.save(update_fields=['is_executed'])

            # Mark existing scraps of this optimization as in-inventory on execution, and
            # retire the racked pieces this job cut into. Execution is one-way here, so no
            # un-consume path is needed.
            try:
                from .inventory_views import mark_scraps_as_executed, mark_consumed_inventory_scraps
                mark_scraps_as_executed(history)
                mark_consumed_inventory_scraps(history)
            except Exception as inv_err:
                print(f"[INVENTORY] Error marking scraps as executed (non-critical): {inv_err}")

            return Response({
                'success': True,
                'is_executed': history.is_executed,
                'label': history.label,
                'label_color': history.label_color,
                'message': 'Marked as executed and scraps added to inventory.'
            })
        else:
            if history.is_executed:
                return Response({
                    'success': False,
                    'detail': 'Cannot revert an executed optimization.'
                }, status=400)
            history.is_executed = False
            history.save(update_fields=['is_executed'])
            return Response({
                'success': True,
                'is_executed': history.is_executed,
                'label': history.label,
                'label_color': history.label_color,
                'message': 'Optimization remains unexecuted.'
            })
        
    except OptimizationHistory.DoesNotExist:
        return Response({
            'success': False,
            'detail': 'Optimization not found or access denied'
        }, status=404)
    except Exception as e:
        return Response({
            'success': False,
            'detail': str(e)
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def rerun_history_optimization(request, history_id):
    """
    Rerun an existing optimization with edited/updated inputs,
    updating the existing history record instead of creating a new one.
    """
    try:
        from django.utils import timezone
        from django.core.cache import cache as django_cache
        from django.conf import settings
        import json
        import pandas as pd
        import os
        import traceback
        import shutil
        import pickle
        from .models import OptimizationHistory, ScrapInventory
        
        # 1. GET THE HISTORY RECORD
        try:
            if request.user.is_superuser or request.user.is_staff:
                history = OptimizationHistory.objects.get(id=history_id)
            else:
                history = OptimizationHistory.objects.get(id=history_id, user=request.user)
        except OptimizationHistory.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Optimization not found or access denied'
            }, status=404)
            
        # 2. CHECK IF EXECUTED LOCK EXISTS
        if history.is_executed:
            return Response({
                'success': False,
                'error': 'This optimization has already been marked as Executed and cannot be edited.'
            }, status=400)
            
        # 3. PARSE PAYLOAD
        data = request.data
        
        # Parts list
        parts_data = data.get('uploaded_file_data')
        if not parts_data:
            return Response({
                'success': False,
                'error': 'No parts data provided'
            }, status=400)
            
        # Parent stock blocks
        parent_blocks_data = data.get('parent_blocks') or data.get('selected_parents') or data.get('parent_blocks_data')
        if not parent_blocks_data:
            return Response({
                'success': False,
                'error': 'No parent stock blocks provided'
            }, status=400)
            
        # Selected blocks for filtering (optional)
        selected_blocks = data.get('selected_blocks', history.selected_blocks)
        
        # Buffer spacing
        buffer_spacing = float(data.get('buffer_spacing', 2.0))
        
        # Max retries & Retry enabled
        max_retries = int(data.get('max_retries', 5000))
        retry_enabled = data.get('retry_enabled', True)
        if isinstance(retry_enabled, str):
            retry_enabled = retry_enabled.lower() == 'true'
            
        # 4. PROCESS PARENT BLOCKS
        parent_block_sizes = []
        parent_labels = []
        parent_quantities = []

        for i, block in enumerate(parent_blocks_data):
            try:
                if isinstance(block, dict):
                    if 'dimensions' in block:
                        dims = block['dimensions']
                        length = float(dims.get('length', 0))
                        width = float(dims.get('width', 0))
                        height = float(dims.get('height', 0))
                    elif 'length' in block and 'width' in block and 'height' in block:
                        length = float(block['length'])
                        width = float(block['width'])
                        height = float(block['height'])
                    else:
                        continue
                elif isinstance(block, list) and len(block) == 3:
                    length = float(block[0])
                    width = float(block[1])
                    height = float(block[2])
                else:
                    continue

                if length <= 0 or width <= 0 or height <= 0:
                    continue

                # Same optional stock limit the initial run accepts; absent = unlimited.
                quantity = None
                if isinstance(block, dict) and block.get('quantity') is not None:
                    try:
                        quantity = int(block['quantity'])
                        if quantity <= 0:
                            continue
                    except (TypeError, ValueError):
                        quantity = None

                parent_block_sizes.append([length, width, height])
                label = block.get('label', f'{length}×{width}×{height}') if isinstance(block, dict) else f'{length}×{width}×{height}'
                parent_labels.append(label)
                parent_quantities.append(quantity)
            except Exception as e:
                continue

        if not parent_block_sizes:
            return Response({
                'success': False,
                'error': 'No valid parent blocks provided'
            }, status=400)

        # Supply stage 1 on a rerun. Without this the endpoint would accept
        # use_scrap_inventory, report it as enabled in the summary, and pack against no
        # scrap at all.
        recovered_stock = []
        if bool(data.get('use_scrap_inventory', False)):
            try:
                from .models import ScrapInventory
                inv_qs = ScrapInventory.objects.filter(
                    is_in_inventory=True, usability__in=['usable', 'manual'])
                ids = data.get('scrap_inventory_ids')
                if ids:
                    inv_qs = inv_qs.filter(id__in=[int(v) for v in ids])
                recovered_stock = [
                    {'id': s.id, 'scrap_id': s.scrap_id,
                     'size': [float(s.length), float(s.width), float(s.height)]}
                    for s in inv_qs
                ]
                print(f"Rerun: offering {len(recovered_stock)} racked pieces")
            except Exception as e:
                print(f"Error loading scrap inventory on rerun (non-critical): {e}")
                recovered_stock = []

        # 5. FILTER SELECTED PARTS IF SPECIFIED
        original_part_count = len(parts_data)
        if selected_blocks:
            parts_data = [p for p in parts_data if p.get('MARK') in selected_blocks]
            
        if not parts_data:
            return Response({
                'success': False,
                'error': 'No parts match the selected filter blocks'
            }, status=400)
            
        # 6. WRITE PARTS DATA TO TEMPORARY EXCEL OR CSV FOR PACKING ORCHESTRATOR
        temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_uploads')
        os.makedirs(temp_dir, exist_ok=True)
        import uuid
        
        ext = ".xlsx"
        if history.uploaded_file_name.lower().endswith(".csv"):
            ext = ".csv"
            
        temp_filename = f"rerun_{uuid.uuid4().hex[:8]}_{history.uploaded_file_name}"
        if not temp_filename.endswith(ext):
            temp_filename += ext
        temp_file_path = os.path.join(temp_dir, temp_filename)
        
        try:
            # Map parameters in parts_data to correct casing if needed
            standardized_parts = []
            for part in parts_data:
                standardized_parts.append({
                    'MARK': str(part.get('MARK', part.get('mark', ''))).strip(),
                    'Bottom Length': float(part.get('Bottom Length', part.get('bottom_length', part.get('BottomLength', 0)))),
                    'Top Length': float(part.get('Top Length', part.get('top_length', part.get('TopLength', 0)))),
                    'Width': float(part.get('Width', part.get('width', 0))),
                    'Height': float(part.get('Height', part.get('height', 0))),
                    'Nos': int(float(part.get('Nos', part.get('nos', part.get('quantity', 0)))))
                })
                
            df_filtered = pd.DataFrame(standardized_parts)
            if ext == ".csv":
                df_filtered.to_csv(temp_file_path, index=False)
            else:
                df_filtered.to_excel(temp_file_path, index=False, engine='openpyxl')
        except Exception as e:
            return Response({
                'success': False,
                'error': f'Failed to write edited parts data: {str(e)}'
            }, status=400)
            
        # 7. RUN OPTIMIZATION WITH RETRY LOGIC
        optimization_start_time = timezone.now()
        helper = None
        block_details = None
        
        try:
            if retry_enabled:
                from .modules.packing_orchestrator import run_optimization_with_retries
                helper, block_details = run_optimization_with_retries(
                    excel_path=temp_file_path,
                    parent_block_sizes=parent_block_sizes,
                    buffer=buffer_spacing,
                    max_tries=max_retries,
                    parent_block_quantities=parent_quantities,
                    recovered_stock=recovered_stock
                )
            else:
                from .modules.packing_orchestrator import Prisms, run_final_code, get_block_details
                all_prisms = []
                for part in standardized_parts:
                    size = [part['Bottom Length'], part['Top Length'], part['Width'], part['Height']]
                    all_prisms.append(Prisms(code=part['MARK'], size=size, quantity=part['Nos']))
                prism_list_sorted = sorted(all_prisms, key=lambda p: p.get_volume(), reverse=True)
                helper = run_final_code(all_prisms=prism_list_sorted, buffer=buffer_spacing,
                                        parent_block_sizes=parent_block_sizes,
                                        parent_block_quantities=parent_quantities,
                                        recovered_stock=recovered_stock)
                block_details = get_block_details(helper)
                
            if helper is None:
                raise Exception("Optimization algorithm returned None")
                
            # Associate parent helper
            for b in helper.all_big_blocks:
                b.parent_helper = helper
                
        except Exception as e:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            return Response({
                'success': False,
                'error': f'Optimization failed: {str(e)}'
            }, status=500)
            
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            
        optimization_end_time = timezone.now()
        optimization_duration = (optimization_end_time - optimization_start_time).total_seconds()
        
        # 8. PREPARE RESULTS
        try:
            if block_details is None:
                block_details = get_block_details(helper)
                
            # Same split as the initial run: a recovered block is material already on the
            # rack, so it is excluded from bought-stock volume and from efficiency, and the
            # prism term is restricted with it to keep the ratio below 100%.
            new_blocks = [b for b in helper.all_big_blocks if not getattr(b, 'is_recovered', False)]
            recovered_blocks = [b for b in helper.all_big_blocks if getattr(b, 'is_recovered', False)]
            recovered_codes = {b.unique_code for b in recovered_blocks}

            total_parts_packed = 0
            total_prism_volume = 0
            recovered_prism_volume = 0
            total_requested = sum(part['Nos'] for part in standardized_parts)

            if block_details and 'blocks' in block_details:
                for block in block_details['blocks']:
                    if 'prisms' in block:
                        for prism_info in block['prisms']:
                            for part in standardized_parts:
                                if part['MARK'] == prism_info['code']:
                                    prism_volume = 0.5 * (part['Bottom Length'] + part['Top Length']) * part['Width'] * part['Height']
                                    count = prism_info.get('number', 0)
                                    total_parts_packed += count
                                    if block.get('code') in recovered_codes:
                                        recovered_prism_volume += prism_volume * count
                                    else:
                                        total_prism_volume += prism_volume * count
                                    break

            total_stock_volume = sum(block.volume for block in new_blocks)
            efficiency = (total_prism_volume / total_stock_volume * 100) if total_stock_volume > 0 else 0

            blocks_info = []
            for block in helper.all_big_blocks:
                prism_counts = {}
                for entry in block.prism_details:
                    prism = entry['prism']
                    count = len(entry['coordinates'])
                    prism_counts[prism.code] = prism_counts.get(prism.code, 0) + count
                prism_list = [{"code": code, "count": count} for code, count in prism_counts.items()]

                blocks_info.append({
                    'code': block.unique_code,
                    'size': [float(dim) for dim in block.size],
                    'efficiency': float(block.get_efficiency()),
                    'prisms': prism_list,
                    'volume': float(block.volume),
                    'start_coord': [float(coord) for coord in block.start_coord],
                    'pattern_key': layout_signature(block),
                    'is_recovered': bool(getattr(block, 'is_recovered', False)),
                    'source_scrap_id': getattr(block, 'source_scrap_id', None)
                })

            scraps_info = []
            for scrap in helper.all_scrap:
                scraps_info.append({
                    'code': scrap.unique_code,
                    'size': [float(dim) for dim in scrap.size],
                    'volume': float(scrap.volume),
                    'start_coord': [float(coord) for coord in scrap.start_coord],
                    'parent_block': scrap.parent_block.unique_code if scrap.parent_block else None
                })
                
            prism_summary = []
            for part in standardized_parts:
                packed_count = 0
                for block_info in blocks_info:
                    for prism_info in block_info['prisms']:
                        if prism_info['code'] == part['MARK']:
                            packed_count += prism_info['count']
                prism_summary.append({
                    'code': part['MARK'],
                    'requested': part['Nos'],
                    'packed': packed_count,
                    'remaining': max(0, part['Nos'] - packed_count),
                    'bottom_length': part['Bottom Length'],
                    'top_length': part['Top Length'],
                    'width': part['Width'],
                    'height': part['Height'],
                    'volume': 0.5 * (part['Bottom Length'] + part['Top Length']) * part['Width'] * part['Height'],
                    'packing_rate': (packed_count / part['Nos'] * 100) if part['Nos'] > 0 else 0
                })
                
        except Exception as e:
            traceback.print_exc()
            return Response({
                'success': False,
                'error': f'Failed to process results structure: {str(e)}'
            }, status=500)
            
        # 9. UPDATE DATABASE RECORD
        # Delete old scraps associated with this history item first
        ScrapInventory.objects.filter(optimization_history=history).delete()
        
        # Clear helper cache - best effort; a stale entry is superseded by the write below
        cache_delete_safe(f"helper_objs_{history.id}", label=f"helper_objs_{history.id}")
        
        # Update fields
        optimization_results = {
            'blocks': blocks_info,
            'scraps': scraps_info,
            'summary': {
                'efficiency': round(efficiency, 2),
                'total_parts_packed': total_parts_packed,
                'total_parts_requested': total_requested,
                'packing_percentage': round(total_parts_packed / total_requested * 100, 2) if total_requested > 0 else 0,
                'total_blocks_created': len(new_blocks),
                'total_stock_volume': round(total_stock_volume, 2),
                'total_prism_volume': round(total_prism_volume, 2),
                'waste_percentage': round(100 - efficiency, 2),
                'total_recovered_blocks': len(recovered_blocks),
                'material_saved_volume': round(recovered_prism_volume, 2),
                'optimization_duration_seconds': round(optimization_duration, 2)
            }
        }

        # Same shop-floor summary the initial run produces, so a reran job does not lose it.
        scrap_inventory_enabled = bool(data.get('use_scrap_inventory', False))
        consumed_from_inventory = [
            c for c in getattr(helper, 'consumed_scraps', [])
            if c.get('origin') == 'inventory'
        ]
        try:
            # Recovered blocks are excluded from the pull list; see the same split in
            # upload_and_optimize.
            optimization_results['summary'].update(build_summary(
                blocks=[b for b in blocks_info if not b.get('is_recovered')],
                scraps=scraps_info,
                prism_summary=prism_summary,
                stock_sizes=stock_sizes_from(parent_block_sizes, parent_labels),
                blade_thickness=buffer_spacing,
                source_file=data.get('uploaded_file_name') or history.uploaded_file_name,
                run_by=request.user.username,
                run_at=timezone.now().isoformat(),
                scrap_inventory_enabled=scrap_inventory_enabled,
                consumed_scraps=consumed_from_inventory,
            ))
        except Exception as e:
            print(f"Error building run summary on rerun (non-critical): {e}")
            traceback.print_exc()

        history.uploaded_file_data = standardized_parts
        if data.get('uploaded_file_name'):
            history.uploaded_file_name = data.get('uploaded_file_name')
        history.selected_blocks = selected_blocks
        history.selected_parents = parent_labels
        history.parameters = {
            'buffer_spacing': buffer_spacing,
            'parent_blocks_used': parent_block_sizes,
            'parent_labels': parent_labels,
            'max_retries': max_retries,
            'retry_enabled': retry_enabled,
            'original_part_count': original_part_count,
            'filtered_part_count': len(standardized_parts),
            'optimization_duration_seconds': optimization_duration,
            'scrap_inventory_enabled': scrap_inventory_enabled,
            'consumed_scraps': consumed_from_inventory,
            'parent_block_quantities': parent_quantities,
            'recovered_stock': recovered_stock,
            # Rewritten, not merged: a rerun replaces the plan, so the pieces the previous
            # plan would have consumed must not stay on the execute list.
            'consumed_scrap_inventory_ids': [
                b.source_inventory_id for b in recovered_blocks
                if getattr(b, 'source_inventory_id', None) is not None
            ]
        }
        history.optimization_results = optimization_results
        history.efficiency = round(efficiency, 2)
        history.total_blocks_created = len(new_blocks)
        history.total_parts_packed = total_parts_packed
        history.total_parts_requested = total_requested
        history.prism_summary = prism_summary
        history.save()
        
        # Save pickled helper to disk
        helpers_dir = os.path.join(settings.MEDIA_ROOT, "helpers")
        pkl_path = os.path.join(helpers_dir, f"{history.id}.pkl")
        try:
            with open(pkl_path, "wb") as f:
                pickle.dump(helper, f)
        except Exception as pkl_err:
            print(f"Failed to save pickled helper: {pkl_err}")
            
        # Recache helper. Non-fatal for the same reason as the initial run: the rerun has
        # already been written to the history row above.
        cache_set_safe(f"helper_objs_{history.id}", helper, timeout=1800,
                       label=f"helper_objs_{history.id}")
        cache_set_safe("latest_helper", helper, timeout=60 * 60 * 24 * 7,
                       label="latest_helper")
        
        # 10. REGENERATE BLOCK 6-SIDE VISUALIZATIONS
        html_base_dir = os.path.join(settings.MEDIA_ROOT, "block_html", str(history.id))
        if os.path.exists(html_base_dir):
            try:
                shutil.rmtree(html_base_dir)
            except Exception as e:
                print(f"Error removing old HTML dir: {e}")
        os.makedirs(html_base_dir, exist_ok=True)
        
        for block in helper.all_big_blocks:
            try:
                generate_block_6_side_images(block, html_base_dir, block.unique_code)
            except Exception as e:
                print(f"Error generating block HTML: {e}")
                
        job_label = f"OPT-{history.id:04d}"
        master_html_path = os.path.join(html_base_dir, f"{job_label}_All_Blocks_6_Sides.html")
        try:
            generate_all_blocks_master_html(helper.all_big_blocks, master_html_path, job_label)
        except Exception as e:
            print(f"Error generating master HTML: {e}")
            
        # Save scraps to DB matching execution state
        try:
            from .inventory_views import auto_save_scraps_from_optimization
            auto_save_scraps_from_optimization(helper, history, request.user)
        except Exception as inv_err:
            print(f"Error auto saving scraps on rerun: {inv_err}")
            
        return Response({
            'success': True,
            'message': 'Optimization updated and rerun successfully',
            'data': {
                'id': history.id,
                'job_name': history.job_name,
                'created_at': history.created_at,
                'efficiency': history.efficiency,
                'uploaded_file_name': history.uploaded_file_name,
                'uploaded_file_data': history.uploaded_file_data,
                'selected_blocks': history.selected_blocks,
                'selected_parents': history.selected_parents,
                'parameters': history.parameters,
                'optimization_results': history.optimization_results,
                'is_executed': history.is_executed,
                'label': history.label,
                'label_color': history.label_color,
                'username': history.user.username,
                'prism_summary': history.prism_summary,
                'summary': dict({
                    'total_blocks_created': history.total_blocks_created,
                    'total_parts_packed': history.total_parts_packed,
                    'total_parts_requested': history.total_parts_requested,
                    'is_successful': history.is_successful
                }, **((history.optimization_results or {}).get('summary') or {}))
            }
        })

    except Exception as e:
        traceback.print_exc()
        return Response({
            'success': False,
            'error': f'Rerun failed: {str(e)}'
        }, status=500)


# ================================
# EXISTING VIEWSETS (UNCHANGED)
# ================================

class StockBlockViewSet(viewsets.ModelViewSet):
    """
    ViewSet for StockBlock model.
    """
    queryset = StockBlock.objects.all()
    serializer_class = StockBlockSerializer
    filterset_fields = ['material_type']
    search_fields = ['name', 'material_type']
    ordering_fields = ['created_at', 'name', 'volume']
    ordering = ['-created_at']


class PartSpecificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for PartSpecification model.
    """
    queryset = PartSpecification.objects.all()
    serializer_class = PartSpecificationSerializer
    filterset_fields = ['thickness']
    search_fields = ['name']
    ordering_fields = ['created_at', 'name', 'volume']
    ordering = ['name']


class CuttingJobViewSet(viewsets.ModelViewSet):
    """
    ViewSet for CuttingJob model.
    """
    queryset = CuttingJob.objects.all()
    serializer_class = CuttingJobSerializer
    filterset_fields = ['status']
    ordering_fields = ['created_at', 'completed_at']
    ordering = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return CuttingJobCreateSerializer
        return CuttingJobSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Create job object
        stock_block_id = serializer.validated_data.get('stock_block_id')
        stock_block = None
        if stock_block_id:
            try:
                stock_block = StockBlock.objects.get(id=stock_block_id)
            except StockBlock.DoesNotExist:
                pass

        job = CuttingJob.objects.create(
            stock_dimensions=serializer.validated_data['stock_dimensions'],
            parts_spec=serializer.validated_data['parts'],
            config_params=serializer.validated_data.get('config_params', {}),
            stock_block=stock_block,
            status='running',
            started_at=timezone.now()
        )

        # Run optimization
        try:
            service = get_cutting_service()
            results = service.run_cutting_job(
                stock_dimensions=job.stock_dimensions,
                parts_spec=job.parts_spec,
                config_params=job.config_params
            )

            # Update job with results
            job.results = results
            job.visualization_files = results.get('visualization_files', [])
            job.status = 'completed'
            job.completed_at = timezone.now()
            job.save()

        except Exception as e:
            job.status = 'failed'
            job.error_message = str(e)
            job.completed_at = timezone.now()
            job.save()

            return Response(
                {
                    'error': str(e),
                    'job_id': job.id,
                    'status': 'failed'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        response_serializer = CuttingJobSerializer(job)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        job = self.get_object()
        serializer = self.get_serializer(job)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def rerun(self, request, pk=None):
        original_job = self.get_object()

        new_job = CuttingJob.objects.create(
            stock_dimensions=original_job.stock_dimensions,
            parts_spec=original_job.parts_spec,
            config_params=original_job.config_params,
            stock_block=original_job.stock_block,
            status='running',
            started_at=timezone.now()
        )

        try:
            service = get_cutting_service()
            results = service.run_cutting_job(
                stock_dimensions=new_job.stock_dimensions,
                parts_spec=new_job.parts_spec,
                config_params=new_job.config_params
            )

            new_job.results = results
            new_job.visualization_files = results.get('visualization_files', [])
            new_job.status = 'completed'
            new_job.completed_at = timezone.now()
            new_job.save()

        except Exception as e:
            new_job.status = 'failed'
            new_job.error_message = str(e)
            new_job.completed_at = timezone.now()
            new_job.save()

            return Response(
                {'error': str(e), 'job_id': new_job.id},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        serializer = self.get_serializer(new_job)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ConfigurationSetViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for ConfigurationSet model.
    """
    queryset = ConfigurationSet.objects.all()
    serializer_class = ConfigurationSetSerializer
    filterset_fields = ['status']
    ordering_fields = ['created_at', 'completed_at']
    ordering = ['-created_at']


# ================================
# OTHER EXISTING ENDPOINTS
# ================================


class VisualizationFileView(APIView):
    """
    API endpoint to serve visualization files.
    """
    def get(self, request, filepath):
        base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'outputs', 'visualizations')
        full_path = os.path.join(base_dir, filepath)

        full_path = os.path.abspath(full_path)
        base_dir = os.path.abspath(base_dir)

        if not full_path.startswith(base_dir):
            raise Http404("Invalid file path")

        if not os.path.exists(full_path):
            raise Http404("File not found")

        try:
            return FileResponse(open(full_path, 'rb'), content_type='text/html')
        except Exception as e:
            raise Http404(f"Error serving file: {e}")

@csrf_exempt
@require_POST
def upload_optimize_django(request):
    """
    Django view decorator version of upload_and_optimize
    """
    try:
        from rest_framework.request import Request
        from rest_framework.parsers import MultiPartParser, FormParser
        
        drf_request = Request(request, parsers=[MultiPartParser(), FormParser()])
        return upload_and_optimize(drf_request)
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
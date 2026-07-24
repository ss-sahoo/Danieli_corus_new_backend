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
        
        for block in blocks:
            efficiency = block.get_efficiency()
            size = block.size
            volume = block.volume
            
            legend_items = []
            seen_codes = set()
            if getattr(block, 'prism_details', None):
                for detail in block.prism_details:
                    prism_code = getattr(detail['prism'], 'code', 'Part')
                    prism_code_clean = str(prism_code).strip()
                    if prism_code_clean not in seen_codes:
                        seen_codes.add(prism_code_clean)
                        import zlib
                        hash_val = zlib.crc32(prism_code_clean.encode('utf-8'))
                        color = colors_palette[hash_val % len(colors_palette)]
                        legend_items.append((prism_code_clean, color))
            
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

        helper = cache.get("latest_helper")
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
            
        from .models import OptimizationHistory
        from .modules.packing_orchestrator import Prisms, run_final_code
        
        history = OptimizationHistory.objects.get(id=int(job_id))
        parts_data = history.uploaded_file_data
        buffer_spacing = history.parameters.get('buffer_spacing', 2)
        parent_block_sizes = history.parameters.get('parent_blocks_used', [])
        
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
        helper = run_final_code(prism_list_sorted, buffer=buffer_spacing, parent_block_sizes=parent_block_sizes)
        
        html_base_dir = os.path.join(settings.MEDIA_ROOT, "block_html", str(history.id))
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
    if not job_id:
        return cache.get("latest_helper")
        
    from django.core.cache import cache as django_cache
    helper_cache_key = f"helper_objs_{job_id}"
    cached_helper = django_cache.get(helper_cache_key)
    if cached_helper is not None:
        return cached_helper

    try:
        from .models import OptimizationHistory
        from .modules.packing_orchestrator import Prisms, run_final_code
        history = OptimizationHistory.objects.get(id=int(job_id))
        parts_data = history.uploaded_file_data
        buffer_spacing = history.parameters.get('buffer_spacing', 2)
        parent_block_sizes = history.parameters.get('parent_blocks_used', [])
        
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
        helper = run_final_code(prism_list_sorted, buffer=buffer_spacing, parent_block_sizes=parent_block_sizes)
        
        django_cache.set(helper_cache_key, helper, timeout=1800)
        return helper
    except Exception as e:
        print(f"[GET_HELPER] Error reconstructing helper for job {job_id}: {e}")
        return cache.get("latest_helper")


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
            # Try by index
            try:
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
        
        try:
            selected_blocks = json.loads(selected_blocks_json)
            parent_blocks_data = json.loads(parent_blocks_json)
        except json.JSONDecodeError as e:
            return Response({
                'success': False,
                'error': f'Invalid JSON in parameters: {str(e)}'
            }, status=400)
        
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
                
                # Add to lists
                parent_block_sizes.append([length, width, height])
                label = block.get('label', f'{length}×{width}×{height}') if isinstance(block, dict) else f'{length}×{width}×{height}'
                parent_labels.append(label)
                
                print(f"Added parent block: {label} = [{length}, {width}, {height}]")
                
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
                    max_tries=max_retries
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
                    parent_block_sizes=parent_block_sizes
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
            
            # Store helper in cache for visualization
            cache.set(
                "latest_helper",
                helper,
                timeout=60 * 60 * 24 * 7  # 2 hours
            )
            # print(f"Cached helper for visualizations.")
            
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
            
            # Calculate totals
            total_parts_packed = 0
            total_prism_volume = 0
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
                                    total_parts_packed += prism_info.get('number', 0)
                                    total_prism_volume += prism_volume * prism_info.get('number', 0)
                                    break
            
            print(f"Packing summary:")
            print(f"- Total parts requested: {total_requested}")
            print(f"- Total parts packed: {total_parts_packed}")
            print(f"- Packing rate: {(total_parts_packed/total_requested*100 if total_requested > 0 else 0):.2f}%")
            
            # Calculate total stock volume
            total_stock_volume = 0
            for block in helper.all_big_blocks:
                total_stock_volume += block.volume
            
            # Calculate efficiency
            if total_stock_volume > 0:
                efficiency = (total_prism_volume / total_stock_volume) * 100
            else:
                efficiency = 0
            
            print(f"- Total stock volume: {total_stock_volume:.2f}")
            print(f"- Total prism volume: {total_prism_volume:.2f}")
            print(f"- Efficiency: {efficiency:.2f}%")
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
                        'start_coord': [float(coord) for coord in block.start_coord]
                    })
                except Exception as e:
                    print(f"Error processing block {block.unique_code}: {e}")
                    continue
            
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
            prism_summary = []
            for part in parts_data:
                # Find matching prism in helper
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
            print(f"Error preparing results: {e}")
            traceback.print_exc()
            # Create minimal results
            blocks_info = []
            scraps_info = []
            prism_summary = []
            total_stock_volume = 0
            total_prism_volume = 0
            total_parts_packed = 0
            total_requested = sum(part['Nos'] for part in parts_data)
            efficiency = 0
        
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
                        'optimization_duration_seconds': optimization_duration
                    },
                    optimization_results=optimization_results,
                    efficiency=round(efficiency, 2),
                    total_blocks_created=len(helper.all_big_blocks),
                    total_parts_packed=total_parts_packed,
                    total_parts_requested=total_requested,
                    prism_summary=prism_summary
                )
                
                # Build a professional, industry-style job name:
                # e.g. "OPT-0007 · SteelParts Jul11" instead of "Run #7 - sample_data"
                raw_stem = os.path.splitext(excel_file.name)[0]          # e.g. "sample_data"
                clean_stem = raw_stem.replace('_', ' ').replace('-', ' ').strip().title()  # "Sample Data"
                date_tag = timezone.now().strftime("%d %b %y")            # "11 Jul 26"
                history.job_name = f"OPT-{history.id:04d} \u00b7 {clean_stem} \u00b7 {date_tag}"
                history.save(update_fields=['job_name'])
                
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
        results = {
            'success': True,
            'efficiency': round(efficiency, 2),
            'total_parts_packed': total_parts_packed,
            'total_parts_requested': total_requested,
            'packing_percentage': round(total_parts_packed / total_requested * 100, 2) if total_requested > 0 else 0,
            'total_blocks_created': len(helper.all_big_blocks),
            'total_stock_volume': round(total_stock_volume, 2),
            'total_prism_volume': round(total_prism_volume, 2),
            'waste_percentage': round(100 - efficiency, 2),
            'blocks': blocks_info,
            'scraps': scraps_info,
            'parent_blocks_used': parent_block_sizes,
            'parent_labels': parent_labels,
            'prism_summary': prism_summary,
            'optimization_parameters': {
                'buffer_spacing': buffer_spacing,
                'max_retries': max_retries,
                'retry_enabled': retry_enabled,
                'optimization_duration_seconds': round(optimization_duration, 2)
            },
            'history_saved': history_saved,
            'history_id': history_id,
            'message': f'Successfully packed {total_parts_packed} out of {total_requested} parts ({total_parts_packed/total_requested*100:.1f}%) into {len(helper.all_big_blocks)} stock blocks with {efficiency:.2f}% efficiency in {optimization_duration:.2f} seconds.',
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
    """
    try:
        from .models import OptimizationHistory
        from django.db.models import Q

        page = max(1, int(request.GET.get('page', 1)))
        page_size = min(100, max(1, int(request.GET.get('page_size', 50))))
        search = request.GET.get('search', '').strip()
        show_all = request.GET.get('all_users', 'false').lower() == 'true'

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
                'optimization_results': history.optimization_results,
                'is_executed': history.is_executed,
                'label': history.label,
                'label_color': history.label_color,
                'username': history.user.username,
                'summary': {
                    'total_blocks_created': history.total_blocks_created,
                    'total_parts_packed': history.total_parts_packed,
                    'total_parts_requested': history.total_parts_requested,
                    'is_successful': history.is_successful
                }
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
        from .models import OptimizationHistory
        
        # Get the history item
        if request.user.is_superuser or request.user.is_staff:
            history = OptimizationHistory.objects.get(id=history_id)
        else:
            history = OptimizationHistory.objects.get(id=history_id, user=request.user)
        
        # Get new status from request
        new_status = request.data.get('is_executed', False)
        
        # Update status
        history.is_executed = new_status
        history.save()
        
        return Response({
            'success': True,
            'is_executed': history.is_executed,
            'label': history.label,
            'label_color': history.label_color,
            'message': f'Optimization marked as {"executed" if new_status else "not executed"}'
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
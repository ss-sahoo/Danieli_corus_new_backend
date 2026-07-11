"""
Scrap Inventory API views.
Global shared inventory — all authenticated users can view/manage.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import IntegrityError

MIN_USABLE_MM = 15.0  # scraps with any dim <= this are "unusable"


def _serialize_scrap(s):
    return {
        'id': s.id,
        'scrap_id': s.scrap_id,
        'parent_block_code': s.parent_block_code,
        'length': s.length,
        'width': s.width,
        'height': s.height,
        'volume': round(s.volume, 2),
        'dimensions_str': s.dimensions_str,
        'usability': s.usability,
        'is_in_inventory': s.is_in_inventory,
        'notes': s.notes,
        'added_by': s.added_by.username if s.added_by else None,
        'optimization_id': s.optimization_history_id,
        'created_at': s.created_at.isoformat(),
    }


# ================================
# LIST INVENTORY
# ================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_inventory(request):
    """
    GET /api/inventory/
    Query params: usability=usable|unusable|all, in_inventory=true|false,
                  search=<scrap_id or parent_block_code>, page=1, page_size=20
    """
    from .models import ScrapInventory

    qs = ScrapInventory.objects.all()

    usability = request.GET.get('usability', 'usable')
    if usability != 'all':
        qs = qs.filter(usability=usability)

    in_inventory = request.GET.get('in_inventory', 'true')
    if in_inventory == 'true':
        qs = qs.filter(is_in_inventory=True)
    elif in_inventory == 'false':
        qs = qs.filter(is_in_inventory=False)

    # Search by scrap_id or parent_block_code (case-insensitive)
    search = request.GET.get('search', '').strip()
    if search:
        from django.db.models import Q
        qs = qs.filter(
            Q(scrap_id__icontains=search) | Q(parent_block_code__icontains=search)
        )

    # Pagination
    try:
        page = max(1, int(request.GET.get('page', 1)))
        page_size = min(100, max(1, int(request.GET.get('page_size', 20))))
    except (ValueError, TypeError):
        page, page_size = 1, 20

    total = qs.count()
    total_pages = max(1, (total + page_size - 1) // page_size)
    page = min(page, total_pages)

    start = (page - 1) * page_size
    end = start + page_size
    items = qs.select_related('added_by')[start:end]

    data = [_serialize_scrap(s) for s in items]
    return Response({
        'success': True,
        'inventory': data,
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total': total,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_previous': page > 1,
        }
    })


# ================================
# ADD UNUSABLE SCRAP TO INVENTORY
# ================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_to_inventory(request):
    """
    POST /api/inventory/add/
    Manually add a scrap (typically unusable) to inventory.
    Body: { scrap_id, parent_block_code, length, width, height, notes? }
    """
    from .models import ScrapInventory

    data = request.data
    scrap_id = str(data.get('scrap_id', '')).strip()
    parent_block_code = str(data.get('parent_block_code', '')).strip()

    try:
        length = float(data['length'])
        width = float(data['width'])
        height = float(data['height'])
    except (KeyError, ValueError, TypeError):
        return Response({'detail': 'length, width, height are required numbers.'}, status=400)

    if not scrap_id or not parent_block_code:
        return Response({'detail': 'scrap_id and parent_block_code are required.'}, status=400)

    volume = length * width * height
    min_dim = min(length, width, height)
    usability = 'unusable' if min_dim <= MIN_USABLE_MM else 'manual'

    try:
        scrap, created = ScrapInventory.objects.get_or_create(
            scrap_id=scrap_id,
            defaults={
                'parent_block_code': parent_block_code,
                'length': length,
                'width': width,
                'height': height,
                'volume': volume,
                'usability': usability,
                'is_in_inventory': True,
                'notes': str(data.get('notes', '')),
                'added_by': request.user,
            }
        )
        if not created:
            # Already exists — ensure it's marked in inventory
            scrap.is_in_inventory = True
            scrap.notes = str(data.get('notes', scrap.notes))
            scrap.save(update_fields=['is_in_inventory', 'notes'])

        return Response({
            'success': True,
            'created': created,
            'scrap': _serialize_scrap(scrap),
            'message': f"Scrap {scrap_id} {'added to' if created else 'updated in'} inventory."
        }, status=201 if created else 200)

    except Exception as e:
        return Response({'detail': str(e)}, status=500)


# ================================
# REMOVE FROM INVENTORY
# ================================

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def remove_from_inventory(request, scrap_pk):
    """
    DELETE /api/inventory/<pk>/remove/
    Marks the scrap as not in inventory (soft delete).
    """
    from .models import ScrapInventory

    try:
        scrap = ScrapInventory.objects.get(pk=scrap_pk)
        scrap.is_in_inventory = False
        scrap.save(update_fields=['is_in_inventory'])
        return Response({'success': True, 'message': f'Scrap {scrap.scrap_id} removed from inventory.'})
    except ScrapInventory.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=404)
    except Exception as e:
        return Response({'detail': str(e)}, status=500)


# ================================
# HELPER: auto-save scraps from optimization
# ================================

def auto_save_scraps_from_optimization(helper, optimization_history, added_by):
    """
    Called after a successful optimization run.
    Saves scraps with all dimensions > MIN_USABLE_MM to inventory automatically.
    Smaller ones are saved with usability='unusable' and is_in_inventory=False.
    Scrap IDs are derived from parent block code: e.g. B1-S1, B1-S2, B2-S1 ...
    """
    from .models import ScrapInventory

    if not helper or not hasattr(helper, 'all_scrap'):
        return []

    saved = []
    # Track per-parent scrap counter for ID generation
    parent_counters = {}

    for scrap in helper.all_scrap:
        try:
            size = scrap.size  # [length, width, height]
            length, width, height = float(size[0]), float(size[1]), float(size[2])
            volume = float(scrap.volume)

            parent_code = scrap.parent_block.unique_code if scrap.parent_block else 'UNK'
            parent_counters[parent_code] = parent_counters.get(parent_code, 0) + 1
            scrap_id = f"{parent_code}-S{parent_counters[parent_code]}"

            min_dim = min(length, width, height)
            is_usable = min_dim > MIN_USABLE_MM
            usability = 'usable' if is_usable else 'unusable'

            # Skip if already exists
            if ScrapInventory.objects.filter(scrap_id=scrap_id).exists():
                # Make unique by appending optimization id
                scrap_id = f"{scrap_id}-H{optimization_history.id}"

            ScrapInventory.objects.create(
                scrap_id=scrap_id,
                parent_block_code=parent_code,
                optimization_history=optimization_history,
                added_by=added_by,
                length=length,
                width=width,
                height=height,
                volume=volume,
                usability=usability,
                is_in_inventory=is_usable,  # only usable ones auto-added
            )
            saved.append(scrap_id)

        except Exception as e:
            print(f"[Inventory] Error saving scrap: {e}")
            continue

    print(f"[Inventory] Saved {len(saved)} scraps. Usable auto-added to inventory.")
    return saved

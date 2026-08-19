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


def _serialize_scrap(s, consumed_info=None, targeting_info=None, history_map=None):
    consumed_by = None
    if consumed_info and s.id in consumed_info:
        consumed_by = consumed_info[s.id]
    
    targeted_by = []
    if targeting_info and s.id in targeting_info:
        targeted_by = targeting_info[s.id]

    produced_by = None
    if history_map is not None:
        if s.optimization_history_id and s.optimization_history_id in history_map:
            run = history_map[s.optimization_history_id]
            produced_by = {
                'id': run['id'],
                'job_name': run['job_name']
            }
    elif s.optimization_history:
        produced_by = {
            'id': s.optimization_history.id,
            'job_name': s.optimization_history.job_name
        }
        
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
        'consumed_by': consumed_by,
        'targeted_by': targeted_by,
        'produced_by': produced_by,
    }


# ================================
# LIST INVENTORY
# ================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_inventory(request):
    """
    GET /api/inventory/
    Query params: usability=usable|unusable|used|all, in_inventory=true|false,
                  search=<scrap_id or parent_block_code>, sort_by=<field>, page=1, page_size=20
    """
    from .models import ScrapInventory, OptimizationHistory
    from django.db.models import Q

    # Fetch mapping of consumed scrap IDs to their executed optimizations (non-revertible)
    consumed_ids_to_run_info = {}
    executed_runs = OptimizationHistory.objects.filter(is_executed=True).values('id', 'job_name', 'parameters')
    for run in executed_runs:
        params = run.get('parameters') or {}
        ids = params.get('consumed_scrap_inventory_ids') or []
        for cid in ids:
            consumed_ids_to_run_info[cid] = {
                'id': run['id'],
                'job_name': run['job_name']
            }

    # Fetch mapping of scrap IDs to list of non-executed optimizations targeting them
    targeting_ids_to_runs = {}
    non_executed_runs = OptimizationHistory.objects.filter(is_executed=False).values('id', 'job_name', 'parameters')
    for run in non_executed_runs:
        params = run.get('parameters') or {}
        ids = params.get('consumed_scrap_inventory_ids') or []
        for cid in ids:
            if cid not in targeting_ids_to_runs:
                targeting_ids_to_runs[cid] = []
            targeting_ids_to_runs[cid].append({
                'id': run['id'],
                'job_name': run['job_name']
            })

    usability = request.GET.get('usability', 'usable')

    if usability == 'used':
        # Show scraps consumed by ANY executed optimization
        qs = ScrapInventory.objects.filter(id__in=consumed_ids_to_run_info.keys())
    else:
        # Only show scraps that are manually added (no optimization_history) or whose parent optimization is executed,
        # and exclude any scraps that have already been consumed by an executed optimization.
        qs = ScrapInventory.objects.filter(
            Q(optimization_history__isnull=True) | Q(optimization_history__is_executed=True)
        ).exclude(id__in=consumed_ids_to_run_info.keys())
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
        qs = qs.filter(
            Q(scrap_id__icontains=search) | Q(parent_block_code__icontains=search)
        )

    # Sorting
    sort_by = request.GET.get('sort_by', '-created_at').strip()
    valid_sort_fields = {
        'volume': 'volume',
        '-volume': '-volume',
        'length': 'length',
        '-length': '-length',
        'width': 'width',
        '-width': '-width',
        'height': 'height',
        '-height': '-height',
        'scrap_id': 'scrap_id',
        '-scrap_id': '-scrap_id',
        'parent_block_code': 'parent_block_code',
        '-parent_block_code': '-parent_block_code',
        'created_at': 'created_at',
        '-created_at': '-created_at'
    }
    if sort_by in valid_sort_fields:
        if sort_by == 'length':
            qs = qs.order_by('length', 'width', 'height')
        elif sort_by == '-length':
            qs = qs.order_by('-length', '-width', '-height')
        elif sort_by == 'width':
            qs = qs.order_by('width', 'length', 'height')
        elif sort_by == '-width':
            qs = qs.order_by('-width', '-length', '-height')
        elif sort_by == 'height':
            qs = qs.order_by('height', 'length', 'width')
        elif sort_by == '-height':
            qs = qs.order_by('-height', '-length', '-width')
        else:
            qs = qs.order_by(sort_by)
    else:
        qs = qs.order_by('-created_at')

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

    # Collect source optimization details efficiently without loading full large JSON rows
    hist_ids = {s.optimization_history_id for s in items if s.optimization_history_id is not None}
    history_map = {}
    if hist_ids:
        runs = OptimizationHistory.objects.filter(id__in=hist_ids).values('id', 'job_name')
        for r in runs:
            history_map[r['id']] = r

    data = [_serialize_scrap(s, consumed_ids_to_run_info, targeting_ids_to_runs, history_map) for s in items]
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

    if ScrapInventory.objects.filter(scrap_id__iexact=scrap_id).exists():
        return Response({'detail': f'Scrap with ID "{scrap_id}" already exists. Please choose a unique Scrap ID.'}, status=400)

    volume = length * width * height
    min_dim = min(length, width, height)
    usability = 'unusable' if min_dim <= MIN_USABLE_MM else 'manual'

    try:
        scrap = ScrapInventory.objects.create(
            scrap_id=scrap_id,
            parent_block_code=parent_block_code,
            length=length,
            width=width,
            height=height,
            volume=volume,
            usability=usability,
            is_in_inventory=True,
            notes=str(data.get('notes', '')),
            added_by=request.user,
        )

        return Response({
            'success': True,
            'created': True,
            'scrap': _serialize_scrap(scrap),
            'message': f"Scrap {scrap_id} added to inventory."
        }, status=201)

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

            # A remnant of a racked offcut should trace back to that offcut's ID, not to the
            # opaque R-code this run happened to give it, so the piece's history survives.
            parent_block = scrap.parent_block
            source_scrap_id = getattr(parent_block, 'source_scrap_id', None) if parent_block else None
            parent_code = source_scrap_id or (parent_block.unique_code if parent_block else 'UNK')

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
                is_in_inventory=False,  # initially False, set to True only when executed
            )
            saved.append(scrap_id)

        except Exception as e:
            print(f"[Inventory] Error saving scrap: {e}")
            continue

    print(f"[Inventory] Saved {len(saved)} scraps. Usable auto-added to inventory.")
    return saved


def mark_scraps_as_executed(optimization_history):
    """
    Called when an optimization is marked as executed.
    Flips is_in_inventory to True for all its associated usable scraps.
    """
    from .models import ScrapInventory

    updated = ScrapInventory.objects.filter(
        optimization_history=optimization_history,
        usability='usable'
    ).update(is_in_inventory=True)

    print(f"[Inventory] Marked {updated} usable scraps in inventory for executed optimization #{optimization_history.id}")
    return updated


def mark_consumed_inventory_scraps(optimization_history):
    """
    Called when an optimization is marked as executed.

    Retires the racked offcuts this job cut into. Consumption happens here rather than at
    run time because a planned run may never be executed, and reserving stock for a plan
    that is abandoned would hide usable material from every later job.

    Together with mark_scraps_as_executed the loop closes on execute: the pieces that were
    cut up leave inventory, and the remnants those cuts produced enter it.
    """
    from .models import ScrapInventory

    params = optimization_history.parameters or {}
    consumed_ids = params.get('consumed_scrap_inventory_ids') or []

    if not consumed_ids:
        return 0

    note = f"Consumed by optimization #{optimization_history.id}."
    updated = 0

    for scrap in ScrapInventory.objects.filter(id__in=consumed_ids, is_in_inventory=True):
        scrap.is_in_inventory = False
        scrap.notes = f"{scrap.notes} {note}".strip() if scrap.notes else note
        scrap.save(update_fields=['is_in_inventory', 'notes'])
        updated += 1

    print(f"[Inventory] Retired {updated} consumed scrap pieces for executed optimization "
          f"#{optimization_history.id}")
    return updated


@api_view(['PATCH', 'PUT'])
@permission_classes([IsAuthenticated])
def update_scrap(request, scrap_pk):
    """
    PATCH or PUT /api/inventory/<pk>/update/
    Allows editing scrap dimensions (length, width, height) and recalculates volume/usability.
    """
    from .models import ScrapInventory

    try:
        scrap = ScrapInventory.objects.get(pk=scrap_pk)
    except ScrapInventory.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=404)

    data = request.data
    try:
        length = float(data['length'])
        width = float(data['width'])
        height = float(data['height'])
    except (KeyError, ValueError, TypeError):
        return Response({'detail': 'length, width, and height must be valid numbers.'}, status=400)

    if length <= 0 or width <= 0 or height <= 0:
        return Response({'detail': 'Dimensions must be positive numbers.'}, status=400)

    scrap.length = length
    scrap.width = width
    scrap.height = height
    scrap.volume = length * width * height

    # Recalculate usability based on minimum dimension
    min_dim = min(length, width, height)
    if min_dim <= MIN_USABLE_MM:
        scrap.usability = 'unusable'
    else:
        if scrap.usability == 'unusable':
            scrap.usability = 'usable'

    if 'notes' in data:
        scrap.notes = str(data['notes'])

    try:
        scrap.save()
        return Response({
            'success': True,
            'scrap': _serialize_scrap(scrap),
            'message': f'Scrap {scrap.scrap_id} updated successfully.'
        })
    except Exception as e:
        return Response({'detail': str(e)}, status=500)


"""
Saved parent (stock) block size API views.
Global shared list — all authenticated users can view/manage.
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


def _serialize_parent_block(b):
    return {
        'id': b.id,
        'label': b.label,
        'dimensions': {
            'length': b.length,
            'width': b.width,
            'height': b.height,
        },
        'dimensions_str': b.dimensions_str,
        'created_by': b.created_by.username if b.created_by else None,
        'created_at': b.created_at.isoformat(),
    }


# ================================
# LIST SAVED PARENT BLOCKS
# ================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_parent_blocks(request):
    """
    GET /api/parent-blocks/
    No query params, no pagination — this list is small (tens of rows).
    """
    from .models import SavedParentBlock

    items = SavedParentBlock.objects.select_related('created_by').all()
    data = [_serialize_parent_block(b) for b in items]

    return Response({
        'success': True,
        'count': len(data),
        'parent_blocks': data,
    })


# ================================
# CREATE SAVED PARENT BLOCK
# ================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_parent_block(request):
    """
    POST /api/parent-blocks/create/
    Body: { label, length, width, height }
    """
    from .models import SavedParentBlock

    data = request.data
    label = str(data.get('label', '')).strip()

    if not label:
        return Response({'detail': 'label is required.'}, status=400)

    try:
        length = float(data['length'])
        width = float(data['width'])
        height = float(data['height'])
    except (KeyError, ValueError, TypeError):
        return Response({'detail': 'length, width, height are required numbers.'}, status=400)

    if length <= 0 or width <= 0 or height <= 0:
        return Response({'detail': 'length, width and height must be greater than 0.'}, status=400)

    if SavedParentBlock.objects.filter(label__iexact=label).exists():
        return Response({'detail': f'A saved parent block named "{label}" already exists.'}, status=400)

    try:
        block = SavedParentBlock.objects.create(
            label=label,
            length=length,
            width=width,
            height=height,
            created_by=request.user,
        )

        return Response({
            'success': True,
            'parent_block': _serialize_parent_block(block),
            'message': f"Parent block {label} saved."
        }, status=201)

    except Exception as e:
        return Response({'detail': str(e)}, status=500)


# ================================
# DELETE SAVED PARENT BLOCK
# ================================

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_parent_block(request, block_pk):
    """
    DELETE /api/parent-blocks/<pk>/delete/
    Hard delete — past optimizations store their own parent block dimensions
    on the OptimizationHistory row, so they are unaffected.
    """
    from .models import SavedParentBlock

    try:
        block = SavedParentBlock.objects.get(pk=block_pk)
        label = block.label
        block.delete()
        return Response({'success': True, 'message': f'Parent block {label} deleted.'})
    except SavedParentBlock.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=404)
    except Exception as e:
        return Response({'detail': str(e)}, status=500)

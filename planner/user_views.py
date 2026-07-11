"""
User management and custom auth views.
Superadmin-only user management endpoints.
"""
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken


# ================================
# CUSTOM LOGIN - returns role info
# ================================

@api_view(['POST'])
@permission_classes([AllowAny])
def custom_login(request):
    """
    POST /auth/login/
    Returns JWT tokens + user role info.
    """
    username = request.data.get('username', '').strip()
    password = request.data.get('password', '').strip()

    if not username or not password:
        return Response(
            {'detail': 'Username and password are required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    user = authenticate(username=username, password=password)
    if user is None:
        return Response(
            {'detail': 'Invalid credentials.'},
            status=status.HTTP_401_UNAUTHORIZED
        )

    if not user.is_active:
        return Response(
            {'detail': 'Account is disabled.'},
            status=status.HTTP_403_FORBIDDEN
        )

    refresh = RefreshToken.for_user(user)

    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_superuser': user.is_superuser,
            'is_staff': user.is_staff,
        }
    })


# ================================
# PERMISSION HELPER
# ================================

def is_superadmin(user):
    return user.is_authenticated and user.is_superuser


# ================================
# USER MANAGEMENT ENDPOINTS
# ================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_users(request):
    """
    GET /api/users/
    Superadmin only — list all users.
    """
    if not is_superadmin(request.user):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    users = User.objects.all().order_by('date_joined')
    data = [_serialize_user(u) for u in users]
    return Response({'success': True, 'users': data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_user(request):
    """
    POST /api/users/create/
    Superadmin only — create a new user.
    Body: { username, password, email, first_name, last_name, is_staff, is_superuser }
    """
    if not is_superadmin(request.user):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    data = request.data
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    email = data.get('email', '').strip()
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    is_staff = bool(data.get('is_staff', False))
    is_superuser = bool(data.get('is_superuser', False))

    if not username:
        return Response({'detail': 'Username is required.'}, status=status.HTTP_400_BAD_REQUEST)
    if not password or len(password) < 6:
        return Response({'detail': 'Password must be at least 6 characters.'}, status=status.HTTP_400_BAD_REQUEST)
    if User.objects.filter(username=username).exists():
        return Response({'detail': 'Username already exists.'}, status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(
        username=username,
        password=password,
        email=email,
        first_name=first_name,
        last_name=last_name,
    )
    user.is_staff = is_staff or is_superuser  # superuser implies staff
    user.is_superuser = is_superuser
    user.save()

    return Response({
        'success': True,
        'message': f'User "{username}" created successfully.',
        'user': _serialize_user(user)
    }, status=status.HTTP_201_CREATED)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_user(request, user_id):
    """
    PUT/PATCH /api/users/<id>/update/
    Superadmin only — update a user.
    """
    if not is_superadmin(request.user):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    data = request.data

    if 'email' in data:
        user.email = data['email'].strip()
    if 'first_name' in data:
        user.first_name = data['first_name'].strip()
    if 'last_name' in data:
        user.last_name = data['last_name'].strip()
    if 'is_staff' in data:
        user.is_staff = bool(data['is_staff'])
    if 'is_superuser' in data:
        user.is_superuser = bool(data['is_superuser'])
        if user.is_superuser:
            user.is_staff = True
    if 'is_active' in data:
        user.is_active = bool(data['is_active'])
    if 'password' in data and data['password']:
        pwd = data['password'].strip()
        if len(pwd) < 6:
            return Response({'detail': 'Password must be at least 6 characters.'}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(pwd)

    user.save()
    return Response({
        'success': True,
        'message': f'User "{user.username}" updated.',
        'user': _serialize_user(user)
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_user(request, user_id):
    """
    DELETE /api/users/<id>/delete/
    Superadmin only — delete a user (cannot delete yourself).
    """
    if not is_superadmin(request.user):
        return Response({'detail': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

    if request.user.id == user_id:
        return Response({'detail': 'You cannot delete your own account.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    username = user.username
    user.delete()
    return Response({'success': True, 'message': f'User "{username}" deleted.'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user_info(request):
    """
    GET /auth/me/
    Returns current user's profile + role.
    """
    return Response({
        'success': True,
        'user': _serialize_user(request.user)
    })


# ================================
# HELPER
# ================================

def _serialize_user(user):
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'is_active': user.is_active,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
        'date_joined': user.date_joined.isoformat(),
        'last_login': user.last_login.isoformat() if user.last_login else None,
    }


# ================================
# TOGGLE OPTIMIZATION EXECUTED STATUS
# ================================

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def toggle_executed(request, history_id):
    """
    PATCH /api/optimization-history/<id>/toggle-executed/
    Toggle or explicitly set the is_executed flag.
    Body (optional): { "is_executed": true }
    """
    try:
        from planner.models import OptimizationHistory
        # Superadmin or staff can toggle execution status of any user's logic
        if request.user.is_superuser or request.user.is_staff:
            history = OptimizationHistory.objects.get(id=history_id)
        else:
            history = OptimizationHistory.objects.get(id=history_id, user=request.user)

        # If explicit value provided use it, otherwise toggle
        if 'is_executed' in request.data:
            history.is_executed = bool(request.data['is_executed'])
        else:
            history.is_executed = not history.is_executed

        history.save(update_fields=['is_executed'])

        return Response({
            'success': True,
            'is_executed': history.is_executed,
            'message': f"Marked as {'executed' if history.is_executed else 'not executed'}."
        })
    except OptimizationHistory.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=404)
    except Exception as e:
        return Response({'detail': str(e)}, status=500)

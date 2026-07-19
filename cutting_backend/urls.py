"""
URL configuration for cutting_backend project.
"""
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenRefreshView
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from planner.user_views import (
    custom_login,
    current_user_info,
    list_users,
    create_user,
    update_user,
    delete_user,
    toggle_executed,
    set_label,
)
from planner.inventory_views import (
    list_inventory,
    add_to_inventory,
    remove_from_inventory,
)

urlpatterns = [
    # Admin
    path('secure-admin/', admin.site.urls),

    # Auth
    path("auth/login/", custom_login, name="jwt_login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="jwt_refresh"),
    path("auth/me/", current_user_info, name="current_user"),

    # User management (superadmin only)
    path("api/users/", list_users, name="list_users"),
    path("api/users/create/", create_user, name="create_user"),
    path("api/users/<int:user_id>/update/", update_user, name="update_user"),
    path("api/users/<int:user_id>/delete/", delete_user, name="delete_user"),
    path("api/optimization-history/<int:history_id>/toggle-executed/", toggle_executed, name="toggle_executed"),
    path("api/optimization-history/<int:history_id>/label/", set_label, name="set_label"),

    # Scrap Inventory (shared across all users)
    path("api/inventory/", list_inventory, name="list_inventory"),
    path("api/inventory/add/", add_to_inventory, name="add_to_inventory"),
    path("api/inventory/<int:scrap_pk>/remove/", remove_from_inventory, name="remove_from_inventory"),

    # API endpoints
    path('api/', include('planner.urls')),

    # API documentation (OpenAPI/Swagger)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # DRF browsable API auth
    path('api-auth/', include('rest_framework.urls')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# Customize admin site
admin.site.site_header = "Cutting Optimization Admin"
admin.site.site_title = "Cutting Optimization"
admin.site.index_title = "Welcome to Cutting Optimization Administration"

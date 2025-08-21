from django.urls import path
from . import views

app_name = 'operations'
urlpatterns = [
    # Operations management
    path('process/<str:serial_number>/', views.manufacturing_process, name='manufacturing_process'),
    path('summary/', views.summary_view, name='summary'),
    path('admin/', views.admin_panel, name='admin_panel'),
    
    # User management APIs
    path('api/users/', views.manage_users, name='api_manage_users'),
    path('api/users/<int:user_id>/', views.manage_user, name='api_manage_user'),
    
    # Operations management APIs
    path('api/operations/', views.manage_operations, name='api_manage_operations'),
    path('api/operations/<int:operation_id>/', views.manage_operation, name='api_manage_operation'),
    
    # Parts management APIs
    path('api/parts/', views.manage_parts, name='api_manage_parts'),
    path('api/parts/<int:part_id>/', views.manage_part, name='api_manage_part'),
    
    # Serial numbers management APIs
    path('api/serials/', views.manage_serials, name='api_manage_serials'),
    path('api/serials/<int:serial_id>/', views.manage_serial, name='api_manage_serial'),
]

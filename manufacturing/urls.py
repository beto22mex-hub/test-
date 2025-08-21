from django.urls import path
from . import views, views_operator, views_debug

app_name = 'manufacturing'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('generate-serial/', views.generate_serial, name='generate_serial'),
    path('manufacturing-process/<str:serial_number>/', views.manufacturing_process, name='manufacturing_process'),
    path('summary/', views.summary_view, name='summary'),
    path('admin-panel/', views.admin_panel, name='admin_panel'),
    path('statistics/', views.statistics_view, name='statistics'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Operator module URLs
    path('operator/', views_operator.operator_dashboard, name='operator_dashboard'),
    path('operator/operation/<int:process_record_id>/', views_operator.operation_detail, name='operation_detail'),
    path('operator/assign/', views_operator.assign_operation, name='assign_operation'),
    path('operator/complete/', views_operator.complete_operation, name='complete_operation'),
    path('operator/release/', views_operator.release_operation, name='release_operation'),
    path('operator/reassign/', views_operator.reassign_operation, name='reassign_operation'),
    
    # Debug URLs
    path('debug-profile/', views_debug.debug_user_profile, name='debug_profile'),
    path('create-profile/', views_debug.create_missing_profile, name='create_missing_profile'),
    
    # AJAX endpoints
    path('ajax/authorized-parts/', views.get_authorized_parts, name='ajax_authorized_parts'),
    path('ajax/validate-order/', views.validate_order_number, name='ajax_validate_order'),
    
    # API endpoints
    path('api/statistics/', views.api_statistics, name='api_statistics'),
    path('api/dashboard-data/', views.api_dashboard_data, name='api_dashboard_data'),
]

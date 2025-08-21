from django.urls import path
from . import views

app_name = 'operators'
urlpatterns = [
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Operator dashboard and operations
    path('', views.operator_dashboard, name='operator_dashboard'),
    path('operation/<int:process_record_id>/', views.operation_work_view, name='operation_work_view'),
    path('operation/<int:process_record_id>/detail/', views.operation_detail, name='operation_detail'),
    
    # API endpoints
    path('api/assign/', views.assign_operation, name='assign_operation'),
    path('api/complete/', views.complete_operation, name='complete_operation'),
    path('api/reject/', views.reject_serial_number, name='reject_serial_number'),
    path('api/release/', views.release_operation, name='release_operation'),
    path('api/reassign/', views.reassign_operation, name='reassign_operation'),
]

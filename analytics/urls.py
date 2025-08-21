from django.urls import path
from . import views

app_name = 'analytics'
urlpatterns = [
    # Statistics and dashboard
    path('', views.dashboard, name='dashboard'),
    path('statistics/', views.statistics_view, name='statistics_view'),
    
    # API endpoints
    path('api/statistics/', views.api_statistics, name='api_statistics'),
    path('api/dashboard/', views.api_dashboard_data, name='api_dashboard_data'),
    
    path('assign_operator/', views.assign_operator, name='assign_operator'),
    path('change_operator/', views.change_operator, name='change_operator'),
    path('start_process/', views.start_process, name='start_process'),
    path('complete_process/', views.complete_process, name='complete_process'),
    path('reject_process/', views.reject_process, name='reject_process'),
]

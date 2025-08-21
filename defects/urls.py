from django.urls import path
from . import views

app_name = 'defects'
urlpatterns = [
    # Defects management
    path('', views.defects_dashboard, name='defects_dashboard'),
    path('repairer/', views.repairer_dashboard, name='repairer_dashboard'),
    path('<int:defect_id>/', views.defect_detail, name='defect_detail'),
    
    # API endpoints
    path('api/assign/', views.assign_defect, name='assign_defect'),
    path('api/resolve/', views.resolve_defect, name='resolve_defect'),
]

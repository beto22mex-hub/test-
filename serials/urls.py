from django.urls import path
from . import views

app_name = 'serials'
urlpatterns = [
    # Serial number generation
    path('generate/', views.generate_serial, name='generate_serial'),
    
    path('csv-preview/', views.csv_preview, name='csv_preview'),
    path('download-csv/', views.download_csv, name='download_csv'),
    
    # API endpoints
    path('api/parts/', views.get_authorized_parts, name='get_authorized_parts'),
    path('api/validate-order/', views.validate_order_number, name='validate_order_number'),
    path('api/search/', views.search_serials, name='search_serials'),
]

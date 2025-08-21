from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views

router = DefaultRouter()
router.register(r'serial-numbers', api_views.SerialNumberViewSet)
router.register(r'operations', api_views.OperationViewSet)
router.register(r'authorized-parts', api_views.AuthorizedPartViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('generate-serial/', api_views.generate_serial_api, name='generate_serial_api'),
    path('process-operation/', api_views.process_operation_api, name='process_operation_api'),
    path('export-excel/', api_views.export_excel, name='export_excel'),
    path('export-pdf/', api_views.export_pdf, name='export_pdf'),
    path('statistics/', api_views.statistics_api, name='statistics_api'),
]

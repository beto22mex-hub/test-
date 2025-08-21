from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from .models import SerialNumber, AuthorizedPart
from .services import SerialNumberGenerator, SerialNumberValidator
from .forms import SerialGenerationForm
import json
import csv
from datetime import datetime


@login_required
def generate_serial(request):
    """Generate new serial number view with bulk generation and CSV export"""
    if request.method == 'POST':
        form = SerialGenerationForm(request.POST)
        if form.is_valid():
            try:
                quantity = form.cleaned_data['quantity']
                order_number = form.cleaned_data['order_number']
                authorized_part = form.cleaned_data['authorized_part']
                
                generated_serials = []
                for i in range(quantity):
                    serial = SerialNumberGenerator.generate_serial_number(
                        order_number=order_number,
                        part_number=authorized_part.part_number,
                        created_by=request.user
                    )
                    generated_serials.append(serial)
                
                request.session['generated_serials'] = [
                    {
                        'serial_number': serial.serial_number,
                        'part_number': serial.authorized_part.part_number,
                        'sku': serial.authorized_part.sku,
                        'order_number': serial.order_number
                    }
                    for serial in generated_serials
                ]
                
                messages.success(
                    request, 
                    f'{quantity} número{"s" if quantity > 1 else ""} de serie generado{"s" if quantity > 1 else ""} exitosamente para la orden {order_number}'
                )
                
                return redirect('serials:download_csv')
                
            except Exception as e:
                messages.error(request, f'Error al generar números de serie: {str(e)}')
    else:
        form = SerialGenerationForm()
    
    # Get authorized parts for autocomplete
    authorized_parts = AuthorizedPart.objects.filter(is_active=True).order_by('part_number')
    
    context = {
        'form': form,
        'authorized_parts': authorized_parts
    }
    
    return render(request, 'serials/generate_serial.html', context)


@login_required
@require_http_methods(["GET"])
def search_serials(request):
    """AJAX endpoint to search serial numbers for operations"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 3:
        return JsonResponse({'serials': []})
    
    serials = SerialNumber.objects.filter(
        Q(serial_number__icontains=query) |
        Q(order_number__icontains=query) |
        Q(authorized_part__part_number__icontains=query) |
        Q(authorized_part__sku__icontains=query)
    ).select_related('authorized_part').order_by('-created_at')[:10]
    
    data = []
    for serial in serials:
        data.append({
            'id': serial.id,
            'serial_number': serial.serial_number,
            'order_number': serial.order_number,
            'part_number': serial.authorized_part.part_number,
            'sku': serial.authorized_part.sku,
            'status': serial.get_status_display(),
            'completion_percentage': serial.completion_percentage,
            'current_operation': serial.current_operation.name if serial.current_operation else 'Completado'
        })
    
    return JsonResponse({'serials': data})


@login_required
@require_http_methods(["GET"])
def get_authorized_parts(request):
    """AJAX endpoint to get authorized parts for autocomplete"""
    query = request.GET.get('q', '')
    
    parts = AuthorizedPart.objects.filter(
        is_active=True,
        part_number__icontains=query
    ).order_by('part_number')[:10]
    
    data = [
        {
            'id': part.id,
            'part_number': part.part_number,
            'sku': part.sku,
            'description': part.description,
            'revision': part.revision
        }
        for part in parts
    ]
    
    return JsonResponse({'parts': data})


@login_required
@require_http_methods(["POST"])
def validate_order_number(request):
    """AJAX endpoint to validate order number"""
    data = json.loads(request.body)
    order_number = data.get('order_number', '')
    
    try:
        SerialNumberValidator.validate_order_number(order_number)
        has_duplicates = SerialNumberValidator.check_order_duplicates(order_number)
        
        return JsonResponse({
            'valid': True,
            'has_duplicates': has_duplicates,
            'message': 'Número de orden válido' if not has_duplicates else 'Este número de orden ya tiene números de serie asociados'
        })
    except Exception as e:
        return JsonResponse({
            'valid': False,
            'message': str(e)
        })


@login_required
def download_csv(request):
    """Download CSV with generated serial numbers"""
    generated_serials = request.session.get('generated_serials', [])
    
    if not generated_serials:
        messages.error(request, 'No hay números de serie para descargar')
        return redirect('serials:generate_serial')
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    response['Content-Disposition'] = f'attachment; filename="numeros_serie_{timestamp}.csv"'
    
    writer = csv.writer(response)
    # Write header
    writer.writerow(['PN', 'SKU', 'SERIAL'])
    
    # Write data
    for serial_data in generated_serials:
        writer.writerow([
            serial_data['part_number'],
            serial_data['sku'],
            serial_data['serial_number']
        ])
    
    # Clear session data after download
    del request.session['generated_serials']
    
    return response


@login_required
def csv_preview(request):
    """Preview page showing generated serials before download"""
    generated_serials = request.session.get('generated_serials', [])
    
    if not generated_serials:
        messages.error(request, 'No hay números de serie para mostrar')
        return redirect('serials:generate_serial')
    
    context = {
        'generated_serials': generated_serials,
        'total_count': len(generated_serials)
    }
    
    return render(request, 'serials/csv_preview.html', context)

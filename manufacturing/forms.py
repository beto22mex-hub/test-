from django import forms
from django.contrib.auth.models import User
from serials.models import AuthorizedPart, SerialNumber
from operations.models import Operation, ProcessRecord


class SerialGenerationForm(forms.Form):
    """Form for generating serial numbers"""
    
    order_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingrese el número de orden',
            'required': True
        }),
        label='Número de Orden'
    )
    
    authorized_part = forms.ModelChoiceField(
        queryset=AuthorizedPart.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'form-control',
            'required': True
        }),
        label='Componente Autorizado',
        empty_label='Seleccione un componente'
    )
    
    quantity = forms.IntegerField(
        min_value=1,
        max_value=100,
        initial=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '1',
            'max': '100'
        }),
        label='Cantidad',
        help_text='Número de series a generar (máximo 100)'
    )
    
    def clean_order_number(self):
        order_number = self.cleaned_data['order_number']
        
        # Basic validation
        if not order_number.strip():
            raise forms.ValidationError('El número de orden es requerido')
        
        # Check format (alphanumeric, hyphens, underscores)
        import re
        if not re.match(r'^[A-Za-z0-9\-_]+$', order_number):
            raise forms.ValidationError(
                'El número de orden solo puede contener letras, números, guiones y guiones bajos'
            )
        
        return order_number.strip().upper()


class LoginForm(forms.Form):
    """Login form"""
    
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Usuario',
            'required': True
        }),
        label='Usuario'
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Contraseña',
            'required': True
        }),
        label='Contraseña'
    )


class ProcessOperationForm(forms.Form):
    """Form for processing operations"""
    
    operation_id = forms.IntegerField(widget=forms.HiddenInput())
    serial_number = forms.CharField(max_length=10, widget=forms.HiddenInput())
    
    status = forms.ChoiceField(
        choices=[
            ('IN_PROGRESS', 'Iniciar Proceso'),
            ('APPROVED', 'Aprobar'),
            ('REJECTED', 'Rechazar')
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Acción'
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Notas adicionales (opcional)'
        }),
        label='Notas'
    )
    
    quality_check_passed = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Control de calidad aprobado'
    )


class SerialNumberEditForm(forms.ModelForm):
    """Form for editing serial numbers"""
    
    class Meta:
        model = SerialNumber
        fields = ['order_number', 'authorized_part', 'status']
        widgets = {
            'order_number': forms.TextInput(attrs={'class': 'form-control'}),
            'authorized_part': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'order_number': 'Número de Orden',
            'authorized_part': 'Componente Autorizado',
            'status': 'Estado'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['authorized_part'].queryset = AuthorizedPart.objects.filter(is_active=True)


class AuthorizedPartForm(forms.ModelForm):
    """Form for managing authorized parts"""
    
    class Meta:
        model = AuthorizedPart
        fields = ['part_number', 'description', 'revision', 'is_active']
        widgets = {
            'part_number': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'revision': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'part_number': 'Número de Parte',
            'description': 'Descripción',
            'revision': 'Revisión',
            'is_active': 'Activo'
        }


class OperationForm(forms.ModelForm):
    """Form for managing operations"""
    
    class Meta:
        model = Operation
        fields = ['name', 'description', 'sequence_number', 'estimated_time_minutes', 'requires_approval', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'sequence_number': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '10'}),
            'estimated_time_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'requires_approval': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': 'Nombre',
            'description': 'Descripción',
            'sequence_number': 'Número de Secuencia',
            'estimated_time_minutes': 'Tiempo Estimado (minutos)',
            'requires_approval': 'Requiere Aprobación',
            'is_active': 'Activo'
        }

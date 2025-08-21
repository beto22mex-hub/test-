from django import forms
from .models import AuthorizedPart


class SerialGenerationForm(forms.Form):
    order_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingresa el número de orden'
        }),
        label='Número de Orden'
    )
    
    authorized_part = forms.ModelChoiceField(
        queryset=AuthorizedPart.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        label='Componente Autorizado',
        empty_label='Selecciona un componente'
    )
    
    quantity = forms.IntegerField(
        min_value=1,
        max_value=200,
        initial=1,
        widget=forms.Select(
            choices=[(i, f'{i} número{"s" if i > 1 else ""} de serie') for i in range(1, 201)],
            attrs={'class': 'form-select'}
        ),
        label='Cantidad a Generar'
    )

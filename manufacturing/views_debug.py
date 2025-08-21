from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from operators.models import UserProfile

@login_required
def debug_user_profile(request):
    """Vista de debug para verificar el perfil del usuario"""
    user = request.user
    has_profile = hasattr(user, 'userprofile')
    
    context = {
        'user': user,
        'has_profile': has_profile,
        'profile': user.userprofile if has_profile else None,
        'is_superuser': user.is_superuser,
        'is_staff': user.is_staff,
    }
    
    return render(request, 'manufacturing/debug_profile.html', context)

@login_required
def create_missing_profile(request):
    """Crear perfil faltante para el usuario actual"""
    if request.method == 'POST':
        user = request.user
        
        if hasattr(user, 'userprofile'):
            messages.info(request, 'El usuario ya tiene un perfil asignado')
            return redirect('manufacturing:debug_profile')
        
        # Crear perfil básico
        role = 'ADMIN' if user.is_superuser else 'OPERATOR'
        
        UserProfile.objects.create(
            user=user,
            role=role,
            employee_id=f'USR{user.id:03d}',
            can_approve_operations=(role == 'ADMIN'),
            can_generate_serials=True,
            can_view_statistics=(role == 'ADMIN'),
            can_manage_users=(role == 'ADMIN')
        )
        
        messages.success(request, f'Perfil creado exitosamente con rol {role}')
        return redirect('manufacturing:debug_profile')
    
    return redirect('manufacturing:debug_profile')

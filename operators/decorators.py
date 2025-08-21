from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps


def operator_required(view_func):
    """Decorator to require OPERATOR, SUPERVISOR, or ADMIN role"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('operators:login')
        
        if not hasattr(request.user, 'userprofile'):
            messages.error(request, 'Tu cuenta no tiene un perfil asignado. Contacta al administrador.')
            return redirect('operators:login')
        
        user_role = request.user.userprofile.role
        if user_role not in ['OPERATOR', 'SUPERVISOR', 'ADMIN']:
            messages.error(request, 'No tienes permisos para acceder a esta sección.')
            return redirect('statistics:dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def supervisor_or_admin_required(view_func):
    """Decorator to require SUPERVISOR or ADMIN role"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('operators:login')
        
        if not hasattr(request.user, 'userprofile'):
            messages.error(request, 'Tu cuenta no tiene un perfil asignado. Contacta al administrador.')
            return redirect('operators:login')
        
        user_role = request.user.userprofile.role
        if user_role not in ['SUPERVISOR', 'ADMIN']:
            messages.error(request, 'No tienes permisos para acceder a esta sección.')
            return redirect('statistics:dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper

from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from functools import wraps


def operator_required(view_func):
    """Decorador que requiere que el usuario sea un operador, supervisor o administrador"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        
        if not hasattr(request.user, 'userprofile'):
            raise PermissionDenied("Usuario sin perfil asignado")
        
        if request.user.userprofile.role not in ['OPERATOR', 'SUPERVISOR', 'ADMIN']:
            raise PermissionDenied("Acceso restringido a operadores, supervisores y administradores")
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view


def supervisor_or_admin_required(view_func):
    """Decorador que requiere que el usuario sea supervisor o admin"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())
        
        if not hasattr(request.user, 'userprofile'):
            raise PermissionDenied("Usuario sin perfil asignado")
        
        if request.user.userprofile.role not in ['SUPERVISOR', 'ADMIN']:
            raise PermissionDenied("Acceso restringido a supervisores y administradores")
        
        return view_func(request, *args, **kwargs)
    
    return _wrapped_view

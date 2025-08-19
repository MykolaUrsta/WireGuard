from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.shortcuts import redirect

def health_check(request):
    return HttpResponse("OK", content_type="text/plain")

def redirect_to_login(request):
    if request.user.is_authenticated:
        return redirect('accounts:vpn_overview')
    return redirect('accounts:login')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('wireguard/', include('wireguard_management.urls', namespace='wireguard')),
    path('locations/', include('locations.urls')),
    # NOTE: audit_logging UI templates are not present; disable routes for now.
    # path('logs/', include('audit_logging.urls')),
    path('health/', health_check, name='health'),
    path('', redirect_to_login),  # Redirect to login or dashboard
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

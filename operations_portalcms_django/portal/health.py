from django.conf import settings
from django.db import connection
from django.db.utils import Error
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@never_cache
@require_GET
def readiness(request):
    """Report the deployed version and verify the default database is usable."""
    payload = {
        'status': 'ok',
        'version': str(getattr(settings, 'APP_VERSION', 'unknown')),
    }

    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Error:
        payload['status'] = 'unavailable'
        return JsonResponse(payload, status=503)

    return JsonResponse(payload)

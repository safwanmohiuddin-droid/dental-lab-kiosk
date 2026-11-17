import logging

from django.db import DatabaseError, connection
from django.http import JsonResponse

log = logging.getLogger(__name__)


def healthz(request):
    """Liveness + database check for monitors and the deploy smoke test."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        log.exception("healthz: database unavailable")
        return JsonResponse({"status": "error", "database": "unavailable"}, status=503)
    return JsonResponse({"status": "ok", "database": "ok"})

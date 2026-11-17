from django.contrib import admin
from django.urls import include, path

from kiosk.views import PersonalLoginView
from ops.views import healthz

urlpatterns = [
    path("admin/", admin.site.urls),
    # Phase 4: kiosk sign-in
    path("k/", include("kiosk.urls")),
    path("accounts/login/", PersonalLoginView.as_view(), name="login"),
    # Phase 7: reports
    path("r/", include("reports.urls")),
    # Phase 9
    path("healthz", healthz, name="healthz"),
]

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from kiosk.views import PersonalLoginView
from ops.views import healthz

urlpatterns = [
    # Most people opening the site are technicians; owners use /r/ and /admin/.
    path("", RedirectView.as_view(pattern_name="kiosk:start"), name="home"),
    path("admin/", admin.site.urls),
    # Phase 4: kiosk sign-in
    path("k/", include("kiosk.urls")),
    path("accounts/login/", PersonalLoginView.as_view(), name="login"),
    # Phase 7: reports
    path("r/", include("reports.urls")),
    # Phase 9
    path("healthz", healthz, name="healthz"),
]

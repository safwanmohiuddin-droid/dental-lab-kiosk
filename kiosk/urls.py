from django.urls import path

from . import views

app_name = "kiosk"

urlpatterns = [
    path("", views.start, name="start"),
    path("pin/<int:employee_id>/", views.pin, name="pin"),
    path("home/", views.home, name="home"),
    path("sign-out/", views.sign_out, name="sign_out"),
    path("register/<str:token>/", views.register, name="register"),
]

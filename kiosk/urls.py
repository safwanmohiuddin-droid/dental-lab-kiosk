from django.urls import path

from . import views

app_name = "kiosk"

urlpatterns = [
    path("", views.start, name="start"),
    path("pin/<int:employee_id>/", views.pin, name="pin"),
    path("home/", views.home, name="home"),
    path("issue/", views.issue, name="issue"),
    path("returns/", views.returns, name="returns"),
    path("returns/<int:move_id>/", views.return_move, name="return_move"),
    path("done/", views.done, name="done"),
    path("sign-out/", views.sign_out, name="sign_out"),
    path("register/<str:token>/", views.register, name="register"),
]

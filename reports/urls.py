from django.urls import path

from . import views

app_name = "reports"
urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("materials/", views.materials, name="materials"),
    path("people/", views.people, name="people"),
]

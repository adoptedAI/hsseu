from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('map/', views.map_view, name='map'),
    path('inspection-map/', views.inspection_map_view, name='inspection_map'),
] 
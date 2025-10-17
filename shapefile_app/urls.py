from django.urls import path
from . import views
#from shapefile_app import views

urlpatterns = [
    path('', views.map_view, name='map_view'),
    path('upload/', views.upload_shapefile, name='upload_shapefile'),
    path('shapefile/<int:shapefile_id>/geojson/', views.get_shapefile_geojson, name='get_shapefile_geojson'),
    path('debug/<int:shapefile_id>/', views.debug_shapefile, name='debug_shapefile'),  # Add this line
]

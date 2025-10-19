from django.urls import path
from . import views
#from .views import MapView, ShapefileUploadView, ShapefileGeoJSONView, DebugShapefileView, ShapefileProcessedGeoJSONView, MergePolygonsView

urlpatterns = [
    path('', views.MapView.as_view(), name='map_view'),
    path('upload/', views.ShapefileUploadView.as_view(), name='upload_shapefile'),
    path('shapefile/<int:pk>/geojson/', views.ShapefileGeoJSONView.as_view(), name='get_shapefile_geojson'),
    path('shapefile/<int:pk>/geojson/processed/', views.ShapefileProcessedGeoJSONView.as_view(), name='get_shapefile_geojson_processed'),
    path('shapefile/<int:pk>/merge/', views.MergePolygonsView.as_view(), name='merge_polygons'),
    path('debug/<int:pk>/', views.DebugShapefileView.as_view(), name='debug_shapefile'),
]

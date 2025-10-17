from django.urls import path
#from .views import MapView, ShapefileUploadView, ShapefileGeoJSONView, DebugShapefileView
from shapefile_app.views import (
    MapView,
    ShapefileUploadView,
    ShapefileGeoJSONView,
    DebugShapefileView,
    ShapefileProcessedGeoJSONView,
)

urlpatterns = [
    path('', MapView.as_view(), name='map_view'),
    path('upload/', ShapefileUploadView.as_view(), name='upload_shapefile'),
    path('shapefile/<int:pk>/geojson/', ShapefileGeoJSONView.as_view(), name='get_shapefile_geojson'),
    path('shapefile/<int:pk>/geojson/processed/', ShapefileProcessedGeoJSONView.as_view(), name='get_shapefile_geojson_processed'),
    path('debug/<int:pk>/', DebugShapefileView.as_view(), name='debug_shapefile'),
]

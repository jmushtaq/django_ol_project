from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView
from .forms import ShapefileUploadForm
from .models import Shapefile
import json

class MapView(ListView):
    model = Shapefile
    template_name = 'shapefile_app/map.html'
    context_object_name = 'shapefiles'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add any additional context if needed
        return context

class ShapefileUploadView(CreateView):
    model = Shapefile
    form_class = ShapefileUploadForm
    template_name = 'shapefile_app/upload.html'
    success_url = reverse_lazy('map_view')

    def form_valid(self, form):
        try:
            response = super().form_valid(form)
            # Add zoom parameter to success URL
            redirect_url = f"{self.success_url}?zoom_to={self.object.id}"
            return redirect(redirect_url)
        except Exception as e:
            form.add_error(None, f'Error saving shapefile: {str(e)}')
            return self.form_invalid(form)

class ShapefileGeoJSONView(DetailView):
    model = Shapefile

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return JsonResponse(self.object.get_geojson_feature_collection())

class ShapefileProcessedGeoJSONView(DetailView):
    model = Shapefile

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        processed_data = self.object.get_processed_geojson_feature_collection()
        if processed_data:
            return JsonResponse(processed_data)
        else:
            return JsonResponse({'error': 'No processed data available'}, status=404)

class DebugShapefileView(DetailView):
    model = Shapefile
    template_name = 'shapefile_app/debug.html'
    context_object_name = 'shapefile'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        shapefile = self.object
        geojson_data = shapefile.get_geojson_feature_collection()

        # Calculate bounds for debugging
        features = geojson_data.get('features', [])
        coords = []
        for feature in features:
            geometry = feature.get('geometry', {})
            if geometry.get('type') == 'Point':
                coords.extend([geometry['coordinates']])
            elif geometry.get('type') in ['LineString', 'MultiLineString']:
                for coord_set in geometry['coordinates']:
                    if isinstance(coord_set[0], (int, float)):
                        coords.extend([coord_set])
                    else:
                        coords.extend(coord_set)
            elif geometry.get('type') in ['Polygon', 'MultiPolygon']:
                for polygon in geometry['coordinates']:
                    for ring in polygon:
                        coords.extend(ring)

        context.update({
            'feature_count': len(features),
    #        'bounds': {
    #            'min_lon': min([c[0] for c in coords]) if coords else 'N/A',
    #            'max_lon': max([c[0] for c in coords]) if coords else 'N/A',
    #            'min_lat': min([c[1] for c in coords]) if coords else 'N/A',
    #            'max_lat': max([c[1] for c in coords]) if coords else 'N/A',
    #        },
            #'geojson_sample': json.dumps(geojson_data, indent=2)[:1000] + '...' if len(json.dumps(geojson_data)) > 1000 else json.dumps(geojson_data, indent=2)
            'geojson_sample': json.dumps(geojson_data, indent=2)
        })
        return context

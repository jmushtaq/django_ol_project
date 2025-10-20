from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['shapefiles_json'] = json.dumps(list(Shapefile.objects.values('id', 'name')))
        return context

@method_decorator(csrf_exempt, name='dispatch')
class MergePolygonsView(View):
    def get(self, request, pk):
        return self._handle_merge_request(request, pk)

    def post(self, request, pk):
        return self._handle_merge_request(request, pk)

    def _handle_merge_request(self, request, pk):
        try:
            shapefile = Shapefile.objects.get(pk=pk)
            selected_feature_ids = []

            # Try GET parameters first
            ids_param = request.GET.get('ids', '')
            if ids_param:
                try:
                    selected_feature_ids = json.loads(ids_param)
                    if not isinstance(selected_feature_ids, list):
                        selected_feature_ids = [selected_feature_ids]
                except json.JSONDecodeError:
                    # Handle comma-separated list format
                    selected_feature_ids = [id.strip() for id in ids_param.split(',') if id.strip()]
            else:
                # Try POST body
                try:
                    data = json.loads(request.body)
                    selected_feature_ids = data.get('selected_features', [])
                except (json.JSONDecodeError, AttributeError):
                    pass

            print(f"Merge request for shapefile {pk}, features: {selected_feature_ids}")

            if not selected_feature_ids:
                return JsonResponse({
                    'success': False,
                    'message': 'No polygon IDs provided. Use ?ids=[1,2,3] or POST with selected_features'
                }, status=400)

            import ipdb; ipdb.set_trace()
            success, message = shapefile.merge_selected_polygons(selected_feature_ids)

            return JsonResponse({
                'success': success,
                'message': message,
                'has_processed_data': shapefile.geojson_data_processed is not None
            })

        except Shapefile.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Shapefile not found'}, status=404)
        except Exception as e:
            print(f"Merge error: {e}")
            return JsonResponse({'success': False, 'message': str(e)}, status=500)

##@method_decorator(csrf_exempt, name='dispatch')
#class MergePolygonsView(View):
#    def get(self, request, *args, **kwargs):
#        # Handle GET requests: display the form
#        import ipdb; ipdb.set_trace()
#        return render(request, self.template_name)
#
#    #def post(self, request, pk):
#    def post(self, request, *args, **kwargs):
#        import ipdb; ipdb.set_trace()
#        try:
#            shapefile = Shapefile.objects.get(pk=pk)
#            data = json.loads(request.body)
#            selected_feature_ids = data.get('selected_features', [])
#
#            print(f"Merge request for shapefile {pk}, features: {selected_feature_ids}")  # Debug
#
#            success, message = shapefile.merge_selected_polygons(selected_feature_ids)
#
#            return JsonResponse({
#                'success': success,
#                'message': message,
#                'has_processed_data': shapefile.geojson_data_processed is not None
#            })
#
#        except Shapefile.DoesNotExist:
#            return JsonResponse({'success': False, 'message': 'Shapefile not found'}, status=404)
#        except Exception as e:
#            print(f"Merge error: {e}")  # Debug
#            return JsonResponse({'success': False, 'message': str(e)}, status=500)


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

@method_decorator(csrf_exempt, name='dispatch')
class CutPolygonView(View):
    def post(self, request, pk):
        try:
            shapefile = Shapefile.objects.get(pk=pk)
            data = json.loads(request.body)
            feature_id = data.get('feature_id')
            cut_line = data.get('cut_line', [])

            print(f"Cut request for shapefile {pk}, feature {feature_id}")

            success, message = shapefile.cut_polygon(feature_id, cut_line)

            return JsonResponse({
                'success': success,
                'message': message,
                'has_processed_data': shapefile.geojson_data_processed is not None
            })

        except Shapefile.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Shapefile not found'}, status=404)
        except Exception as e:
            print(f"Cut error: {e}")
            return JsonResponse({'success': False, 'message': str(e)}, status=500)

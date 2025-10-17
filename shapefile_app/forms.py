from django import forms
from .models import Shapefile
import os
from django.core.files.uploadedfile import InMemoryUploadedFile
import zipfile
import tempfile
from osgeo import ogr
import json

import logging
logger = logging.getLogger(__name__)


class ShapefileUploadForm(forms.ModelForm):
    shapefile_zip = forms.FileField(
        label='Shapefile ZIP',
        help_text='Upload a ZIP file containing .shp, .shx, .dbf, and .prj files'
    )

    class Meta:
        model = Shapefile
        fields = ['name']

    def clean_shapefile_zip(self):
        zip_file = self.cleaned_data['shapefile_zip']
        if not zip_file.name.endswith('.zip'):
            raise forms.ValidationError('Please upload a ZIP file')
        return zip_file

    def clean(self):
        cleaned_data = super().clean()
        zip_file = cleaned_data.get('shapefile_zip')

        if zip_file:
            try:
                # Convert shapefile early to validate
                geojson_data = self.convert_shapefile_to_geojson(zip_file)
                # Store the converted data for use in save method
                self.geojson_data = geojson_data
            except Exception as e:
                raise forms.ValidationError(f'Shapefile conversion error: {str(e)}')

        return cleaned_data

    def save(self, commit=True):
        # Delete previous uploads before saving new one
        Shapefile.delete_previous_uploads()

        instance = super().save(commit=False)
        zip_file = self.cleaned_data['shapefile_zip']

        try:
            # Extract and convert shapefile to GeoJSON
            geojson_data = self.convert_shapefile_to_geojson(zip_file)
            instance.geojson_data = geojson_data

            if commit:
                instance.save()
            return instance
        except Exception as e:
            raise forms.ValidationError(f'Error converting shapefile: {str(e)}')

    def convert_shapefile_to_geojson(self, zip_file):
        """Convert uploaded shapefile ZIP to GeoJSON with proper CRS handling"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extract ZIP file
            try:
                with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
            except zipfile.BadZipFile:
                raise forms.ValidationError('Invalid ZIP file')

            # Find .shp file
            shp_file = None
            for file in os.listdir(temp_dir):
                if file.endswith('.shp'):
                    shp_file = os.path.join(temp_dir, file)
                    break

            if not shp_file:
                raise forms.ValidationError('No .shp file found in the ZIP archive')

            # Convert to GeoJSON using GDAL
            try:
                driver = ogr.GetDriverByName('ESRI Shapefile')
                data_source = driver.Open(shp_file, 0)

                if data_source is None:
                    raise forms.ValidationError('Could not open shapefile. Make sure all required files (.shp, .shx, .dbf) are present.')

                layer = data_source.GetLayer()
                feature_count = layer.GetFeatureCount()

                if feature_count == 0:
                    raise forms.ValidationError('Shapefile contains no features')

                # Get spatial reference from shapefile
                spatial_ref = layer.GetSpatialRef()
                coord_transform = None

                if spatial_ref:
                    # Transform to WGS84 (EPSG:4326) if needed
                    wgs84_ref = ogr.osr.SpatialReference()
                    wgs84_ref.ImportFromEPSG(4326)

                    if not spatial_ref.IsSame(wgs84_ref):
                        coord_transform = ogr.osr.CoordinateTransformation(spatial_ref, wgs84_ref)

                # Create GeoJSON structure
                features = []
                for feature in layer:
                    geom = feature.GetGeometryRef()
                    if geom:
                        # Transform geometry to WGS84 if needed
                        if coord_transform:
                            geom.Transform(coord_transform)

                        geojson_geom = json.loads(geom.ExportToJson())
                        properties = {}
                        for i in range(feature.GetFieldCount()):
                            field_name = feature.GetFieldDefnRef(i).GetName()
                            properties[field_name] = feature.GetField(i)

                        features.append({
                            'type': 'Feature',
                            'geometry': geojson_geom,
                            'properties': properties
                        })

                data_source = None

                if not features:
                    raise forms.ValidationError('No valid geometries found in shapefile')

                return {
                    'type': 'FeatureCollection',
                    'crs': {
                        'type': 'name',
                        'properties': {
                            'name': 'EPSG:4326'
                        }
                    },
                    'features': features
                }

            except Exception as e:
                raise forms.ValidationError(f'GDAL error: {str(e)}')

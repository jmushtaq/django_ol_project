from django.db import models
import json

class Shapefile(models.Model):
    name = models.CharField(max_length=255)
    geojson_data = models.JSONField(default=dict)
    geojson_data_processed = models.JSONField('Source Polygon intersected with hist and split (multi) polygon geometry', blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def get_geojson_feature_collection(self):
        """Return GeoJSON data as a FeatureCollection"""
        if isinstance(self.geojson_data, str):
            return json.loads(self.geojson_data)
        return self.geojson_data

    def get_processed_geojson_feature_collection(self):
        """Return processed GeoJSON data as a FeatureCollection"""
        if not self.geojson_data_processed:
            return None
        if isinstance(self.geojson_data_processed, str):
            return json.loads(self.geojson_data_processed)
        return self.geojson_data_processed

    @classmethod
    def delete_previous_uploads(cls):
        """Delete all previously uploaded shapefiles"""
        cls.objects.all().delete()


from django.db import models
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
from django.utils import timezone
import json

import geopandas as gpd
from shapely.geometry import shape, Polygon, MultiPolygon
from shapely.ops import unary_union



class Shapefile(models.Model):
    name = models.CharField(max_length=255)
    geojson_data = models.JSONField(default=dict)
    geojson_data_processed = models.JSONField('Source Polygon intersected with hist and split (multi) polygon geometry', blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def gdf_shp(self, crs='epsg:28350'):
        return  gpd.read_file(json.dumps(self.geojson_data)).to_crs(crs)

    def gdf_processed(self, crs='epsg:28350'):
        return  gpd.read_file(json.dumps(self.geojson_data_processed)).to_crs(crs)

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

    def merge_selected_polygons(self, selected_feature_ids):
        """Merge selected polygons from processed data using GeoPandas"""
        try:
            source_data = self.get_processed_geojson_feature_collection()
            source_field = 'processed'

            if not source_data or 'features' not in source_data:
                return False, "No source data available for merging"

            # Convert to GeoDataFrame
            gdf = gpd.GeoDataFrame.from_features(source_data['features'])

            # Filter selected features
            selected_indices = [int(idx) for idx in selected_feature_ids if idx.isdigit()]

            if len(selected_indices) < 2:
                return False, "Please select at least 2 polygons to merge"

            # Check if all selected indices are valid
            valid_indices = [idx for idx in selected_indices if idx < len(gdf)]
            if len(valid_indices) < 2:
                return False, "Invalid polygon indices selected"

            selected_gdf = gdf.iloc[valid_indices].copy()
            remaining_gdf = gdf.drop(valid_indices)

            # Check if polygons are adjacent/touching using GeoPandas
            if not self._are_polygons_adjacent_geopandas(selected_gdf):
                return False, "Selected polygons are not adjacent/touching"

            # Merge polygons using GeoPandas
            merged_geometry = self._merge_polygons_geopandas(selected_gdf)

            if merged_geometry is None or merged_geometry.is_empty:
                return False, "Failed to merge polygons - resulting geometry is empty"

            # Create new feature for merged polygon
            merged_feature = {
                'type': 'Feature',
                'geometry': merged_geometry.__geo_interface__,
                'properties': {
                    'name': 'Merged Polygon',
                    'original_features': len(selected_gdf),
                    'merged_features': selected_feature_ids,
                    'source_layer': source_field,
                    'merged_at': timezone.now().isoformat(),
                    'area_sq_km': round(merged_geometry.area * 10000, 2)  # Approximate area in sq km
                }
            }

            # Convert remaining features back to GeoJSON features
            remaining_features = []
            for idx, row in remaining_gdf.iterrows():
                feature = {
                    'type': 'Feature',
                    'geometry': row.geometry.__geo_interface__,
                    'properties': row.drop('geometry').to_dict()
                }
                remaining_features.append(feature)

            # Add the merged feature
            remaining_features.append(merged_feature)

            # Create new processed data
            processed_data = {
                'type': 'FeatureCollection',
                'features': remaining_features
            }

            # Save to processed field
            self.geojson_data_processed = processed_data
            self.save()

            return True, f"Successfully merged polygons {selected_feature_ids} (Area: {merged_feature['properties']['area_sq_km']} sq km)"

        except Exception as e:
            print(f"GeoPandas merge error: {e}")
            # Fallback to GEOS method if GeoPandas fails
            return self._merge_selected_polygons_fallback(selected_feature_ids)

    def _are_polygons_adjacent_geopandas(self, gdf):
        """Check if polygons are adjacent/touching using GeoPandas spatial operations"""
        if len(gdf) < 2:
            return False

        # Create a union of all geometries to check connectivity
        combined_geometry = gdf.unary_union

        # If the union is a single polygon (not multi), they are connected
        if isinstance(combined_geometry, (Polygon)):
            return True
        elif isinstance(combined_geometry, MultiPolygon):
            # For MultiPolygon, check if it's actually connected (single component)
            # by comparing with the convex hull or buffer method
            individual_areas = gdf.geometry.area.sum()
            combined_area = combined_geometry.area

            # If areas are similar, they are likely connected
            area_ratio = combined_area / individual_areas
            return area_ratio <= 1.1  # Allow 10% tolerance for gaps/overlaps

        return False

    def _merge_polygons_geopandas(self, gdf):
        """Merge multiple polygons into one using GeoPandas"""
        try:
            # Use unary_union for robust merging
            merged_geometry = gdf.unary_union

            # Ensure we have a valid geometry
            if merged_geometry.is_valid:
                return merged_geometry
            else:
                # Try to fix invalid geometry
                merged_geometry = merged_geometry.buffer(0)
                if merged_geometry.is_valid:
                    return merged_geometry
                else:
                    return None

        except Exception as e:
            print(f"GeoPandas merge error: {e}")
            return None


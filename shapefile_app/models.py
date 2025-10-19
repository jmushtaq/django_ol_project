from django.db import models
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
from django.utils import timezone
import json

import geopandas as gpd


try:
    from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
    GEOS_AVAILABLE = True
except ImportError:
    GEOS_AVAILABLE = False
    print("GEOS not available - polygon merging disabled")


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
        """Merge selected polygons from processed data and update processed data"""
        if not GEOS_AVAILABLE:
            return False, "GEOS library not available - polygon merging disabled"

        try:
            # Use processed data as source, fallback to original if no processed data exists
            if self.geojson_data_processed:
                source_data = self.get_processed_geojson_feature_collection()
                source_field = 'processed'
            else:
                source_data = self.get_geojson_feature_collection()
                source_field = 'original'

            features = source_data.get('features', [])

            # Filter selected features
            selected_features = []
            other_features = []

            for i, feature in enumerate(features):
                if str(i) in selected_feature_ids:
                    selected_features.append(feature)
                else:
                    other_features.append(feature)

            if len(selected_features) < 2:
                return False, "Please select at least 2 polygons to merge"

            # Convert selected features to GEOS geometries and check adjacency
            geos_polygons = []
            for feature in selected_features:
                geom = feature.get('geometry')
                if geom and geom.get('type') in ['Polygon', 'MultiPolygon']:
                    geos_geom = GEOSGeometry(json.dumps(geom))
                    if isinstance(geos_geom, Polygon):
                        geos_polygons.append(geos_geom)
                    elif isinstance(geos_geom, MultiPolygon):
                        geos_polygons.extend(list(geos_geom))

            if len(geos_polygons) < 2:
                return False, "No valid polygons found in selection"

            # Check if polygons are adjacent/touching
            if not self._are_polygons_adjacent(geos_polygons):
                return False, "Selected polygons are not adjacent/touching"

            # Merge polygons
            merged_geometry = self._merge_polygons(geos_polygons)

            if not merged_geometry:
                return False, "Failed to merge polygons"

            # Create new feature collection with merged polygon
            merged_feature = {
                'type': 'Feature',
                'geometry': json.loads(merged_geometry.geojson),
                'properties': {
                    'name': 'Merged Polygon',
                    'original_features': len(selected_features),
                    'merged_features': selected_feature_ids,
                    'source_layer': source_field,
                    'merged_at': timezone.now().isoformat()
                }
            }

            # Create new feature collection
            new_features = other_features + [merged_feature]

            processed_data = {
                'type': 'FeatureCollection',
                'features': new_features
            }

            # Save to processed field (always update processed data)
            self.geojson_data_processed = processed_data
            self.save()

            return True, f"Successfully merged polygons {selected_feature_ids}"

        except Exception as e:
            return False, f"Error merging polygons: {str(e)}"

    def _are_polygons_adjacent(self, polygons):
        """Check if polygons are adjacent/touching each other"""
        if len(polygons) < 2:
            return False

        # Create a graph to track connectivity
        connected_components = []

        for i, poly1 in enumerate(polygons):
            connected_to = None
            # Find if this polygon connects to any existing component
            for j, component in enumerate(connected_components):
                for poly_idx in component:
                    poly2 = polygons[poly_idx]
                    if (poly1.touches(poly2) or
                        poly1.intersects(poly2) or
                        poly1.overlaps(poly2) or
                        poly1.intersection(poly2).area > 0):
                        connected_to = j
                        break
                if connected_to is not None:
                    break

            if connected_to is not None:
                connected_components[connected_to].append(i)
            else:
                # Start new component
                connected_components.append([i])

        # Merge connected components
        merged = True
        while merged and len(connected_components) > 1:
            merged = False
            for i in range(len(connected_components)):
                for j in range(i + 1, len(connected_components)):
                    component1 = connected_components[i]
                    component2 = connected_components[j]
                    # Check if any polygon in component1 touches any in component2
                    for idx1 in component1:
                        for idx2 in component2:
                            poly1 = polygons[idx1]
                            poly2 = polygons[idx2]
                            if (poly1.touches(poly2) or
                                poly1.intersects(poly2) or
                                poly1.overlaps(poly2) or
                                poly1.intersection(poly2).area > 0):
                                connected_components[i].extend(connected_components[j])
                                connected_components.pop(j)
                                merged = True
                                break
                        if merged:
                            break
                    if merged:
                        break
                if merged:
                    break

        # All polygons are connected if there's only one component
        return len(connected_components) == 1

    def _merge_polygons(self, polygons):
        """Merge multiple polygons into one"""
        try:
            # Start with first polygon
            merged = polygons[0]

            # Union with remaining polygons
            for polygon in polygons[1:]:
                merged = merged.union(polygon)

            return merged
        except Exception as e:
            print(f"Merge error: {e}")
            return None

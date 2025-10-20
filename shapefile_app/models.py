import math
from django.conf import settings
from django.db import models
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon
from django.utils import timezone
import json

import pandas as pd
import geopandas as gpd
from shapely.geometry import shape, Polygon, MultiPolygon, LineString
from shapely.ops import unary_union

from shapefile_app.utils.plot_utils import plot_gdf, plot_multi, plot_overlay

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
            #return self._merge_selected_polygons_fallback(selected_feature_ids)

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

    def cut_polygon(self, feature_id, cut_line):
        """Cut a polygon using a line segment - with better error handling"""
        try:
            import geopandas as gpd
            from shapely.geometry import Polygon, LineString
            from shapely.ops import split
            import json

            source_data = self.get_processed_geojson_feature_collection()

            if not source_data or 'features' not in source_data:
                return False, "No source data available for cutting"

            # Validate cut line
            if len(cut_line) < 2:
                return False, "Cut line must have at least 2 points"
            linestring = LineString(cut_line)
            gdf = self.gdf_processed(crs=settings.CRS)

            # Get the feature to cut
            feature_idx = int(feature_id)
            if feature_idx >= len(gdf):
                return False, f"Invalid feature ID: {feature_id}"

            #target_feature = gdf.iloc[feature_idx]
            #target_geometry = target_feature.geometry

            #cut_line = [[115.9108077401263, -34.15361264163583], [115.9148041754924, -34.15477445913835]]
            gdf_single = gdf.iloc[[feature_idx]]
            #gdf_excl_single = gpd.overlay(gdf_single, gdf, how='symmetric_difference')
            gdf_excl_single = gdf.drop(feature_idx)

            polygon_single = gdf_single.iloc[0].geometry
            split_result = split(polygon_single, linestring)
            partitioned_polygons = list(split_result.geoms)
            gdf_partitioned = gpd.GeoDataFrame(geometry=partitioned_polygons)
            gdf_partitioned.set_crs(gdf.crs, inplace=True)
            #plot_gdf(gdf_partitioned)

            # Debug: print what we got from the split
            if len(gdf_partitioned) < 2:
                return False, f"Cut operation produced only {len(gdf_partitioned)} valid polygon(s)."

            print(f"Split produced {len(gdf_partitioned)} geometries:")
            print(gdf_partitioned)

            for idx, row in gdf_partitioned.iterrows():
                row['cut_part'] = idx + 1
                row['original_feature'] = feature_id
                row['area'] = round(row.geometry.area, 2)

            # Save to processed field
            #self.geojson_data_processed = processed_data
            #import ipdb; ipdb.set_trace()
            gdf_rejoin = gpd.GeoDataFrame(pd.concat([gdf_partitioned, gdf_excl_single], ignore_index=True))
            self.geojson_data_processed = json.loads(gdf_rejoin.set_crs(settings.CRS).to_json())
            self.save()

            return True, f"Successfully cut polygon {feature_id} into {len(gdf_partitioned)} parts)"

        except Exception as e:
            import traceback
            print(f"Cut polygon error: {e}")
            print(traceback.format_exc())
            return False, f"Error cutting polygon: {str(e)}"


    def _cut_polygon(self, feature_id, cut_line):
        """Cut a polygon using a line segment - with better error handling"""
        try:
            import geopandas as gpd
            from shapely.geometry import Polygon, LineString
            from shapely.ops import split
            import json

            # Use processed data as source, fallback to original
            if self.geojson_data_processed:
                source_data = self.get_processed_geojson_feature_collection()
            else:
                source_data = self.get_geojson_feature_collection()

            if not source_data or 'features' not in source_data:
                return False, "No source data available for cutting"

            # Convert to GeoDataFrame
            gdf = gpd.GeoDataFrame.from_features(source_data['features'])

            # Get the feature to cut
            feature_idx = int(feature_id)
            if feature_idx >= len(gdf):
                return False, f"Invalid feature ID: {feature_id}"

            target_feature = gdf.iloc[feature_idx]
            target_geometry = target_feature.geometry

            # Validate cut line
            if len(cut_line) < 2:
                return False, "Cut line must have at least 2 points"

            # Create LineString from cut points
            cut_line_geom = LineString(cut_line)

            # Ensure geometries are valid
            target_geometry = target_geometry.buffer(0)
            if not target_geometry.is_valid or target_geometry.is_empty:
                return False, "Target polygon geometry is invalid or empty"

            # Extend line to ensure it cuts completely through the polygon
            extended_line = self._create_cutting_line(target_geometry, cut_line_geom)

            # Perform the split operation
            result = split(target_geometry, extended_line)

            # Check if split was successful
            if result.is_empty:
                return False, "Cut line does not intersect the polygon properly"

            # Extract ALL geometries from the result, not just Polygons
            partitioned_geometries = []
            for geom in result.geoms:
                # Buffer to ensure validity
                valid_geom = geom.buffer(0)
                if valid_geom.is_valid and not valid_geom.is_empty:
                    partitioned_geometries.append(valid_geom)

            # Debug: print what we got from the split
            print(f"Split produced {len(partitioned_geometries)} geometries:")
            for i, geom in enumerate(partitioned_geometries):
                print(f"  {i}: {geom.geom_type} - area: {geom.area}")

            # Convert MultiPolygons to individual Polygons
            all_polygons = []
            for geom in partitioned_geometries:
                if isinstance(geom, Polygon):
                    all_polygons.append(geom)
                elif hasattr(geom, 'geoms'):  # MultiPolygon, GeometryCollection, etc.
                    for sub_geom in geom.geoms:
                        if isinstance(sub_geom, Polygon):
                            valid_sub = sub_geom.buffer(0)
                            if valid_sub.is_valid and not valid_sub.is_empty:
                                all_polygons.append(valid_sub)

            print(f"After processing, we have {len(all_polygons)} polygons")

            # We need at least 2 polygons to consider it a successful cut
            if len(all_polygons) < 2:
                # Try alternative cutting method
                all_polygons = self._try_alternative_cut(target_geometry, extended_line)
                if len(all_polygons) < 2:
                    return False, f"Cut operation produced only {len(all_polygons)} valid polygon(s). Try a different cut line that crosses the polygon completely."

            # Create new features from cut results
            new_features = []
            for i, polygon_geom in enumerate(all_polygons):
                # Convert geometry to GeoJSON-compatible dict
                geometry_dict = self._geometry_to_geojson_dict(polygon_geom)
                if not geometry_dict:
                    print(f"Failed to convert polygon {i} to GeoJSON")
                    continue

                new_properties = target_feature.drop('geometry').to_dict()
                new_properties.update({
                    'cut_part': i + 1,
                    'original_feature': feature_id,
                    'area_sq_km': round(polygon_geom.area * 10000, 2)
                })

                new_feature = {
                    'type': 'Feature',
                    'geometry': geometry_dict,
                    'properties': new_properties
                }
                new_features.append(new_feature)

            print(f"Created {len(new_features)} new features")

            if len(new_features) < 2:
                return False, f"Only created {len(new_features)} valid feature(s) from cut operation"

            # Remove the original feature and add the cut parts
            remaining_gdf = gdf.drop(feature_idx)
            remaining_features = []

            for idx, row in remaining_gdf.iterrows():
                geometry_dict = self._geometry_to_geojson_dict(row.geometry)
                if not geometry_dict:
                    continue

                feature = {
                    'type': 'Feature',
                    'geometry': geometry_dict,
                    'properties': row.drop('geometry').to_dict()
                }
                remaining_features.append(feature)

            # Combine all features
            all_features = remaining_features + new_features

            # Create new processed data
            processed_data = {
                'type': 'FeatureCollection',
                'features': all_features
            }

            # Validate the entire GeoJSON structure before saving
            if not self._is_valid_geojson(processed_data):
                return False, "Generated GeoJSON data is not valid"

            # Save to processed field
            #self.geojson_data_processed = processed_data
            import ipdb; ipdb.set_trace()
            gdf = gpd.GeoDataFrame.from_features(processed_data['features'])
            self.geojson_data_processed = json.loads(gdf.set_crs(settings.CRS).to_json())

            self.save()

            total_parts = len(new_features)
            total_area = sum(feat['properties']['area_sq_km'] for feat in new_features)
            return True, f"Successfully cut polygon {feature_id} into {total_parts} parts (Total area: {total_area} sq km)"

        except Exception as e:
            import traceback
            print(f"Cut polygon error: {e}")
            print(traceback.format_exc())
            return False, f"Error cutting polygon: {str(e)}"

    def _try_alternative_cut(self, polygon, line):
        """Try alternative methods to cut the polygon"""
        from shapely.geometry import Polygon
        from shapely.ops import split

        all_polygons = []

        # Method 1: Try with a slightly buffered line
        try:
            buffered_line = line.buffer(0.0001)
            result = split(polygon, buffered_line)
            for geom in result.geoms:
                valid_geom = geom.buffer(0)
                if valid_geom.is_valid and not valid_geom.is_empty and isinstance(valid_geom, Polygon):
                    all_polygons.append(valid_geom)
        except:
            pass

        if len(all_polygons) >= 2:
            return all_polygons

        # Method 2: Use difference operation
        try:
            buffered_line = line.buffer(0.0001)
            difference = polygon.difference(buffered_line)
            if hasattr(difference, 'geoms'):
                for geom in difference.geoms:
                    valid_geom = geom.buffer(0)
                    if valid_geom.is_valid and not valid_geom.is_empty and isinstance(valid_geom, Polygon):
                        all_polygons.append(valid_geom)
        except:
            pass

        return all_polygons

    def _geometry_to_geojson_dict(self, geometry):
        """Convert a Shapely geometry to a GeoJSON-compatible dictionary"""
        try:
            # Use __geo_interface__ to get the GeoJSON representation
            geo_interface = geometry.__geo_interface__

            # Ensure it's a valid GeoJSON geometry
            if not isinstance(geo_interface, dict):
                return None

            required_keys = ['type', 'coordinates']
            if not all(key in geo_interface for key in required_keys):
                return None

            return geo_interface

        except Exception as e:
            print(f"Geometry to GeoJSON conversion error: {e}")
            return None

    def _is_valid_geojson(self, geojson_data):
        """Validate that the GeoJSON structure is valid and JSON-serializable"""
        try:
            # Test JSON serialization
            json.dumps(geojson_data)
            return True
        except Exception as e:
            print(f"GeoJSON validation error: {e}")
            return False

    def _create_cutting_line(self, polygon, original_line):
        """Create a line that properly cuts through the polygon"""
        from shapely.geometry import LineString, Point

        # Get line coordinates
        coords = list(original_line.coords)
        if len(coords) < 2:
            return original_line

        start_point = Point(coords[0])
        end_point = Point(coords[-1])

        # Calculate direction vector
        dx = end_point.x - start_point.x
        dy = end_point.y - start_point.y

        # If line is degenerate, create a meaningful cutting line
        if abs(dx) < 1e-10 and abs(dy) < 1e-10:
            bounds = polygon.bounds
            # Create a diagonal cutting line through the polygon
            return LineString([
                (bounds[0], bounds[1]),  # southwest
                (bounds[2], bounds[3])   # northeast
            ])

        # Calculate line length for normalization
        line_length = ((dx ** 2) + (dy ** 2)) ** 0.5

        # Get polygon bounds for extension
        bounds = polygon.bounds
        poly_width = bounds[2] - bounds[0]
        poly_height = bounds[3] - bounds[1]
        max_dimension = max(poly_width, poly_height)

        # Extend line significantly beyond polygon bounds to ensure complete cut
        extension_distance = max_dimension * 2.0  # Increased extension

        # Normalize direction vector
        norm_dx = dx / line_length
        norm_dy = dy / line_length

        # Extend both ends of the line
        extended_start = (
            start_point.x - norm_dx * extension_distance,
            start_point.y - norm_dy * extension_distance
        )
        extended_end = (
            end_point.x + norm_dx * extension_distance,
            end_point.y + norm_dy * extension_distance
        )

        return LineString([extended_start, extended_end])

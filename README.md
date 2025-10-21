virtualenv venv
. venv/bin/activate

pip install - requirements.txt

---------------------------------------------
ipython profile create

vi ~/.ipython/profile_default/ipython_config.py

c = get_config()
c.InteractiveShellApp.exec_lines = [
    '%autoreload 2',
    'import numpy as np',
    'import pandas as pd',
    'import geopandas as gpd',
    #'import scipy'
    #'%matplotlib',
]
c.InteractiveShellApp.extensions = [
    'autoreload'
]
---------------------------------------------

./manage.py shell_plus

gdf = gpd.read_file('/home/jawaidm/projects/django_ol_project/shapefile_app/utils/Shapefiles/demarcation_16_polygons/Demarcation_Boundary_16_polygons.shp')

import json
s=Shapefile.objects.create(name='Test 1')
s.geojson_data=json.loads(gdf.to_crs(settings.CRS).to_json())
s.save()

gdf_final_result = gpd.read_file('/home/jawaidm/projects/django_ol_project/shapefile_app/utils/Shapefiles/gdf_final_result/')
s.geojson_data_processed=json.loads(gdf_final_result.to_crs(settings.CRS).to_json())
s.save()

# Refresh browser, these sould now appear




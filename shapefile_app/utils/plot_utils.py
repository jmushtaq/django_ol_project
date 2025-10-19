from django.conf import settings
import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union, polygonize

def annotate_plot(gdf, ax, label_prefix=None):
    row_idx = 0
    for idx, row in gdf.iterrows():
        # Get the centroid of the geometry for label placement
        # For points, this is the point itself. For polygons/lines, it's the centroid.
        # Use .representative_point() for polygons to ensure the point is within the polygon.

        #idx = row.name
        label_prefix = None
        row_geom = row.geometry if 'geometry' in gdf.columns else row.geom
        if row_geom.geom_type == 'Point':
            x, y = row_geom.x, row_geom.y
        else:
            #x, y = row_geom.centroid.x, row_geom.centroid.y
            x, y = row_geom.representative_point().x, row_geom.representative_point().y

        # Get the label text from a column in your GeoDataFrame (e.g., 'name_column')
        if 'origin' in row.keys().to_list() and row.origin == 'BASE':
            label_prefix = 'BASE'
        label = f'{label_prefix} ({idx})' if label_prefix else str(idx)
        #label = label_prefix + '_' + str(idx) if label_prefix else f'{idx} ({row_idx})'

        # Add the label using annotate
        ax.annotate(text=label, xy=(x, y),
                    xytext=(3, 3), # Offset text slightly from the centroid
                    textcoords="offset points",
                    horizontalalignment='center',
                    fontsize=9,
                    color='black') # Customize color, font size, etc.
        row_idx += 1
    return ax

def plot_gdf(gdf, annotate=True):
    ''' Annotate the plot with a feature index

        from silrec.utils.plot_utils import plot_gdf
        plot_gdf(gdf)
    '''
    def get_random_color():
        return "#%06x" % np.random.randint(0, 0xFFFFFF)

    # Create a list of random colors, one for each feature in the GeoDataFrame
    random_colors = [get_random_color() for _ in range(len(gdf))]
    gdf['random_color'] = random_colors

    # Assuming 'gdf' is your GeoDataFrame
    ax = gdf.plot(color=gdf['random_color'], figsize=(10, 10))

    npolys = len(gdf)
    area_ha = round(gdf.area.sum()/10000, 2)
    ax.set_title(f'Polys {npolys}. Area Ha {area_ha}')

    # annotate the plot
    if annotate:
        annotate_plot(gdf, ax, label_prefix=None)

    plt.show()


def plot_overlay(gdf_base, gdf_hist, annotate=False):

    def get_random_color():
        return "#%06x" % np.random.randint(0, 0xFFFFFF)

    # Create a list of random colors, one for each feature in the GeoDataFrame
    random_colors = [get_random_color() for _ in range(len(gdf_base)+len(gdf_hist))]
    #gdf_overlay['random_color'] = random_colors


    # Create a plot to visualize the overlay
    fig, ax = plt.subplots(1, 1, figsize=(10, 10))

    # annotate the plot
    if annotate:
        annotate_plot(gdf_base, ax, label_prefix='base')
        annotate_plot(gdf_hist, ax, label_prefix='hist')

    # Plot the original GeoDataFrames with transparency
    gdf_base.plot(ax=ax, edgecolor='black', color='lightblue', alpha=0.5, label='Base Shapefile Geometries')
    gdf_hist.plot(ax=ax, edgecolor='red', color='lightgreen', alpha=0.5, label='Historical Intersecting Polygons')
    #gdf_base.plot(ax=ax, color=gdf['random_color'], edgecolor='black', alpha=0.5, label='Base Shapefile Geometries')
    #gdf_hist.plot(ax=ax, color=gdf['random_color'], edgecolor='red', alpha=0.5, label='Historical Intersecting Polygons')

    # Plot the overlay GeoDataFrame
    #overlay_gdf.plot(ax=ax, color='red', edgecolor='k', alpha=0.7, label='Intersection')

    # Add a legend and title
    ax.legend()
    ax.set_title('Overlay Plot of Base Shapefile Geometries and Hiostorical Intersecting Polygons')

    plt.show()

def plot_multi(gdf_list, use_random_cols=True):

    def get_random_color():
        return "#%06x" % np.random.randint(0, 0xFFFFFF)

    if len(gdf_list)<=3:
        nrows = 1
    elif len(gdf_list)>3 and len(gdf_list)<=6:
        nrows = 2
    else:
        raise Exception(f'Max. number of gdfs is 6: {len(gdf_list)}')

    if len(gdf_list)==1:
        ncols = 1
    elif len(gdf_list)==2:
        ncols = 2
    else:
        ncols = 3


    fig, axs = plt.subplots(nrows=nrows, ncols=ncols, figsize=(15, 10))
    for i, gdf in enumerate(gdf_list):

#        random_colors = [get_random_color() for _ in range(len(gdf))]
        if use_random_cols is True or 'origin' not in list(gdf.columns):
            random_colors = [get_random_color() for _ in range(len(gdf))]
        else:
            random_colors = ['cornflowerblue' for _ in range(len(gdf))]
            try:
                # colour the base_polygon
                indices = gdf.index[gdf['origin'] == 'BASE'].tolist()
                idx = gdf.index.get_loc(indices[0])
                random_colors[idx] = 'limegreen'

                # colour the neighbouring polygons that have been cookie-cut
                indices_cut = gdf.index[gdf['origin'] == 'CUT'].tolist()
                if len(indices_cut) > 0:
                    for idx_cut in indices_cut:
                        idx = gdf.index.get_loc(idx_cut)
                        random_colors[idx] = 'cyan'

            except Exception as e:
                print(f'{e}')

        npolys = len(gdf)
        area_ha = round(gdf.area.sum()/10000, 2)
        if nrows==1:
            col = i % 3   # Calculate column index
            #gdf.plot(ax=axs[col], color='blue', edgecolor='black')
            #gdf.plot(ax=axs[col], color=random_colors[:npolys+1], edgecolor='black')
            gdf.plot(ax=axs[col], color=random_colors, edgecolor='black')
            #gdf.plot(ax=axs[col], color='blue', edgecolor='black')
            axs[col].set_title(f'Polys {npolys}. Area Ha {area_ha}')
            annotate_plot(gdf, axs[col], label_prefix=None)
        else:
            row = i // 3  # Calculate row index
            col = i % 3   # Calculate column index
            #gdf.plot(ax=axs[row, col], color=random_colors[:npolys+1], edgecolor='black', linewidth=0.5)
            gdf.plot(ax=axs[row, col], color=random_colors, edgecolor='black', linewidth=0.5)
            #gdf.plot(ax=axs[row, col], color='blue', edgecolor='black', linewidth=0.5)
            axs[row,col].set_title(f'Polys {npolys}. Area Ha {area_ha}')
            annotate_plot(gdf, axs[row,col], label_prefix=None)

    # Handle extra subplots if number of GDFs is less than 6
    if len(gdf_list) > 3 and len(gdf_list) < 6:
        for j in range(len(gdf_list), 6):
            row = j // 3
            col = j % 3
            axs[row, col].set_visible(False) # Hide empty subplots

    # Display the plot
    plt.tight_layout() # Adjusts subplot params for a tight layout
    #plt.tight_layout(rect=[0, 0.03, 1, 0.95]) # Adjust layout to prevent title overlap
    plt.show()


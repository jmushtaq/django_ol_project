import geopandas as gpd

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import tkinter as tk
from tkinter import ttk

class ZoomableChart:
    def __init__(self, fig, canvas, chart_frame):
        self.fig = fig
        self.canvas = canvas
        self.chart_frame = chart_frame
        self.zoom_level = 1.0
        self.original_figsize = fig.get_size_inches()
        self.setup_zoom_handlers()

    def setup_zoom_handlers(self):
        # Bind mouse events for zooming
        self.canvas.mpl_connect('scroll_event', self.on_scroll)
        self.canvas.mpl_connect('button_press_event', self.on_button_press)
        self.canvas.mpl_connect('button_release_event', self.on_button_release)
        self.canvas.mpl_connect('motion_notify_event', self.on_motion)

        self.dragging = False
        self.start_x = 0
        self.start_y = 0

    def on_scroll(self, event):
        if event.inaxes:
            # Zoom factor
            zoom_factor = 1.1 if event.button == 'up' else 0.9

            # Get current limits
            xlim = event.inaxes.get_xlim()
            ylim = event.inaxes.get_ylim()

            # Calculate new limits
            xdata = event.xdata
            ydata = event.ydata

            new_xlim = [
                xdata - (xdata - xlim[0]) * zoom_factor,
                xdata + (xlim[1] - xdata) * zoom_factor
            ]
            new_ylim = [
                ydata - (ydata - ylim[0]) * zoom_factor,
                ydata + (ylim[1] - ydata) * zoom_factor
            ]

            # Apply new limits
            event.inaxes.set_xlim(new_xlim)
            event.inaxes.set_ylim(new_ylim)
            self.canvas.draw_idle()

    def on_button_press(self, event):
        if event.button == 2:  # Middle mouse button for panning
            self.dragging = True
            self.start_x = event.x
            self.start_y = event.y
            self.canvas.widgetlock(self)

    def on_button_release(self, event):
        if event.button == 2:
            self.dragging = False
            self.canvas.widgetlock.release(self)

    def on_motion(self, event):
        if self.dragging and event.inaxes:
            dx = event.x - self.start_x
            dy = event.y - self.start_y

            # Convert pixel distance to data distance
            xlim = event.inaxes.get_xlim()
            ylim = event.inaxes.get_ylim()

            xrange = xlim[1] - xlim[0]
            yrange = ylim[1] - ylim[0]

            # Adjust limits based on drag
            scale_x = xrange / self.fig.bbox.width
            scale_y = yrange / self.fig.bbox.height

            new_xlim = [xlim[0] - dx * scale_x, xlim[1] - dx * scale_x]
            new_ylim = [ylim[0] + dy * scale_y, ylim[1] + dy * scale_y]

            event.inaxes.set_xlim(new_xlim)
            event.inaxes.set_ylim(new_ylim)

            self.start_x = event.x
            self.start_y = event.y
            self.canvas.draw_idle()

def plot_geodataframe(ax, gdf, title):
    """Helper function to plot GeoDataFrame with annotations and color coding"""
    if gdf is not None and not gdf.empty and hasattr(gdf, 'geometry'):
        try:
            # Check if 'colour' column exists
            has_color_column = 'colour' in gdf.columns

            # Define default color (steelblue) for when no color column exists
            default_color = 'steelblue'

            if has_color_column:
                # Plot each geometry with its specific color
                for idx, (geometry, color) in enumerate(zip(gdf.geometry, gdf['colour'])):
                    # Create a temporary GeoDataFrame for this single geometry
                    temp_gdf = gpd.GeoDataFrame([{'geometry': geometry}], crs=gdf.crs)

                    # Plot with the specified color, fallback to default if color is invalid
                    try:
                        temp_gdf.plot(ax=ax, color=color, alpha=0.7, edgecolor='black', linewidth=0.8)
                    except (ValueError, TypeError):
                        # If color is invalid, use default color
                        temp_gdf.plot(ax=ax, color=default_color, alpha=0.7, edgecolor='black', linewidth=0.8)
            else:
                # Plot all geometries with default color if no color column exists
                gdf.plot(ax=ax, color=default_color, alpha=0.7, edgecolor='black', linewidth=0.8)

            # Add annotations for polygons (regardless of color)
            for idx, geometry in enumerate(gdf.geometry):
                if hasattr(geometry, 'representative_point'):
                    try:
                        rep_point = geometry.representative_point()
                        ax.annotate(str(idx),
                                  (rep_point.x, rep_point.y),
                                  xytext=(3, 3), textcoords="offset points",
                                  fontsize=8, fontweight='bold',
                                  bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.8, edgecolor='black'),
                                  ha='center', va='center')
                    except:
                        # If representative_point fails, use centroid
                        try:
                            centroid = geometry.centroid
                            ax.annotate(str(idx),
                                      (centroid.x, centroid.y),
                                      xytext=(3, 3), textcoords="offset points",
                                      fontsize=8, fontweight='bold',
                                      bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.8, edgecolor='black'),
                                      ha='center', va='center')
                        except:
                            pass

            ax.set_title(title, fontweight='bold')
            # Remove axis labels
            ax.set_xlabel('')
            ax.set_ylabel('')
            ax.grid(True, alpha=0.3)

        except Exception as e:
            ax.text(0.5, 0.5, f'Plot error: {str(e)}', ha='center', va='center',
                   transform=ax.transAxes, fontsize=10)
            ax.set_title(title, fontweight='bold')
    else:
        ax.text(0.5, 0.5, 'No valid geometry data', ha='center', va='center',
               transform=ax.transAxes, fontsize=10)
        ax.set_title(title, fontweight='bold')

class IndividualChartPopup:
    def __init__(self, root, gdf, title, description=""):
        self.root = root
        self.gdf = gdf
        self.title = title
        self.description = description
        self.popup_window = None
        self.canvas = None
        self.fig = None

    def open_popup(self):
        # Create new window for individual chart
        self.popup_window = tk.Toplevel(self.root)
        self.popup_window.title(f"Chart: {self.title}")
        self.popup_window.geometry("1000x700")
        self.popup_window.configure(bg='white')

        # Enable full window controls
        self.popup_window.resizable(True, True)
        self.popup_window.focus_set()

        # Create main frame
        main_frame = tk.Frame(self.popup_window, bg='white')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # Create title frame
        title_frame = tk.Frame(main_frame, bg='white')
        title_frame.pack(fill=tk.X, pady=(0, 10))

        # Chart title
        title_label = tk.Label(title_frame, text=self.title,
                              font=('Arial', 16, 'bold'), bg='white')
        title_label.pack()

        # Description if provided
        if self.description:
            desc_label = tk.Label(title_frame, text=self.description,
                                 font=('Arial', 10), bg='white', wraplength=900, justify=tk.CENTER)
            desc_label.pack(pady=(5, 0))

        # Create chart frame
        chart_frame = tk.Frame(main_frame, relief=tk.RAISED, bd=2, bg='white')
        chart_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        # Create figure with larger size for popup
        self.fig, ax = plt.subplots(figsize=(12, 8))

        # Plot the GeoDataFrame with annotations and color coding
        plot_geodataframe(ax, self.gdf, self.title)

        # Create canvas
        self.canvas = FigureCanvasTkAgg(self.fig, chart_frame)
        self.canvas.draw()

        # Make it zoomable
        ZoomableChart(self.fig, self.canvas, chart_frame)

        # Add enhanced toolbar
        toolbar_frame = tk.Frame(chart_frame)
        toolbar_frame.pack(side=tk.BOTTOM, fill=tk.X)

        toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        toolbar.update()

        # Pack canvas
        self.canvas.get_tk_widget().pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # Add control buttons frame
        control_frame = tk.Frame(main_frame, bg='white')
        control_frame.pack(fill=tk.X, pady=10)

        # Close button
        close_button = tk.Button(control_frame, text="Close Chart",
                                command=self.close_popup,
                                font=('Arial', 10), bg='lightcoral', fg='white', width=15)
        close_button.pack(side=tk.RIGHT, padx=5)

        # Export button
        export_button = tk.Button(control_frame, text="Export as PNG",
                                 command=self.export_chart,
                                 font=('Arial', 10), bg='lightgreen', width=15)
        export_button.pack(side=tk.RIGHT, padx=5)

        # Info button
        info_button = tk.Button(control_frame, text="Chart Info",
                               command=self.show_info,
                               font=('Arial', 10), bg='lightblue', width=15)
        info_button.pack(side=tk.LEFT, padx=5)

        # Bind escape key to close
        self.popup_window.bind('<Escape>', lambda e: self.close_popup())

        # Handle window close event properly
        self.popup_window.protocol("WM_DELETE_WINDOW", self.close_popup)

    def export_chart(self):
        try:
            filename = f"{self.title.replace(' ', '_')}.png"
            self.fig.savefig(filename, dpi=300, bbox_inches='tight', facecolor='white')

            # Show success message
            success_label = tk.Label(self.popup_window, text=f"Exported as {filename}",
                                   font=('Arial', 9), bg='lightgreen', fg='darkgreen')
            success_label.pack(pady=5)
            self.popup_window.after(2000, success_label.destroy)  # Remove after 2 seconds

        except Exception as e:
            error_label = tk.Label(self.popup_window, text=f"Export failed: {str(e)}",
                                 font=('Arial', 9), bg='lightcoral', fg='darkred')
            error_label.pack(pady=5)
            self.popup_window.after(3000, error_label.destroy)

    def show_info(self):
        info_text = f"Chart: {self.title}\n"
        if self.gdf is not None and not self.gdf.empty:
            info_text += f"Features: {len(self.gdf)}\n"
            info_text += f"Geometry type: {self.gdf.geometry.type.iloc[0] if len(self.gdf) > 0 else 'Unknown'}\n"
            info_text += f"CRS: {self.gdf.crs if self.gdf.crs else 'None'}\n"
            if 'colour' in self.gdf.columns:
                unique_colors = self.gdf['colour'].unique()
                info_text += f"Color scheme: {len(unique_colors)} unique colors\n"
            if self.description:
                info_text += f"Description: {self.description}"

        # Create info popup
        info_window = tk.Toplevel(self.popup_window)
        info_window.title("Chart Information")
        info_window.geometry("400x200")
        info_window.configure(bg='white')

        info_label = tk.Label(info_window, text=info_text, font=('Arial', 10),
                             bg='white', justify=tk.LEFT, padx=20, pady=20)
        info_label.pack(fill=tk.BOTH, expand=True)

        close_button = tk.Button(info_window, text="Close", command=info_window.destroy,
                               font=('Arial', 10), bg='lightgray')
        close_button.pack(pady=10)

    def close_popup(self):
        if self.popup_window:
            plt.close(self.fig)
            self.popup_window.destroy()
            self.popup_window = None

def create_tabbed_charts(*tab_lists, tab_names=None, tab_descriptions=None, chart_titles=None, chart_descriptions=None):
    """
    Create a tabbed multi-chart canvas with vertical scrolling.

    Parameters:
    *tab_lists: Variable number of lists, each containing GeoDataFrames for a tab
    tab_names: Optional list of names for each tab
    tab_descriptions: Optional list of descriptions for each tab
    chart_titles: Optional nested list of titles for each chart
    chart_descriptions: Optional nested list of descriptions for each chart
    """
    # Create main window
    root = tk.Tk()
    root.title("GeoDataFrame Charts - Tabbed Interface")
    root.geometry("1400x800")

    # Validate input
    if not tab_lists:
        raise ValueError("At least one tab of GeoDataFrames must be provided")

    # Create notebook (tabbed interface)
    notebook = ttk.Notebook(root)
    notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Default tab names
    if tab_names is None:
        #tab_names = [f"Tab {i+1}" for i in range(len(tab_lists))]
        tab_names = [f"Tab {i}" for i in range(len(tab_lists))]
    elif len(tab_names) < len(tab_lists):
        tab_names.extend([f"Tab {i}" for i in range(len(tab_names), len(tab_lists))])

    # Default tab descriptions
    default_descriptions = [
        "Spatial analysis of geographic features and distributions across the study area.",
        "Regional mapping showing territorial boundaries and spatial relationships.",
        "Geographic data visualization with coordinate reference system projections.",
        "Spatial patterns and clustering analysis of geographic phenomena.",
        "Cartographic representation of spatial data with thematic mapping."
    ]

    if tab_descriptions is None:
        tab_descriptions = {}
        for i in range(len(tab_lists)):
            if i < len(default_descriptions):
                tab_descriptions[i] = default_descriptions[i]
            else:
                tab_descriptions[i] = f"Spatial data visualization for geographic dataset {i+1}"
    elif isinstance(tab_descriptions, list):
        tab_descriptions = {i: desc for i, desc in enumerate(tab_descriptions)}

    # Create each tab
    for tab_idx, tab_gdfs in enumerate(tab_lists):
        if not tab_gdfs:
            continue

        # Create main frame for this tab with vertical scrollbar
        tab_frame = tk.Frame(notebook)
        notebook.add(tab_frame, text=tab_names[tab_idx])

        # Create container with vertical scrollbar
        main_container = tk.Frame(tab_frame)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Create vertical scrollbar
        v_scrollbar = ttk.Scrollbar(main_container, orient=tk.VERTICAL)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Create canvas with vertical scrollbar
        canvas = tk.Canvas(main_container, yscrollcommand=v_scrollbar.set, bg='white')
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Configure scrollbar
        v_scrollbar.config(command=canvas.yview)

        # Create scrollable frame
        scrollable_frame = tk.Frame(canvas, bg='white')

        # Create window in canvas
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        def configure_scroll_region(event, c=canvas, cw=canvas_window):
            c.configure(scrollregion=c.bbox("all"))
            c.itemconfig(cw, width=c.winfo_width())

        scrollable_frame.bind("<Configure>", lambda e, c=canvas, cw=canvas_window: configure_scroll_region(e, c, cw))

        def on_canvas_configure(event, c=canvas, cw=canvas_window):
            c.itemconfig(cw, width=event.width)

        canvas.bind("<Configure>", lambda e, c=canvas, cw=canvas_window: on_canvas_configure(e, c, cw))

        # Create tab description frame
        desc_frame = tk.Frame(scrollable_frame, relief=tk.GROOVE, bd=1, bg='lightyellow')
        desc_frame.pack(fill=tk.X, padx=10, pady=10)

        # Add description text
        desc_label = tk.Label(desc_frame, text=tab_descriptions.get(tab_idx, f"Spatial data tab {tab_idx + 1}"),
                             font=('Arial', 10), bg='lightyellow', wraplength=1200, justify=tk.LEFT)
        desc_label.pack(padx=10, pady=10)

        # Create charts container
        charts_container = tk.Frame(scrollable_frame, bg='white')
        charts_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        zoomable_charts = []

        # Arrange charts in rows of 3 with wrapping
        charts_per_row = 3
        current_row = 0
        current_col = 0

        # Process each GeoDataFrame in the tab
        for chart_idx, gdf in enumerate(tab_gdfs):
            # Calculate row and column position
            if chart_idx > 0 and chart_idx % charts_per_row == 0:
                current_row += 1
                current_col = 0
            else:
                current_col = chart_idx % charts_per_row

            # Create container for chart with individual popup button
            chart_container = tk.Frame(charts_container, bg='white')
            chart_container.grid(row=current_row, column=current_col, padx=10, pady=10, sticky="nsew")

            # Configure grid weights for responsive layout
            charts_container.grid_rowconfigure(current_row, weight=1)
            charts_container.grid_columnconfigure(current_col, weight=1)

            # Add individual chart popup button
            chart_title = f"Chart {chart_idx + 1}"
            if chart_titles and tab_idx < len(chart_titles) and chart_idx < len(chart_titles[tab_idx]):
                chart_title = chart_titles[tab_idx][chart_idx]

            chart_description = ""
            if chart_descriptions and tab_idx < len(chart_descriptions) and chart_idx < len(chart_descriptions[tab_idx]):
                chart_description = chart_descriptions[tab_idx][chart_idx]

            popup_button = tk.Button(chart_container, text="📊",
                                   font=('Arial', 10),
                                   command=lambda g=gdf, t=chart_title, d=chart_description: open_individual_chart(g, t, d),
                                   bg='lightgreen', width=2)
            popup_button.pack(anchor='ne', pady=(0, 2))

            # Create frame for the chart
            chart_frame = tk.Frame(chart_container, relief=tk.RAISED, bd=1)
            chart_frame.pack(fill=tk.BOTH, expand=True)

            # Create figure for each chart - larger size like in the maximized view
            fig, ax = plt.subplots(figsize=(6, 4.5))

            # Plot the GeoDataFrame with annotations and color coding
            plot_geodataframe(ax, gdf, chart_title)

            # Embed in tkinter
            chart_canvas = FigureCanvasTkAgg(fig, chart_frame)
            chart_canvas.draw()

            # Create zoomable chart instance
            zoom_chart = ZoomableChart(fig, chart_canvas, chart_frame)
            zoomable_charts.append(zoom_chart)

            # Add matplotlib navigation toolbar for each chart
            toolbar_frame = tk.Frame(chart_frame)
            toolbar_frame.pack(side=tk.BOTTOM, fill=tk.X)

            toolbar = NavigationToolbar2Tk(chart_canvas, toolbar_frame)
            toolbar.update()

            # Pack the chart canvas
            chart_canvas.get_tk_widget().pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

        # Fix mouse wheel scrolling for this tab
        def _on_mousewheel(event, c=canvas):
            c.yview_scroll(int(-1*(event.delta/120)), "units")

        # Bind mouse wheel to the canvas and all its children
        def bind_to_children(widget):
            widget.bind("<MouseWheel>", lambda e, c=canvas: _on_mousewheel(e, c))
            for child in widget.winfo_children():
                bind_to_children(child)

        # Bind mouse wheel to the canvas and scrollable frame
        canvas.bind("<MouseWheel>", lambda e, c=canvas: _on_mousewheel(e, c))
        scrollable_frame.bind("<MouseWheel>", lambda e, c=canvas: _on_mousewheel(e, c))
        bind_to_children(scrollable_frame)

    def open_individual_chart(gdf, title, description):
        chart_popup = IndividualChartPopup(root, gdf, title, description)
        chart_popup.open_popup()

    # Add instructions
    instructions = tk.Label(root,
                          text="Navigation: Click tabs to switch views | Click 📊 for individual chart popup | Scroll: Mouse Wheel",
                          font=('Arial', 8), bg='lightyellow', relief=tk.SUNKEN)
    instructions.pack(side=tk.BOTTOM, fill=tk.X)

    root.mainloop()

# Example usage function with color demonstration
def example_usage():
    """
    Example of how to use the function with sample data including color columns.
    This requires geopandas and some sample geographic data.
    """
    try:
        import geopandas as gpd
        from shapely.geometry import Polygon

        # Create sample GeoDataFrames with color columns
        # Tab 1: Urban Areas with different colors
        urban_polys = gpd.GeoDataFrame({
            'geometry': [
                Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
                Polygon([(2, 0), (3, 0), (3, 1), (2, 1)]),
                Polygon([(1, 2), (2, 2), (2, 3), (1, 3)]),
                Polygon([(3, 2), (4, 2), (4, 3), (3, 3)]),
                Polygon([(0.5, 1.5), (1.5, 1.5), (1.5, 2.5), (0.5, 2.5)]),
                Polygon([(2.5, 1.5), (3.5, 1.5), (3.5, 2.5), (2.5, 2.5)])
            ],
            'colour': ['red', 'blue', 'green', 'orange', 'purple', 'brown']
        })

        # Tab 2: Rural Areas with some colors repeated
        rural_polys = gpd.GeoDataFrame({
            'geometry': [
                Polygon([(5, 0), (6, 0), (6, 1), (5, 1)]),
                Polygon([(7, 0), (8, 0), (8, 1), (7, 1)]),
                Polygon([(5, 2), (6, 2), (6, 3), (5, 3)]),
                Polygon([(7, 2), (8, 2), (8, 3), (7, 3)]),
                Polygon([(6, 4), (7, 4), (7, 5), (6, 5)])
            ],
            'colour': ['lightblue', 'lightgreen', 'lightblue', 'lightgreen', 'yellow']
        })

        # Tab 3: Mixed Areas without color column (should use default)
        mixed_polys = gpd.GeoDataFrame({
            'geometry': [
                Polygon([(0, 4), (1, 4), (1, 5), (0, 5)]),
                Polygon([(2, 4), (3, 4), (3, 5), (2, 5)]),
                Polygon([(4, 4), (5, 4), (5, 5), (4, 5)]),
                Polygon([(1, 6), (2, 6), (2, 7), (1, 7)]),
                Polygon([(3, 6), (4, 6), (4, 7), (3, 7)]),
                Polygon([(5, 6), (6, 6), (6, 7), (5, 7)])
            ]
            # No 'colour' column - will use default steelblue
        })

        # Create tab lists
        tab1 = [urban_polys]
        tab2 = [rural_polys]
        tab3 = [mixed_polys]

        # Custom tab names and descriptions
        tab_names = ["Urban Areas (Colored)", "Rural Districts (Colored)", "Mixed Zones (Default)"]

        tab_descriptions = [
            "Urban development patterns with custom color coding for different zones",
            "Rural land use mapping with thematic color scheme",
            "Mixed-use zones using default color scheme (no color column provided)"
        ]

        # Call the function
        create_tabbed_charts(
            tab1, tab2, tab3,
            tab_names=tab_names,
            tab_descriptions=tab_descriptions
        )

    except ImportError:
        print("geopandas or shapely not available. Using empty example.")
        # Fallback example without actual GeoDataFrames
        empty_tab1 = [None]  # Placeholder for GeoDataFrames
        empty_tab2 = [None]
        empty_tab3 = [None]

        create_tabbed_charts(empty_tab1, empty_tab2, empty_tab3)

# Uncomment to run the example
# example_usage()

# Main function call for user data
# create_tabbed_charts(list1, list2, list3, list4)


if __name__ == "__main__":
    gdf1 = gpd.read_file('silrec/utils/Shapefiles/demarcation_1_polygons/Demarcation_Boundary_1_polygons.shp')
    gdf2 = gpd.read_file('silrec/utils/Shapefiles/demarcation_2_polygons/Demarcation_Boundary_2_polygons.shp')
    gdf5 = gpd.read_file('silrec/utils/Shapefiles/demarcation_5_polygons/Demarcation_Boundary_5_polygons.shp')
    gdf16= gpd.read_file('silrec/utils/Shapefiles/demarcation_16_polygons/Demarcation_Boundary_16_polygons.shp')

    tab_names = ["Tab 0", "Tab 1", "Tab 2", "Tab 3"]

    tab_descriptions = [
        "1. Point data analysis showing spatial distribution of sample locations",
        "2. Polygon features representing geographic boundaries and areas of interest",
        "3. Point data analysis showing spatial distribution of sample locations",
        "4. Polygon features representing geographic boundaries and areas of interest"
    ]

    gdf1['colour'] = 'green'
    gdf16['colour'] = 'yellow'
    gdf16['colour'][4] = 'grey'

    list1 = [gdf1, gdf2, gdf5, gdf16]
    list2 = [gdf2, gdf5, gdf16]
    list3 = [gdf5, gdf16, gdf1, gdf2 ]
    list4 = [gdf16, gdf1, gdf2, gdf5, gdf1]

#    create_tabbed_charts(
#        list1, list2, list3, list4,
#        tab_names=tab_names,
#        tab_descriptions=tab_descriptions
#    )

    gdf_list = [list1, list2, list3, list4]
    create_tabbed_charts(
        *gdf_list
    )


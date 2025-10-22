// Debug function to show cutting state
function updateCuttingDebug() {
    const debugInfo = document.getElementById('cutting-debug-info');
    if (debugInfo) {
        debugInfo.innerHTML = `
            Cutting: ${polygonCutter.isCuttingEnabled}<br>
            Selected: ${polygonCutter.selectedPolygon ? 'Yes' : 'No'}<br>
            Points: ${polygonCutter.cutLinePoints.length}<br>
        `;
    }
}

// Western Australia bounds (approximate)
const WA_BOUNDS = [112.5, -35.5, 129.0, -13.5];

// Initialize map with default controls (includes zoom buttons)
const map = new ol.Map({
    target: 'map',
    layers: [
        new ol.layer.Tile({
            source: new ol.source.OSM()
        })
    ],
    view: new ol.View({
        center: ol.proj.fromLonLat([120.5, -24.5]),
        zoom: 6
    })
});

// Fit map to Western Australia bounds
const waExtent = ol.proj.transformExtent(WA_BOUNDS, 'EPSG:4326', 'EPSG:3857');
map.getView().fit(waExtent, { padding: [50, 50, 50, 50] });

// Store layer references and selection state
const shapefileLayers = {};
const selectedFeatures = new Map(); // shapefileId -> Set of feature IDs

// Selection style
const selectStyle = new ol.style.Style({
    stroke: new ol.style.Stroke({
        color: 'yellow',
        width: 4
    }),
    fill: new ol.style.Fill({
        color: 'rgba(255, 255, 0, 0.3)'
    })
});

// Create select interaction
const selectInteraction = new ol.interaction.Select({
    style: selectStyle,
    condition: ol.events.condition.click,
    layers: function(layer) {
        // Allow selection from both layers, but cutting will only use processed
        return layer instanceof ol.layer.Vector &&
            Object.values(shapefileLayers).includes(layer);
    }
});

// Add select interaction to map
map.addInteraction(selectInteraction);

// Update selection handler to only process processed layer features
selectInteraction.on('select', function(e) {
    e.selected.forEach(function(feature) {
        const shapefileId = feature.get('shapefileId');
        const featureId = feature.get('featureId');
        const layerType = feature.get('layerType');

        // Only allow selection from processed layers
        if (layerType === 'processed') {
            if (!selectedFeatures.has(shapefileId)) {
                selectedFeatures.set(shapefileId, new Set());
            }
            selectedFeatures.get(shapefileId).add(featureId);
        } else {
            // Remove selection from original layers
            selectInteraction.getFeatures().remove(feature);
        }
    });

    e.deselected.forEach(function(feature) {
        const shapefileId = feature.get('shapefileId');
        const featureId = feature.get('featureId');

        if (selectedFeatures.has(shapefileId)) {
            selectedFeatures.get(shapefileId).delete(featureId);
        }
    });

    updateAllSelectionInfo();
});

// Function to show status messages
function showStatusMessage(message, type = 'info') {
    // Remove existing messages
    const existingMessages = document.querySelectorAll('.status-message');
    existingMessages.forEach(msg => msg.remove());

    // Create new message
    const messageDiv = document.createElement('div');
    messageDiv.className = `status-message alert alert-${type} alert-dismissible fade show`;

    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'danger') icon = '❌';
    if (type === 'warning') icon = '⚠️';

    messageDiv.innerHTML = `
        ${icon} ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    document.body.appendChild(messageDiv);

    // Auto-dismiss after 5 seconds for success/info, 10 seconds for errors/warnings
    const dismissTime = type === 'success' || type === 'info' ? 5000 : 10000;
    setTimeout(() => {
        if (messageDiv.parentNode) {
            messageDiv.remove();
        }
    }, dismissTime);
}

// Layer control toggle functionality
const layerToggleBtn = document.getElementById('layer-toggle-btn');
const layerControl = document.getElementById('layer-control');

layerToggleBtn.addEventListener('click', function() {
    if (layerControl.style.display === 'none') {
        layerControl.style.display = 'block';
    } else {
        layerControl.style.display = 'none';
    }
});

// Close layer control when clicking outside
document.addEventListener('click', function(event) {
    if (!layerControl.contains(event.target) && !layerToggleBtn.contains(event.target)) {
        layerControl.style.display = 'none';
    }
});

// Function to load and display shapefile
function loadShapefile(shapefileId, layerType = 'original') {
    const layerKey = `${shapefileId}_${layerType}`;

    if (shapefileLayers[layerKey]) {
        shapefileLayers[layerKey].setVisible(true);
        if (layerType === 'processed') {
            zoomToLayer(shapefileLayers[layerKey]);
        }
        // Update annotations when layer visibility changes
        updateAnnotations();
        return;
    }

    const url = layerType === 'processed'
        ? `/shapefile/${shapefileId}/geojson/processed/`
        : `/shapefile/${shapefileId}/geojson/`;

    fetch(url)
        .then(response => {
            if (!response.ok) {
                if (layerType === 'processed' && response.status === 404) {
                    console.log(`No processed data for shapefile ${shapefileId}`);
                    return null;
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(geojsonData => {
            if (!geojsonData && layerType === 'processed') {
                console.log(`Skipping processed layer for shapefile ${shapefileId} - no data`);
                return;
            }

            const vectorSource = new ol.source.Vector({
                features: geojsonData ? new ol.format.GeoJSON().readFeatures(geojsonData, {
                    dataProjection: 'EPSG:4326',
                    featureProjection: 'EPSG:3857'
                }) : []
            });

            // Add feature IDs and metadata for selection
            vectorSource.getFeatures().forEach((feature, index) => {
                //feature.set('featureId', feature.id_.toString());
                feature.set('featureId', index.toString());
                feature.set('shapefileId', shapefileId.toString());
                feature.set('layerType', layerType);
            });

            const style = layerType === 'processed'
                ? new ol.style.Style({
                    stroke: new ol.style.Stroke({ color: 'red', width: 3 }),
                    fill: new ol.style.Fill({ color: 'rgba(255, 0, 0, 0.2)' })
                })
                : new ol.style.Style({
                    stroke: new ol.style.Stroke({ color: 'blue', width: 2 }),
                    fill: new ol.style.Fill({ color: 'rgba(0, 0, 255, 0.1)' })
                });

            const vectorLayer = new ol.layer.Vector({
                source: vectorSource,
                style: style
            });

            // Listen for visibility changes to update annotations
            vectorLayer.on('change:visible', function() {
                setTimeout(updateAnnotations, 100);
            });

            map.addLayer(vectorLayer);
            shapefileLayers[layerKey] = vectorLayer;

            // Initialize selection set for this shapefile (only for processed layers)
            if (layerType === 'processed' && !selectedFeatures.has(shapefileId.toString())) {
                selectedFeatures.set(shapefileId.toString(), new Set());
            }

            updateAllSelectionInfo();
            if (vectorSource.getFeatures().length > 0) {
                zoomToLayer(vectorLayer);
            }

            // Update annotations after layer is loaded
            setTimeout(updateAnnotations, 200);

            console.log(`Loaded ${vectorSource.getFeatures().length} features for ${layerType} layer`);
        })
        .catch(error => {
            console.error(`Error loading ${layerType} shapefile:`, error);
            if (layerType === 'original') {
                alert(`Error loading ${layerType} layer: ${error.message}`);
            }
        });
}

// Function to update selection info for all shapefiles
function updateAllSelectionInfo() {
    // Clear existing selection info
    document.querySelectorAll('.selection-info').forEach(el => el.remove());

    // Update for each shapefile with processed data
    selectedFeatures.forEach((selectedSet, shapefileId) => {
        const selectionCount = selectedSet.size;
        const hasProcessedLayer = shapefileLayers.hasOwnProperty(`${shapefileId}_processed`);

        if (selectionCount > 0 && hasProcessedLayer) {
            const infoElement = document.createElement('div');
            infoElement.id = `selection-info-${shapefileId}`;
            infoElement.className = 'selection-info small text-muted mt-1';

            const canMerge = selectionCount >= 2;
            const mergeButtonClass = canMerge ? 'btn-success' : 'btn-secondary';
            const mergeButtonDisabled = !canMerge ? 'disabled' : '';
            const tooltipText = canMerge ? '' : 'Must select at least two polygons';

            infoElement.innerHTML = `
                <div><strong>Processed Layer Selection:</strong></div>
                <div>Selected: ${selectionCount} polygon(s)</div>
                <button class="btn ${mergeButtonClass} btn-sm mt-1 merge-btn"
                        ${mergeButtonDisabled}
                        onclick="mergeSelectedPolygons(${shapefileId})"
                        data-bs-toggle="tooltip"
                        data-bs-title="${tooltipText}">
                    Merge Selected
                </button>
                <button class="btn btn-secondary btn-sm mt-1" onclick="clearSelection(${shapefileId})">
                    Clear
                </button>
            `;

            const layerGroup = document.querySelector(`[id="layer${shapefileId}"]`).closest('.layer-group');
            if (layerGroup) {
                layerGroup.appendChild(infoElement);

                // Initialize Bootstrap tooltips
                const tooltipTriggerList = [].slice.call(infoElement.querySelectorAll('[data-bs-toggle="tooltip"]'));
                tooltipTriggerList.map(function (tooltipTriggerEl) {
                    return new bootstrap.Tooltip(tooltipTriggerEl);
                });
            }
        }
    });

    // Show message if trying to select from original layer
    const originalSelected = selectInteraction.getFeatures().getArray().some(feature =>
        feature.get('layerType') === 'original'
    );

    if (originalSelected) {
        showStatusMessage('Selection is only allowed from processed (red) layers', 'warning');
        // Clear selection from original layers
        const originalFeatures = selectInteraction.getFeatures().getArray().filter(feature =>
            feature.get('layerType') === 'original'
        );
        originalFeatures.forEach(feature => {
            selectInteraction.getFeatures().remove(feature);
        });
    }
}

// Update merge function to show proper status messages
function mergeSelectedPolygons(shapefileId) {
    const shapefileIdStr = shapefileId.toString();

    if (!selectedFeatures.has(shapefileIdStr) || selectedFeatures.get(shapefileIdStr).size < 2) {
        showStatusMessage('Please select at least 2 polygons to merge from the processed layer', 'warning');
        return;
    }

    const selectedIds = Array.from(selectedFeatures.get(shapefileIdStr));

    console.log(`Attempting to merge shapefile ${shapefileId}, features: ${selectedIds}`);

    // Use GET request with URL parameters
    const mergeUrl = `/shapefile/${shapefileId}/merge/?ids=${JSON.stringify(selectedIds)}`;
    console.log(`Sending GET to: ${mergeUrl}`);

    showStatusMessage(`Merging polygons ${selectedIds.join(', ')}...`, 'info');

    fetch(mergeUrl, {
        method: 'GET',
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => {
        console.log(`Response status: ${response.status}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('Merge response:', data);
        if (data.success) {
            showStatusMessage(data.message, 'success');
            // Clear current selection
            clearSelection(shapefileId);

            // Reload the processed layer
            removeShapefile(shapefileId, 'processed');
            setTimeout(() => {
                const processedCheckbox = document.getElementById(`layer${shapefileId}_processed`);
                if (processedCheckbox) {
                    processedCheckbox.checked = true;
                    loadShapefile(shapefileId, 'processed');
                } else {
                    // Create processed checkbox if it doesn't exist
                    const layerGroup = document.querySelector(`[id="layer${shapefileId}"]`).closest('.layer-group');
                    if (layerGroup) {
                        const originalLabel = document.querySelector(`[for="layer${shapefileId}"]`).textContent;
                        const processedHtml = `
                            <div class="form-check ms-3">
                                <input class="form-check-input layer-checkbox"
                                    type="checkbox"
                                    value="${shapefileId}"
                                    id="layer${shapefileId}_processed"
                                    data-layer-type="processed"
                                    checked>
                                <label class="form-check-label" for="layer${shapefileId}_processed">
                                    ${originalLabel.replace('(O)', '(P)')}
                                </label>
                            </div>
                        `;
                        layerGroup.querySelector('.form-check').insertAdjacentHTML('afterend', processedHtml);
                        loadShapefile(shapefileId, 'processed');
                    }
                }
            }, 500);
        } else {
            showStatusMessage(data.message, 'danger');
        }
    })
    .catch(error => {
        console.error('Merge error:', error);
        showStatusMessage('Error merging polygons: ' + error.message, 'danger');
    });
}

// Update clear selection to show info
function clearSelection(shapefileId) {
    const shapefileIdStr = shapefileId.toString();

    if (selectedFeatures.has(shapefileIdStr)) {
        selectedFeatures.get(shapefileIdStr).clear();

        // Clear selection from map
        const selectedFeaturesArray = selectInteraction.getFeatures().getArray();
        const featuresToDeselect = selectedFeaturesArray.filter(feature =>
            feature.get('shapefileId') === shapefileIdStr
        );

        featuresToDeselect.forEach(feature => {
            selectInteraction.getFeatures().remove(feature);
        });

        updateAllSelectionInfo();
        showStatusMessage('Selection cleared', 'info');
    }
}

// Update function to remove shapefile layer (with annotation cleanup)
function removeShapefile(shapefileId, layerType = 'original') {
    const layerKey = `${shapefileId}_${layerType}`;
    if (shapefileLayers[layerKey]) {
        map.removeLayer(shapefileLayers[layerKey]);
        delete shapefileLayers[layerKey];

        // Also remove corresponding annotation layer
        const annotationKey = `${shapefileId}_${layerType}_annotations`;
        if (shapefileLayers[annotationKey]) {
            map.removeLayer(shapefileLayers[annotationKey]);
            delete shapefileLayers[annotationKey];
        }

        // Clear selection for this shapefile
        clearSelection(shapefileId);

        // Update annotations after removal
        updateAnnotations();

        if (Object.keys(shapefileLayers).length === 0) {
            map.getView().fit(waExtent, { padding: [50, 50, 50, 50], duration: 1000 });
        }
    }
}

// Function to zoom to a specific layer
function zoomToLayer(layer) {
    const source = layer.getSource();
    const extent = source.getExtent();

    if (!ol.extent.isEmpty(extent)) {
        map.getView().fit(extent, {
            padding: [50, 50, 50, 50],
            maxZoom: 15,
            duration: 1000
        });
    }
}

// Update layer checkbox handler to manage annotations
document.addEventListener('change', function(e) {
    if (e.target.classList.contains('layer-checkbox')) {
        const shapefileId = e.target.value;
        const layerType = e.target.dataset.layerType;

        if (e.target.checked) {
            loadShapefile(shapefileId, layerType);
        } else {
            removeShapefile(shapefileId, layerType);
        }

        // Update annotations after a short delay to ensure layer visibility has updated
        setTimeout(updateAnnotations, 300);
    }
});

// Update map view change to refresh annotations (for zoom/pan)
map.getView().on('change:center', updateAnnotations);
map.getView().on('change:resolution', updateAnnotations);

// Load all checked layers initially
document.querySelectorAll('.layer-checkbox:checked').forEach(checkbox => {
    const shapefileId = checkbox.value;
    const layerType = checkbox.dataset.layerType;
    loadShapefile(shapefileId, layerType);
});

// Auto-zoom to newly uploaded shapefile
const urlParams = new URLSearchParams(window.location.search);
const zoomToId = urlParams.get('zoom_to');

if (zoomToId) {
    Object.keys(shapefileLayers).forEach(layerKey => {
        if (layerKey.startsWith(`${zoomToId}_`)) {
            const [shapefileId, layerType] = layerKey.split('_');
            removeShapefile(shapefileId, layerType);
        }
    });

    setTimeout(() => {
        const originalCheckbox = document.getElementById(`layer${zoomToId}`);
        if (originalCheckbox) {
            originalCheckbox.checked = true;
            loadShapefile(zoomToId, 'original');
        }
    }, 500);

    window.history.replaceState({}, document.title, window.location.pathname);
}

// CSRF token helper function
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Update the debug info function
function updateDebugInfo() {
    const debugInfo = document.getElementById('debug-info');
    if (!debugInfo) return;

    const shapefileIds = Array.from(selectedFeatures.keys());
    let mergeUrl = '';

    if (shapefileIds.length > 0) {
        const firstShapefileId = shapefileIds[0];
        const selectedIds = Array.from(selectedFeatures.get(firstShapefileId));
        mergeUrl = `/shapefile/${firstShapefileId}/merge/?ids=${JSON.stringify(selectedIds)}`;
    }

    debugInfo.innerHTML = `
        Loaded shapefiles: ${Object.keys(shapefileLayers).join(', ')}<br>
        Selected features: ${JSON.stringify(Array.from(selectedFeatures.entries()))}<br>
        Merge URL: ${mergeUrl}
    `;
}

// Function to check if only one layer is visible
function getVisibleLayersCount() {
    let count = 0;
    Object.values(shapefileLayers).forEach(layer => {
        if (layer.getVisible()) {
            count++;
        }
    });
    return count;
}

// Function to get representative point for a geometry
function getRepresentativePoint(geometry) {
    if (geometry.getType() === 'Point') {
        return geometry.getCoordinates();
    } else if (geometry.getType() === 'Polygon') {
        // Use the first interior point or centroid as representative point
        try {
            return geometry.getInteriorPoint().getCoordinates();
        } catch (e) {
            return geometry.getExtent();
        }
    } else if (geometry.getType() === 'MultiPolygon') {
        // For MultiPolygon, use the first polygon's interior point
        const polygons = geometry.getPolygons();
        if (polygons.length > 0) {
            try {
                return polygons[0].getInteriorPoint().getCoordinates();
            } catch (e) {
                return polygons[0].getExtent();
            }
        }
    }
    // Fallback to centroid
    return geometry.getExtent();
}

// Function to create or update annotations
function updateAnnotations() {
    // Remove existing annotations
    const existingAnnotationLayers = Object.keys(shapefileLayers).filter(key => key.endsWith('_annotations'));
    existingAnnotationLayers.forEach(key => {
        map.removeLayer(shapefileLayers[key]);
        delete shapefileLayers[key];
    });

    const visibleCount = getVisibleLayersCount();

    // Only show annotations if exactly one layer is visible
    if (visibleCount === 1) {
        // Find the single visible layer
        let targetLayer = null;
        let targetLayerKey = null;

        Object.entries(shapefileLayers).forEach(([key, layer]) => {
            if (layer.getVisible() && !key.endsWith('_annotations')) {
                targetLayer = layer;
                targetLayerKey = key;
            }
        });

        if (targetLayer && targetLayerKey) {
            const [shapefileId, layerType] = targetLayerKey.split('_');
            createAnnotationsForLayer(shapefileId, layerType, targetLayer);
        }
    }
}

// Function to create annotations for a specific layer
function createAnnotationsForLayer(shapefileId, layerType, sourceLayer) {
    const annotationKey = `${shapefileId}_${layerType}_annotations`;
    const annotationSource = new ol.source.Vector();

    // Fetch the original GeoJSON to get the actual feature data from the API
    const url = layerType === 'processed'
        ? `/shapefile/${shapefileId}/geojson/processed/`
        : `/shapefile/${shapefileId}/geojson/`;

    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(geojsonData => {
            if (!geojsonData || !geojsonData.features) {
                console.log('No GeoJSON features found');
                return;
            }

            console.log(`Creating annotations for ${geojsonData.features.length} features from API`);

            // Create annotations directly from the GeoJSON features
            geojsonData.features.forEach((feature, index) => {
                if (!feature.geometry) return;

                // Get the actual feature ID
                let actualFeatureId = index;

                // Try to get ID from feature properties
                if (feature.properties) {
                    if (feature.properties.id !== undefined) {
                        actualFeatureId = feature.properties.id;
                    } else if (feature.properties.ID !== undefined) {
                        actualFeatureId = feature.properties.ID;
                    } else if (feature.properties.fid !== undefined) {
                        actualFeatureId = feature.properties.fid;
                    } else if (feature.properties.FID !== undefined) {
                        actualFeatureId = feature.properties.FID;
                    } else if (feature.properties.ogc_fid !== undefined) {
                        actualFeatureId = feature.properties.ogc_fid;
                    }
                    // For cut polygons, use the original feature ID
                    else if (feature.properties.original_feature !== undefined) {
                        actualFeatureId = feature.properties.original_feature;
                    }
                    // For merged polygons, show merged info
                    else if (feature.properties.merged_features !== undefined) {
                        actualFeatureId = `M(${feature.properties.merged_features.length})`;
                    }
                }

                // Use feature.id as last resort
                if (feature.id !== undefined && feature.id !== null) {
                    actualFeatureId = feature.id;
                }

                // Convert GeoJSON geometry to OpenLayers geometry
                const olGeometry = new ol.format.GeoJSON().readGeometry(feature.geometry, {
                    dataProjection: 'EPSG:4326',
                    featureProjection: 'EPSG:3857'
                });

                const representativePoint = getRepresentativePoint(olGeometry);

                // Create point feature for annotation
                const pointFeature = new ol.Feature({
                    geometry: new ol.geom.Point(representativePoint),
                    index: actualFeatureId,
                    shapefileId: shapefileId,
                    layerType: layerType,
                    originalProperties: feature.properties
                });

                annotationSource.addFeature(pointFeature);
            });

            const annotationLayer = new ol.layer.Vector({
                source: annotationSource,
                style: function(feature) {
                    const index = feature.get('index');
                    return new ol.style.Style({
                        text: new ol.style.Text({
                            text: index.toString(),
                            font: 'bold 14px Arial',
                            fill: new ol.style.Fill({
                                color: layerType === 'processed' ? '#ff0000' : '#0000ff'
                            }),
                            stroke: new ol.style.Stroke({
                                color: '#ffffff',
                                width: 3
                            }),
                            offsetY: -15
                        })
                    });
                }
            });

            map.addLayer(annotationLayer);
            shapefileLayers[annotationKey] = annotationLayer;
        })
        .catch(error => {
            console.error('Error fetching GeoJSON for annotations:', error);
        });
}

// Annotation toggle functionality
const annotationToggleBtn = document.getElementById('annotation-toggle-btn');
let annotationsEnabled = false;

annotationToggleBtn.addEventListener('click', function() {
    annotationsEnabled = !annotationsEnabled;

    if (annotationsEnabled) {
        this.style.background = 'rgba(0, 123, 255, 0.2)';
        this.style.borderColor = '#007bff';
        updateAnnotations();
    } else {
        this.style.background = 'rgba(255, 255, 255, 0.9)';
        this.style.borderColor = '#ccc';
        // Remove all annotation layers
        const annotationLayers = Object.keys(shapefileLayers).filter(key => key.endsWith('_annotations'));
        annotationLayers.forEach(key => {
            map.removeLayer(shapefileLayers[key]);
            delete shapefileLayers[key];
        });
    }
});

// Initialize polygon cutting functionality
const polygonCutter = new PolygonCutter(map, selectInteraction);

// Cutting toggle functionality
const cuttingToggleBtn = document.getElementById('cutting-toggle-btn');
const cuttingPanel = document.getElementById('cutting-panel');

cuttingToggleBtn.addEventListener('click', function() {
    polygonCutter.isCuttingEnabled = !polygonCutter.isCuttingEnabled;

    if (polygonCutter.isCuttingEnabled) {
        this.style.background = 'rgba(220, 53, 69, 0.2)';
        this.style.borderColor = '#dc3545';
        this.style.color = '#dc3545';
        cuttingPanel.style.display = 'block';
        polygonCutter.activateCuttingMode();
    } else {
        this.style.background = 'rgba(255, 255, 255, 0.9)';
        this.style.borderColor = '#ccc';
        this.style.color = '';
        cuttingPanel.style.display = 'none';
        polygonCutter.deactivateCuttingMode();
    }

    updateCuttingDebug();
});

// Cutting panel button handlers
document.getElementById('cut-polygon-btn').addEventListener('click', function() {
    polygonCutter.executeCut();
    updateCuttingDebug();
});

document.getElementById('clear-cutting-btn').addEventListener('click', function() {
    polygonCutter.clearCutting();
    updateCuttingDebug();
});

document.getElementById('close-cutting-btn').addEventListener('click', function() {
    polygonCutter.isCuttingEnabled = false;
    cuttingToggleBtn.style.background = 'rgba(255, 255, 255, 0.9)';
    cuttingToggleBtn.style.borderColor = '#ccc';
    cuttingToggleBtn.style.color = '';
    cuttingPanel.style.display = 'none';
    polygonCutter.deactivateCuttingMode();
    updateCuttingDebug();
});

// Update cutting status display
function updateCuttingStatus() {
    const selectionStatus = document.getElementById('cutting-selection-status');
    const lineStatus = document.getElementById('cutting-line-status');
    const cutButton = document.getElementById('cut-polygon-btn');

    if (polygonCutter.selectedPolygon) {
        selectionStatus.innerHTML = `<span class="text-success">Polygon selected</span>`;
    } else {
        selectionStatus.innerHTML = `<span class="text-muted">No polygon selected</span>`;
    }

    if (polygonCutter.cutLinePoints.length > 0) {
        lineStatus.innerHTML = `<span class="text-info">${polygonCutter.cutLinePoints.length} line points</span>`;
    } else {
        lineStatus.innerHTML = `<span class="text-muted">No cut line drawn</span>`;
    }

    cutButton.disabled = !polygonCutter.selectedPolygon || polygonCutter.cutLinePoints.length < 2;
}

//// Listen for cutting events to update UI
//polygonCutter.on('selectionChanged', updateCuttingStatus);
//polygonCutter.on('lineChanged', updateCuttingStatus);
//polygonCutter.on('cutCompleted', function() {
//    updateCuttingStatus();
//    updateCuttingDebug();
//});
//
//// Initialize cutting status
//updateCuttingStatus();

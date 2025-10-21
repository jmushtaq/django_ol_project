class PolygonMerger {
    constructor(map, shapefileLayers, selectedFeatures, selectInteraction, showStatusMessage) {
        this.map = map;
        this.shapefileLayers = shapefileLayers;
        this.selectedFeatures = selectedFeatures;
        this.selectInteraction = selectInteraction;
        this.showStatusMessage = showStatusMessage;

        this.init();
    }

    init() {
        this.setupSelectionInteraction();
    }

    setupSelectionInteraction() {
        // Selection style
        this.selectStyle = new ol.style.Style({
            stroke: new ol.style.Stroke({
                color: 'yellow',
                width: 4
            }),
            fill: new ol.style.Fill({
                color: 'rgba(255, 255, 0, 0.3)'
            })
        });

        // Update selection handler to only process processed layer features
        this.selectInteraction.on('select', (e) => {
            this.handleSelection(e);
        });
    }

    handleSelection(e) {
        e.selected.forEach((feature) => {
            const shapefileId = feature.get('shapefileId');
            const featureId = feature.get('featureId');
            const layerType = feature.get('layerType');

            // Only allow selection from processed layers
            if (layerType === 'processed') {
                if (!this.selectedFeatures.has(shapefileId)) {
                    this.selectedFeatures.set(shapefileId, new Set());
                }
                this.selectedFeatures.get(shapefileId).add(featureId);
            } else {
                // Remove selection from original layers
                this.selectInteraction.getFeatures().remove(feature);
            }
        });

        e.deselected.forEach((feature) => {
            const shapefileId = feature.get('shapefileId');
            const featureId = feature.get('featureId');

            if (this.selectedFeatures.has(shapefileId)) {
                this.selectedFeatures.get(shapefileId).delete(featureId);
            }
        });

        this.updateAllSelectionInfo();
    }

    // Function to update selection info for all shapefiles
    updateAllSelectionInfo() {
        // Clear existing selection info
        document.querySelectorAll('.selection-info').forEach(el => el.remove());

        // Update for each shapefile with processed data
        this.selectedFeatures.forEach((selectedSet, shapefileId) => {
            const selectionCount = selectedSet.size;
            const hasProcessedLayer = this.shapefileLayers.hasOwnProperty(`${shapefileId}_processed`);

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
                            onclick="polygonMerger.mergeSelectedPolygons(${shapefileId})"
                            data-bs-toggle="tooltip"
                            data-bs-title="${tooltipText}">
                        Merge Selected
                    </button>
                    <button class="btn btn-secondary btn-sm mt-1" onclick="polygonMerger.clearSelection(${shapefileId})">
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
        const originalSelected = this.selectInteraction.getFeatures().getArray().some(feature =>
            feature.get('layerType') === 'original'
        );

        if (originalSelected) {
            this.showStatusMessage('Selection is only allowed from processed (red) layers', 'warning');
            // Clear selection from original layers
            const originalFeatures = this.selectInteraction.getFeatures().getArray().filter(feature =>
                feature.get('layerType') === 'original'
            );
            originalFeatures.forEach(feature => {
                this.selectInteraction.getFeatures().remove(feature);
            });
        }
    }

    // Function to merge selected polygons
    mergeSelectedPolygons(shapefileId) {
        const shapefileIdStr = shapefileId.toString();

        if (!this.selectedFeatures.has(shapefileIdStr) || this.selectedFeatures.get(shapefileIdStr).size < 2) {
            this.showStatusMessage('Please select at least 2 polygons to merge from the processed layer', 'warning');
            return;
        }

        const selectedIds = Array.from(this.selectedFeatures.get(shapefileIdStr));

        console.log(`Attempting to merge shapefile ${shapefileId}, features: ${selectedIds}`);

        // Use GET request with URL parameters
        const mergeUrl = `/shapefile/${shapefileId}/merge/?ids=${JSON.stringify(selectedIds)}`;
        console.log(`Sending GET to: ${mergeUrl}`);

        this.showStatusMessage(`Merging polygons ${selectedIds.join(', ')}...`, 'info');

        fetch(mergeUrl, {
            method: 'GET',
            headers: {
                'X-CSRFToken': this.getCookie('csrftoken')
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
                this.showStatusMessage(data.message, 'success');
                // Clear current selection
                this.clearSelection(shapefileId);

                // Reload the processed layer
                this.removeShapefile(shapefileId, 'processed');
                setTimeout(() => {
                    const processedCheckbox = document.getElementById(`layer${shapefileId}_processed`);
                    if (processedCheckbox) {
                        processedCheckbox.checked = true;
                        if (typeof loadShapefile === 'function') {
                            loadShapefile(shapefileId, 'processed');
                        }
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
                            if (typeof loadShapefile === 'function') {
                                loadShapefile(shapefileId, 'processed');
                            }
                        }
                    }
                }, 500);
            } else {
                this.showStatusMessage(data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('Merge error:', error);
            this.showStatusMessage('Error merging polygons: ' + error.message, 'danger');
        });
    }

    // Function to clear selection
    clearSelection(shapefileId) {
        const shapefileIdStr = shapefileId.toString();

        if (this.selectedFeatures.has(shapefileIdStr)) {
            this.selectedFeatures.get(shapefileIdStr).clear();

            // Clear selection from map
            const selectedFeaturesArray = this.selectInteraction.getFeatures().getArray();
            const featuresToDeselect = selectedFeaturesArray.filter(feature =>
                feature.get('shapefileId') === shapefileIdStr
            );

            featuresToDeselect.forEach(feature => {
                this.selectInteraction.getFeatures().remove(feature);
            });

            this.updateAllSelectionInfo();
            this.showStatusMessage('Selection cleared', 'info');
        }
    }

    // Function to remove shapefile layer
    removeShapefile(shapefileId, layerType = 'original') {
        const layerKey = `${shapefileId}_${layerType}`;
        if (this.shapefileLayers[layerKey]) {
            this.map.removeLayer(this.shapefileLayers[layerKey]);
            delete this.shapefileLayers[layerKey];

            // Also remove corresponding annotation layer
            const annotationKey = `${shapefileId}_${layerType}_annotations`;
            if (this.shapefileLayers[annotationKey]) {
                this.map.removeLayer(this.shapefileLayers[annotationKey]);
                delete this.shapefileLayers[annotationKey];
            }

            // Clear selection for this shapefile
            this.clearSelection(shapefileId);

            // Update annotations after removal
            if (typeof updateAnnotations === 'function') {
                updateAnnotations();
            }
        }
    }

    getCookie(name) {
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
}

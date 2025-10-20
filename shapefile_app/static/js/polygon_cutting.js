// Polygon Cutting Functionality
class PolygonCutter {
    constructor(map, shapefileLayers, selectedFeatures, selectInteraction, showStatusMessage) {
        this.map = map;
        this.shapefileLayers = shapefileLayers;
        this.selectedFeatures = selectedFeatures;
        this.selectInteraction = selectInteraction;
        this.showStatusMessage = showStatusMessage;

        this.isCuttingEnabled = false;
        this.selectedPolygon = null;
        this.cutLinePoints = [];
        this.cutLineLayer = null;
        this.cutLineSource = null;
        this.drawInteraction = null;

        // UI Elements
        this.cuttingToggleBtn = null;
        this.cuttingPanel = null;

        this.init();
    }

    init() {
        this.createCutLineLayer();
        this.setupEventListeners();
    }

    createCutLineLayer() {
        this.cutLineSource = new ol.source.Vector();
        this.cutLineLayer = new ol.layer.Vector({
            source: this.cutLineSource,
            style: new ol.style.Style({
                stroke: new ol.style.Stroke({
                    color: '#ff00ff',
                    width: 4,
                    lineDash: [5, 5]
                }),
                image: new ol.style.Circle({
                    radius: 6,
                    fill: new ol.style.Fill({
                        color: '#ff00ff'
                    }),
                    stroke: new ol.style.Stroke({
                        color: '#ffffff',
                        width: 2
                    })
                })
            }),
            zIndex: 1001
        });
    }

    setupEventListeners() {
        // Get UI elements from map.html
        this.cuttingToggleBtn = document.getElementById('cutting-toggle-btn');
        this.cuttingPanel = document.getElementById('cutting-panel');
        this.cutPolygonBtn = document.getElementById('cut-polygon-btn');
        this.clearCuttingBtn = document.getElementById('clear-cutting-btn');
        this.closeCuttingBtn = document.getElementById('close-cutting-btn');
        this.cuttingSelectionStatus = document.getElementById('cutting-selection-status');
        this.cuttingLineStatus = document.getElementById('cutting-line-status');

        // Add event listeners
        this.cuttingToggleBtn.addEventListener('click', () => {
            this.toggleCuttingMode();
        });

        this.cutPolygonBtn.addEventListener('click', () => {
            this.executeCut();
        });

        this.clearCuttingBtn.addEventListener('click', () => {
            this.clearCutting();
        });

        this.closeCuttingBtn.addEventListener('click', () => {
            this.disableCuttingMode();
        });
    }

    toggleCuttingMode() {
        if (this.isCuttingEnabled) {
            this.disableCuttingMode();
        } else {
            this.enableCuttingMode();
        }
    }

    enableCuttingMode() {
        this.isCuttingEnabled = true;
        this.cuttingToggleBtn.style.background = 'rgba(220, 53, 69, 0.9)';
        this.cuttingToggleBtn.style.color = 'white';
        this.cuttingToggleBtn.title = 'Disable Polygon Cutting';
        this.cuttingPanel.style.display = 'block';

        this.map.addLayer(this.cutLineLayer);
        this.setupCuttingInteractions();

        this.showStatusMessage('Polygon cutting enabled. Select a polygon from processed layer.', 'info');
    }

    disableCuttingMode() {
        this.isCuttingEnabled = false;
        this.cuttingToggleBtn.style.background = 'rgba(255, 255, 255, 0.9)';
        this.cuttingToggleBtn.style.color = 'inherit';
        this.cuttingToggleBtn.title = 'Enable Polygon Cutting';
        this.cuttingPanel.style.display = 'none';

        this.cleanupCuttingInteractions();
        this.map.removeLayer(this.cutLineLayer);
        this.clearCutting();

        this.showStatusMessage('Polygon cutting disabled', 'info');
    }

    setupCuttingInteractions() {
        // Override the select interaction to prevent deselection
        this.originalSelectHandler = this.selectInteraction.getFeatures().on('add', (evt) => {
            this.handlePolygonSelection(evt.element);
        });

        // Add click interaction for drawing cut lines anywhere on map
        this.mapClickHandler = (evt) => {
            this.handleMapClick(evt);
        };
        this.map.on('click', this.mapClickHandler);

        // Use existing select interaction for polygon selection
        this.selectInteraction.setActive(true);
    }

    cleanupCuttingInteractions() {
        // Remove event listeners
        if (this.mapClickHandler) {
            this.map.un('click', this.mapClickHandler);
        }

        // Restore original select behavior
        if (this.originalSelectHandler) {
            this.selectInteraction.getFeatures().un('add', this.originalSelectHandler);
        }

        // Clear current selection
        if (this.selectedPolygon) {
            this.selectInteraction.getFeatures().remove(this.selectedPolygon);
            this.selectedPolygon = null;
        }
    }

    handlePolygonSelection(feature) {
        if (!this.isCuttingEnabled) return;

        // Only allow selection from processed layers
        if (feature.get('layerType') !== 'processed') {
            // Remove non-processed features from selection
            this.selectInteraction.getFeatures().remove(feature);
            return;
        }

        // If we already have a selected polygon, keep it and don't select new one
        if (this.selectedPolygon && this.selectedPolygon !== feature) {
            this.selectInteraction.getFeatures().remove(feature);
            return;
        }

        // Select the new polygon
        this.selectedPolygon = feature;
        this.updateSelectionStatus();
        this.clearCutLine();

        this.showStatusMessage(`Polygon ${feature.get('featureId')} selected for cutting`, 'info');
    }

    handleMapClick(evt) {
        if (!this.isCuttingEnabled) return;

        const coordinate = evt.coordinate;

        // Check if we have a selected polygon
        if (!this.selectedPolygon) {
            this.showStatusMessage('Please select a polygon first by clicking on it', 'warning');
            return;
        }

        // Allow clicks anywhere on the map to add cut line points
        this.addCutLinePoint(coordinate);
    }

    addCutLinePoint(coordinate) {
        this.cutLinePoints.push(coordinate);

        // Update the cut line
        this.updateCutLine();

        // Update UI status
        this.updateLineStatus();

        // Enable cut button if we have at least 2 points
        if (this.cutLinePoints.length >= 2) {
            this.cutPolygonBtn.disabled = false;
        }

        this.showStatusMessage(`Point ${this.cutLinePoints.length} placed`, 'info');
    }

    updateCutLine() {
        // Clear existing features
        this.cutLineSource.clear();

        if (this.cutLinePoints.length > 0) {
            // Add points
            this.cutLinePoints.forEach(point => {
                const pointFeature = new ol.Feature({
                    geometry: new ol.geom.Point(point)
                });
                this.cutLineSource.addFeature(pointFeature);
            });

            // Add line if we have at least 2 points
            if (this.cutLinePoints.length >= 2) {
                const lineFeature = new ol.Feature({
                    geometry: new ol.geom.LineString(this.cutLinePoints)
                });
                this.cutLineSource.addFeature(lineFeature);
            }
        }
    }

    updateSelectionStatus() {
        if (this.selectedPolygon) {
            const featureId = this.selectedPolygon.get('featureId');
            this.cuttingSelectionStatus.innerHTML = `<span class="text-success"><strong>Polygon ${featureId} selected</strong></span>`;
        } else {
            this.cuttingSelectionStatus.innerHTML = '<span class="text-muted">No polygon selected</span>';
        }
    }

    updateLineStatus() {
        if (this.cutLinePoints.length === 0) {
            this.cuttingLineStatus.innerHTML = '<span class="text-muted">No cut line drawn</span>';
        } else if (this.cutLinePoints.length === 1) {
            this.cuttingLineStatus.innerHTML = '<span class="text-warning">1 point placed - click for second point</span>';
        } else {
            this.cuttingLineStatus.innerHTML = `<span class="text-success">${this.cutLinePoints.length} points - ready to cut</span>`;
        }
    }

    clearCutLine() {
        this.cutLinePoints = [];
        this.cutLineSource.clear();
        this.updateLineStatus();
        this.cutPolygonBtn.disabled = true;
    }

    clearCutting() {
        if (this.selectedPolygon) {
            this.selectInteraction.getFeatures().remove(this.selectedPolygon);
            this.selectedPolygon = null;
        }
        this.clearCutLine();
        this.updateSelectionStatus();
        this.showStatusMessage('Cutting cleared', 'info');
    }

    async executeCut() {
        if (!this.selectedPolygon || this.cutLinePoints.length < 2) {
            this.showStatusMessage('Please select a polygon and draw a cut line with at least 2 points', 'warning');
            return;
        }

        const shapefileId = this.selectedPolygon.get('shapefileId');
        const featureId = this.selectedPolygon.get('featureId');

        this.showStatusMessage(`Cutting polygon ${featureId}...`, 'info');

        // Disable cut button during operation
        this.cutPolygonBtn.disabled = true;

        try {
            // Convert coordinates to WGS84 for backend
            const cutLineWGS84 = this.cutLinePoints.map(coord =>
                ol.proj.toLonLat(coord)
            );

            const response = await fetch(`/shapefile/${shapefileId}/cut_polygon/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCookie('csrftoken')
                },
                body: JSON.stringify({
                    feature_id: featureId,
                    cut_line: cutLineWGS84
                })
            });

            const data = await response.json();

            if (data.success) {
                this.showStatusMessage(data.message, 'success');
                this.clearCutting();

                // Reload the processed layer to show the cut result
                this.reloadProcessedLayer(shapefileId);

            } else {
                this.showStatusMessage('Error: ' + data.message, 'danger');
                this.cutPolygonBtn.disabled = false;
            }

        } catch (error) {
            console.error('Cut error:', error);
            this.showStatusMessage('Error cutting polygon: ' + error.message, 'danger');
            this.cutPolygonBtn.disabled = false;
        }
    }

    reloadProcessedLayer(shapefileId) {
        // Remove and reload the processed layer
        if (this.shapefileLayers[`${shapefileId}_processed`]) {
            this.map.removeLayer(this.shapefileLayers[`${shapefileId}_processed`]);
            delete this.shapefileLayers[`${shapefileId}_processed`];

            // Trigger reload
            setTimeout(() => {
                const processedCheckbox = document.getElementById(`layer${shapefileId}_processed`);
                if (processedCheckbox && processedCheckbox.checked) {
                    if (typeof loadShapefile === 'function') {
                        loadShapefile(shapefileId, 'processed');
                    }
                }
            }, 500);
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

let streams = [];
let currentStream = null;
let zones = [];
let isDrawing = false;
let startX, startY;
let canvas, ctx;
let capturedImage = null;
let liveVideo = null;
let isLiveMode = true;

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    canvas = document.getElementById('videoCanvas');
    if (!canvas) {
        console.error('Canvas not found');
        return;
    }
    ctx = canvas.getContext('2d');
    liveVideo = document.getElementById('liveVideo');

    // Update canvas size when video loads
    liveVideo.onload = function() {
        canvas.width = liveVideo.naturalWidth || liveVideo.width;
        canvas.height = liveVideo.naturalHeight || liveVideo.height;
        canvas.style.width = liveVideo.width + 'px';
        canvas.style.height = liveVideo.height + 'px';
        redrawCanvas();
    };

    // Load streams
    await loadStreams();

    // Setup event listeners
    setupEventListeners();

    // Load current stream settings
    if (streams.length > 0) {
        loadStreamSettings(streams[0].id);
    }
});

async function loadStreams() {
    try {
        const response = await fetch('/api/settings');
        const config = await response.json();
        streams = config.streams || [];
        
        const select = document.getElementById('cameraSelect');
        select.innerHTML = '';
        if (streams.length === 0) {
            const option = document.createElement('option');
            option.textContent = 'No cameras available';
            option.disabled = true;
            select.appendChild(option);
            return;
        }

        streams.forEach(stream => {
            const option = document.createElement('option');
            option.value = stream.id;
            option.textContent = stream.name;
            select.appendChild(option);
        });
        
        // Set zone mode
        document.getElementById('zoneMode').value = config.zone_mode || 'all';
    } catch (error) {
        showNotification('Failed to load cameras: ' + error.message, 'danger');
    }
}

function setupEventListeners() {
    // Canvas drawing
    canvas.addEventListener('mousedown', startDrawing);
    canvas.addEventListener('mousemove', draw);
    canvas.addEventListener('mouseup', stopDrawing);
    canvas.addEventListener('mouseleave', stopDrawing);
    
    // Buttons
    document.getElementById('captureBtn').addEventListener('click', captureFrame);
    document.getElementById('clearZonesBtn').addEventListener('click', clearZones);
    document.getElementById('saveZonesBtn').addEventListener('click', saveZones);
    
    // Camera select
    document.getElementById('cameraSelect').addEventListener('change', (e) => {
        loadStreamSettings(e.target.value);
    });
    
    // Sliders
    document.getElementById('sensitivitySlider').addEventListener('input', (e) => {
        document.getElementById('sensitivityValue').textContent = e.target.value;
    });
    document.getElementById('retriggerSlider').addEventListener('input', (e) => {
        document.getElementById('retriggerValue').textContent = e.target.value;
    });
    document.getElementById('maxClipSlider').addEventListener('input', (e) => {
        document.getElementById('maxClipValue').textContent = e.target.value;
    });
    document.getElementById('preRecordSlider').addEventListener('input', (e) => {
        document.getElementById('preRecordValue').textContent = e.target.value;
    });
}

function startLiveStream(streamId) {
    const stream = streams.find(s => s.id === streamId);
    if (!stream || !stream.rtsp_url) {
        liveVideo.src = '/static/img/no-signal.svg';
        return;
    };

    isLiveMode = true;
    capturedImage = null;

    // Start live MJPEG stream
    const streamUrl = `/api/stream_proxy?rtsp_url=${encodeURIComponent(stream.rtsp_url)}&t=${Date.now()}`;
    liveVideo.src = streamUrl;
    liveVideo.style.display = 'block';

    // Make canvas transparent and overlay on top
    canvas.style.background = 'transparent';

    document.getElementById('captureBtn').innerHTML = '<i class="fas fa-camera"></i> Freeze Frame';
}

async function captureFrame() {
    if (isLiveMode) {
        // Freeze the current frame
        isLiveMode = false;

        // Stop live stream
        liveVideo.style.display = 'none';

        // Capture current frame to canvas
        document.getElementById('captureBtn').disabled = true;
        document.getElementById('captureBtn').innerHTML = '<i class="fas fa-spinner fa-spin"></i> Capturing...';

        try {
            const streamId = document.getElementById('cameraSelect').value;
            const response = await fetch(`/api/camera_snapshot/${streamId}`);
            const result = await response.json();

            if (result.success) {
                const img = new Image();
                img.onload = () => {
                    canvas.width = result.width;
                    canvas.height = result.height;
                    ctx.drawImage(img, 0, 0);
                    capturedImage = ctx.getImageData(0, 0, canvas.width, canvas.height);
                    canvas.style.background = '#000';
                    redrawCanvas();
                };
                img.src = result.image;
            } else {
                showNotification('Failed to capture frame: ' + (result.error || 'Unknown error'), 'danger');
                // Go back to live mode
                isLiveMode = true;
                liveVideo.style.display = 'block';
            }
        } catch (error) {
            showNotification('Error capturing frame: ' + error.message, 'danger');
            // Go back to live mode
            isLiveMode = true;
            liveVideo.style.display = 'block';
        } finally {
            document.getElementById('captureBtn').disabled = false;
            document.getElementById('captureBtn').innerHTML = '<i class="fas fa-video"></i> Resume Live';
        }
    } else {
        // Resume live stream
        const streamId = document.getElementById('cameraSelect').value;
        startLiveStream(streamId);
    }
}

function startDrawing(e) {
    isDrawing = true;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    startX = (e.clientX - rect.left) * scaleX;
    startY = (e.clientY - rect.top) * scaleY;
}

function draw(e) {
    if (!isDrawing) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const currentX = (e.clientX - rect.left) * scaleX;
    const currentY = (e.clientY - rect.top) * scaleY;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Redraw image if in frozen mode
    if (capturedImage) {
        ctx.putImageData(capturedImage, 0, 0);
    }
    drawExistingZones();

    // Draw current rectangle
    ctx.strokeStyle = '#0EA5E9'; // Use primary color
    ctx.lineWidth = 2;
    ctx.strokeRect(startX, startY, currentX - startX, currentY - startY);
}

function stopDrawing(e) {
    if (!isDrawing) return;
    isDrawing = false;

    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const endX = (e.clientX - rect.left) * scaleX;
    const endY = (e.clientY - rect.top) * scaleY;

    const x = Math.min(startX, endX);
    const y = Math.min(startY, endY);
    const w = Math.abs(endX - startX);
    const h = Math.abs(endY - startY);

    // Only add zone if it has some size
    if (w > 10 && h > 10) {
        zones.push({
            x: x / canvas.width,
            y: y / canvas.height,
            w: w / canvas.width,
            h: h / canvas.height
        });
        updateZonesList();
        redrawCanvas();
    }
}

function drawExistingZones() {
    zones.forEach((zone, index) => {
        const x = zone.x * canvas.width;
        const y = zone.y * canvas.height;
        const w = zone.w * canvas.width;
        const h = zone.h * canvas.height;
        
        ctx.strokeStyle = '#0EA5E9'; // Primary color
        ctx.fillStyle = 'rgba(14, 165, 233, 0.2)'; // Primary color with alpha
        ctx.lineWidth = 2;
        ctx.fillRect(x, y, w, h);
        ctx.strokeRect(x, y, w, h);
        
        // Draw label
        ctx.fillStyle = '#0EA5E9';
        ctx.font = 'bold 14px Arial';
        ctx.fillText(`Zone ${index + 1}`, x + 5, y + 20);
    });
}

function redrawCanvas() {
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (capturedImage) {
        ctx.putImageData(capturedImage, 0, 0);
    }
    drawExistingZones();
}

function clearZones() {
    if (confirm('Clear all detection zones?')) {
        zones = [];
        updateZonesList();
        redrawCanvas();
    }
}

function updateZonesList() {
    const list = document.getElementById('zonesList');
    const count = document.getElementById('zoneCount');
    if(count) count.textContent = zones.length;
    
    if (zones.length === 0) {
        list.innerHTML = '<div class="list-group-item text-muted" style="background: var(--bg-tertiary); border-color: var(--border-color);"><small>No zones defined. Draw on the canvas to add zones.</small></div>';
        return;
    }
    
    list.innerHTML = zones.map((zone, i) => `
        <div class="list-group-item d-flex justify-content-between align-items-center" style="background: var(--bg-tertiary); border-color: var(--border-color); color: var(--text-secondary);">
            <span>Zone ${i + 1}</span>
            <button class="btn btn-sm btn-danger" onclick="removeZone(${i})" style="background: var(--danger-color); border: none;">
                <i class="fas fa-trash"></i>
            </button>
        </div>
    `).join('');
}

function removeZone(index) {
    zones.splice(index, 1);
    updateZonesList();
    redrawCanvas();
}

async function loadStreamSettings(streamId) {
    currentStream = streams.find(s => s.id === streamId);
    if (!currentStream) return;

    const camName = document.getElementById('cameraName');
    if(camName) camName.textContent = currentStream.name;

    // Load zones
    const zoneMode = document.getElementById('zoneMode').value;
    if (zoneMode === 'individual') {
        zones = currentStream.motion_zones || [];
    } else {
        try {
            const response = await fetch('/api/settings');
            const config = await response.json();
            zones = config.motion_zones || [];
        } catch(e) {
            showNotification('Could not load global zones', 'danger');
        }
    }

    // Load other settings
    document.getElementById('sensitivitySlider').value = currentStream.motion_sensitivity || 100;
    document.getElementById('sensitivityValue').textContent = currentStream.motion_sensitivity || 100;

    document.getElementById('retriggerSlider').value = currentStream.retrigger_time || 5;
    document.getElementById('retriggerValue').textContent = currentStream.retrigger_time || 5;

    document.getElementById('maxClipSlider').value = currentStream.max_clip_length || 300;
    document.getElementById('maxClipValue').textContent = currentStream.max_clip_length || 300;

    document.getElementById('preRecordSlider').value = currentStream.pre_record_buffer || 0;
    document.getElementById('preRecordValue').textContent = currentStream.pre_record_buffer || 0;

    updateZonesList();
    redrawCanvas();

    // Start live stream
    startLiveStream(streamId);
}

async function saveZones() {
    const streamId = document.getElementById('cameraSelect').value;
    if (!streamId) {
        showNotification('Please select a camera first.', 'warning');
        return;
    }
    const zoneMode = document.getElementById('zoneMode').value;
    const sensitivity = parseInt(document.getElementById('sensitivitySlider').value);
    const retriggerTime = parseInt(document.getElementById('retriggerSlider').value);
    const maxClipLength = parseInt(document.getElementById('maxClipSlider').value);
    const preRecordBuffer = parseInt(document.getElementById('preRecordSlider').value);
    
    try {
        const response = await fetch('/api/zone_settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                stream_id: streamId,
                zone_mode: zoneMode,
                zones: zones,
                motion_sensitivity: sensitivity,
                retrigger_time: retriggerTime,
                max_clip_length: maxClipLength,
                pre_record_buffer: preRecordBuffer
            })
        });
        
        const result = await response.json();
        if (result.success) {
            showNotification('Settings saved successfully!', 'success');
        } else {
            showNotification('Error: ' + (result.error || 'Unknown error'), 'danger');
        }
    } catch (error) {
        showNotification('Failed to save settings: ' + error.message, 'danger');
    }
}

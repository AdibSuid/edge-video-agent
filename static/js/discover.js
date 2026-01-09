// Auto-detect and populate subnet on page load
window.addEventListener('DOMContentLoaded', () => {
    // Try to get local network subnet automatically
    fetch('/api/get_local_subnet')
        .then(r => r.json())
        .then(data => {
            if (data.success && data.subnet) {
                const subnetEl = document.getElementById('subnet');
                if (subnetEl) subnetEl.value = data.subnet;
            }
        })
        .catch(() => {
            // Keep default value if detection fails
        });
});

async function startDiscovery() {
    const btn = document.getElementById('discoverBtn');
    if (!btn) return;
    btn.classList.add('scanning');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Starting Discovery...';

    try {
        const response = await fetch('/api/discover', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });

        const data = await response.json();

        if (data.success) {
            displayCameras(data.cameras);
            if (data.filtered_count > 0) {
                const msg = `Note: ${data.filtered_count} camera(s) already added to the system were hidden from the list.`;
                showNotification(msg, 'info');
            }
            if(data.cameras.length == 0) {
                 showNotification('No new cameras found.', 'info');
            }
        } else {
            showNotification('Discovery Failed: ' + data.error, 'danger');
        }
    } catch (error) {
        showNotification('Discovery Error: ' + error.toString(), 'danger');
    } finally {
        btn.classList.remove('scanning');
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-search"></i> Start Discovery';
    }
}

async function startScan() {
    const btn = document.getElementById('scanBtn');
    const subnet = document.getElementById('subnet').value;
    if (!btn) return;
    
    btn.classList.add('scanning');
    btn.disabled = true;
     btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Scanning...';


    try {
        const response = await fetch('/api/scan_network', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ subnet: subnet })
        });

        const data = await response.json();

        if (data.success) {
            const cameras = data.ips.map(ip => ({
                ip: ip,
                name: `Device ${ip}`,
                manufacturer: 'Unknown'
            }));
            displayCameras(cameras);
             if(cameras.length == 0) {
                 showNotification('No devices found on this subnet.', 'info');
            }
        } else {
            showNotification('Scan Failed: ' + data.error, 'danger');
        }
    } catch (error) {
        showNotification('Scan Error: ' + error.toString(), 'danger');
    } finally {
        btn.classList.remove('scanning');
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-wifi"></i> Scan Subnet';
    }
}

function displayCameras(cameras) {
    const list = document.getElementById('camerasList');
    const count = document.getElementById('cameraCount');

    if (count) count.textContent = cameras.length;

    if (cameras.length === 0) {
        list.innerHTML = `<div class="empty-state" style="padding: 40px; text-align: center;">
            <i class="fas fa-video-slash" style="font-size: 48px; color: var(--text-muted); margin-bottom: 16px;"></i>
            <h5 style="color: var(--text-primary);">No Cameras Found</h5>
            <p style="color: var(--text-muted);">Try another scan or check your network connection.</p>
        </div>`;
        return;
    }

    list.innerHTML = cameras.map(cam => `
        <div class="camera-list-item">
            <div class="camera-icon">
                <i class="fas fa-video"></i>
            </div>
            <div class="camera-details">
                <div class="camera-name">${cam.name || cam.ip}</div>
                <div class="camera-meta">
                    <span>IP: ${cam.ip}${cam.port ? ':' + cam.port : ''}</span>
                    <span>Manufacturer: ${cam.manufacturer || 'Unknown'}</span>
                    ${cam.model ? `<span>Model: ${cam.model}</span>` : ''}
                </div>
            </div>
            <div class="camera-actions">
                <button class="btn-camera-action" 
                        onclick="showCameraModal('view', '${cam.ip}', '${cam.port || 80}', '${cam.name || cam.ip}')">
                    <i class="fas fa-eye"></i> View
                </button>
                <button class="btn-camera-action primary" 
                        onclick="showCameraModal('add', '${cam.ip}', '${cam.port || 80}', '${cam.name || cam.ip}')">
                    <i class="fas fa-plus"></i> Add
                </button>
            </div>
        </div>
    `).join('');
}


// Show modal for camera actions
let cameraAction = null;
function showCameraModal(action, ip, port, name) {
    cameraAction = action;
    document.getElementById('modalCameraIp').value = ip;
    document.getElementById('modalCameraPort').value = port;
    document.getElementById('modalCameraName').value = name;
    
    const camId = `cam-${ip.replace(/\./g, '-')}`;
    document.getElementById('modalCameraId').value = action === 'add' ? camId : '';
    document.getElementById('modalUsername').value = '';
    document.getElementById('modalPassword').value = '';
    
    // Show/hide Camera ID field based on action
    document.getElementById('cameraIdField').style.display = action === 'add' ? 'block' : 'none';
    document.getElementById('modalAddBtn').style.display = action === 'add' ? 'inline-block' : 'none';
    document.getElementById('modalViewBtn').style.display = action === 'view' ? 'inline-block' : 'none';

    if (action === 'add') {
        document.getElementById('cameraModalLabel').innerHTML = '<i class="fas fa-plus-circle"></i> Add Camera';
    } else {
        document.getElementById('cameraModalLabel').innerHTML = '<i class="fas fa-eye"></i> View Stream';
    }
    
    const modal = new bootstrap.Modal(document.getElementById('cameraModal'));
    modal.show();
}

// Modal Add Camera
document.getElementById('modalAddBtn').onclick = async function() {
    const ip = document.getElementById('modalCameraIp').value;
    const port = document.getElementById('modalCameraPort').value;
    const name = document.getElementById('modalCameraName').value;
    const cameraId = document.getElementById('modalCameraId').value;
    const username = document.getElementById('modalUsername').value;
    const password = document.getElementById('modalPassword').value;
    
    if (!username || !password) {
        showNotification('Please enter username and password', 'warning');
        return;
    }
    
    // Disable button and show loading
    const btn = document.getElementById('modalAddBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Retrieving stream...';
    
    let rtspUrl = null;
    let errorMsg = null;
    
    // Try ONVIF to get RTSP URL automatically
    try {
        const response = await fetch('/api/onvif_rtsp_uri', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ ip, port, username, password })
        });
        const data = await response.json();
        
        if (data.success && data.rtsp_url) {
            rtspUrl = data.rtsp_url;
        } else {
            errorMsg = data.error || 'Failed to get RTSP URL via ONVIF';
            if (response.status === 401) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-plus"></i> Add Camera';
                showNotification('Authentication Failed. Please check credentials.', 'danger');
                return;
            }
        }
    } catch (err) {
        errorMsg = err.toString();
    }
    
    if (!rtspUrl) {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-plus"></i> Add Camera';
        showNotification(`Connection Failed: ${errorMsg}`, 'danger');
        return;
    }
    
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Adding camera...';
    await addStream(cameraId, name, rtspUrl);
    
    bootstrap.Modal.getInstance(document.getElementById('cameraModal')).hide();
    btn.disabled = false;
    btn.innerHTML = '<i class="fas fa-plus"></i> Add Camera';
};

// Modal View Stream
document.getElementById('modalViewBtn').onclick = async function() {
    const ip = document.getElementById('modalCameraIp').value;
    const port = document.getElementById('modalCameraPort').value;
    const name = document.getElementById('modalCameraName').value;
    const username = document.getElementById('modalUsername').value;
    const password = document.getElementById('modalPassword').value;
    
    if (!username || !password) {
        showNotification('Please enter username and password', 'warning');
        return;
    }
    
    const btn = document.getElementById('modalViewBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Connecting...';
    
    let rtspUrl = null;
    let errorMsg = null;
    
    try {
        const response = await fetch('/api/onvif_rtsp_uri', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ ip, port, username, password })
        });
        const data = await response.json();
        
        if (data.success && data.rtsp_url) {
            rtspUrl = data.rtsp_url;
        } else {
            errorMsg = data.error || 'Failed to retrieve stream';
            if (response.status === 401) {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-video"></i> View Stream';
                showNotification('Authentication Failed. Invalid credentials.', 'danger');
                return;
            }
        }
    } catch (err) {
        errorMsg = err.toString();
    }
    
    if (!rtspUrl) {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-video"></i> View Stream';
        showNotification(`Connection Failed: ${errorMsg}`, 'danger');
        return;
    }
    
    bootstrap.Modal.getInstance(document.getElementById('cameraModal')).hide();
    btn.disabled = false;
    btn.innerHTML = '<i class="fas fa-video"></i> View Stream';
    
    openStreamViewer(name, rtspUrl);
};

function openStreamViewer(cameraName, rtspUrl) {
    document.getElementById('streamCameraName').textContent = cameraName;
    
    document.getElementById('streamLoadingIndicator').style.display = 'block';
    document.getElementById('streamContainer').style.display = 'none';
    document.getElementById('streamError').style.display = 'none';
    
    const streamModal = new bootstrap.Modal(document.getElementById('streamViewerModal'));
    streamModal.show();
    
    testAndStartStream(rtspUrl);
}

async function testAndStartStream(rtspUrl) {
    try {
        const testResponse = await fetch('/api/test_stream', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ rtsp_url: rtspUrl })
        });
        
        const testData = await testResponse.json();
        
        if (!testData.success || !testData.valid) {
            document.getElementById('streamLoadingIndicator').style.display = 'none';
            document.getElementById('streamError').style.display = 'block';
            document.getElementById('streamErrorMessage').textContent = 'Stream test failed: ' + (testData.error || 'Camera not accessible');
            return;
        }
        
        const streamUrl = `/api/stream_proxy?rtsp_url=${encodeURIComponent(rtspUrl)}&t=${Date.now()}`;
        const streamImg = document.getElementById('streamImage');
        
        streamImg.onload = function() {
            document.getElementById('streamLoadingIndicator').style.display = 'none';
            document.getElementById('streamContainer').style.display = 'block';
        };
        
        streamImg.onerror = function() {
            document.getElementById('streamLoadingIndicator').style.display = 'none';
            document.getElementById('streamError').style.display = 'block';
            document.getElementById('streamErrorMessage').textContent = 'Failed to load stream. Please check camera connection.';
        };
        
        streamImg.src = streamUrl;
        
    } catch (error) {
        document.getElementById('streamLoadingIndicator').style.display = 'none';
        document.getElementById('streamError').style.display = 'block';
        document.getElementById('streamErrorMessage').textContent = 'Error: ' + error.toString();
    }
}

document.getElementById('streamViewerModal').addEventListener('hidden.bs.modal', function() {
    const streamImg = document.getElementById('streamImage');
    streamImg.src = '';
});

async function addStream(cameraId, name, rtspUrl) {
    try {
        const payload = { id: cameraId, name, rtsp_url: rtspUrl };
        const response = await fetch('/api/add_stream', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (data.success) {
            showNotification('Camera added successfully! Redirecting...', 'success');
            setTimeout(() => { window.location.href = '/'; }, 1500);
        } else {
            showNotification('Failed to add camera: ' + data.error, 'danger');
        }
    } catch (error) {
        showNotification('Error adding camera: ' + error.toString(), 'danger');
    }
}

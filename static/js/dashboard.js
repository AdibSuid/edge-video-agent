// dashboard.js - Frontend logic for Edge Agent Dashboard

let uploadChart = null;

// Initialize dashboard
document.addEventListener('DOMContentLoaded', function() {
    initUploadChart();
    updateNetworkStatus();
    updateMotionStatus();
    
    // Refresh every 2 seconds
    setInterval(updateNetworkStatus, 2000);
    setInterval(updateMotionStatus, 2000);
});

// Initialize upload speed chart
function initUploadChart() {
    const ctx = document.getElementById('uploadChart');
    if (!ctx) return;
    
    uploadChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Upload Speed (Mbps)',
                data: [],
                borderColor: 'rgb(75, 192, 192)',
                backgroundColor: 'rgba(75, 192, 192, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                x: {
                    display: false
                },
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Mbps'
                    }
                }
            }
        }
    });
}

// Update network status
async function updateNetworkStatus() {
    try {
        const response = await fetch('/api/network_status');
        const data = await response.json();
        
        // Update speed display
        const speedElement = document.getElementById('uploadSpeed');
        if (speedElement) {
            speedElement.textContent = data.upload_mbps.toFixed(2) + ' Mbps';
        }
        
        // Update status badge
        const statusElement = document.getElementById('networkStatus');
        if (statusElement) {
            if (data.is_slow) {
                statusElement.className = 'badge bg-warning';
                statusElement.textContent = 'Slow Connection';
            } else {
                statusElement.className = 'badge bg-success';
                statusElement.textContent = 'Good Connection';
            }
        }
        
        // Update chart
        if (uploadChart && data.history && data.history.length > 0) {
            uploadChart.data.labels = data.history.map(h => {
                const time = new Date(h.timestamp);
                return time.toLocaleTimeString();
            });
            uploadChart.data.datasets[0].data = data.history.map(h => h.mbps);
            uploadChart.update('none'); // Update without animation for better performance
        }
        
    } catch (error) {
        console.error('Failed to update network status:', error);
    }
}

// Update motion status for all streams
async function updateMotionStatus() {
    try {
        const response = await fetch('/api/motion_status');
        const data = await response.json();
        
        let activeCount = 0;
        let motionCount = 0;
        
        // Update each stream card
        for (const [streamId, status] of Object.entries(data)) {
            const card = document.getElementById(`stream-${streamId}`);
            if (card) {
                activeCount++;
                
                const motionStatus = card.querySelector('.motion-status');
                if (status.active) {
                    card.classList.remove('motion-idle');
                    card.classList.add('motion-active');
                    motionStatus.className = 'badge bg-success motion-status';
                    motionStatus.textContent = `Motion (${status.fps}fps)`;
                    motionCount++;
                } else {
                    card.classList.remove('motion-active');
                    card.classList.add('motion-idle');
                    motionStatus.className = 'badge bg-secondary motion-status';
                    motionStatus.textContent = `Idle (${status.fps}fps)`;
                }
            }
        }
        
        // Update counters
        const activeElement = document.getElementById('activeStreams');
        if (activeElement) {
            activeElement.textContent = activeCount;
        }
        
        const motionElement = document.getElementById('motionStreams');
        if (motionElement) {
            motionElement.textContent = motionCount;
        }
        
    } catch (error) {
        console.error('Failed to update motion status:', error);
    }
}

// Update cloud upload status
async function updateCloudUploadStatus() {
    try {
        const response = await fetch('/api/cloud_upload_status');
        const data = await response.json();
        
        const statusElement = document.getElementById('cloudUploadStatus');
        const queueElement = document.getElementById('cloudUploadQueue');
        
        if (statusElement) {
            if (data.enabled && data.authenticated) {
                statusElement.className = 'badge bg-success';
                statusElement.textContent = 'Connected';
            } else if (data.enabled && !data.authenticated) {
                statusElement.className = 'badge bg-warning';
                statusElement.textContent = 'Auth Failed';
            } else {
                statusElement.className = 'badge bg-secondary';
                statusElement.textContent = 'Disabled';
            }
        }
        
        if (queueElement) {
            queueElement.textContent = data.queue_size || 0;
        }
        
    } catch (error) {
        console.error('Failed to update cloud upload status:', error);
    }
}

// Remove stream
async function removeStream(streamId) {
    if (!confirm('Remove this camera?')) {
        return;
    }
    
    try {
        const response = await fetch('/api/remove_stream', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ stream_id: streamId })
        });
        
        const data = await response.json();
        
        if (data.success) {
            window.location.reload();
        } else {
            alert('Failed to remove camera: ' + data.error);
        }
    } catch (error) {
        alert('Error removing camera: ' + error);
    }
}

// Toggle stream enable/disable
async function toggleStream(streamId, button) {
    const currentEnabled = button.dataset.enabled === 'true';
    const newEnabled = !currentEnabled;
    
    try {
        const response = await fetch('/api/toggle_stream', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                stream_id: streamId,
                enabled: newEnabled
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            button.dataset.enabled = newEnabled.toString();
            button.innerHTML = `<i class="fas fa-power-off"></i> ${newEnabled ? 'Disable' : 'Enable'}`;
            
            // Update card appearance
            const card = document.getElementById(`stream-${streamId}`);
            if (card) {
                if (newEnabled) {
                    card.style.opacity = '1';
                } else {
                    card.style.opacity = '0.6';
                }
            }
        } else {
            alert('Failed to toggle camera: ' + data.error);
        }
    } catch (error) {
        alert('Error toggling camera: ' + error);
    }
}

// Start polling for cloud upload status
setInterval(updateCloudUploadStatus, 5000);
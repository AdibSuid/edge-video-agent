/**
 * TapView Agent - Main JavaScript
 * Professional CCTV Web Application
 */

// Sidebar toggle
document.addEventListener('DOMContentLoaded', function() {
    const toggleBtn = document.getElementById('toggleSidebar');
    const sidebar = document.getElementById('sidebar');

    if (toggleBtn) {
        toggleBtn.addEventListener('click', function() {
            sidebar.classList.toggle('active');
        });
    }

    // Initialize status updates
    updateSystemStatus();
    setInterval(updateSystemStatus, 3000);
});

// Update system status in top bar and sidebar
async function updateSystemStatus() {
    try {
        // Update motion status
        const motionResponse = await fetch('/api/motion_status');
        const motionData = await motionResponse.json();

        let activeCount = 0;
        let motionCount = 0;

        Object.entries(motionData).forEach(([streamId, status]) => {
            activeCount++;
            if (status.active) {
                motionCount++;
                updateCameraCard(streamId, status);
            } else {
                updateCameraCard(streamId, status);
            }
        });

        // Update top bar
        const topBarActive = document.getElementById('topBarActiveStreams');
        const topBarMotion = document.getElementById('topBarMotionStreams');
        if (topBarActive) topBarActive.textContent = activeCount;
        if (topBarMotion) topBarMotion.textContent = motionCount;

        // Update dashboard stats
        const dashActive = document.getElementById('activeStreams');
        const dashMotion = document.getElementById('motionStreams');
        if (dashActive) dashActive.textContent = activeCount;
        if (dashMotion) dashMotion.textContent = motionCount;

        // System status indicator
        const systemIcon = document.getElementById('systemStatusIcon');
        const systemText = document.getElementById('systemStatusText');
        if (systemIcon && activeCount > 0) {
            systemIcon.style.color = 'var(--success-color)';
            systemText.textContent = `${activeCount} Camera${activeCount !== 1 ? 's' : ''} Active`;
        }

    } catch (error) {
        console.error('Failed to update system status:', error);
    }

    // Update cloud upload status
    try {
        const cloudResponse = await fetch('/api/cloud_upload_status');
        const cloudData = await cloudResponse.json();

        updateStatusBadge('topBarCloudStatus', cloudData.enabled && cloudData.authenticated, 'Connected', 'Off');
        updateStatusBadge('cloudUploadStatus', cloudData.enabled && cloudData.authenticated, 'Connected', 'Disabled');

        const queueElement = document.getElementById('cloudUploadQueue');
        if (queueElement) queueElement.textContent = cloudData.queue_size || 0;

    } catch (error) {
        console.error('Failed to update cloud status:', error);
    }

    // Update stream push status
    try {
        const pushResponse = await fetch('/api/stream_push_status');
        const pushData = await pushResponse.json();

        updateStatusBadge('topBarStreamPushStatus', pushData.enabled && pushData.connected, 'Connected', 'Off');
        updateStatusBadge('streamPushStatus', pushData.enabled && pushData.connected, 'Connected', 'Disabled');

        const countElement = document.getElementById('streamPushCount');
        if (countElement) countElement.textContent = pushData.stream_count || 0;

    } catch (error) {
        console.error('Failed to update stream push status:', error);
    }
}

// Update status badge
function updateStatusBadge(elementId, isActive, activeText, inactiveText) {
    const element = document.getElementById(elementId);
    if (!element) return;

    if (isActive) {
        element.className = 'stat-badge success';
        element.innerHTML = `<i class="fas fa-circle"></i> ${activeText}`;
    } else {
        element.className = 'stat-badge secondary';
        element.innerHTML = `<i class="fas fa-circle"></i> ${inactiveText}`;
    }
}

// Update camera card status
function updateCameraCard(streamId, status) {
    const card = document.querySelector(`[data-camera-id="${streamId}"]`);
    if (!card) return;

    // Update motion status badge
    const statusBadge = card.querySelector('.motion-status-badge');
    const fpsElement = card.querySelector('.camera-fps');

    if (status.active) {
        if (statusBadge) {
            statusBadge.className = 'status-badge motion';
            statusBadge.innerHTML = `<i class="fas fa-running"></i> Motion`;
        }
    } else {
        if (statusBadge) {
            statusBadge.className = 'status-badge idle';
            statusBadge.innerHTML = `<i class="fas fa-circle"></i> Idle`;
        }
    }

    // Update FPS
    if (fpsElement) {
        fpsElement.textContent = `${status.fps} fps`;
    }
}

// Remove stream
async function removeStream(streamId) {
    if (!confirm('Remove this camera? This action cannot be undone.')) {
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
            // Remove card with animation
            const card = document.querySelector(`[data-camera-id="${streamId}"]`);
            if (card) {
                card.style.transition = 'all 0.3s';
                card.style.opacity = '0';
                card.style.transform = 'scale(0.8)';
                setTimeout(() => {
                    card.remove();
                    updateCameraCount();
                }, 300);
            }
        } else {
            showNotification('Failed to remove camera: ' + data.error, 'danger');
        }
    } catch (error) {
        showNotification('Error removing camera: ' + error, 'danger');
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
            const card = document.querySelector(`[data-camera-id="${streamId}"]`);
            if (card) {
                card.style.opacity = newEnabled ? '1' : '0.6';
            }

            showNotification(`Camera ${newEnabled ? 'enabled' : 'disabled'}`, 'success');
        } else {
            showNotification('Failed to toggle camera: ' + data.error, 'danger');
        }
    } catch (error) {
        showNotification('Error toggling camera: ' + error, 'danger');
    }
}

// Update camera count
function updateCameraCount() {
    const count = document.querySelectorAll('.camera-card').length;
    const countElement = document.getElementById('cameraCount');
    if (countElement) {
        countElement.textContent = count;
    }
}

// Show notification (toast)
function showNotification(message, type = 'info') {
    // Create toast element
    const toast = document.createElement('div');
    toast.className = `notification-toast ${type}`;
    toast.style.cssText = `
        position: fixed;
        top: 90px;
        right: 20px;
        background: var(--bg-secondary);
        color: var(--text-primary);
        padding: 16px 20px;
        border-radius: var(--border-radius-sm);
        border: 1px solid var(--border-color);
        border-left: 4px solid var(--${type === 'danger' ? 'danger' : type === 'success' ? 'success' : 'primary'}-color);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        z-index: 9999;
        animation: slideIn 0.3s;
        min-width: 300px;
    `;

    const icon = type === 'success' ? 'check-circle' : type === 'danger' ? 'exclamation-circle' : 'info-circle';
    toast.innerHTML = `
        <div style="display: flex; align-items: center; gap: 12px;">
            <i class="fas fa-${icon}" style="font-size: 20px;"></i>
            <span>${message}</span>
        </div>
    `;

    document.body.appendChild(toast);

    // Auto remove after 3 seconds
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Add CSS for toast animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Initialize on page load
updateCameraCount();

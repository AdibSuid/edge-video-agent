# Cloud Deployment Configuration Guide

This guide outlines the configuration changes needed when moving from local testing to cloud deployment with your DeepStream pipeline server.

## Overview

After successfully testing RTMP push functionality locally, update your `config.yaml` to point to cloud infrastructure instead of localhost services.

## Required Configuration Changes

### 1. RTMP Push Destination
```yaml
# Change from local testing to cloud RTMP server
cloud_rtmp_url: rtmp://your-cloud-server-ip:1935  # Replace with actual cloud RTMP URL
```

### 2. DeepStream API Endpoint
```yaml
# Change from localhost mock server to cloud DeepStream API
deepstream_api_url: http://your-cloud-server-ip:9002  # Replace with actual cloud API URL
```

### 3. MediaMTX Server Settings
```yaml
# Update to cloud MediaMTX server
mediamtx_hostname: your-cloud-mediamtx-hostname  # Replace with cloud hostname/IP
mediamtx_rtsp_port: 8554  # Usually stays the same
```

### 4. Cloud Upload Configuration
```yaml
# Enable cloud uploads and update URLs
cloud_upload_enabled: true
cloud_upload_url: http://your-cloud-upload-server:8081  # Replace with actual upload endpoint
cloud_username: your-cloud-username
cloud_password: your-cloud-password
```

### 5. Public Access Settings
```yaml
# For external access to RTSP streams
edge_public_domain: your-public-domain.com  # Or use edge_public_ip
edge_public_ip: your-public-ip
ngrok_enabled: false  # Disable since you're using cloud infrastructure
```

### 6. Camera RTSP URLs
Update the `streams` section if your cloud cameras have different IPs/credentials:
```yaml
streams:
- id: Camera1
  name: "Cloud Camera 1"
  rtsp_url: rtsp://username:password@cloud-camera-ip:554/stream
  enabled: true
  streaming_enabled: true
  # ... other camera settings remain the same
```

### 7. Network and Performance Tuning
```yaml
# Adjust based on cloud network conditions
motion_high_fps: 25  # Full FPS for cloud processing
motion_low_fps: 5    # Lower idle FPS to save bandwidth
chunk_bitrate: 2000000  # Adjust based on cloud bandwidth
```

## Cloud Infrastructure Requirements

Ensure your cloud setup has:

1. **MediaMTX Server** running with RTMP input (port 1935) and RTSP output (port 8554)
2. **DeepStream REST API Server** running on port 9002
3. **Cloud Upload Server** accepting chunked video uploads
4. **Network connectivity** between Edge Agent and cloud servers
5. **Proper firewall rules** allowing RTMP/RTSP traffic

## Testing Cloud Deployment

After updating configuration:

1. **Start MediaMTX** on cloud server with appropriate config
2. **Start DeepStream** pipeline on cloud server  
3. **Run Edge Agent**: `python app.py --config config.yaml`
4. **Verify RTMP connections** in MediaMTX logs
5. **Test RTSP output** from cloud MediaMTX
6. **Check DeepStream API** for stream registrations
7. **Monitor cloud uploads** for video chunks

## Troubleshooting

- **RTMP push fails**: Check cloud RTMP server connectivity and authentication
- **DeepStream registration fails**: Verify API endpoint and network access
- **No RTSP output**: Ensure MediaMTX is receiving RTMP streams
- **Upload failures**: Check cloud upload server credentials and connectivity

## Local vs Cloud Differences

| Setting | Local Testing | Cloud Deployment |
|---------|---------------|------------------|
| `cloud_rtmp_url` | `rtmp://localhost:1935` | `rtmp://your-cloud-ip:1935` |
| `deepstream_api_url` | `http://localhost:9002` | `http://your-cloud-ip:9002` |
| `cloud_upload_enabled` | `false` | `true` |
| `ngrok_enabled` | `true` | `false` |
| Camera RTSP URLs | Local network IPs | Cloud camera IPs |

## Security Considerations

- Use strong passwords for cloud services
- Implement proper firewall rules
- Consider VPN for camera-to-cloud connectivity
- Enable HTTPS for API endpoints when possible
- Regularly rotate authentication credentials</content>
<parameter name="filePath">c:\Users\adibc\Documents\edge-video-agent\CLOUD_DEPLOYMENT.md
# Deployment Guide for Edge Video Agent

This guide explains how to deploy the Edge Video Agent web app on an edge device (e.g., Raspberry Pi 5 or Windows machine) using Docker. It also covers configuration for Telegram notifications and cloud uploader integration.

---

## 1. Prerequisites
- Docker installed on your edge device
- Access to Docker Hub
- Network access to ONVIF cameras
- (Optional) Telegram bot token and chat ID for notifications
- Cloud server endpoint for uploads

---

## 2. Configuration

### Edit `config.yaml`
- Open `config.yaml` in the project directory.
- Update the following sections as needed:

#### Cameras
- Add or update camera credentials (username, password) and network details.
- Example:
  ```yaml
  streams:
    - id: cam1
      name: "Front Door"
      rtsp_url: "rtsp://<camera-ip>:554/stream"
      username: "admin"
      password: "yourpassword"
      enabled: true
  ```

#### Telegram Notification
- Set up your Telegram bot and get the token and chat ID.
- Update in `config.yaml`:
  ```yaml
  telegram:
    enabled: true
    bot_token: "<your-telegram-bot-token>"
    chat_id: "<your-chat-id>"
  ```

#### Cloud Uploader
- If you have a cloud server for uploads, update:
  ```yaml
  cloud_uploader:
    enabled: true
    endpoint: "https://your-cloud-server/upload"
    api_key: "<your-api-key>"
  ```

---

## 3. Deploy with Docker

### Step 1: Pull the Docker Image
```bash
docker pull kambing74/edge-video-agent:rpi   # For Raspberry Pi
# OR
docker pull kambing74/edge-video-agent:windows   # For Windows
```

### Step 2: Run the Container
```bash
docker run -d -p 5000:5000 \
  -v /path/to/config.yaml:/app/config.yaml \
  --name edge-video-agent kambing74/edge-video-agent:rpi
```
- Adjust the image tag for your platform.
- Mount your custom `config.yaml` if needed.

### Step 3: Access the Web App
- Open a browser and go to: `http://<device-ip>:5000`

---

## 4. Additional Notes
- **Camera Discovery:** The app will auto-discover ONVIF cameras if configured.
- **RTSP URLs:** Exposed via `/api/streams` endpoint for integration with MediaMTX or DeepStream Triton.
- **Logs:** Check the `logs/` directory for event logs and errors.
- **Cloud Upload:** Ensure your cloud server is reachable and credentials are correct.
- **Telegram:** Make sure your bot is active and chat ID is valid.

---

## 5. Troubleshooting
- If the container fails to start, check Docker logs:
  ```bash
  docker logs edge-video-agent
  ```
- Verify network access to cameras and cloud server.
- Ensure all required fields in `config.yaml` are filled.

---

## 6. Updating Configuration
- To change configuration, edit `config.yaml` and restart the container:
  ```bash
  docker restart edge-video-agent
  ```

---

## 7. Stopping and Removing the Container
```bash
docker stop edge-video-agent
docker rm edge-video-agent
```

---

For further help, see the README.md or contact the maintainer.

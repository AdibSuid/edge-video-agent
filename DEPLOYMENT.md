# Deployment & Packaging Guide

This document provides a short guide for deploying the edge agent and wiring it to a cloud SRT listener (for ingestion by DeepStream/Triton or other services). It also includes a simple packaging/install plan for Windows and Linux CPU-only installs.

## Recommended topology

- Run a public SRT listener in your cloud (VM with public IP or load balancer) and let agents (caller mode) connect to it. This avoids inbound firewall changes on many remote networks.
- Example: DeepStream/Triton runs on a cloud VM and listens on port 9000 for incoming SRT streams. Agents connect to `srt://cloud.example:9000`.

## SRT settings

- Use the same passphrase on both ends (configured in `config.yaml` as `srt_passphrase`).
- Use `srt_mode: caller` in `config.yaml` for the agent when the cloud listener is publicly reachable.
- `srt_params` may be used to set additional srtsrc/srtsink query params (latency, pksize, etc.).

Example agent `config.yaml` snippet:

```yaml
cloud_srt_host: "srt://your-cloud-server:9000"
srt_passphrase: "SOMESTRONGPASS"
srt_mode: caller
srt_params: {}
default_bitrate: 2000000
low_bitrate: 400000
```

## DeepStream listener example (high-level)

On the inference host run a pipeline that accepts SRT and forwards to DeepStream/Triton. Example pipeline outline (adapt for your DeepStream/GST plugin versions):

```
gst-launch-1.0 \
  srtsrc uri="srt://0.0.0.0:9000?mode=listener&passphrase=SOMESTRONGPASS" ! \
  tsdemux name=dmux dmux. ! queue ! h264parse ! nvv4l2decoder ! nvstreammux name=mux batch-size=1 width=1280 height=720 ! \
  nvinferserver config-file-path=/path/to/triton-deepstream-config.txt ! nvdsosd ! nvegltransform ! nveglglessink
```

Notes:
- Use `nvv4l2decoder` or the appropriate HW decoder for your platform.
- `nvinferserver` is the DeepStream plugin that forwards frames to Triton.

## Alternative: VPN / WireGuard

- If you prefer not to expose a public SRT listener, deploy a small WireGuard VPN server and have agents join it. The cloud inference host joins the same VPN; the agent can then use private addresses.
- Advantages: strong security and simple firewall rules. Disadvantages: extra operations overhead.

## Quick install / packaging plan (CPU only)

Linux (recommended):
1. Provide `install.sh` that:
   - sets up a Python venv in `venv/`,
   - installs `pip install -r requirements.txt`,
   - checks for GStreamer and instructs the user to install system packages if missing.
2. Ship `systemd` unit file example to run `python app.py` as a service.

Windows:
1. Provide `install.bat` that:
   - creates a venv, activates it, installs `pip install -r requirements.txt`.
   - prints instructions for installing GStreamer (user must do this manually).
2. Provide a simple scheduled task or a wrapper to run the agent at boot.

## Packaging notes

- For wider distribution consider building an OS-specific package (deb for Debian/Ubuntu, MSI for Windows). For most deployments a simple script plus a `systemd` unit (Linux) and a Scheduled Task (Windows) is sufficient.

## Security

- Keep `srt_passphrase` secret.
- Restrict cloud listener access at the firewall level to known IP ranges when possible.
- Rotate passphrases periodically.

## Next steps

1. Add `srt_mode` and `srt_params` to the UI/config editor.
2. Optionally provide a small WireGuard setup script for private deployments.
3. Add sample `systemd` unit and Scheduled Task examples to the repo.

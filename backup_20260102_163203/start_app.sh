#!/bin/bash
# Start edge-video-agent without venv to use system OpenCV with CUDA

cd /home/orin/Documents/edge-video-agent

# Use system Python3 which has access to OpenCV 4.10 with CUDA
python3 app.py

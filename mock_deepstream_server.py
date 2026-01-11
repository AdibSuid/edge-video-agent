#!/usr/bin/env python3
"""
Mock DeepStream REST API Server
Simulates the cloud DeepStream pipeline for local testing
"""

from flask import Flask, request, jsonify
import time
from datetime import datetime

app = Flask(__name__)

# Store active streams
streams = {}

@app.route('/api/v1/health/get-dsready-state', methods=['GET'])
def health_check():
    """Mock health check endpoint"""
    return jsonify({
        "status": "success",
        "pipeline_ready": True,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/v1/stream/get-stream-info', methods=['GET'])
def get_stream_info():
    """Mock get stream info endpoint"""
    stream_list = []
    for camera_id, info in streams.items():
        stream_list.append({
            "camera_id": camera_id,
            "camera_name": info['camera_name'],
            "camera_url": info['camera_url'],
            "status": "active",
            "added_at": info['added_at']
        })

    return jsonify({
        "status": "success",
        "streams": stream_list,
        "count": len(stream_list)
    })

@app.route('/api/v1/stream/add', methods=['POST'])
def add_stream():
    """Mock add stream endpoint"""
    data = request.json

    print("=" * 60)
    print("📥 RECEIVED STREAM ADD REQUEST")
    print("=" * 60)
    print(f"Full payload: {data}")

    if not data or 'key' not in data or 'value' not in data:
        return jsonify({
            "status": "error",
            "message": "Invalid payload format"
        }), 400

    value = data['value']
    camera_id = value.get('camera_id')
    camera_name = value.get('camera_name')
    camera_url = value.get('camera_url')
    change = value.get('change')

    if not all([camera_id, camera_name, camera_url, change]):
        return jsonify({
            "status": "error",
            "message": "Missing required fields"
        }), 400

    if change != "camera_add":
        return jsonify({
            "status": "error",
            "message": f"Unknown change type: {change}"
        }), 400

    # Simulate checking if stream URL is accessible
    print(f"\n✓ Camera ID: {camera_id}")
    print(f"✓ Camera Name: {camera_name}")
    print(f"✓ Camera URL: {camera_url}")
    print(f"✓ Change Type: {change}")

    # Store the stream
    streams[camera_id] = {
        'camera_name': camera_name,
        'camera_url': camera_url,
        'added_at': datetime.now().isoformat()
    }

    print(f"\n✅ Stream '{camera_id}' added successfully!")
    print(f"📊 Total streams: {len(streams)}")
    print("=" * 60)

    return jsonify({
        "status": "success",
        "message": f"Stream {camera_id} added successfully",
        "camera_id": camera_id,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/v1/stream/remove', methods=['POST'])
def remove_stream():
    """Mock remove stream endpoint"""
    data = request.json

    print("=" * 60)
    print("📤 RECEIVED STREAM REMOVE REQUEST")
    print("=" * 60)

    if not data or 'key' not in data or 'value' not in data:
        return jsonify({
            "status": "error",
            "message": "Invalid payload format"
        }), 400

    value = data['value']
    camera_id = value.get('camera_id')
    change = value.get('change')

    if change != "camera_remove":
        return jsonify({
            "status": "error",
            "message": f"Unknown change type: {change}"
        }), 400

    if camera_id not in streams:
        return jsonify({
            "status": "error",
            "message": f"Stream {camera_id} not found"
        }), 404

    # Remove the stream
    removed = streams.pop(camera_id)

    print(f"✓ Removed stream: {camera_id}")
    print(f"📊 Remaining streams: {len(streams)}")
    print("=" * 60)

    return jsonify({
        "status": "success",
        "message": f"Stream {camera_id} removed successfully",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/v1/infer/set-interval', methods=['POST'])
def set_inference_interval():
    """Mock set inference interval endpoint"""
    data = request.json
    print(f"📊 Set inference interval: {data}")
    return jsonify({
        "status": "success",
        "message": "Inference interval updated"
    })

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 MOCK DEEPSTREAM REST API SERVER")
    print("=" * 60)
    print("Server running on: http://localhost:9002")
    print("Endpoints available:")
    print("  GET  /api/v1/health/get-dsready-state")
    print("  GET  /api/v1/stream/get-stream-info")
    print("  POST /api/v1/stream/add")
    print("  POST /api/v1/stream/remove")
    print("  POST /api/v1/infer/set-interval")
    print("=" * 60)
    print("\n✅ Ready to receive streams from Edge Agent\n")

    # Run on port 9002 to match your cloud DeepStream
    app.run(host='0.0.0.0', port=9002, debug=False)

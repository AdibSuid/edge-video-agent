import json
import importlib

# Import the app module
app = importlib.import_module('app')

# Monkeypatch start_stream and stop_stream to avoid side-effects
started = []
stopped = []

def fake_start_stream(stream):
    started.append(stream.get('id'))

def fake_stop_stream(stream_id):
    stopped.append(stream_id)

app.start_stream = fake_start_stream
app.stop_stream = fake_stop_stream

# Prepare config with two streams
app.config = {
    'cloud_srt_host': 'srt://example:9000',
    'srt_passphrase': 'pass',
    'streams': [
        {'id': 'cam1', 'name': 'backyard', 'rtsp_url': 'rtsp://1', 'enabled': True},
        {'id': 'cam2', 'name': 'porch', 'rtsp_url': 'rtsp://2', 'enabled': True},
    ]
}

# Use Flask test client
client = app.app.test_client()

print('Initial streams:', [s['id'] for s in app.config['streams']])

# Test toggle_stream: disable cam1
resp = client.post('/api/toggle_stream', json={'stream_id': 'cam1', 'enabled': False})
print('/api/toggle_stream disable cam1 ->', resp.status_code, resp.get_json())

# Ensure config updated
print('After toggle, cam1 enabled?', next(s for s in app.config['streams'] if s['id']=='cam1')['enabled'])
print('stop calls:', stopped)

# Test remove_stream: remove cam2
resp = client.post('/api/remove_stream', json={'stream_id': 'cam2'})
print('/api/remove_stream cam2 ->', resp.status_code, resp.get_json())
print('Streams after remove:', [s['id'] for s in app.config.get('streams', [])])
print('stop calls after remove:', stopped)

# Test remove non-existent stream
resp = client.post('/api/remove_stream', json={'stream_id': 'does_not_exist'})
print('/api/remove_stream non-existent ->', resp.status_code, resp.get_json())

# Test toggle non-existent
resp = client.post('/api/toggle_stream', json={'stream_id': 'does_not_exist', 'enabled': True})
print('/api/toggle_stream non-existent ->', resp.status_code, resp.get_json())

# Test missing fields
resp = client.post('/api/toggle_stream', json={'stream_id': 'cam1'})
print('/api/toggle_stream missing enabled ->', resp.status_code, resp.get_json())
resp = client.post('/api/remove_stream', json={})
print('/api/remove_stream missing id ->', resp.status_code, resp.get_json())

print('started:', started)
print('done')

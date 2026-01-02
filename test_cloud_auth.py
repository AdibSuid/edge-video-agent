#!/usr/bin/env python3
"""
Test cloud authentication with current config
"""

import yaml
import requests

print("=" * 60)
print("Cloud Authentication Test")
print("=" * 60)

# Load config
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

server_url = config.get('cloud_upload_url', '').rstrip('/')
username = config.get('cloud_username', '')
password = config.get('cloud_password', '')

print(f"\nServer URL: {server_url}")
print(f"Username: {username}")
print(f"Password: {'*' * len(password)}")
print("")

if not server_url or not username or not password:
    print("❌ Missing credentials in config.yaml")
    exit(1)

# Test authentication
auth_url = f"{server_url}/auth/login"
print(f"Testing: {auth_url}")
print("")

try:
    print("Sending POST request...")
    response = requests.post(
        auth_url,
        data={
            "username": username,
            "password": password
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "accept": "application/json"
        },
        timeout=10
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response Headers: {dict(response.headers)}")
    print(f"Response Body: {response.text}")
    print("")
    
    if response.status_code == 200:
        data = response.json()
        if 'access_token' in data:
            print("✅ Authentication successful!")
            print(f"Access token: {data['access_token'][:50]}...")
        else:
            print("⚠️  Got 200 but no access_token in response")
            print(f"Response keys: {list(data.keys())}")
    else:
        print(f"❌ Authentication failed: {response.status_code}")
        print(f"Error: {response.text}")
        
except requests.exceptions.ConnectionError as e:
    print(f"❌ Connection Error: Cannot reach {auth_url}")
    print(f"   Error: {e}")
    print("\n   Possible issues:")
    print("   - Server is down")
    print("   - Wrong URL/port")
    print("   - Network/firewall blocking connection")
    
except requests.exceptions.Timeout:
    print(f"❌ Timeout: Server took too long to respond")
    
except Exception as e:
    print(f"❌ Unexpected error: {e}")

print("")
print("=" * 60)

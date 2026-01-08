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

# Try multiple possible auth endpoints
auth_endpoints = [
    "/api/auth/login",     # Common REST API pattern
    "/api/login",          # Alternative
    "/auth/login",         # Current endpoint
    "/login",              # Web endpoint
]

print("Testing multiple authentication endpoints...")
print("=" * 60)

for endpoint in auth_endpoints:
    auth_url = f"{server_url}{endpoint}"
    print(f"\n🔍 Testing: {auth_url}")
    print("-" * 60)

    print(f"\n🔍 Testing: {auth_url}")
    print("-" * 60)

    try:
        # Try form-encoded (current method)
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
            timeout=5
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                if 'access_token' in data:
                    print("✅ SUCCESS! Found access_token")
                    print(f"   Token: {data['access_token'][:50]}...")
                    print(f"\n✨ Use this endpoint: {endpoint}")
                    break
                else:
                    print(f"⚠️  200 OK but no access_token")
                    print(f"   Keys: {list(data.keys())}")
            except:
                print(f"⚠️  200 OK but not JSON: {response.text[:100]}")
        elif response.status_code == 404:
            print("❌ 404 Not Found - Wrong endpoint")
        else:
            print(f"❌ Failed: {response.text[:200]}")
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection failed")
    except requests.exceptions.Timeout:
        print(f"❌ Timeout")
    except Exception as e:
        print(f"❌ Error: {e}")

print("")
print("=" * 60)
print("\nIf none worked, try JSON format:")
print("")

# Try JSON format instead of form-encoded
auth_url = f"{server_url}/api/auth/login"
print(f"Testing JSON format: {auth_url}")
print("-" * 60)

try:
    print("Sending with JSON body...")
    response = requests.post(
        auth_url,
        json={
            "username": username,
            "password": password
        },
        headers={"Content-Type": "application/json"},
        timeout=10
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text[:200]}")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text[:200]}")
    
    if response.status_code == 200:
        data = response.json()
        if 'access_token' in data:
            print("✅ JSON format works!")
            print(f"   Token: {data['access_token'][:50]}...")
        else:
            print(f"   Keys: {list(data.keys())}")
    
except Exception as e:
    print(f"Error: {e}")

print("")
print("=" * 60)

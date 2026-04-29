"""
Simple test to check if endpoint exists and accepts requests
"""
import requests

url = "http://localhost:5000/api/cameras/cs_ground/upload"

print(f"Testing: {url}")
print("\n1. OPTIONS request (CORS preflight):")
try:
    response = requests.options(url)
    print(f"   Status: {response.status_code}")
    print(f"   Headers: {dict(response.headers)}")
except Exception as e:
    print(f"   Error: {e}")

print("\n2. POST request (no file - should fail with 400):")
try:
    response = requests.post(url)
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text}")
except Exception as e:
    print(f"   Error: {e}")

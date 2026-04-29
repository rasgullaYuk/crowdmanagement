"""
Direct test upload to the new endpoint
"""
import requests
import os

# Get file
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
test_video = os.path.join(project_root, "test.mp4")

if not os.path.exists(test_video):
    print(f"❌ Test video not found: {test_video}")
    exit(1)

file_size = os.path.getsize(test_video) / (1024*1024)
print(f"📹 Test video: {test_video}")
print(f"   Size: {file_size:.2f} MB")

url = "http://localhost:5000/api/cameras/cs_ground/upload"

print(f"\n🔄 Testing upload to: {url}")
print("   (no timeout - will wait as long as needed)")

try:
    with open(test_video, 'rb') as f:
        files = {'video': (os.path.basename(test_video), f, 'video/mp4')}
        print("   ⬆️  Sending request...")
        response = requests.post(url, files=files, timeout=None)
    
    print(f"\n📊 Response:")
    print(f"   Status: {response.status_code}")
    print(f"   Headers: {dict(response.headers)}")
    print(f"\n   Body: {response.text[:500]}")
    
except requests.exceptions.RequestException as e:
    print(f"\n❌ Request failed: {type(e).__name__}: {e}")
except Exception as e:
    print(f"\n❌ Error: {type(e).__name__}: {e}")

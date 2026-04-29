"""
Quick test for the new generic upload endpoint
"""
import requests
import os

BASE_URL = "http://localhost:5000"

# Find test video in project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
test_video = os.path.join(project_root, "test.mp4")

if not os.path.exists(test_video):
    print(f"❌ Test video not found at {test_video}")
    print("Please ensure test.mp4 exists in the project root")
    exit(1)

print("="*60)
print("Testing Generic Upload Endpoint")
print("="*60)
print(f"\n📹 Test video: {test_video}")
print(f"   Size: {os.path.getsize(test_video) / (1024*1024):.2f} MB")

# Test CS Ground upload
zone = "cs_ground"
url = f"{BASE_URL}/api/cameras/{zone}/upload"

print(f"\n🔄 Uploading to: {url}")
print("   This will take 30-60 seconds for CSRNet processing...")

try:
    with open(test_video, 'rb') as f:
        files = {'video': f}
        response = requests.post(url, files=files, timeout=180)
    
    if response.status_code == 200:
        data = response.json()
        print("\n✅ Upload successful!")
        print(f"\n📊 Results:")
        print(f"   Zone: {data.get('zone')}")
        if 'analysis' in data:
            a = data['analysis']
            print(f"   Avg Crowd: {a.get('crowd_count')} people")
            print(f"   Peak: {a.get('peak_count')} people")
            print(f"   Density: {a.get('density_level')}")
            print(f"   Processing Time: {a.get('processing_time')}")
            print(f"   Forecast Video: {BASE_URL}{a.get('forecast_video_url')}")
            print(f"\n🎥 Open forecast video: {BASE_URL}{a.get('forecast_video_url')}")
    else:
        print(f"\n❌ Upload failed: {response.status_code}")
        print(f"   Response: {response.text}")
        
except requests.exceptions.Timeout:
    print("\n⏱️  Request timed out (processing may still be running)")
except Exception as e:
    print(f"\n❌ Error: {e}")

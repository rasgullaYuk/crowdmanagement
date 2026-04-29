"""
Test the new quick upload endpoint
"""
import requests
import os

video_path = os.path.join("uploads", "pavithra.mp4")

if os.path.exists(video_path):
    print(f"📤 Testing quick upload with {video_path}...")
    with open(video_path, 'rb') as f:
        response = requests.post(
            "http://localhost:5000/api/cameras/upload-video-quick",
            files={'video': f},
            data={'zone_id': 'test'},
            timeout=30
        )
    
    print(f"Status: {response.status_code}")
    if response.ok:
        print("✅ SUCCESS!")
        data = response.json()
        print(f"Message: {data.get('message')}")
        if 'analysis' in data:
            print(f"Crowd Count: {data['analysis'].get('crowd_count')}")
            print(f"Density: {data['analysis'].get('density_level')}")
    else:
        print(f"❌ FAILED: {response.text}")
else:
    print(f"❌ Video not found: {video_path}")

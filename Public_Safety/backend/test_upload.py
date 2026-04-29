"""
Simple test to verify video upload endpoint works
"""
import requests
import os
import time

print("=" * 70)
print("🧪 TESTING VIDEO UPLOAD ENDPOINT")
print("=" * 70)
print()

# Check backend is running
print("1️⃣ Checking if backend is running...")
try:
    response = requests.get("http://localhost:5000/api/responders", timeout=5)
    if response.ok:
        print("   ✅ Backend is running on port 5000")
    else:
        print(f"   ⚠️ Backend responded with status {response.status_code}")
except Exception as e:
    print(f"   ❌ Cannot connect to backend: {e}")
    print("   Make sure to run: python app.py")
    exit(1)

print()

# Find a small test video
print("2️⃣ Looking for test video...")
video_candidates = [
    os.path.join("uploads", "pavithra.mp4"),
    "pavithra.mp4",
]

video_path = None
for candidate in video_candidates:
    if os.path.exists(candidate):
        video_path = candidate
        break

if not video_path:
    print("   ❌ No test video found!")
    print("   Expected: uploads/pavithra.mp4")
    exit(1)

file_size = os.path.getsize(video_path) / 1024  # KB
print(f"   ✅ Found: {video_path} ({file_size:.1f} KB)")
print()

# Upload the video
print("3️⃣ Uploading video to backend...")
print("   This may take 30 seconds to 2 minutes...")
print()

start_time = time.time()

try:
    with open(video_path, 'rb') as f:
        response = requests.post(
            "http://localhost:5000/api/cameras/upload-video",
            files={'video': ('test.mp4', f, 'video/mp4')},
            data={'zone_id': 'test_zone'},
            timeout=300  # 5 minute timeout
        )
    
    elapsed = time.time() - start_time
    
    print(f"   ⏱️ Processing took {elapsed:.1f} seconds")
    print()
    print("4️⃣ Response:")
    print(f"   Status Code: {response.status_code}")
    
    if response.ok:
        print("   ✅ SUCCESS!")
        print()
        data = response.json()
        
        if 'analysis' in data:
            analysis = data['analysis']
            print("   📊 Analysis Results:")
            print(f"      - Crowd Count: {analysis.get('crowd_count', 'N/A')}")
            print(f"      - Density: {analysis.get('density_level', 'N/A')}")
            print(f"      - Sentiment: {analysis.get('sentiment', 'N/A')}")
            
            if analysis.get('found_persons'):
                print(f"      - Found Persons: {len(analysis['found_persons'])}")
                for i, person in enumerate(analysis['found_persons'], 1):
                    print(f"         {i}. {person.get('description', 'Unknown')}")
        else:
            print("   ⚠️ No analysis data in response")
            print(f"   Response: {data}")
    else:
        print("   ❌ FAILED!")
        print(f"   Error: {response.text[:500]}")
        
except requests.exceptions.Timeout:
    print("   ❌ Request timed out after 5 minutes")
    print("   The video might be too large or analysis is stuck")
    
except Exception as e:
    print(f"   ❌ Error: {e}")

print()
print("=" * 70)
print("TEST COMPLETE")
print("=" * 70)

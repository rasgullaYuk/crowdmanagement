"""
Simple test upload script using existing videos
"""
import requests
import os

BASE_URL = "http://localhost:5000"
UPLOADS_FOLDER = "uploads"

# Find existing videos
existing_videos = []
if os.path.exists(UPLOADS_FOLDER):
    for file in os.listdir(UPLOADS_FOLDER):
        if file.endswith('.mp4') and not file.startswith('analysis_') and not file.startswith('processed_'):
            existing_videos.append(file)

if not existing_videos:
    print("❌ No test videos found in uploads folder!")
    print("Please add a .mp4 video file to backend/uploads/ folder")
    exit(1)

# Use first available video
test_video = os.path.join(UPLOADS_FOLDER, existing_videos[0])

print("="*70)
print("TESTING VIDEO UPLOAD")
print("="*70)
print(f"\n📹 Test video: {existing_videos[0]}")

size_mb = os.path.getsize(test_video) / (1024*1024)
print(f"📊 Size: {size_mb:.2f} MB")

# Test endpoints
endpoints = [
    {'url': f'{BASE_URL}/api/cameras/food-court/upload', 'name': 'Food Court'},
    {'url': f'{BASE_URL}/api/cameras/parking/upload', 'name': 'Parking'},
]

for endpoint in endpoints:
    print(f"\n{'='*70}")
    print(f"Testing {endpoint['name']} endpoint")
    print(f"{'='*70}")
    
    try:
        with open(test_video, 'rb') as f:
            print("⏳ Uploading...")
            response = requests.post(
                endpoint['url'], 
                files={'video': f},
                data={'continuous': 'false'},  # Disable continuous mode for faster testing
                timeout=120
            )
        
        if response.ok:
            data = response.json()
            print(f"✅ SUCCESS!")
            print(f"Status: {response.status_code}")
            print(f"Message: {data.get('message', 'No message')}")
            
            analysis = data.get('analysis')
            if analysis:
                print(f"\n📊 Analysis Results:")
                print(f"   Crowd Count: {analysis.get('crowd_count', 'N/A')}")
                print(f"   Density: {analysis.get('density_level', 'N/A')}")
                print(f"   Description: {analysis.get('description', 'N/A')}")
                
                anomalies = analysis.get('anomalies', [])
                if anomalies:
                    print(f"\n   🚨 Anomalies Detected: {len(anomalies)}")
                    for a in anomalies[:3]:  # Show first 3
                        if isinstance(a, dict):
                            print(f"      - {a.get('type')}: {a.get('description')}")
        else:
            print(f"❌ Failed: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

print(f"\n{'='*70}")
print("TEST COMPLETE!")
print(f"{'='*70}")
print("\n✅ View results at:")
print("   • User Dashboard: http://localhost:3000/dashboard/user")
print("   • Admin Dashboard: http://localhost:3000/dashboard/admin")

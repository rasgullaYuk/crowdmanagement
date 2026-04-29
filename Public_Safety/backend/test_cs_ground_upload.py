"""
Test script for CS Ground video upload with CSRNet analysis
"""
import requests
import os

# Configuration
VIDEO_PATH = "food.mp4"  # Change to your video file
API_URL = "http://localhost:5000/api/cameras/cs_ground/upload"

print("="*70)
print("CS GROUND VIDEO UPLOAD TEST")
print("="*70)

# Check if video exists
if not os.path.exists(VIDEO_PATH):
    print(f"\n❌ Error: Video file '{VIDEO_PATH}' not found!")
    print("\nPlease:")
    print("1. Place a test video in the backend folder")
    print("2. Update VIDEO_PATH in this script")
    exit(1)

print(f"\nUploading: {VIDEO_PATH}")
print("This may take up to 20 seconds...\n")

try:
    with open(VIDEO_PATH, 'rb') as f:
        response = requests.post(
            API_URL,
            files={'video': f},
            timeout=30
        )
    
    print(f"Status Code: {response.status_code}\n")
    
    if response.ok:
        data = response.json()
        analysis = data.get('analysis', {})
        
        print("✅ SUCCESS!")
        print("="*70)
        print(f"Zone: {analysis.get('zone_id', 'N/A')}")
        print(f"Average Count: {analysis.get('crowd_count', 0)} people")
        print(f"Peak Count: {analysis.get('peak_count', 0)} people")
        print(f"Density Level: {analysis.get('density_level', 'N/A')}")
        print(f"Frames Analyzed: {analysis.get('frames_analyzed', 0)}")
        print(f"Processing Time: {analysis.get('processing_time', 'N/A')}")
        
        xrai = analysis.get('xrai_visualizations', [])
        if xrai:
            print(f"\n🎨 {len(xrai)} XAI Visualizations Generated:")
            for viz in xrai:
                url = f"http://localhost:5000{viz['url']}"
                print(f"  • {viz['title']}: {url}")
        
        print("\n" + "="*70)
        print("COPY THESE URLS TO YOUR BROWSER TO SEE XAI VISUALIZATIONS:")
        print("="*70)
        for viz in xrai:
            print(f"http://localhost:5000{viz['url']}")
        
    else:
        print("❌ UPLOAD FAILED")
        print(f"Response: {response.text}")
        
except requests.exceptions.Timeout:
    print("❌ Request timed out (>30s)")
    print("CSRNet analysis may be taking too long")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)

"""
Test CS Ground forecast upload
"""
import requests
import os

VIDEO_PATH = "food.mp4"
API_URL = "http://localhost:5000/api/cameras/cs_ground/upload"

print("="*70)
print("CS GROUND FORECAST TEST")
print("="*70)

if not os.path.exists(VIDEO_PATH):
    print(f"\n❌ Video '{VIDEO_PATH}' not found!")
    exit(1)

print(f"\nUploading: {VIDEO_PATH}")
print("Processing may take 30-60 seconds...\n")

try:
    with open(VIDEO_PATH, 'rb') as f:
        response = requests.post(
            API_URL,
            files={'video': f},
            timeout=120  # Increased for full video processing
        )
    
    print(f"Status: {response.status_code}\n")
    
    if response.ok:
        data = response.json()
        analysis = data.get('analysis', {})
        
        print("✅ FORECAST GENERATED!")
        print("="*70)
        print(f"Zone: {analysis.get('zone_id', 'N/A')}")
        print(f"Average Count: {analysis.get('crowd_count', 0)} people")
        print(f"Peak Count: {analysis.get('peak_count', 0)} people")
        print(f"Density Level: {analysis.get('density_level', 'N/A')}")
        print(f"Frames Processed: {analysis.get('frames_processed', 0)}")
        print(f"Processing Time: {analysis.get('processing_time', 'N/A')}")
        print(f"Prediction: +{analysis.get('prediction_minutes', 15)} minutes")
        
        video_url = analysis.get('forecast_video_url', '')
        if video_url:
            full_url = f"http://localhost:5000{video_url}"
            print(f"\n🎬 FORECAST VIDEO:")
            print(f"   {full_url}")
            print("\n📹 Download or stream this video to see:")
            print("   Left: Current density")
            print("   Right: 15-minute forecast")
        
        print("\n" + "="*70)
    else:
        print("❌ FAILED")
        print(f"{response.text}")
        
except requests.exceptions.Timeout:
    print("❌ Timeout - Processing took >120s")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)

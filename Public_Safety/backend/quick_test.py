"""
ULTRA SIMPLE PHOTO UPLOAD TEST
"""
import requests
import os
import cv2
import numpy as np

# Create test photo
print("Creating test photo...")
img = np.ones((600, 800, 3), dtype=np.uint8) * 180
for i in range(30):
    x = np.random.randint(50, 750)
    y = np.random.randint(50, 550)
    cv2.circle(img, (x, y), 15, (50, 50, 180), -1)

os.makedirs("uploads", exist_ok=True)
test_photo = "uploads/crowd_test.jpg"
cv2.imwrite(test_photo, img)
print(f"✅ Created: {test_photo}\n")

print("="*70)
print("UPLOADING PHOTO")
print("="*70)

try:
    with open(test_photo, 'rb') as f:
        response = requests.post(
            "http://localhost:5000/api/cameras/food_court/upload-photo",
            files={'photo': f},
            timeout=120
        )
    
    print(f"Status: {response.status_code}\n")
    
    if response.ok:
        data = response.json()
        analysis = data.get('analysis', {})
        
        print("✅ SUCCESS!")
        print(f"Crowd: {analysis.get('crowd_count', 0)} people")
        print(f"Density: {analysis.get('density_level', 'Unknown')}")
        
        xrai = analysis.get('xrai_visualizations', [])
        if xrai:
            print(f"\n🎨 {len(xrai)} XRAI images:")
            for v in xrai:
                print(f"  {v['title']}: http://localhost:5000{v['url']}")
    else:
        print("❌ FAILED:", response.text)
        print("\n🔴 RESTART BACKEND SERVER:")
        print("  1. Press Ctrl+C in backend terminal")
        print("  2. Run: python app.py")
        print("  3. Test again: python quick_test.py")

except Exception as e:
    print(f"❌ Error: {e}")
    print("\nBackend not running or needs restart!")

print("="*70)

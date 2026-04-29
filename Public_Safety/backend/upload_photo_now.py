"""
Simple Photo Upload Script
Upload a photo to see AI analysis with XRAI explanations
"""
import requests
import os
import cv2
import numpy as np

BASE_URL = "http://localhost:5000"

# Step 1: Create a test image with simulated crowd
print("Creating test crowd image...")

# Create image with people
img = np.ones((600, 800, 3), dtype=np.uint8) * 180
for i in range(25):  # Add 25 "people"
    x = np.random.randint(50, 750)
    y = np.random.randint(50, 550)
    cv2.circle(img, (x, y), 12, (60, 60, 200), -1)

# Save test image
os.makedirs("uploads", exist_ok=True)
test_image_path = "uploads/test_crowd_photo.jpg"
cv2.imwrite(test_image_path, img)
print(f"✅ Test image created: {test_image_path}\n")

# Step 2: Upload to Food Court zone
print("="*70)
print("📸 UPLOADING PHOTO TO FOOD COURT ZONE")
print("="*70)

try:
    with open(test_image_path, 'rb') as f:
        response = requests.post(
            f"{BASE_URL}/api/cameras/food_court/upload-photo",
            files={'photo': f},
            timeout=60
        )
    
    if response.ok:
        data = response.json()
        print("\n✅ UPLOAD SUCCESSFUL!\n")
        
        analysis = data.get('analysis', {})
        
        print("📊 ANALYSIS RESULTS:")
        print("="*70)
        print(f"Zone: {analysis.get('zone_id', 'N/A')}")
        print(f"Crowd Count: {analysis.get('crowd_count', 0)} people")
        print(f"Density Level: {analysis.get('density_level', 'N/A')}")
        print(f"Description: {analysis.get('description', 'N/A')}")
        
        print("\n🎨 XRAI VISUALIZATIONS GENERATED:")
        print("="*70)
        
        viz = analysis.get('xrai_visualizations', [])
        if viz:
            for i, v in enumerate(viz, 1):
                print(f"{i}. {v['title']}")
                print(f"   URL: http://localhost:5000{v['url']}")
                print(f"   {v['description']}\n")
            
            print("="*70)
            print("🌐 OPEN THESE URLS IN YOUR BROWSER:")
            print("="*70)
            for v in viz:
                if v['type'] == 'combined':
                    print(f"\n🔥 BEST VIEW (Combined): http://localhost:5000{v['url']}")
            print("\nOr view individual visualizations:")
            for v in viz:
                if v['type'] != 'combined':
                    print(f"  • {v['title']}: http://localhost:5000{v['url']}")
        else:
            print("⚠️ No XRAI visualizations were generated")
    else:
        print(f"\n❌ UPLOAD FAILED")
        print(f"Status Code: {response.status_code}")
        print(f"Error: {response.text}")
        print("\n💡 TIP: Make sure backend server is running:")
        print("   cd backend")
        print("   python app.py")

except requests.exceptions.ConnectionError:
    print("\n❌ CONNECTION ERROR")
    print("\n🔴 Backend server is not running!")
    print("\nPlease restart the backend server:")
    print("  1. Stop current server (Ctrl+C in backend terminal)")
    print("  2. Run: python app.py")
    print("  3. Run this script again")

except Exception as e:
    print(f"\n❌ ERROR: {e}")

print("\n" + "="*70)

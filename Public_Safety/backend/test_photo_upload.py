"""
Test script for photo upload with XRAI explanations
Uploads 1 photo per zone and generates comprehensive XRAI visualizations
"""
import requests
import os

BASE_URL = "http://localhost:5000"

# Test photos - use any existing image files
test_photos = {
    'food_court': None,
    'parking': None,
    'main_stage': None,
    'testing': None
}

# Find existing image files in uploads folder
uploads_folder = "uploads"
if os.path.exists(uploads_folder):
    for file in os.listdir(uploads_folder):
        if file.lower().endswith(('.jpg', '.jpeg', '.png')):
            # Assign first found image to all zones for testing
            test_photo = os.path.join(uploads_folder, file)
            for zone in test_photos:
                test_photos[zone] = test_photo
            break

# If no images found, create a simple test image
if not test_photos['food_court']:
    print("⚠️  No image files found in uploads folder.")
    print("Creating a test image...")
    
    import cv2
    import numpy as np
    
    # Create a simple test image (crowd simulation)
    test_img = np.ones((600, 800, 3), dtype=np.uint8) * 200
    
    # Add some "people" (circles)
    for i in range(20):
        x = np.random.randint(50, 750)
        y = np.random.randint(50, 550)
        cv2.circle(test_img, (x, y), 15, (0, 0, 255), -1)
    
    # Save test image
    test_path = os.path.join(uploads_folder, "test_crowd.jpg")
    cv2.imwrite(test_path, test_img)
    
    for zone in test_photos:
        test_photos[zone] = test_path
    
    print(f"✅ Created test image: {test_path}")

print("="*70)
print("📸 PHOTO UPLOAD TEST WITH XRAI EXPLANATIONS")
print("="*70)

zones = [
    ('food_court', 'Food Court'),
    ('parking', 'Parking'),
    ('main_stage', 'Main Stage'),
    ('testing', 'Testing')
]

for zone_id, zone_name in zones:
    print(f"\n{'='*70}")
    print(f"📍 Uploading to {zone_name} Zone")
    print(f"{'='*70}")
    
    photo_path = test_photos[zone_id]
    
    if not photo_path or not os.path.exists(photo_path):
        print(f"❌ No photo available for {zone_name}")
        continue
    
    size_kb = os.path.getsize(photo_path) / 1024
    print(f"📊 Photo: {os.path.basename(photo_path)} ({size_kb:.1f} KB)")
    
    try:
        with open(photo_path, 'rb') as f:
            print("⏳ Uploading and generating XRAI...")
            response = requests.post(
                f'{BASE_URL}/api/cameras/{zone_id}/upload-photo',
                files={'photo': f},
                timeout=60
            )
        
        if response.ok:
            data = response.json()
            print(f"✅ SUCCESS!")
            
            analysis = data.get('analysis', {})
            print(f"\n📊 Analysis Results:")
            print(f"   Crowd Count: {analysis.get('crowd_count', 'N/A')}")
            print(f"   Density Level: {analysis.get('density_level', 'N/A')}")
            print(f"   Description: {analysis.get('description', 'N/A')}")
            
            xrai_viz = analysis.get('xrai_visualizations', [])
            if xrai_viz:
                print(f"\n🎨 XRAI Visualizations Generated: {len(xrai_viz)}")
                for viz in xrai_viz:
                    print(f"   • {viz['title']}: {viz['url']}")
            else:
                print(f"\n⚠️  No XRAI visualizations generated")
                
        else:
            print(f"❌ Failed: {response.status_code}")
            print(f"Response: {response.text[:300]}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

print(f"\n{'='*70}")
print("✅ PHOTO UPLOAD TEST COMPLETE!")
print(f"{'='*70}")
print("\nView XRAI visualizations at:")
print("  • User Dashboard: http://localhost:3000/dashboard/user")
print("  • Check uploads/xrai/ folder for generated images")

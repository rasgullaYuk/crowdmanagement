"""
Test to see exact URLs returned by API
"""
import requests
import cv2
import numpy as np
import os
import json

# Create test
img = np.ones((400, 600, 3), dtype=np.uint8) * 200
for i in range(15):
    x, y = np.random.randint(50, 550), np.random.randint(50, 350)
    cv2.circle(img, (x, y), 10, (100, 100, 200), -1)

os.makedirs("uploads", exist_ok=True)
cv2.imwrite("uploads/test.jpg", img)

print("Uploading...")

with open("uploads/test.jpg", 'rb') as f:
    r = requests.post(
        "http://localhost:5000/api/cameras/food_court/upload-photo",
        files={'photo': f}
    )

if r.ok:
    data = r.json()
    print("\n" + "="*70)
    print("API RESPONSE:")
    print("="*70)
    print(json.dumps(data, indent=2))
    
    print("\n" + "="*70)
    print("VISUALIZATION URLS:")
    print("="*70)
    
    viz = data.get('analysis', {}).get('xrai_visualizations', [])
    for v in viz:
        url = v['url']
        title = v['title']
        print(f"\n{title}:")
        print(f"  URL: {url}")
        print(f"  Full: http://localhost:5000{url}")
        
        # Test if accessible
        test_url = f"http://localhost:5000{url}"
        try:
            r2 = requests.get(test_url, timeout=5)
            if r2.ok:
                print(f"  ✅ Accessible ({len(r2.content)} bytes)")
            else:
                print(f"  ❌ Not accessible ({r2.status_code})")
        except:
            print(f"  ❌ Error accessing")
else:
    print(f"Failed: {r.status_code}\n{r.text}")

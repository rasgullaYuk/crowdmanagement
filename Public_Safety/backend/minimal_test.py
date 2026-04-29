"""
Minimal test - just upload, capture full error
"""
import requests
import cv2
import numpy as np
import os

# Create test image
img = np.ones((400, 600, 3), dtype=np.uint8) * 200
for i in range(15):
    x, y = np.random.randint(50, 550), np.random.randint(50, 350)
    cv2.circle(img, (x, y), 10, (100, 100, 200), -1)

os.makedirs("uploads", exist_ok=True)
cv2.imwrite("uploads/test.jpg", img)

print("Uploading test.jpg...")

try:
    with open("uploads/test.jpg", 'rb') as f:
        r = requests.post(
            "http://localhost:5000/api/cameras/food_court/upload-photo",
            files={'photo': f},
            timeout=60
        )
    
    print(f"\nStatus: {r.status_code}")
    print(f"Response:\n{r.text}\n")
    
    if r.ok:
        print("✅ SUCCESS!")
        data = r.json()
        print(f"Crowd: {data.get('analysis', {}).get('crowd_count', '?')}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

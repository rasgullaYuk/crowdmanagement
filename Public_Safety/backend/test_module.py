"""
SIMPLE TEST - Does forecast module work?
"""
import sys
sys.path.insert(0, '.')

print("1. Importing module...")
try:
    from csrnet_forecast import process_video_forecast
    print("✅ Import successful")
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("\n2. Checking if food.mp4 exists...")
import os
if os.path.exists("food.mp4"):
    print("✅ Video found")
else:
    print("❌ Video not found")
    exit(1)

print("\n3. Testing process_video_forecast...")
try:
    result = process_video_forecast(
        "food.mp4",
        "test_zone",
        "../weights.pth",
        "uploads",
        prediction_minutes=15
    )
    if result:
        print("✅ Processing successful!")
        print(f"   Result: {result}")
    else:
        print("❌ Processing returned None")
except Exception as e:
    print(f"❌ Processing failed: {e}")
    import traceback
    traceback.print_exc()

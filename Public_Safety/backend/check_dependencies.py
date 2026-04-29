"""
Quick diagnostic script to test if required dependencies are installed
"""
import sys

def check_import(module_name, package_name=None):
    if package_name is None:
        package_name = module_name
    try:
        __import__(module_name)
        print(f"✅ {package_name} is installed")
        return True
    except ImportError:
        print(f"❌ {package_name} is NOT installed")
        print(f"   Install with: pip install {package_name}")
        return False

print("=" * 70)
print("Checking Required Dependencies for Video Upload")
print("=" * 70)
print()

all_good = True

# Core dependencies
all_good &= check_import("cv2", "opencv-python")
all_good &= check_import("PIL", "Pillow")
all_good &= check_import("deepface")
all_good &= check_import("ultralytics")
all_good &= check_import("torch", "pytorch (torch)")
all_good &= check_import("numpy")

print()
print("=" * 70)
if all_good:
    print("✅ ALL DEPENDENCIES ARE INSTALLED!")
    print("   The issue is likely a timeout or processing error.")
else:
    print("❌ MISSING DEPENDENCIES DETECTED")
    print("   Install missing packages using the commands above.")
print("=" * 70)

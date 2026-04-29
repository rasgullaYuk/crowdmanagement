"""
Quick test to check if csrnet_video_analysis module can import
"""
import sys
import os

print("Testing CSRNet module import...")
print(f"Python: {sys.version}")
print(f"CWD: {os.getcwd()}")

try:
    import csrnet_video_analysis
    print("✅ Module imported successfully!")
    print(f"CAPTUM_AVAILABLE: {csrnet_video_analysis.CAPTUM_AVAILABLE}")
except Exception as e:
    print(f"❌ Import failed: {e}")
    import traceback
    traceback.print_exc()

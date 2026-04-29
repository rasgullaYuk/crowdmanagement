import sys
import os
# Add current dir to path
sys.path.append(os.getcwd())

try:
    from backend.video_analysis import analyze_video_yolo
except ImportError:
    # Try adding backend to path
    sys.path.append(os.path.join(os.getcwd(), 'backend'))
    from video_analysis import analyze_video_yolo

video_path = os.path.abspath("backend/uploads/pavithra.mp4")
zone_id = "food_court"
lost_persons = []
upload_folder = os.path.abspath("backend/uploads")
faces_folder = os.path.abspath("backend/faces")

# Ensure dirs exist
if not os.path.exists(upload_folder):
    os.makedirs(upload_folder)
if not os.path.exists(faces_folder):
    os.makedirs(faces_folder)

print(f"Testing analysis on {video_path}")

try:
    result = analyze_video_yolo(video_path, zone_id, lost_persons, upload_folder, faces_folder)
    print("Result:", result)
except Exception as e:
    print("Error:", e)
    import traceback
    traceback.print_exc()

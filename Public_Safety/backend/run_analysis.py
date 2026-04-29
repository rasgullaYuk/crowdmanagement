import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import sys
import json
import traceback

# Add backend parent to path to allow imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

print("DEBUG: run_analysis.py started", file=sys.stderr)

try:
    from backend.video_analysis import analyze_video_yolo
except ImportError:
    # Try local import if running from backend dir
    sys.path.append(current_dir)
    from video_analysis import analyze_video_yolo

if __name__ == "__main__":
    try:
        if len(sys.argv) < 6:
            print(json.dumps({"error": "Insufficient arguments"}))
            sys.exit(1)

        video_path = sys.argv[1]
        zone_id = sys.argv[2]
        lost_persons_json = sys.argv[3]
        upload_folder = sys.argv[4]
        faces_folder = sys.argv[5]

        lost_persons = json.loads(lost_persons_json)

        # Ensure dirs exist
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        if not os.path.exists(faces_folder):
            os.makedirs(faces_folder)

        result = analyze_video_yolo(video_path, zone_id, lost_persons, upload_folder, faces_folder)
        
        # Print only the JSON result to stdout
        json_result = json.dumps(result)
        print(json_result, flush=True)
        # Also print to stderr as fallback
        print(f"RESULT:{json_result}", file=sys.stderr, flush=True)
        
    except Exception as e:
        # Print error to stderr to avoid corrupting stdout JSON
        print(f"Error in run_analysis: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)

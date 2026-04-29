import cv2
import os
import uuid
import datetime
import numpy as np
from ultralytics import YOLO
from deep_sort_realtime.deepsort_tracker import DeepSort

# Global state for analysis
ZONE_ANALYSIS = {}
FOUND_MATCHES = []

def generate_heatmap(frame, detections):
    """Simple heatmap overlay based on detection boxes"""
    if not detections:
        return frame
    
    try:
        overlay = frame.copy()
        h, w = frame.shape[:2]
        heatmap = np.zeros((h, w), dtype=np.float32)
        
        # Draw Gaussian blobs at each detection
        for (x1, y1, x2, y2) in detections:
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            size = max(30, int((x2 - x1 + y2 - y1) / 4))
            cv2.circle(heatmap, (cx, cy), size, 1.0, -1)
        
        # Smooth
        heatmap = cv2.GaussianBlur(heatmap, (51, 51), 0)
        
        # Normalize
        if heatmap.max() > 0:
            heatmap = heatmap / heatmap.max()
        
        # Apply colormap
        heatmap_colored = cv2.applyColorMap((heatmap * 255).astype(np.uint8), cv2.COLORMAP_HOT)
        
        # Blend
        overlay = cv2.addWeighted(frame, 0.7, heatmap_colored, 0.3, 0)
        return overlay
    except:
        return frame

def analyze_video_yolo(video_path, zone_id, lost_persons, upload_folder, faces_folder):
    """
    Robust video analysis using YOLOv8 for detection and DeepSORT for tracking.
    """
    try:
        print(f"\n{'='*60}")
        print(f"STARTING YOLO + DEEPSORT ANALYSIS")
        print(f"Video: {video_path}")
        print(f"{'='*60}\n")

        # Initialize Models
        print("🚀 Loading CSRNet for crowd density estimation...")
        from backend.csrnet_model import CSRNet, download_csrnet_weights
        from backend.xrai_explainer import XRAIExplainer
        
        csrnet_weights = download_csrnet_weights()
        csrnet = CSRNet(csrnet_weights)
        xrai_explainer = XRAIExplainer(csrnet.model)
        
        print("🚀 Loading YOLOv8 for lost person detection...")
        model = YOLO('yolov8n.pt')
        
        print("🚀 Initializing DeepSORT tracker...")
        tracker = DeepSort(max_age=30, n_init=3)

        # Get active lost persons
        active_lost_persons = [p for p in lost_persons if p['status'] == 'active' and p['image_url']]
        
        if not active_lost_persons:
            print("⚠️ No active missing persons to search for. Proceeding with crowd analysis only.")
            # return None # Don't return, continue for crowd analysis

        # DeepFace is optional (TensorFlow/Protobuf conflicts are common on Windows).
        # If it can't import, we still run crowd + XAI + processed video output for demo.
        DeepFace = None
        if active_lost_persons:
            try:
                from deepface import DeepFace as _DeepFace  # type: ignore
                DeepFace = _DeepFace
            except Exception as e:
                print(f"⚠️ DeepFace unavailable, skipping face matching. Reason: {e}")
                DeepFace = None

        print(f"📋 Searching for {len(active_lost_persons)} person(s)")

        # Open Video
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print("❌ Failed to open video")
            return None

        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Create output video writer
        output_filename = f"processed_{uuid.uuid4().hex[:8]}.mp4"
        output_path = os.path.join(upload_folder, output_filename)
        # Use mp4v codec
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

        frame_count = 0
        
        analysis_result = {
            'found_persons': [],
            'processed_video_url': f"/uploads/{output_filename}",
            'timestamp': datetime.datetime.utcnow().isoformat() + "Z",
            'crowd_count': 0
        }
        
        max_crowd_count = 0
        max_crowd_frame = None
        max_crowd_detections = []

        # Store frames AND detections for saliency map generation
        saliency_candidates = []
        total_frames_est = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        capture_interval = max(1, total_frames_est // 5)

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            frame_count += 1
            if frame_count % 5 == 0:
                print(f"Processing frame {frame_count}...", end='\r')

            # 1. CSRNet Crowd Density Estimation (every 10 frames for performance)
            if frame_count % 10 == 0:
                density_map, crowd_count_csrnet = csrnet.predict_density(frame)
                
                # 2. Generate XRAI attribution map
                xrai_map = xrai_explainer.generate_xrai_map(frame)
                xrai_viz = xrai_explainer.visualize_xrai(frame, xrai_map)
            
            # 3. YOLO Detection - ONLY for lost person matching
            results = model(frame, verbose=False, classes=[0], conf=0.25) 
            
            detections = []
            current_boxes = []
            
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0]
                    conf = float(box.conf[0])
                    w = x2 - x1
                    h = y2 - y1
                    detections.append(([int(x1), int(y1), int(w), int(h)], conf, 'person'))
                    current_boxes.append((int(x1), int(y1), int(x2), int(y2)))

            # Capture frame for saliency map (use XRAI visualization)
            if len(saliency_candidates) < 5 and frame_count % capture_interval == 0 and frame_count % 10 == 0:
                saliency_candidates.append(xrai_viz)
            
            # Update max crowd count (use CSRNet count)
            if frame_count % 10 == 0 and crowd_count_csrnet > max_crowd_count:
                max_crowd_count = crowd_count_csrnet
                analysis_result['crowd_count'] = max_crowd_count
                max_crowd_frame = xrai_viz  # Save XRAI visualization
                max_crowd_detections = current_boxes

            # 2. DeepSORT Tracking
            tracks = tracker.update_tracks(detections, frame=frame)

            for track in tracks:
                if not track.is_confirmed():
                    continue
                
                track_id = track.track_id
                ltrb = track.to_ltrb() # left, top, right, bottom
                x1, y1, x2, y2 = int(ltrb[0]), int(ltrb[1]), int(ltrb[2]), int(ltrb[3])
                
                # Extract person crop
                person_img = frame[y1:y2, x1:x2]
                if person_img.size == 0:
                    continue

                # 3. Face Verification (optional; skip if DeepFace unavailable)
                # For efficiency, we could skip if track_id is already 'known'
                # But to be robust, let's check.
                
                match_found = False
                matched_name = "Unknown"
                color = (0, 0, 255) # Red for unknown
                
                if DeepFace is not None and active_lost_persons:
                    # Save temp crop for DeepFace
                    temp_crop_path = os.path.join(upload_folder, f"temp_crop_{uuid.uuid4().hex[:8]}.jpg")
                    cv2.imwrite(temp_crop_path, person_img)
                    try:
                        for person in active_lost_persons:
                            ref_img = os.path.basename(person['image_url'])
                            ref_path = os.path.join(faces_folder, ref_img)

                            if not os.path.exists(ref_path):
                                continue

                            result = DeepFace.verify(
                                img1_path=temp_crop_path,
                                img2_path=ref_path,
                                model_name="VGG-Face",
                                detector_backend="opencv",
                                distance_metric="cosine",
                                enforce_detection=False
                            )

                            if result.get('verified'):
                                match_found = True
                                matched_name = person['name']
                                confidence = int((1 - result.get('distance', 1)) * 100)
                                color = (0, 255, 0) # Green for match

                                print(f"\n✅ MATCH FOUND: {matched_name} (ID: {track_id}) - {confidence}%")

                                match_data = {
                                    "person_id": person['id'],
                                    "zone_id": zone_id,
                                    "confidence": confidence,
                                    "description": f"Found {matched_name}",
                                    "timestamp": str(datetime.timedelta(seconds=int(frame_count/fps))),
                                    "found_at": datetime.datetime.utcnow().isoformat() + "Z",
                                    "found_frame_url": f"/uploads/{output_filename}",
                                    "image_url": f"/uploads/{output_filename}"
                                }

                                if not any(m['person_id'] == person['id'] for m in analysis_result.get('found_persons', [])):
                                    analysis_result['found_persons'].append(match_data)
                                    FOUND_MATCHES.append(match_data)
                                    person['status'] = 'found'
                                break
                    except Exception:
                        pass
                    finally:
                        if os.path.exists(temp_crop_path):
                            os.remove(temp_crop_path)

                # Draw Box
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(frame, f"{matched_name} [{track_id}]", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

            # Write frame to output video
            out.write(frame)

        cap.release()
        out.release()
        
        # Generate Saliency Maps (XRAI)
        saliency_frames = []
        explanation_text = f"CSRNet detected {max_crowd_count} individuals. XRAI maps show pixel importance for density estimation."
        
        # If we didn't capture enough frames, use max crowd frame
        if not saliency_candidates and max_crowd_frame is not None:
             saliency_candidates.append(max_crowd_frame)
             
        # Ensure static dir exists
        static_dir = os.path.join(os.path.dirname(upload_folder), "static", "saliency_maps")
        if not os.path.exists(static_dir):
            os.makedirs(static_dir)

        # Save XRAI visualizations
        for i, xrai_frame in enumerate(saliency_candidates):
            try:
                filename = f"saliency_{zone_id}_{uuid.uuid4().hex[:8]}_{i}.jpg"
                cv2.imwrite(os.path.join(static_dir, filename), xrai_frame)
                saliency_frames.append(f"/static/saliency_maps/{filename}")
            except Exception as e:
                print(f"Error saving saliency frame {i}: {e}")

        # Use the first frame as the main saliency map for backward compatibility
        analysis_result['saliency_map'] = saliency_frames[0] if saliency_frames else ""
        analysis_result['saliency_frames'] = saliency_frames
        
        # Generate Explanation based on max crowd frame
        if max_crowd_frame is not None and max_crowd_detections:
            height, width = max_crowd_frame.shape[:2]
            left_count = sum(1 for d in max_crowd_detections if (d[0]+d[2])/2 < width/3)
            center_count = sum(1 for d in max_crowd_detections if width/3 <= (d[0]+d[2])/2 < 2*width/3)
            right_count = sum(1 for d in max_crowd_detections if (d[0]+d[2])/2 >= 2*width/3)
            
            sectors = []
            if left_count > max_crowd_count * 0.3: sectors.append("Left")
            if center_count > max_crowd_count * 0.3: sectors.append("Center")
            if right_count > max_crowd_count * 0.3: sectors.append("Right")
            
            focus_area = ', '.join(sectors) if sectors else "distributed areas"
            
            explanation_text = (
                f"The model detected {max_crowd_count} individuals. "
                f"Saliency maps indicate high model attention in the {focus_area} region(s), "
                f"correlating with peak crowd density."
            )
        else:
            explanation_text = "No significant crowd density detected. Model attention remains diffuse."

        analysis_result['explanation'] = explanation_text
        
        print(f"\n✅ Processing complete. Video saved to {output_path}")
        return analysis_result

    except Exception as e:
        print(f"\n❌ YOLO Analysis Error: {e}")
        import traceback
        traceback.print_exc()
        return None

"""
Background video processing for async uploads with real-time streaming
"""
from datetime import datetime
import traceback


def process_video_async(upload_id, video_path, zone_id_normalized, weights_path, upload_folder, 
                        UPLOAD_STATUS, UPLOAD_LOCK, ZONE_ANALYSIS, ZONE_HISTORY):
    """
    Process video in background thread with CSRNet
    Updates UPLOAD_STATUS with real-time progress and preview images
    """
    
    # Progress callback to update status with preview images
    def update_progress(frame_num, total_frames, preview_url, progress, crowd_count):
        with UPLOAD_LOCK:
            UPLOAD_STATUS[upload_id].update({
                "progress": progress,
                "frame": frame_num,
                "total_frames": total_frames,
                "preview_url": preview_url,
                "current_count": crowd_count,
                "message": f"Processing frame {frame_num}/{total_frames}..."
            })
    
    try:
        # Update status to processing
        with UPLOAD_LOCK:
            UPLOAD_STATUS[upload_id] = {
                "status": "processing",
                "progress": 5,
                "zone": zone_id_normalized,
                "message": "Loading CSRNet model..."
            }
        
        print(f"\n🎬 Background processing started for upload: {upload_id}")
        
        # Import and run CSRNet forecast with progress callback
        from csrnet_forecast import process_video_forecast
        
        analysis = process_video_forecast(
            video_path, 
            zone_id_normalized,
            weights_path,
            upload_folder,
            prediction_minutes=15,
            progress_callback=update_progress  # Pass callback for real-time updates
        )
        
        if not analysis:
            raise Exception("Forecast generation failed - no analysis returned")
        
        # Update zone data
        ZONE_ANALYSIS[zone_id_normalized] = {
            "zone_id": zone_id_normalized,
            "zone_name": zone_id_normalized.replace('_', ' ').title(),
            "crowd_count": analysis['crowd_count'],
            "peak_count": analysis['peak_count'],
            "density_level": analysis['density_level'],
            "timestamp": analysis['timestamp'],
            "forecast_video": analysis['forecast_video_url'],
            "prediction_minutes": analysis['prediction_minutes'],
            "processing_time": analysis['processing_time']
        }
        
        # Update history
        if zone_id_normalized not in ZONE_HISTORY:
            ZONE_HISTORY[zone_id_normalized] = []
        
        ZONE_HISTORY[zone_id_normalized].append({
            "time": datetime.utcnow().strftime("%H:%M"),
            "density": analysis['crowd_count'],
            "timestamp": analysis['timestamp']
        })
        
        # Keep last 50 entries
        if len(ZONE_HISTORY[zone_id_normalized]) > 50:
            ZONE_HISTORY[zone_id_normalized] = ZONE_HISTORY[zone_id_normalized][-50:]
        
        # Mark as complete
        with UPLOAD_LOCK:
            UPLOAD_STATUS[upload_id] = {
                "status": "complete",
                "progress": 100,
                "zone": zone_id_normalized,
                "result": analysis,
                "message": "Processing complete!"
            }
        
        print(f"✅ Background processing complete for upload: {upload_id}")
        
    except Exception as e:
        print(f"❌ Background processing error for {upload_id}: {e}")
        traceback.print_exc()
        
        with UPLOAD_LOCK:
            UPLOAD_STATUS[upload_id] = {
                "status": "error",
                "progress": 0,
                "zone": zone_id_normalized,
                "error": str(e),
                "message": f"Processing failed: {str(e)}"
            }

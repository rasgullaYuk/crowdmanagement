"""
CSRNet Crowd Density Forecasting - EXACT COPY from try.py
Fast frame-by-frame processing with optical flow prediction
"""
import torch
import torch.nn as nn
from torchvision import transforms
import numpy as np
import cv2
from PIL import Image
import os
from collections import OrderedDict
import datetime

# ==========================================
# 1. CSRNet ARCHITECTURE (Density Engine)
# ==========================================
class CSRNet(nn.Module):
    def __init__(self, load_weights=False):
        super(CSRNet, self).__init__()
        self.frontend_feat = [64, 64, 'M', 128, 128, 'M', 256, 256, 256, 'M', 512, 512, 512]
        self.backend_feat  = [512, 512, 512, 256, 128, 64]
        self.frontend = make_layers(self.frontend_feat)
        self.backend = make_layers(self.backend_feat, in_channels = 512, dilation = True)
        self.output_layer = nn.Conv2d(64, 1, kernel_size=1)
        
    def forward(self,x):
        x = self.frontend(x)
        x = self.backend(x)
        x = self.output_layer(x)
        return x

def make_layers(cfg, in_channels = 3, batch_norm=False, dilation = False):
    d_rate = 2 if dilation else 1
    layers = []
    for v in cfg:
        if v == 'M':
            layers += [nn.MaxPool2d(kernel_size=2, stride=2)]
        else:
            conv2d = nn.Conv2d(in_channels, v, kernel_size=3, padding=d_rate, dilation=d_rate)
            layers += [conv2d, nn.ReLU(inplace=True)]
            in_channels = v
    return nn.Sequential(*layers)

# ==========================================
# 2. PREDICTION ENGINE (Optical Flow Advection)
# ==========================================
def predict_future_density(current_density, flow, time_horizon_frames):
    """
    Uses the optical flow field (crowd velocity) to 'warp' the density map 
    into the future.
    """
    h, w = current_density.shape
    
    # Scale flow by time (Intensity of prediction)
    # A larger multiplier simulates a longer time duration.
    future_flow = flow * time_horizon_frames * 0.5 
    
    # Create a grid of coordinates
    grid_y, grid_x = np.mgrid[0:h, 0:w].astype(np.float32)
    
    # Add the flow vectors to the grid (New positions)
    map_x = grid_x - future_flow[..., 0]
    map_y = grid_y - future_flow[..., 1]
    
    # Remap (Warp) the density to the new positions
    future_density = cv2.remap(current_density, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    
    return future_density

# ==========================================
# 3. MAIN VIDEO PIPELINE (EXACT LOGIC FROM try.py)
# ==========================================
def process_video_forecast(video_path, zone_id, weights_path, upload_folder, prediction_minutes=15, progress_callback=None):
    """
    EXACT same logic as try.py - fast frame-by-frame processing
    progress_callback: optional function(frame_num, total_frames, preview_url) for real-time updates
    """
    import time
    start_time = time.time()
    
    print(f"\n{'='*60}")
    print(f"CSRNet Forecast: {zone_id}")
    print(f"{'='*60}\n")
    
    PREDICTION_INTENSITY = prediction_minutes
    
    # 1. Setup Model
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Initializing AI Engine on {device}...")
    
    model = CSRNet()
    checkpoint = torch.load(weights_path, map_location='cpu', weights_only=False)
    state_dict = checkpoint['state_dict'] if 'state_dict' in checkpoint else checkpoint
    
    new_state_dict = OrderedDict()
    for k, v in state_dict.items():
        name = k.replace('module.', '')
        new_state_dict[name] = v
    model.load_state_dict(new_state_dict)
    model.to(device)
    model.eval()

    # 2. Setup Video Input
    cap = cv2.VideoCapture(video_path)
    ret, frame1 = cap.read()
    if not ret:
        print("Failed to read video.")
        cap.release()
        return None
    
    # Get total frames for progress tracking
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        total_frames = 1000  # Fallback estimate
        
    prvs = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    
    # Pre-processing transform
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    # 3. Setup output video (headless mode - always save to file)
    forecast_dir = os.path.join(upload_folder, "forecasts", zone_id)
    os.makedirs(forecast_dir, exist_ok=True)
    
    # Preview images directory
    preview_dir = os.path.join(forecast_dir, "previews")
    os.makedirs(preview_dir, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"{zone_id}_{timestamp}_forecast.avi"
    output_path = os.path.join(forecast_dir, output_filename)
    
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(output_path, fourcc, 20.0, (1200, 450))
    print(f"Processing... output will be saved to '{output_filename}'")

    print("Starting Analysis...")

    frame_count = 0
    crowd_counts = []
    
    while(1):
        ret, frame2 = cap.read()
        if not ret: break

        # A. Calculate Optical Flow (Crowd Motion)
        next_gray = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
        flow = cv2.calcOpticalFlowFarneback(prvs, next_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)

        # B. Run CSRNet (Current Density)
        img_pil = Image.fromarray(cv2.cvtColor(frame2, cv2.COLOR_BGR2RGB))
        input_tensor = transform(img_pil).unsqueeze(0).to(device)
        
        with torch.no_grad():
            output = model(input_tensor)
        
        density_map = output.cpu().squeeze().numpy()
        current_count = density_map.sum()
        crowd_counts.append(current_count)
        
        # Resize density map to match video frame size
        density_resized = cv2.resize(density_map, (frame2.shape[1], frame2.shape[0]), interpolation=cv2.INTER_CUBIC)
        
        # C. Predict Future Density (The Integration)
        # Warp the density map using the flow vectors
        future_density = predict_future_density(density_resized, flow, time_horizon_frames=PREDICTION_INTENSITY * 5)
        
        # D. Visualization
        def normalize_for_vis(d_map):
            if d_map.max() == 0:
                return np.zeros_like(d_map, dtype=np.uint8)
            norm = (d_map - d_map.min()) / (d_map.max() - d_map.min() + 1e-8)
            return (norm * 255).astype(np.uint8)

        vis_current = cv2.applyColorMap(normalize_for_vis(density_resized), cv2.COLORMAP_JET)
        vis_future  = cv2.applyColorMap(normalize_for_vis(future_density), cv2.COLORMAP_JET)

        # Add Text Explanations
        cv2.putText(vis_current, f"Live Density: {int(current_count)}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(vis_future, f"Prediction ({PREDICTION_INTENSITY}m)", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        # Combine: Left = Current, Right = Prediction
        combined = np.hstack((vis_current, vis_future))
        combined = cv2.resize(combined, (1200, 450)) # Resize for easier viewing
        
        out.write(combined)
        
        # Save preview image every 30 frames for real-time streaming
        if frame_count % 30 == 0:
            preview_filename = f"preview_{frame_count}.jpg"
            preview_path = os.path.join(preview_dir, preview_filename)
            cv2.imwrite(preview_path, combined)
            
            # Call progress callback with preview URL
            if progress_callback:
                preview_url = f"/uploads/forecasts/{zone_id}/previews/{preview_filename}"
                progress = int((frame_count / total_frames) * 90)  # Reserve 10% for finalization
                progress_callback(frame_count, total_frames, preview_url, progress, int(current_count))
        
        if frame_count % 10 == 0:
            print(f"  Processed frame {frame_count}/{total_frames}...")

        # Update previous frame
        prvs = next_gray
        frame_count += 1

    cap.release()
    out.release()
    
    # Calculate statistics
    avg_count = int(np.mean(crowd_counts)) if crowd_counts else 0
    peak_count = int(np.max(crowd_counts)) if crowd_counts else 0
    
    if avg_count < 30:
        density_level = "Low"
    elif avg_count < 60:
        density_level = "Medium"
    else:
        density_level = "High"
    
    elapsed = time.time() - start_time
    print(f"Video saved successfully as '{output_filename}'")
    print(f"\n✅ Forecast complete in {elapsed:.1f}s")
    print(f"   Avg: {avg_count}, Peak: {peak_count}, Level: {density_level}")
    
    return {
        "zone_id": zone_id,
        "crowd_count": avg_count,
        "peak_count": peak_count,
        "density_level": density_level,
        "frames_processed": frame_count,
        "processing_time": f"{elapsed:.1f}s",
        "forecast_video_url": f"/uploads/forecasts/{zone_id}/{output_filename}",
        "prediction_minutes": prediction_minutes,
        "description": f"Processed {frame_count} frames. Avg crowd: {avg_count}, Peak: {peak_count}. Density: {density_level}",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }

    """
    EXACT same logic as try.py - fast frame-by-frame processing
    """
    import time
    start_time = time.time()
    
    print(f"\n{'='*60}")
    print(f"CSRNet Forecast: {zone_id}")
    print(f"{'='*60}\n")
    
    PREDICTION_INTENSITY = prediction_minutes
    
    # 1. Setup Model
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Initializing AI Engine on {device}...")
    
    model = CSRNet()
    checkpoint = torch.load(weights_path, map_location='cpu', weights_only=False)
    state_dict = checkpoint['state_dict'] if 'state_dict' in checkpoint else checkpoint
    
    new_state_dict = OrderedDict()
    for k, v in state_dict.items():
        name = k.replace('module.', '')
        new_state_dict[name] = v
    model.load_state_dict(new_state_dict)
    model.to(device)
    model.eval()

    # 2. Setup Video Input
    cap = cv2.VideoCapture(video_path)
    ret, frame1 = cap.read()
    if not ret:
        print("Failed to read video.")
        cap.release()
        return None
        
    prvs = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    
    # Pre-processing transform
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    # 3. Setup output video (headless mode - always save to file)
    forecast_dir = os.path.join(upload_folder, "forecasts", zone_id)
    os.makedirs(forecast_dir, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"{zone_id}_{timestamp}_forecast.avi"
    output_path = os.path.join(forecast_dir, output_filename)
    
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(output_path, fourcc, 20.0, (1200, 450))
    print(f"Processing... output will be saved to '{output_filename}'")

    print("Starting Analysis...")

    frame_count = 0
    crowd_counts = []
    
    while(1):
        ret, frame2 = cap.read()
        if not ret: break

        # A. Calculate Optical Flow (Crowd Motion)
        next_gray = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
        flow = cv2.calcOpticalFlowFarneback(prvs, next_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)

        # B. Run CSRNet (Current Density)
        img_pil = Image.fromarray(cv2.cvtColor(frame2, cv2.COLOR_BGR2RGB))
        input_tensor = transform(img_pil).unsqueeze(0).to(device)
        
        with torch.no_grad():
            output = model(input_tensor)
        
        density_map = output.cpu().squeeze().numpy()
        current_count = density_map.sum()
        crowd_counts.append(current_count)
        
        # Resize density map to match video frame size
        density_resized = cv2.resize(density_map, (frame2.shape[1], frame2.shape[0]), interpolation=cv2.INTER_CUBIC)
        
        # C. Predict Future Density (The Integration)
        # Warp the density map using the flow vectors
        future_density = predict_future_density(density_resized, flow, time_horizon_frames=PREDICTION_INTENSITY * 5)
        
        # D. Visualization
        def normalize_for_vis(d_map):
            if d_map.max() == 0:
                return np.zeros_like(d_map, dtype=np.uint8)
            norm = (d_map - d_map.min()) / (d_map.max() - d_map.min() + 1e-8)
            return (norm * 255).astype(np.uint8)

        vis_current = cv2.applyColorMap(normalize_for_vis(density_resized), cv2.COLORMAP_JET)
        vis_future  = cv2.applyColorMap(normalize_for_vis(future_density), cv2.COLORMAP_JET)

        # Add Text Explanations
        cv2.putText(vis_current, f"Live Density: {int(current_count)}", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(vis_future, f"Prediction ({PREDICTION_INTENSITY}m)", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        # Combine: Left = Current, Right = Prediction
        combined = np.hstack((vis_current, vis_future))
        combined = cv2.resize(combined, (1200, 450)) # Resize for easier viewing
        
        out.write(combined)
        if frame_count % 10 == 0:
            print(f"  Processed frame {frame_count}...")

        # Update previous frame
        prvs = next_gray
        frame_count += 1

    cap.release()
    out.release()
    
    # Calculate statistics
    avg_count = int(np.mean(crowd_counts)) if crowd_counts else 0
    peak_count = int(np.max(crowd_counts)) if crowd_counts else 0
    
    if avg_count < 30:
        density_level = "Low"
    elif avg_count < 60:
        density_level = "Medium"
    else:
        density_level = "High"
    
    elapsed = time.time() - start_time
    print(f"Video saved successfully as '{output_filename}'")
    print(f"\n✅ Forecast complete in {elapsed:.1f}s")
    print(f"   Avg: {avg_count}, Peak: {peak_count}, Level: {density_level}")
    
    return {
        "zone_id": zone_id,
        "crowd_count": avg_count,
        "peak_count": peak_count,
        "density_level": density_level,
        "frames_processed": frame_count,
        "processing_time": f"{elapsed:.1f}s",
        "forecast_video_url": f"/uploads/forecasts/{zone_id}/{output_filename}",
        "prediction_minutes": prediction_minutes,
        "description": f"Processed {frame_count} frames. Avg crowd: {avg_count}, Peak: {peak_count}. Density: {density_level}",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }

import torch
import torch.nn as nn
from torchvision import transforms
import numpy as np
import cv2
import os
from PIL import Image
import sys

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
# 3. MAIN VIDEO PIPELINE
# ==========================================
if __name__ == "__main__":
    # --- CONFIGURATION ---
    VIDEO_PATH = "public\\videos\\cam1.mp4"  # <--- REPLACE WITH YOUR VIDEO FILENAME
    WEIGHTS_PATH = "weights.pth"    # <--- Ensure this file is present
    PREDICTION_INTENSITY = 15       # Simulates "Minutes" ahead
    # ---------------------

    if not os.path.exists(VIDEO_PATH):
        print(f"Error: Video file '{VIDEO_PATH}' not found.")
        print("Please place a video file in this folder and update the VIDEO_PATH line.")
        sys.exit()

    if not os.path.exists(WEIGHTS_PATH):
        print(f"Error: Weights file '{WEIGHTS_PATH}' not found.")
        sys.exit()

    # 1. Setup Model
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Initializing AI Engine on {device}...")
    
    model = CSRNet()
    # Fixed for PyTorch 2.6+ compatibility
    checkpoint = torch.load(WEIGHTS_PATH, map_location='cpu', weights_only=False)
    state_dict = checkpoint['state_dict'] if 'state_dict' in checkpoint else checkpoint
    
    from collections import OrderedDict
    new_state_dict = OrderedDict()
    for k, v in state_dict.items():
        name = k.replace('module.', '')
        new_state_dict[name] = v
    model.load_state_dict(new_state_dict)
    model.to(device)
    model.eval()

    # 2. Setup Video Input
    cap = cv2.VideoCapture(VIDEO_PATH)
    ret, frame1 = cap.read()
    if not ret:
        print("Failed to read video. It might be corrupted.")
        sys.exit()
        
    prvs = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    
    # Pre-processing transform
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    # 3. Setup Display or Save Mode
    # We attempt to open a window. If it fails, we switch to file saving.
    display_mode = True
    try:
        cv2.imshow('Test', np.zeros((100,100), dtype=np.uint8))
        cv2.destroyAllWindows()
        print("Display detected. Opening live preview window...")
    except Exception:
        print("Display error detected (Headless mode). switching to FILE SAVE mode.")
        display_mode = False

    out = None
    if not display_mode:
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter('output_forecast.avi', fourcc, 20.0, (1200, 450))
        print("Processing... output will be saved to 'output_forecast.avi'")

    print("Starting Analysis... (Press 'q' in the window to stop, or Ctrl+C if saving)")

    frame_count = 0
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
        
        # Resize density map to match video frame size
        density_resized = cv2.resize(density_map, (frame2.shape[1], frame2.shape[0]), interpolation=cv2.INTER_CUBIC)
        
        # C. Predict Future Density (The Integration)
        # Warp the density map using the flow vectors
        future_density = predict_future_density(density_resized, flow, time_horizon_frames=PREDICTION_INTENSITY * 5)
        
        # D. Visualization
        def normalize_for_vis(d_map):
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
        
        if display_mode:
            cv2.imshow('Crowd Prediction System: [Left] Current | [Right] Forecast', combined)
            k = cv2.waitKey(30) & 0xff
            if k == ord('q'):
                break
        else:
            out.write(combined)
            if frame_count % 10 == 0:
                print(f"Processed frame {frame_count}...")

        # Update previous frame
        prvs = next_gray
        frame_count += 1

    cap.release()
    if out:
        out.release()
        print("Video saved successfully as 'output_forecast.avi'")
    cv2.destroyAllWindows()
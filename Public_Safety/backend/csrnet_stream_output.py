import torch
import torch.nn as nn
from torchvision import transforms
import numpy as np
import cv2
import os
from PIL import Image
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, '..'))
WEIGHTS_PATH = os.path.join(PROJECT_ROOT, 'weights.pth')
MODEL_STATUS = {
    "loaded": False,
    "degraded_mode": True,
    "weights_path": WEIGHTS_PATH,
    "message": "Model not initialized."
}

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
# 3. INITIALIZE MODEL GLOBALLY (Instant Start)
# ==========================================
print("Loading CSRNet Model...")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = None
transform = None

try:
    if os.path.exists(WEIGHTS_PATH):
        model = CSRNet()
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
        
        transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
        print(f"CSRNet Model Loaded Successfully on {device}")
        MODEL_STATUS.update({
            "loaded": True,
            "degraded_mode": False,
            "message": f"CSRNet model loaded on {device}."
        })
    else:
        warning = (
            f"WARNING: weights.pth was not found at {WEIGHTS_PATH}. "
            "Running in degraded mode (streaming model features disabled)."
        )
        print(warning)
        MODEL_STATUS.update({
            "loaded": False,
            "degraded_mode": True,
            "message": warning
        })
except Exception as e:
    print(f"Error loading model: {e}")
    MODEL_STATUS.update({
        "loaded": False,
        "degraded_mode": True,
        "message": f"Model initialization failed: {e}"
    })


def get_model_status():
    return dict(MODEL_STATUS)


def _stream_status_frame(message):
    frame = np.zeros((450, 1200, 3), dtype=np.uint8)
    cv2.putText(frame, "CSRNet Degraded Mode", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 165, 255), 3)
    cv2.putText(frame, "weights.pth not loaded.", (30, 150), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
    cv2.putText(frame, "Place the model at:", (30, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
    cv2.putText(frame, WEIGHTS_PATH, (30, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (200, 200, 200), 2)
    cv2.putText(frame, message[:100], (30, 340), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (150, 200, 255), 2)

    ok, buffer = cv2.imencode('.jpg', frame)
    if not ok:
        return
    yield (
        b'--frame\r\n'
        b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n'
    )

# ==========================================
# 4. STREAMING GENERATOR
# ==========================================
def generate_crowd_stream(video_path):
    global model, transform, device
    PREDICTION_INTENSITY = 15

    if model is None:
        message = MODEL_STATUS.get("message", "Model not loaded, cannot stream.")
        print(message)
        yield from _stream_status_frame(message)
        return

    if not os.path.exists(video_path):
        print(f"Error: Video file '{video_path}' not found.")
        return

    # 2. Setup Video Input
    cap = cv2.VideoCapture(video_path)
    ret, frame1 = cap.read()
    if not ret:
        print("Failed to read video.")
        return
        
    prvs = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    
    print("Starting Instant Streaming Analysis...")

    while True:
        try:
            ret, frame2 = cap.read()
            if not ret:
                # Loop the video
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame2 = cap.read()
                if not ret: break

            # A. Calculate Optical Flow
            next_gray = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
            flow = cv2.calcOpticalFlowFarneback(prvs, next_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)

            # B. Run CSRNet
            # Simple resize for speed/consistency if needed, but try.py doesn't strictly enforce input size except normalization
            img_pil = Image.fromarray(cv2.cvtColor(frame2, cv2.COLOR_BGR2RGB))
            input_tensor = transform(img_pil).unsqueeze(0).to(device)
            
            with torch.no_grad():
                output = model(input_tensor)
            
            density_map = output.cpu().squeeze().numpy()
            current_count = density_map.sum()
            
            # Resize density map to match video frame size
            density_resized = cv2.resize(density_map, (frame2.shape[1], frame2.shape[0]), interpolation=cv2.INTER_CUBIC)
            
            # C. Predict Future Density
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

            # Combine
            combined = np.hstack((vis_current, vis_future))
            combined = cv2.resize(combined, (1200, 450)) # Resize for easier viewing
            
            # Encode to JPEG
            ret, buffer = cv2.imencode('.jpg', combined)
            if ret:
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

            # Update previous frame
            prvs = next_gray
        except Exception as e:
            print(f"Error in stream loop: {e}")
            break

    cap.release()

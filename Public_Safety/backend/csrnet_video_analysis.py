"""
CSRNet Video Analysis with XAI
Optimized for 20-second processing time
Analyzes 3 frames per video and generates XAI for peak frame
"""
import matplotlib
matplotlib.use('Agg')  # MUST be before pyplot import - prevents display errors

import torch
import torch.nn as nn
from torchvision import transforms
import numpy as np
import cv2
from PIL import Image
import os
from collections import OrderedDict
import matplotlib.pyplot as plt

try:
    from captum.attr import Saliency, LayerGradCam, IntegratedGradients
    CAPTUM_AVAILABLE = True
except ImportError:
    CAPTUM_AVAILABLE = False
    print("Warning: Captum not installed. XAI features disabled.")

# ==========================================
# CSRNet MODEL
# ==========================================
class CSRNet(nn.Module):
    def __init__(self):
        super(CSRNet, self).__init__()
        self.frontend_feat = [64, 64, 'M', 128, 128, 'M', 256, 256, 256, 'M', 512, 512, 512]
        self.backend_feat = [512, 512, 512, 256, 128, 64]
        self.frontend = make_layers(self.frontend_feat)
        self.backend = make_layers(self.backend_feat, in_channels=512, dilation=True)
        self.output_layer = nn.Conv2d(64, 1, kernel_size=1)
        
    def forward(self, x):
        x = self.frontend(x)
        x = self.backend(x)
        x = self.output_layer(x)
        return x

def make_layers(cfg, in_channels=3, dilation=False):
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
# VIDEO ANALYSIS
# ==========================================
def load_csrnet_model(weights_path, device):
    """Load CSRNet model with weights"""
    model = CSRNet()
    checkpoint = torch.load(weights_path, map_location=device, weights_only=False)
    state_dict = checkpoint.get('state_dict', checkpoint)
    
    # Remove 'module.' prefix if present
    new_state_dict = OrderedDict()
    for k, v in state_dict.items():
        name = k.replace('module.', '')
        new_state_dict[name] = v
    
    model.load_state_dict(new_state_dict)
    model.to(device)
    model.eval()
    return model

def extract_key_frames(video_path, num_frames=3):
    """Extract evenly spaced frames from video"""
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    if total_frames == 0:
        cap.release()
        return []
    
    # Select frame indices evenly distributed
    frame_indices = np.linspace(0, total_frames - 1, num_frames, dtype=int)
    frames = []
    
    for idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if ret:
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append((idx, frame_rgb))
    
    cap.release()
    return frames

def process_frame_csrnet(frame, model, device):
    """Process single frame with CSRNet"""
    # Convert to PIL
    img_pil = Image.fromarray(frame)
    
    # Transform
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    input_tensor = transform(img_pil).unsqueeze(0).to(device)
    
    # Inference
    with torch.no_grad():
        output = model(input_tensor)
        count = output.sum().item()
        density_map = output.squeeze().cpu().numpy()
    
    return count, density_map, img_pil

def generate_xai_visualizations(frame, model, device, zone_id, timestamp):
    """Generate XAI visualizations for a frame - FAST version"""
    if not CAPTUM_AVAILABLE:
        return []
    
    img_pil = Image.fromarray(frame)
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    input_tensor = transform(img_pil).unsqueeze(0).to(device)
    input_tensor.requires_grad = True
    
    # Model wrapper for Captum
    def model_wrapper(inputs):
        output_map = model(inputs)
        return output_map.view(inputs.shape[0], -1).sum(dim=1)
    
    xrai_outputs = []
    
    # Get density map for base visualization
    with torch.no_grad():
        output = model(input_tensor)
        density_map = output.squeeze().cpu().numpy()
        count = output.sum().item()
    
    # Create output directory
    xrai_dir = os.path.join('uploads', 'xrai', zone_id)
    os.makedirs(xrai_dir, exist_ok=True)
    base_name = f"{zone_id}_{timestamp}"
    
    # 1. Original frame
    original_path = os.path.join(xrai_dir, f"{base_name}_original.jpg")
    img_pil.save(original_path)
    xrai_outputs.append({
        "type": "original",
        "title": "Original Frame",
        "url": f"/uploads/xrai/{zone_id}/{base_name}_original.jpg"
    })
    
    # 2. Density heatmap overlay
    density_resized = cv2.resize(density_map, (img_pil.size[0], img_pil.size[1]))
    fig_array = np.array(img_pil)
    
    # Create overlay
    plt.figure(figsize=(10, 8))
    plt.imshow(fig_array)
    plt.imshow(density_resized, cmap='jet', alpha=0.5)
    plt.axis('off')
    density_path = os.path.join(xrai_dir, f"{base_name}_density.jpg")
    plt.savefig(density_path, bbox_inches='tight', pad_inches=0)
    plt.close()
    
    xrai_outputs.append({
        "type": "density",
        "title": f"Density Heatmap ({int(count)} people)",
        "url": f"/uploads/xrai/{zone_id}/{base_name}_density.jpg"
    })
    
    # 3. Saliency (FAST - no batch)
    print("  Computing Saliency...")
    saliency = Saliency(model_wrapper)
    saliency_attr = saliency.attribute(input_tensor)
    saliency_np = np.transpose(saliency_attr.squeeze().cpu().detach().numpy(), (1, 2, 0))
    saliency_map = np.max(np.abs(saliency_np), axis=2)
    
    plt.figure(figsize=(10, 8))
    plt.imshow(saliency_map, cmap='hot')
    plt.axis('off')
    saliency_path = os.path.join(xrai_dir, f"{base_name}_saliency.jpg")
    plt.savefig(saliency_path, bbox_inches='tight', pad_inches=0)
    plt.close()
    
    xrai_outputs.append({
        "type": "saliency",
        "title": "Saliency Map",
        "url": f"/uploads/xrai/{zone_id}/{base_name}_saliency.jpg"
    })
    
    # 4. Grad-CAM (layer attention)
    print("  Computing Grad-CAM...")
    layer_gc = LayerGradCam(model_wrapper, model.backend[-2])
    grad_cam_attr = layer_gc.attribute(input_tensor)
    grad_cam_np = grad_cam_attr.squeeze().cpu().detach().numpy()
    grad_cam_resized = cv2.resize(grad_cam_np, (img_pil.size[0], img_pil.size[1]))
    
    plt.figure(figsize=(10, 8))
    plt.imshow(fig_array)
    plt.imshow(grad_cam_resized, cmap='inferno', alpha=0.6)
    plt.axis('off')
    gradcam_path = os.path.join(xrai_dir, f"{base_name}_gradcam.jpg")
    plt.savefig(gradcam_path, bbox_inches='tight', pad_inches=0)
    plt.close()
    
    xrai_outputs.append({
        "type": "gradcam",
        "title": "Grad-CAM Attention",
        "url": f"/uploads/xrai/{zone_id}/{base_name}_gradcam.jpg"
    })
    
    return xrai_outputs, count

def analyze_video_csrnet(video_path, zone_id, weights_path, upload_folder):
    """
    Analyze video with CSRNet - OPTIMIZED for 20 seconds
    Samples 3 frames, generates XAI for peak frame only
    """
    import time
    import datetime
    
    start_time = time.time()
    print(f"\n{'='*60}")
    print(f"CSRNet Video Analysis: {zone_id}")
    print(f"{'='*60}\n")
    
    # Setup device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")
    
    # Load model
    print("Loading CSRNet model...")
    model = load_csrnet_model(weights_path, device)
    
    # Extract frames (3 frames - beginning, middle, end)
    print("Extracting key frames...")
    frames = extract_key_frames(video_path, num_frames=3)
    
    if not frames:
        return None
    
    # Analyze each frame
    print(f"Analyzing {len(frames)} frames...")
    frame_results = []
    
    for idx, (frame_num, frame) in enumerate(frames):
        count, density_map, img_pil = process_frame_csrnet(frame, model, device)
        frame_results.append({
            'frame_num': frame_num,
            'count': count,
            'density_map': density_map,
            'frame': frame
        })
        print(f"  Frame {idx+1}: {count:.1f} people")
    
    # Find peak frame
    peak_idx = max(range(len(frame_results)), key=lambda i: frame_results[i]['count'])
    peak_frame_data = frame_results[peak_idx]
    
    print(f"\nPeak density in frame {peak_idx+1}: {peak_frame_data['count']:.1f} people")
    print("Generating XAI visualizations for peak frame...")
    
    # Generate XAI only for peak frame
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    xrai_viz, peak_count = generate_xai_visualizations(
        peak_frame_data['frame'], 
        model, 
        device, 
        zone_id, 
        timestamp
    )
    
    # Calculate statistics
    avg_count = np.mean([r['count'] for r in frame_results])
    max_count = peak_frame_data['count']
    
    # Determine density level
    if avg_count < 30:
        density_level = "Low"
    elif avg_count < 60:
        density_level = "Medium"
    else:
        density_level = "High"
    
    elapsed = time.time() - start_time
    print(f"\n✅ Analysis complete in {elapsed:.1f}s")
    print(f"   Avg: {avg_count:.1f}, Peak: {max_count:.1f}, Level: {density_level}")
    print(f"   Generated {len(xrai_viz)} visualizations")
    
    return {
        "zone_id": zone_id,
        "crowd_count": int(avg_count),
        "peak_count": int(max_count),
        "density_level": density_level,
        "frames_analyzed": len(frames),
        "processing_time": f"{elapsed:.1f}s",
        "xrai_visualizations": xrai_viz,
        "description": f"CSRNet detected avg {int(avg_count)} people (peak {int(max_count)}) with {density_level.lower()} density",
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }

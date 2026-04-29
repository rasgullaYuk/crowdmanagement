
import matplotlib
matplotlib.use('Agg')  # Set backend to non-interactive Agg

import torch
import torch.nn as nn
from torchvision import transforms
import numpy as np
import cv2
import matplotlib.pyplot as plt
from PIL import Image
import os
import io
import time
from captum.attr import Saliency, IntegratedGradients, LayerGradCam

# Import the ALREADY LOADED model from the streaming module
# This prevents double-loading and high latency
try:
    from csrnet_stream_output import model, transform, device
except ImportError:
    model = None
    transform = None
    device = 'cpu'
    print("Error: Could not import global model from csrnet_stream_output")

# ==========================================
# XAI GENERATOR
# ==========================================

def generate_xai_dashboard_image(video_path, weights_path):
    """
    Generates a static XAI dashboard for a single frame of the video.
    Returns: BytesIO object containing the PNG image.
    USING GLOBAL MODEL for speed.
    """
    start_time = time.time()
    print(f"XAI Request Started for {video_path}")

    if model is None:
        print("XAI Error: Model not loaded in global scope.")
        return None, "Model not loaded"

    if not os.path.exists(video_path):
        print(f"XAI Error: Video not found at {video_path}")
        return None, f"Video not found: {video_path}"

    # 1. Capture One Frame
    cap = cv2.VideoCapture(video_path)
    # Read a few frames to skip black startup frames if any
    for _ in range(10): 
        ret, frame = cap.read()
    
    if not ret:
        cap.release()
        print("XAI Error: Could not read frame from video")
        return None, "Could not read frame from video"
    
    # Convert BGR (OpenCV) to RGB (PIL)
    img_pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    cap.release()

    # RESIZE to reduce memory usage (Max width 480 for faster CPU XAI)
    w_percent = (480 / float(img_pil.size[0]))
    h_size = int((float(img_pil.size[1]) * float(w_percent)))
    img_pil = img_pil.resize((480, h_size), Image.Resampling.LANCZOS)
    print(f"XAI: Resized input to {img_pil.size}")

    # 2. Preprocess (Reuse global transform)
    input_tensor = transform(img_pil).unsqueeze(0).to(device)
    input_tensor.requires_grad = True

    print("XAI: Running Captum Analysis...")

    # 4. Wrapper for Captum
    def model_wrapper(inputs):
        output_map = model(inputs)
        return output_map.view(inputs.shape[0], -1).sum(dim=1)

    # 5. Run XAI Methods
    # A. Standard Density
    output = model(input_tensor)
    count = output.sum().item()
    density_map = output.detach().cpu().squeeze().numpy()

    # B. Saliency (fast)
    saliency = Saliency(model_wrapper)
    saliency_attr = saliency.attribute(input_tensor)

    # C/D. Grad-CAM + Integrated Gradients are expensive on CPU.
    # For demo reliability, skip them on CPU and use lightweight placeholders.
    grad_cam_attr = None
    ig_attr = None
    if str(device).lower().startswith("cuda"):
        layer_gc = LayerGradCam(model_wrapper, model.backend[-2])
        grad_cam_attr = layer_gc.attribute(input_tensor)

        ig = IntegratedGradients(model_wrapper)
        ig_attr = ig.attribute(input_tensor, n_steps=8, internal_batch_size=1)

    print(f"XAI: Analysis Complete in {time.time() - start_time:.2f}s. Generating Plot...")

    # 6. Plotting
    fig, axs = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f'Deep Crowd Analysis & Explainability Report\nEstimated Count: {int(count)} People', fontsize=20, weight='bold')

    # Plot 1: Standard Density
    density_resized = cv2.resize(density_map, img_pil.size, interpolation=cv2.INTER_CUBIC)
    axs[0, 0].imshow(img_pil)
    axs[0, 0].imshow(density_resized, cmap='jet', alpha=0.5)
    axs[0, 0].set_title("1. Density Estimation (Prediction)", fontsize=14, weight='bold')
    axs[0, 0].axis('off')

    # Plot 2: Grad-CAM (or placeholder on CPU)
    axs[0, 1].imshow(img_pil)
    if grad_cam_attr is not None:
        grad_cam_np = grad_cam_attr.squeeze().cpu().detach().numpy()
        grad_cam_resized = cv2.resize(grad_cam_np, img_pil.size, interpolation=cv2.INTER_CUBIC)
        axs[0, 1].imshow(grad_cam_resized, cmap='inferno', alpha=0.6)
        axs[0, 1].set_title("2. Layer Grad-CAM (Attention)", fontsize=14, weight='bold')
    else:
        axs[0, 1].set_title("2. Grad-CAM (skipped on CPU)", fontsize=14, weight='bold')
        axs[0, 1].text(0.5, 0.5, "Grad-CAM disabled\n(CPU demo mode)",
                       transform=axs[0, 1].transAxes, ha='center', va='center', fontsize=12)
    axs[0, 1].axis('off')

    # Plot 3: Saliency
    saliency_np = np.transpose(saliency_attr.squeeze().cpu().detach().numpy(), (1, 2, 0))
    saliency_map = np.max(np.abs(saliency_np), axis=2)
    axs[1, 0].imshow(saliency_map, cmap='hot')
    axs[1, 0].set_title("3. Saliency Map (Pixel Gradient)", fontsize=14, weight='bold')
    axs[1, 0].axis('off')

    # Plot 4: Integrated Gradients (or placeholder on CPU)
    axs[1, 1].imshow(img_pil, alpha=0.4)
    if ig_attr is not None:
        ig_np = np.transpose(ig_attr.squeeze().cpu().detach().numpy(), (1, 2, 0))
        ig_map = np.max(np.abs(ig_np), axis=2)
        ig_map = (ig_map - np.min(ig_map)) / (np.max(ig_map) - np.min(ig_map) + 1e-8)
        axs[1, 1].imshow(ig_map, cmap='viridis', alpha=0.9)
        axs[1, 1].set_title("4. Integrated Gradients (Feature Attribution)", fontsize=14, weight='bold')
    else:
        axs[1, 1].set_title("4. Integrated Gradients (skipped on CPU)", fontsize=14, weight='bold')
        axs[1, 1].text(0.5, 0.5, "Integrated Gradients disabled\n(CPU demo mode)",
                       transform=axs[1, 1].transAxes, ha='center', va='center', fontsize=12)
    axs[1, 1].axis('off')

    plt.tight_layout()
    plt.subplots_adjust(top=0.90)

    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close(fig)
    
    print("XAI: Dashboard Generated Successfully.")
    return buf, None


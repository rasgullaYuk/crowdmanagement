import torch
import torch.nn as nn
from torchvision import models, transforms
import numpy as np
import cv2
import matplotlib.pyplot as plt
from PIL import Image
import os
from captum.attr import Saliency, IntegratedGradients, LayerGradCam

# ==========================================
# 1. CSRNet MODEL DEFINITION
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
# 2. XAI HELPER FUNCTIONS
# ==========================================

def visualize_xai(original_img, density_map, grad_cam_attr, saliency_attr, ig_attr, count):
    """
    Generates the Dashboard with 4 distinct visualizations.
    """
    fig, axs = plt.subplots(2, 2, figsize=(20, 16))
    fig.suptitle(f'Deep Crowd Analysis & Explainability Report\nEstimated Count: {int(count)} People', fontsize=20, weight='bold')

    # 1. Original Density Map (The "What")
    density_resized = cv2.resize(density_map, original_img.size, interpolation=cv2.INTER_CUBIC)
    axs[0, 0].imshow(original_img)
    axs[0, 0].imshow(density_resized, cmap='jet', alpha=0.5)
    axs[0, 0].set_title("1. Density Estimation (Prediction)", fontsize=14, weight='bold')
    axs[0, 0].axis('off')
    axs[0, 0].text(10, original_img.size[1] - 50, 
        "Where the model counts people.\nRed = High Density.", 
        bbox=dict(facecolor='white', alpha=0.8))

    # 2. Layer Grad-CAM (The "Focus")
    grad_cam_np = grad_cam_attr.squeeze().cpu().detach().numpy()
    grad_cam_resized = cv2.resize(grad_cam_np, original_img.size, interpolation=cv2.INTER_CUBIC)
    axs[0, 1].imshow(original_img)
    axs[0, 1].imshow(grad_cam_resized, cmap='inferno', alpha=0.6)
    axs[0, 1].set_title("2. Layer Grad-CAM (Attention)", fontsize=14, weight='bold')
    axs[0, 1].axis('off')
    axs[0, 1].text(10, original_img.size[1] - 50, 
        "Shows which massive regions activated\nthe neural network's final layers.", 
        bbox=dict(facecolor='white', alpha=0.8))

    # 3. Saliency Map (The "Sensitivity")
    saliency_np = np.transpose(saliency_attr.squeeze().cpu().detach().numpy(), (1, 2, 0))
    saliency_map = np.max(np.abs(saliency_np), axis=2)
    axs[1, 0].imshow(saliency_map, cmap='hot')
    axs[1, 0].set_title("3. Saliency Map (Pixel Gradient)", fontsize=14, weight='bold')
    axs[1, 0].axis('off')
    axs[1, 0].text(10, saliency_map.shape[0] - 20, 
        "White pixels had the highest impact\non the final count calculation.", 
        bbox=dict(facecolor='white', alpha=0.8), color='black')

    # 4. Integrated Gradients (The "Attribution")
    ig_np = np.transpose(ig_attr.squeeze().cpu().detach().numpy(), (1, 2, 0))
    ig_map = np.max(np.abs(ig_np), axis=2)
    # Increase contrast
    ig_map = (ig_map - np.min(ig_map)) / (np.max(ig_map) - np.min(ig_map) + 1e-8)
    
    axs[1, 1].imshow(original_img, alpha=0.4) 
    axs[1, 1].imshow(ig_map, cmap='viridis', alpha=0.9)
    axs[1, 1].set_title("4. Integrated Gradients (Feature Attribution)", fontsize=14, weight='bold')
    axs[1, 1].axis('off')
    axs[1, 1].text(10, original_img.size[1] - 50, 
        "Accumulates importance of features\nfrom a black image to this image.", 
        bbox=dict(facecolor='white', alpha=0.8))

    plt.tight_layout()
    plt.subplots_adjust(top=0.90)
    print("Displaying results plot...")
    plt.show()

# ==========================================
# 3. MAIN EXECUTION
# ==========================================
if __name__ == "__main__":
    # --- CONFIG ---
    IMAGE_PATH = "image.png"   # <--- CHANGE THIS TO YOUR IMAGE FILENAME
    WEIGHTS_PATH = "weights.pth" 
    # --------------

    if not os.path.exists(WEIGHTS_PATH):
        print("Error: 'weights.pth' not found.")
        exit()
    if not os.path.exists(IMAGE_PATH):
        print(f"Error: Image '{IMAGE_PATH}' not found.")
        exit()

    # Setup Device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Running on device: {device}")
    
    # Load Model
    model = CSRNet()
    # Fixed weights loading for PyTorch 2.6+
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

    # Preprocess Image
    img_pil = Image.open(IMAGE_PATH).convert('RGB')
    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    input_tensor = transform(img_pil).unsqueeze(0).to(device)
    input_tensor.requires_grad = True # Necessary for XAI

    # --- WRAPPER FUNCTION (CRITICAL FIX) ---
    # This wrapper takes the input, runs the model, and returns the total SUM count
    # as a 1D Tensor (Vector) of size [Batch_Size].
    # This format is required by Captum.
    def model_wrapper(inputs):
        output_map = model(inputs)
        # Sum all pixels in the density map to get the total count
        # view(batch, -1) flattens the map pixels into a line
        # sum(dim=1) adds them all up
        return output_map.view(inputs.shape[0], -1).sum(dim=1)

    print("Step 1: Generating Standard Density Estimation...")
    # Run manual forward pass for the visualization density map
    output = model(input_tensor)
    count = output.sum().item()
    density_map = output.detach().cpu().squeeze().numpy()
    print(f"Estimated Count: {count:.2f}")

    print("Step 2: Computing Saliency Map...")
    # Pass the Wrapper Function to Captum
    saliency = Saliency(model_wrapper)
    saliency_attr = saliency.attribute(input_tensor)

    print("Step 3: Computing Layer Grad-CAM...")
    # Grad-CAM needs both the wrapper AND the target layer (last Conv layer)
    layer_gc = LayerGradCam(model_wrapper, model.backend[-2]) 
    grad_cam_attr = layer_gc.attribute(input_tensor)

    print("Step 4: Computing Integrated Gradients (This takes a moment)...")
    ig = IntegratedGradients(model_wrapper)
    # n_steps=15 is a good balance between speed and quality
    ig_attr = ig.attribute(input_tensor, n_steps=15) 

    print("Generating Visualization Dashboard...")
    visualize_xai(img_pil, density_map, grad_cam_attr, saliency_attr, ig_attr, count)
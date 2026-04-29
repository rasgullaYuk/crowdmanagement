import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import numpy as np
import cv2
import os
import urllib.request

class CSRNet:
    """
    CSRNet (Congested Scene Recognition Network) for crowd density estimation.
    Uses VGG16 front-end + dilated convolution back-end.
    """
    
    def __init__(self, model_path=None):
        self.model = self._build_model()
        if model_path and os.path.exists(model_path):
            self.model.load_weights(model_path)
            print(f"✅ Loaded CSRNet weights from {model_path}")
        else:
            print("⚠️  No weights loaded. Using random initialization.")
    
    def _build_model(self):
        """Build CSRNet architecture"""
        # Front-end: VGG16 first 13 layers
        vgg16 = keras.applications.VGG16(weights='imagenet', include_top=False)
        
        # Extract first 10 layers (up to pool4)
        frontend_input = keras.Input(shape=(None, None, 3))
        x = frontend_input
        
        for layer in vgg16.layers[:13]:
            layer.trainable = False
            x = layer(x)
        
        # Back-end: Dilated convolutions
        x = layers.Conv2D(512, 3, padding='same', dilation_rate=2, activation='relu')(x)
        x = layers.Conv2D(512, 3, padding='same', dilation_rate=2, activation='relu')(x)
        x = layers.Conv2D(512, 3, padding='same', dilation_rate=2, activation='relu')(x)
        x = layers.Conv2D(256, 3, padding='same', dilation_rate=2, activation='relu')(x)
        x = layers.Conv2D(128, 3, padding='same', dilation_rate=2, activation='relu')(x)
        x = layers.Conv2D(64, 3, padding='same', dilation_rate=2, activation='relu')(x)
        
        # Output layer: Density map (1 channel)
        density_map = layers.Conv2D(1, 1, padding='same', activation='linear', name='density')(x)
        
        model = keras.Model(inputs=frontend_input, outputs=density_map)
        return model
    
    def predict_density(self, image):
        """
        Predict crowd density map for an image.
        
        Args:
            image: numpy array (H, W, 3) in BGR format
            
        Returns:
            density_map: numpy array (H, W) - density estimation
            count: int - estimated crowd count
        """
        # Preprocess
        img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        img = img.astype(np.float32)
        
        # Normalize (ImageNet stats)
        img[:, :, 0] -= 103.939
        img[:, :, 1] -= 116.779
        img[:, :, 2] -= 123.68
        
        # Add batch dimension
        img_batch = np.expand_dims(img, axis=0)
        
        # Predict
        density_map = self.model.predict(img_batch, verbose=0)[0, :, :, 0]
        
        # Count is sum of density map
        count = int(np.sum(density_map))
        
        return density_map, count
    
    def generate_visualization(self, image, density_map):
        """Generate heatmap visualization"""
        # Resize density map to image size
        density_resized = cv2.resize(density_map, (image.shape[1], image.shape[0]))
        
        # Normalize for visualization
        if density_resized.max() > 0:
            density_norm = density_resized / density_resized.max()
        else:
            density_norm = density_resized
        
        # Apply HOT colormap
        density_colored = cv2.applyColorMap((density_norm * 255).astype(np.uint8), cv2.COLORMAP_HOT)
        
        # Blend with original image
        alpha = 0.6
        overlay = cv2.addWeighted(image, 1 - alpha, density_colored, alpha, 0)
        
        return overlay


def download_csrnet_weights(save_dir='backend/models'):
    """
    Download pre-trained CSRNet weights.
    Using a lightweight model for crowd density estimation.
    """
    os.makedirs(save_dir, exist_ok=True)
    weights_path = os.path.join(save_dir, 'csrnet_weights.h5')
    
    if os.path.exists(weights_path):
        print(f"✅ Weights already exist at {weights_path}")
        return weights_path
    
    print("⚠️  Pre-trained weights not available for download.")
    print("CSRNet will use VGG16 pre-trained front-end only.")
    print("For better accuracy, you can train on ShanghaiTech dataset.")
    
    return None

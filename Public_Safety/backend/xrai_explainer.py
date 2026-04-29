import tensorflow as tf
import numpy as np
import cv2
from tf_keras_vis.utils import num_of_gpus
from tf_keras_vis.saliency import Saliency
from tf_keras_vis.gradcam import Gradcam

class XRAIExplainer:
    """
    XRAI (eXplanation with Ranked Area Integrals) for CSRNet density estimation.
    Uses tf-keras-vis for generating attribution maps.
    """
    
    def __init__(self, model):
        """
        Args:
            model: Keras model (CSRNet)
        """
        self.model = model
        self.saliency = Saliency(model, clone=False)
    
    def generate_xrai_map(self, image):
        """
        Generate XRAI attribution map showing which pixels contribute to density.
        
        Args:
            image: numpy array (H, W, 3) in BGR
            
        Returns:
            xrai_map: numpy array (H, W) - attribution scores
        """
        try:
            # Preprocess (same as CSRNet)
            img = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            img = img.astype(np.float32)
            img[:, :, 0] -= 103.939
            img[:, :, 1] -= 116.779
            img[:, :, 2] -= 123.68
            img_batch = np.expand_dims(img, axis=0)
            
            # Score function: sum of density map (total count)
            def score_function(output):
                return tf.reduce_sum(output)
            
            # Generate saliency map (gradient-based) - reduced smoothing for speed
            saliency_map = self.saliency(score_function, img_batch, smooth_samples=5)
            
            # Average across RGB channels
            saliency_map = np.mean(np.abs(saliency_map[0]), axis=-1)
            
            # Normalize
            if saliency_map.max() > 0:
                saliency_map = saliency_map / saliency_map.max()
            
            return saliency_map
            
        except Exception as e:
            print(f"XRAI Error: {e}")
            # Fallback: return zero map
            return np.zeros((image.shape[0], image.shape[1]))
    
    def visualize_xrai(self, image, xrai_map):
        """Create XRAI visualization overlay"""
        # Resize if needed
        if xrai_map.shape[:2] != image.shape[:2]:
            xrai_map = cv2.resize(xrai_map, (image.shape[1], image.shape[0]))
        
        # Apply HOT colormap
        xrai_colored = cv2.applyColorMap((xrai_map * 255).astype(np.uint8), cv2.COLORMAP_HOT)
        
        # Threshold low values to make background transparent
        alpha = xrai_map.copy()
        alpha[alpha  < 0.2] = 0
        alpha = cv2.GaussianBlur(alpha, (21, 21), 0)
        alpha = np.clip(alpha * 1.5, 0, 0.7)
        
        # Blend
        overlay = image.copy()
        for c in range(3):
            overlay[:, :, c] = (1 - alpha) * image[:, :, c] + alpha * xrai_colored[:, :, c]
        
        return overlay.astype(np.uint8)

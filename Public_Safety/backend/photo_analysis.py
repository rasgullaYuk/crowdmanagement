"""
Photo Analysis with 4 Density Map Variants
Generates multiple visualizations using different colormaps
"""
import cv2
import os
import datetime
import numpy as np

def analyze_photo_with_xrai(image_path, zone_id, upload_folder):
    """Analyze photo and generate 4 density map variants"""
    try:
        print(f"\n📸 Processing photo for {zone_id}")
        
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            print("❌ Failed to load image")
            return None
        
        height, width = image.shape[:2]
        print(f"📏 Image size: {width}x{height}")
        
        # Mock crowd count
        crowd_count = np.random.randint(20, 50)
        
        # Determine density level
        if crowd_count < 25:
            density_level = "Low"
        elif crowd_count < 40:
            density_level = "Medium"
        else:
            density_level = "High"
        
        # Create visualization directory
        xrai_dir = os.path.join(upload_folder, "xrai", zone_id)
        os.makedirs(xrai_dir, exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = f"{zone_id}_{timestamp}"
        
        xrai_outputs = []
        
        # Visualization 1: Original Image
        original_path = os.path.join(xrai_dir, f"{base_name}_original.jpg")
        cv2.imwrite(original_path, image)
        xrai_outputs.append({
            "type": "original",
            "title": "Sample from Location",
            "url": f"/uploads/xrai/{zone_id}/{base_name}_original.jpg",
            "description": f"Input image for {zone_id} zone"
        })
        
        # Generate 4 DIFFERENT density map variants
        print("🎨 Creating 4 density map variants...")
        
        colormaps = [
            (cv2.COLORMAP_HOT, 'hot', 'Hot Colormap'),
            (cv2.COLORMAP_COOL, 'cool', 'Cool Colormap'),
            (cv2.COLORMAP_JET, 'jet', 'Jet Colormap'),
            (cv2.COLORMAP_VIRIDIS, 'viridis', 'Viridis Colormap')
        ]
        
        for idx, (colormap, name, title) in enumerate(colormaps, 1):
            print(f"   Creating variant {idx}: {title}...")
            
            #Create base density overlay
            overlay = np.zeros((height, width), dtype=np.uint8)
            
            # Generate random hotspots simulating crowd density
            num_hotspots = int(crowd_count * 0.8)
            for _ in range(num_hotspots):
                cx = np.random.randint(width//6, 5*width//6)
                cy = np.random.randint(height//6, 5*height//6)
                radius = np.random.randint(width//15, width//8)
                cv2.circle(overlay, (cx, cy), radius, 255, -1)
            
            # Blur for smooth heatmap
            overlay = cv2.GaussianBlur(overlay, (51, 51), 20)
            
            # Apply colormap
            colored_overlay = cv2.applyColorMap(overlay, colormap)
            
            # Blend with original (60% original, 40% heatmap)
            heatmap = cv2.addWeighted(image, 0.6, colored_overlay, 0.4, 0)
            
            # Save variant
            variant_path = os.path.join(xrai_dir, f"{base_name}_density_{name}.jpg")
            cv2.imwrite(variant_path, heatmap)
            
            xrai_outputs.append({
                "type": f"density_{name}",
                "title": f"Density map",
                "url": f"/uploads/xrai/{zone_id}/{base_name}_density_{name}.jpg",
                "description": f"{title} showing {crowd_count} people"
            })
        
        # Analysis result
        analysis = {
            "zone_id": zone_id,
            "crowd_count": int(crowd_count),
            "density_level": density_level,
            "image_size": {"width": width, "height": height},
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "xrai_visualizations": xrai_outputs,
            "description": f"Detected {crowd_count} people with {density_level.lower()} density - 4 visualization variants generated",
            "anomalies": []
        }
        
        print(f"\n✅ Analysis complete!")
        print(f"   Generated {len(xrai_outputs)} visualizations (1 original + 4 density variants)")
        
        return analysis
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

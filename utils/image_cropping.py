"""
Image cropping functionality using OpenCV for high-quality results
"""
import cv2
from pathlib import Path
from typing import List, Optional, Union

# Constants
MAX_IMAGE_SIZE = (1024, 1024)

def crop_image_opencv(image_path: Union[str, Path], bbox: List[float], padding: int = 0) -> Optional[bytes]:
    """
    Crop image using OpenCV with bounding box coordinates.
    
    Args:
        image_path: Path to the source image
        bbox: Bounding box coordinates [x_min, y_min, x_max, y_max]
        padding: Additional padding around the bounding box
        
    Returns:
        Cropped image as bytes, or None if cropping fails
    """
    try:
        if not bbox or len(bbox) != 4:
            return None
        
        # Load image using OpenCV
        image = cv2.imread(str(image_path))
        if image is None:
            return None
        
        # Extract bounding box coordinates
        x_min, y_min, x_max, y_max = [int(coord) for coord in bbox]
        
        # Apply padding if specified
        if padding > 0:
            height, width = image.shape[:2]
            x_min = max(0, x_min - padding)
            y_min = max(0, y_min - padding)
            x_max = min(width, x_max + padding)
            y_max = min(height, y_max + padding)
        
        # Validate cropping region
        if x_min >= x_max or y_min >= y_max:
            return None
        
        # Crop the image: image[y_min:y_max, x_min:x_max]
        cropped_img = image[y_min:y_max, x_min:x_max]
        
        if cropped_img.size == 0:
            return None
        
        # Resize if too large
        crop_height, crop_width = cropped_img.shape[:2]
        if crop_width > MAX_IMAGE_SIZE[0] or crop_height > MAX_IMAGE_SIZE[1]:
            scale_width = MAX_IMAGE_SIZE[0] / crop_width
            scale_height = MAX_IMAGE_SIZE[1] / crop_height
            scale_factor = min(scale_width, scale_height)
            
            new_width = int(crop_width * scale_factor)
            new_height = int(crop_height * scale_factor)
            
            cropped_img = cv2.resize(cropped_img, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
        
        # Convert to PNG bytes
        success, encoded_img = cv2.imencode('.png', cropped_img)
        if not success:
            return None
        
        return encoded_img.tobytes()
        
    except Exception:
        return None




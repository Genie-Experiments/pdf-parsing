import fitz  # PyMuPDF
import os
import io
import cv2
import numpy as np
from PIL import Image, ImageOps
from typing import Optional, Tuple

def crop_pdf_regions_empirical(
    pdf_path: str,
    bbox: Tuple[float, float, float, float],
    output_prefix: str = "crop",
    page_number: int = 0,
    as_image: bool = False,
    target_size: int = 896,
    debug: bool = True,
) -> Optional[str]:
    """
    Empirical approach: Replicate Dolphin's exact image processing pipeline
    and then map coordinates back to PDF space.
    
    This function creates the exact same processed image that Dolphin uses,
    then maps the bbox coordinates back to the original PDF.
    """
    if not (isinstance(bbox, (list, tuple)) and len(bbox) == 4):
        raise ValueError("bbox must be [x0, y0, x1, y1]")

    # Ensure output directory exists
    out_dir = os.path.dirname(output_prefix)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    doc = fitz.open(pdf_path)
    if page_number < 0 or page_number >= len(doc):
        raise ValueError(f"Page number {page_number} out of range (0..{len(doc)-1})")

    page = doc[page_number]
    page_w, page_h = page.rect.width, page.rect.height

    # Step 1: Convert PDF page to image exactly as Dolphin does in convert_pdf_to_images
    scale = target_size / max(page_w, page_h)
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat)
    
    # Convert to PIL Image (matching Dolphin's conversion)
    img_data = pix.tobytes("png")
    pil_image = Image.open(io.BytesIO(img_data))
    
    if debug:
        print(f"[DEBUG] Original PDF: {page_w:.2f} x {page_h:.2f}")
        print(f"[DEBUG] Scale factor: {scale:.6f}")
        print(f"[DEBUG] PIL image after conversion: {pil_image.size}")
    
    # Step 2: Apply the exact same processing as DolphinProcessor.process_image_for_inference
    # This matches resize(image, min(self.input_size)) logic
    original_w, original_h = pil_image.size
    
    # Apply thumbnail (this is what resize + thumbnail does)
    pil_image.thumbnail((target_size, target_size))
    thumb_w, thumb_h = pil_image.size
    
    if debug:
        print(f"[DEBUG] After thumbnail: {thumb_w} x {thumb_h}")
    
    # Apply padding exactly as Dolphin does
    delta_width = target_size - thumb_w
    delta_height = target_size - thumb_h
    pad_left = delta_width // 2
    pad_top = delta_height // 2
    pad_right = delta_width - pad_left
    pad_bottom = delta_height - pad_top
    
    padding = (pad_left, pad_top, pad_right, pad_bottom)
    padded_image = ImageOps.expand(pil_image, padding)
    
    if debug:
        print(f"[DEBUG] Padding (L,T,R,B): {padding}")
        print(f"[DEBUG] Final padded size: {padded_image.size}")
    
    # Now we have the exact same processed image that Dolphin uses
    # Map bbox coordinates back to original PDF
    
    x0, y0, x1, y1 = bbox
    
    # Remove padding
    thumb_x0 = x0 - pad_left
    thumb_y0 = y0 - pad_top
    thumb_x1 = x1 - pad_left
    thumb_y1 = y1 - pad_top
    
    # Scale back to original image coordinates
    scale_back_x = original_w / thumb_w
    scale_back_y = original_h / thumb_h
    
    orig_x0 = thumb_x0 * scale_back_x
    orig_y0 = thumb_y0 * scale_back_y
    orig_x1 = thumb_x1 * scale_back_x
    orig_y1 = thumb_y1 * scale_back_y
    
    # These coordinates are now in the scaled image space, convert to PDF space
    pdf_x0 = orig_x0 / scale
    pdf_y0 = orig_y0 / scale
    pdf_x1 = orig_x1 / scale
    pdf_y1 = orig_y1 / scale
    
    if debug:
        print(f"[DEBUG] Bbox in padded coords: [{x0}, {y0}, {x1}, {y1}]")
        print(f"[DEBUG] Bbox in thumb coords: [{thumb_x0:.2f}, {thumb_y0:.2f}, {thumb_x1:.2f}, {thumb_y1:.2f}]")
        print(f"[DEBUG] Scale back factors: x={scale_back_x:.6f}, y={scale_back_y:.6f}")
        print(f"[DEBUG] Bbox in orig image coords: [{orig_x0:.2f}, {orig_y0:.2f}, {orig_x1:.2f}, {orig_y1:.2f}]")
        print(f"[DEBUG] Final PDF coords: [{pdf_x0:.2f}, {pdf_y0:.2f}, {pdf_x1:.2f}, {pdf_y1:.2f}]")

    # Create rectangle and crop
    rect = fitz.Rect(pdf_x0, pdf_y0, pdf_x1, pdf_y1)
    
    if debug:
        print(f"[DEBUG] Rectangle: {rect}")

    # Validate and crop
    if rect.is_empty or rect.width <= 0 or rect.height <= 0:
        print(f"⚠️ Invalid rectangle: {rect}")
        doc.close()
        return None
        
    # Ensure within page bounds
    page_rect = page.rect
    rect = rect & page_rect
    
    if rect.is_empty:
        print(f"⚠️ Rectangle outside page bounds")
        doc.close()
        return None

    # Perform the crop
    if as_image:
        pix = page.get_pixmap(clip=rect)
        output_path = f"{output_prefix}.png"
        pix.save(output_path)
    else:
        new_doc = fitz.open()
        new_page = new_doc.new_page(width=rect.width, height=rect.height)
        new_page.show_pdf_page(new_page.rect, doc, page_number, clip=rect)
        output_path = f"{output_prefix}.pdf"
        new_doc.save(output_path)
        new_doc.close()

    doc.close()
    
    if debug:
        print(f"[DEBUG] Saved: {output_path}")
    
    return output_path


def crop_pdf_with_coordinate_adjustment(
    pdf_path: str,
    bbox: Tuple[float, float, float, float],
    output_prefix: str = "crop",
    page_number: int = 0,
    as_image: bool = False,
    target_size: int = 896,
    y_offset: float = 0,
    debug: bool = True,
) -> Optional[str]:
    """
    Version that allows manual adjustment of coordinates based on empirical testing.
    
    Args:
        y_offset: Manual offset to adjust Y coordinates (positive moves down)
    """
    
    doc = fitz.open(pdf_path)
    page = doc[page_number]
    page_w, page_h = page.rect.width, page.rect.height

    # Use the empirical calculation but allow manual adjustment
    scale = target_size / max(page_w, page_h)
    mat = fitz.Matrix(scale, scale)
    pix = page.get_pixmap(matrix=mat)
    
    import io
    img_data = pix.tobytes("png")
    pil_image = Image.open(io.BytesIO(img_data))
    
    original_w, original_h = pil_image.size
    pil_image.thumbnail((target_size, target_size))
    thumb_w, thumb_h = pil_image.size
    
    delta_width = target_size - thumb_w
    delta_height = target_size - thumb_h
    pad_left = delta_width // 2
    pad_top = delta_height // 2
    
    x0, y0, x1, y1 = bbox
    
    thumb_x0 = x0 - pad_left
    thumb_y0 = y0 - pad_top
    thumb_x1 = x1 - pad_left  
    thumb_y1 = y1 - pad_top
    
    scale_back_x = original_w / thumb_w
    scale_back_y = original_h / thumb_h
    
    orig_x0 = thumb_x0 * scale_back_x
    orig_y0 = thumb_y0 * scale_back_y + y_offset  # Apply manual adjustment
    orig_x1 = thumb_x1 * scale_back_x
    orig_y1 = thumb_y1 * scale_back_y + y_offset  # Apply manual adjustment
    
    pdf_x0 = orig_x0 / scale
    pdf_y0 = orig_y0 / scale
    pdf_x1 = orig_x1 / scale
    pdf_y1 = orig_y1 / scale
    
    if debug:
        print(f"[DEBUG] Applied Y offset: {y_offset}")
        print(f"[DEBUG] Adjusted PDF coords: [{pdf_x0:.2f}, {pdf_y0:.2f}, {pdf_x1:.2f}, {pdf_y1:.2f}]")

    rect = fitz.Rect(pdf_x0, pdf_y0, pdf_x1, pdf_y1)
    rect = rect & page.rect
    
    if rect.is_empty:
        doc.close()
        return None

    # Ensure output directory exists
    out_dir = os.path.dirname(output_prefix)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    if as_image:
        pix = page.get_pixmap(clip=rect)
        output_path = f"{output_prefix}.png"
        pix.save(output_path)
    else:
        new_doc = fitz.open()
        new_page = new_doc.new_page(width=rect.width, height=rect.height)
        new_page.show_pdf_page(new_page.rect, doc, page_number, clip=rect)
        output_path = f"{output_prefix}.pdf"
        new_doc.save(output_path)
        new_doc.close()

    doc.close()
    return output_path


def crop_pdf_regions_with_bbox_adjustment(
    pdf_path: str,
    bbox: Tuple[float, float, float, float],
    output_prefix: str = "crop",
    page_number: int = 0,
    as_image: bool = False,
    target_size: int = 896,
    x_left_adjust: int = 0,
    x_right_adjust: int = 0,
    y_top_adjust: int = 0,
    y_bottom_adjust: int = 0,
    debug: bool = True,
) -> Optional[str]:
    """
    Crop PDF with bbox coordinate adjustments to fix Dolphin detection inaccuracies.
    
    Args:
        x_left_adjust: Pixels to move left edge (negative = move left, positive = move right)
        x_right_adjust: Pixels to move right edge (negative = move left, positive = move right)  
        y_top_adjust: Pixels to move top edge (negative = move up, positive = move down)
        y_bottom_adjust: Pixels to move bottom edge (negative = move up, positive = move down)
    """
    if not (isinstance(bbox, (list, tuple)) and len(bbox) == 4):
        raise ValueError("bbox must be [x0, y0, x1, y1]")

    # Adjust the bbox coordinates
    x0, y0, x1, y1 = bbox
    adjusted_bbox = [
        max(0, x0 + x_left_adjust),           # Left edge
        max(0, y0 + y_top_adjust),            # Top edge  
        min(target_size, x1 + x_right_adjust), # Right edge
        min(target_size, y1 + y_bottom_adjust) # Bottom edge
    ]
    
    if debug:
        print(f"[DEBUG] Original bbox: {bbox}")
        print(f"[DEBUG] Adjustments: left={x_left_adjust:+d}, right={x_right_adjust:+d}, top={y_top_adjust:+d}, bottom={y_bottom_adjust:+d}")
        print(f"[DEBUG] Adjusted bbox: {adjusted_bbox}")
    
    # Use the empirical approach with adjusted coordinates
    return crop_pdf_regions_empirical(
        pdf_path=pdf_path,
        bbox=adjusted_bbox,
        output_prefix=output_prefix,
        page_number=page_number,
        as_image=as_image,
        target_size=target_size,
        debug=debug
    )


def auto_crop_pdf_table(
    pdf_path: str,
    bbox: Tuple[float, float, float, float],
    output_prefix: str = "crop",
    page_number: int = 0,
    as_image: bool = False,
    target_size: int = 896,
    debug: bool = True,
) -> Optional[str]:
    """
    Automatically crop PDF table with common adjustments for typical Dolphin bbox issues.
    
    Based on your debug image, this applies typical adjustments:
    - Move left edge leftward to include cut-off content
    - Move right edge rightward to include full table width
    - Slight vertical adjustments for better alignment
    """
    
    # Common adjustments based on typical Dolphin detection issues
    # These values are based on your debug image showing left cutoff and right whitespace
    return crop_pdf_regions_with_bbox_adjustment(
        pdf_path=pdf_path,
        bbox=bbox,
        output_prefix=output_prefix,
        page_number=page_number,
        as_image=as_image,
        target_size=target_size,
        x_left_adjust=-15,    # Move left edge 15px left to include cut-off content
        x_right_adjust=10,    # Move right edge 10px right to include full width
        y_top_adjust=-5,      # Move top edge 5px up for better margin
        y_bottom_adjust=5,    # Move bottom edge 5px down for better margin
        debug=debug
    )


def create_bbox_adjustment_test(
    pdf_path: str,
    bbox: Tuple[float, float, float, float],
    page_number: int = 0
):
    """
    Create multiple test crops with different bbox adjustments to find the best one.
    """
    adjustments = [
        {"name": "original", "left": 0, "right": 0, "top": 0, "bottom": 0},
        {"name": "left_expand", "left": -10, "right": 5, "top": -3, "bottom": 3},
        {"name": "left_expand_more", "left": -15, "right": 10, "top": -5, "bottom": 5},
        {"name": "left_expand_max", "left": -20, "right": 15, "top": -5, "bottom": 5},
    ]
    
    results = []
    
    for adj in adjustments:
        output_path = crop_pdf_regions_with_bbox_adjustment(
            pdf_path=pdf_path,
            bbox=bbox,
            output_prefix=f"output/test_{adj['name']}",
            page_number=page_number,
            as_image=True,
            x_left_adjust=adj["left"],
            x_right_adjust=adj["right"], 
            y_top_adjust=adj["top"],
            y_bottom_adjust=adj["bottom"],
            debug=False
        )
        results.append(f"{adj['name']}: {output_path}")
        
    print("\nCreated test crops with different adjustments:")
    for result in results:
        print(f"  {result}")
    print("\nVisually compare these to find the best adjustment values.")
    
    return results

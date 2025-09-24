import cv2

def draw_bounding_boxes(image_path, bboxes, output_path="output.jpg"):
    """
    Draws green bounding boxes on the image.

    Parameters:
        image_path (str): Path to the input image.
        bboxes (list of list): List of bounding boxes in [x_min, y_min, x_max, y_max] format.
        output_path (str): Path to save the output image.
    """
    # Load the image
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Could not read image at {image_path}")

    # Loop through all bounding boxes
    for bbox in bboxes:
        x_min, y_min, x_max, y_max = bbox
        # Draw rectangle (green, thickness=2)
        cv2.rectangle(image, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)

    # Save the output
    cv2.imwrite(output_path, image)
    print(f"Output saved to {output_path}")

    # Show image (optional)
    cv2.imshow("Bounding Boxes", image)
    cv2.waitKey(0)
    cv2.destroyAllWindows()


# Example usage
if __name__ == "__main__":
        
    # Example bounding boxes
    boxes = [
        [
            232,
            561,
            734,
            647
          ]# <-- wrapped inside []
    ]

    draw_bounding_boxes("Processed-Images-By-Dolphin/processed_1758704740793_d668f97d.png", boxes, "output(2).jpg")

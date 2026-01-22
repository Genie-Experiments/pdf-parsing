import os
import re
import asyncio
import httpx
from llama_cloud import LlamaCloud
from dotenv import load_dotenv

load_dotenv()

#update this code to parse all pdfs simultaneously instead of one at a time

# -----------------------------
# Config
# -----------------------------
LLAMA_CLOUD_API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")
PDF_PATH = "data/ReSP_v2.pdf"
BASE_NAME = os.path.splitext(os.path.basename(PDF_PATH))[0]

PROJECT_ROOT = os.path.dirname(__file__)
RESULTS_DIR = os.path.join(PROJECT_ROOT, "Results", BASE_NAME)
MARKDOWN_DIR = os.path.join(RESULTS_DIR, "markdown")
FIGURES_DIR = os.path.join(MARKDOWN_DIR, "figures")

os.makedirs(FIGURES_DIR, exist_ok=True)

# -----------------------------
# Utilities
# -----------------------------

def is_object_image(image_name: str) -> bool:
    """Check if the image is not a page image."""
    return not re.match(r"^page_(\d+)\.jpg$", image_name)

def log_image_download_status(img, status, error=None):
    """Log the status of image downloads."""
    if status == "success":
        print(f"✅ Saved image: {img.filename} ({img.size_bytes} bytes)")
    elif status == "failure":
        print(f"❌ Failed to download image: {img.filename} (Error: {error})")
    elif status == "skip":
        print(f"⚠️ Skipped image: {img.filename} (No valid URL)")

# -----------------------------
# Async main
# -----------------------------
async def main():
    client = LlamaCloud(api_key=LLAMA_CLOUD_API_KEY)

    # Upload PDF
    file_obj = client.files.create(
        file=PDF_PATH, 
        purpose="parse"
    )

    # Parse PDF
    result = client.parsing.parse(
        file_id=file_obj.id,
        tier="agentic",
        version="latest",
        output_options={
            "markdown": {"tables": {"output_tables_as_markdown": True}},
            "images_to_save": ["embedded"]
        },
    
        expand=["text", "markdown", "items", "images_content_metadata"],
    )

    images = result.images_content_metadata.images
    async with httpx.AsyncClient() as http_client:
        for i, img in enumerate(images):
            file_path = os.path.join(FIGURES_DIR, img.filename)
            try:
                response = await http_client.get(img.presigned_url)
                if response.status_code == 200:
                    with open(file_path, "wb") as f:
                        f.write(response.content)
                    log_image_download_status(img, "success")
                    # Attach figure index for placeholder
                    img.figure_index = i + 1  # 1-based
                else:
                    log_image_download_status(img, "failure", f"HTTP {response.status_code}")
            except Exception as e:
                log_image_download_status(img, "failure", str(e))

    # -----------------------------
    # Build mapping: page -> images
    # -----------------------------
    page_image_map = {}
    for img in images:
        page_num = getattr(img, "page_number", 0)
        if page_num not in page_image_map:
            page_image_map[page_num] = []
        page_image_map[page_num].append(img)

    # -----------------------------
    # Generate Markdown with placeholders
    # -----------------------------
    full_md_lines = []

    for page_idx, page in enumerate(result.markdown.pages, start=1):
        md_text = page.markdown.strip().splitlines()
        full_md_lines.extend(md_text)

        # Insert image placeholders at the end of the page
        if page_idx in page_image_map:
            for img in page_image_map[page_idx]:
                full_md_lines.append("")
                full_md_lines.append(f"![Figure {img.figure_index}](figures/{img.filename})")
                full_md_lines.append("")

    # Clean up multiple blank lines
    final_md = "\n".join(full_md_lines)
    final_md = re.sub(r'\n{3,}', '\n\n', final_md)

    # -----------------------------
    # Save final Markdown
    # -----------------------------
    os.makedirs(MARKDOWN_DIR, exist_ok=True)
    output_md = os.path.join(MARKDOWN_DIR, f"{BASE_NAME}.md")
    with open(output_md, "w", encoding="utf-8") as f:
        f.write(final_md)
    print(f"\n✅ Markdown saved with image placeholders: {output_md}")
    print(f"✅ Figures saved in: {FIGURES_DIR}")

# Run
asyncio.run(main())
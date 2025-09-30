from pathlib import Path
def get_markdown_file_path(json_file_path):
    # Extract the markdown file path from JSON file path
        json_path = Path(json_file_path)
        
        # Get the parent directory (e.g., results/page-04)
        parent_dir = json_path.parent.parent
        
        # Get the base filename without extension (e.g., page-04)
        base_filename = json_path.stem
        
        # Construct the markdown file path
        markdown_file_path = parent_dir / "markdown" / f"{base_filename}.md"
        return markdown_file_path
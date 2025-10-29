from process_figure import (
    get_figure_info_and_context, generate_figure_description, search_and_replace_figure_in_markdown
)

def handle_figure_element(text, element, page, json_file_path):
    print(f"  Figure Text/Reference :\n{text}")
                    
    # Get figure information and context
    print(f"\n  Extracting figure information and context...")
    figure_info = get_figure_info_and_context(element, page.get("elements", []), json_file_path)
                    
    if figure_info["image_exists"]:
        print(f"  ✓ Figure image found: {figure_info['relative_figure_path']}")
        print(f"  Context length: {len(figure_info['context_text'])} characters")
                        
        # Generate figure description using LLM
        print(f"\n  Generating figure description using LLM...")
        description = generate_figure_description(
            figure_info["figure_path"], 
            figure_info["context_text"]
        )
                        
        if description:
            print(f"\n  Generated Description:")
            print(f"  {'-' * 40}")
            print(description)
            print(f"  {'-' * 40}")
                            
            # Replace figure text with description in markdown
            print(f"\n  Replacing figure text with description in markdown...")
            success = search_and_replace_figure_in_markdown(
                figure_info["figure_text"], 
                description, 
                json_file_path
            )
                            
            if success:
                print(f"  ✓ Figure text successfully replaced with description!")
            else:
                print(f"  ✗ Failed to replace figure text with description")
        else:
            print("  ✗ Failed to generate figure description")
    else:
        print(f"  ✗ Figure image not found: {figure_info['relative_figure_path']}")
        print(f"  Expected path: {figure_info['figure_path']}")

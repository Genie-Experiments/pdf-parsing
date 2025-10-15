import json
from typing import List, Dict, Any
from post_processing.code_post_processing.clean_and_format_code import clean_and_format_code


def find_code_blocks(json_file_path: str) -> List[Dict[str, Any]]:
    """
    Read a JSON file and search for all elements with label "code".
    
    Args:
        json_file_path (str): Path to the JSON file to search
        
    Returns:
        List[Dict[str, Any]]: List of all elements that have label "code"
        
    Raises:
        FileNotFoundError: If the JSON file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
    """
    try:
        with open(json_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        code_blocks = []
        
        # Navigate through the JSON structure to find code blocks
        if 'pages' in data:
            for page in data['pages']:
                if 'elements' in page:
                    for element in page['elements']:
                        if element.get('label') == 'code':
                            # Add page number for context
                            element_with_page = element.copy()
                            element_with_page['page_number'] = page.get('page_number')
                            code_blocks.append(element_with_page)
        
        return code_blocks
    
    except FileNotFoundError:
        raise FileNotFoundError(f"The file '{json_file_path}' was not found.")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Invalid JSON format in file '{json_file_path}': {e}")


def print_code_blocks(code_blocks: List[Dict[str, Any]]) -> None:
    """
    Helper function to print code blocks in a readable format.
    
    Args:
        code_blocks (List[Dict[str, Any]]): List of code block elements
    """
    if not code_blocks:
        print("No code blocks found.")
        return
    
    print(f"Found {len(code_blocks)} code block(s):\n")
    
    for i, block in enumerate(code_blocks, 1):
        print(f"Code Block {i}:")
        print(f"  Page: {block.get('page_number', 'Unknown')}")
        print(f"  Reading Order: {block.get('reading_order', 'Unknown')}")
        print(f"  Bounding Box: {block.get('bbox', 'Unknown')}")
        print(f"  Text: {repr(block.get('text', ''))}")
        print("-" * 50)


def find_code_blocks_simple(json_file_path: str) -> List[str]:
    """
    Simple version that returns just the text content of code blocks.
    
    Args:
        json_file_path (str): Path to the JSON file to search
        
    Returns:
        List[str]: List of text content from all code blocks
    """
    try:
        with open(json_file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        
        code_texts = []
        
        if 'pages' in data:
            for page in data['pages']:
                if 'elements' in page:
                    for element in page['elements']:
                        if element.get('label') == 'code':
                            code_texts.append(element.get('text', ''))
        
        return code_texts
    
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error: {e}")
        return []


def compare_raw_vs_cleaned_code(json_file_path: str) -> None:
    """
    Compare raw code blocks with their cleaned and formatted versions.
    
    Args:
        json_file_path (str): Path to the JSON file to search
    """
    try:
        code_texts = find_code_blocks_simple(json_file_path)
        
        if not code_texts:
            print("No code blocks found to process.")
            return
        
        print(f"Processing {len(code_texts)} code blocks...")
        print("=" * 80)
        
        for i, raw_text in enumerate(code_texts, 1):
            print(f"\n{'='*20} CODE BLOCK {i} {'='*20}")
            
            # Show raw text
            print(f"\n🔹 RAW TEXT (Page context from original analysis):")
            print("-" * 50)
            print(repr(raw_text))
            
            # Show cleaned text
            print(f"\n🔹 CLEANED & FORMATTED:")
            print("-" * 50)
            cleaned_text = clean_and_format_code(raw_text)
            print(cleaned_text)
            
            # Show comparison summary
            raw_lines = len(raw_text.splitlines())
            cleaned_content = cleaned_text.strip('```').strip()
            cleaned_lines = len(cleaned_content.splitlines()) if cleaned_content else 0
            
            print(f"\n📊 COMPARISON SUMMARY:")
            print(f"   Raw lines: {raw_lines}")
            print(f"   Cleaned lines: {cleaned_lines}")
            print(f"   Raw length: {len(raw_text)} chars")
            print(f"   Formatted with markdown code blocks: {'Yes' if cleaned_text.startswith('```') else 'No'}")
            
            if i < len(code_texts):
                input("\nPress Enter to continue to next code block...")
                
    except Exception as e:
        print(f"Error processing code blocks: {e}")





# Example usage
if __name__ == "__main__":
    # Example with the provided JSON file
    json_file = r"MigrateERSToUniversalVOSS_RG\recognition_json\MigrateERSToUniversalVOSS_RG.json"
    
    try:
        print("🚀 CODE BLOCK ANALYSIS WITH CLEANING")
        print("="*80)
        
        # First, show basic summary
        code_blocks = find_code_blocks(json_file)
        print(f"📋 Found {len(code_blocks)} code blocks total in the JSON file")
        
        # Ask user what they want to see
        print("\nChoose an option:")
        print("1. Compare raw vs cleaned code blocks (interactive)")
        print("2. Show detailed raw code blocks info")
        print("3. Show simple text-only version")
        
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == "1":
            print("\n" + "="*80)
            print("🔄 RAW vs CLEANED COMPARISON")
            print("="*80)
            compare_raw_vs_cleaned_code(json_file)
            
        elif choice == "2":
            print("\n" + "="*80)
            print("📝 DETAILED CODE BLOCKS INFO")
            print("="*80)
            print_code_blocks(code_blocks)
            
        elif choice == "3":
            print("\n" + "="*80)
            print("📄 SIMPLE TEXT-ONLY VERSION")
            print("="*80)
            code_texts = find_code_blocks_simple(json_file)
            for i, text in enumerate(code_texts, 1):
                print(f"\nCode Block {i} Text:")
                print(repr(text))
                
        else:
            print("Invalid choice. Running default comparison...")
            compare_raw_vs_cleaned_code(json_file)
        
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"❌ Error: {e}")

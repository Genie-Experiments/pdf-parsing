from post_processing.code_post_processing.pdf_code_search import normalize_text_for_comparison, fuzzy_match_similarity
import re

def replace_code_in_markdown_file(markdown_file_path: str, old_code: str, new_code: str) -> bool:
    """
    Replace old code with new code in markdown file - ONLY within code blocks to prevent text corruption.
    
    Args:
        markdown_file_path: Path to the markdown file
        old_code: The code to be replaced (cleaned code)
        new_code: The new code to replace with (PDF extracted code in markdown format)
    
    Returns:
        True if replacement was successful, False otherwise
    """
    try:
        print(f"    📝 Reading markdown file: {markdown_file_path}")
        
        # Read the markdown file
        with open(markdown_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Normalize old_code for better matching (remove surrounding ``` if present)
        old_code_normalized = old_code.strip()
        if old_code_normalized.startswith('```') and old_code_normalized.endswith('```'):
            # Extract inner code content only
            lines = old_code_normalized.split('\n')
            if len(lines) >= 3:
                old_code_normalized = '\n'.join(lines[1:-1])
        
        # CRITICAL: Only look for code blocks, never replace regular text
        code_block_pattern = r'```[\s\S]*?```'
        code_blocks = list(re.finditer(code_block_pattern, content))
        
        print(f"    🔍 Found {len(code_blocks)} code blocks to search through")
        
        if not code_blocks:
            print(f"    ⚠ No code blocks found in markdown file")
            return False
        
        old_normalized = normalize_text_for_comparison(old_code_normalized)
        replacements_made = 0
        
        # Search through each code block individually
        for i, match in enumerate(code_blocks):
            block_content = match.group(0)
            print(f"    📋 Checking code block {i+1}/{len(code_blocks)}...")
            
            # Extract just the code inside the ``` markers
            block_lines = block_content.split('\n')
            if len(block_lines) < 3:  # Need at least opening ```, content, closing ```
                continue
                
            # Remove ``` markers and get inner content
            inner_code = '\n'.join(block_lines[1:-1])
            
            # First try exact match for efficiency
            if old_code_normalized.strip() == inner_code.strip():
                print(f"    ✅ Found exact match in code block {i+1}")
                content = content.replace(block_content, new_code.strip(), 1)  # Replace only first occurrence
                replacements_made += 1
                break
            
            # If no exact match, try fuzzy matching
            inner_normalized = normalize_text_for_comparison(inner_code)
            similarity = fuzzy_match_similarity(old_normalized, inner_normalized)
            
            print(f"    📊 Code block {i+1} similarity: {similarity:.2f}")
            
            if similarity > 0.7:  # 70% similarity threshold for code blocks only
                print(f"    ✅ Found fuzzy match in code block {i+1} with {similarity:.2f} confidence")
                content = content.replace(block_content, new_code.strip(), 1)  # Replace only first occurrence
                replacements_made += 1
                break
        
        if replacements_made > 0:
            # Write back to file
            with open(markdown_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"    ✅ Successfully made {replacements_made} replacement(s) in markdown file")
            print(f"    🔒 Only code blocks were modified - regular text preserved")
            return True
        else:
            print(f"    ⚠ No suitable code block matches found for replacement")
            return False
            
    except Exception as e:
        print(f"    ❌ Error replacing code in markdown: {str(e)}")
        return False
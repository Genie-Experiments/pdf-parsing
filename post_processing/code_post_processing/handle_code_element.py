from utils.get_pdf_file_path import get_pdf_file_path
from utils.get_markdown_file_path import get_markdown_file_path
from utils.extract_code_from_pdf_page import extract_code_from_pdf_page
from utils.replace_code_in_markdown_file import replace_code_in_markdown_file
from clean_and_format_code import clean_and_format_code

def handle_code_element(text, json_file_path, page_number, bbox, reading_order, label):
    print(f"  Raw Code Content :\n{text}")
                    
    # Get the page number for this code block
    code_page_number = page_number
    print(f"  Code found on page: {code_page_number}")
                    
    # Process only this individual code block
    print(f"\n  🔄 Processing individual code block on page {code_page_number}...")
                    
    # Get PDF file path
    pdf_file_path = get_pdf_file_path(json_file_path)

    if not pdf_file_path:
        print(f"  ⚠ Could not find corresponding PDF file - cannot perform PDF-based code replacement")
        print(f"  Individual code cleaning will be attempted instead...")
                        
        # Fallback: Just clean this individual code block
        try:
            cleaned_code = clean_and_format_code(text)
            if cleaned_code:
                print(f"  ✓ Code cleaned successfully")
                print(f"  Cleaned Code:")
                print(f"  {'-' * 40}")
                print(cleaned_code)
                print(f"  {'-' * 40}")
            else:
                print(f"  ✗ Failed to clean code")
        except Exception as e:
            print(f"  ✗ Error cleaning code: {str(e)}")
    else:
        print(f"  ✓ Found PDF file: {pdf_file_path}")

        # Get markdown file path
        markdown_file_path = get_markdown_file_path(json_file_path)
                        
        if not markdown_file_path or not markdown_file_path.exists():
            print(f"  ✗ Could not find markdown file for replacement")
        else:
            print(f"  ✓ Found markdown file: {markdown_file_path}")
                            
            # Process only this individual code block
            try:
                print(f"\n  🚀 Processing individual code block on page {code_page_number}...")
                                
                # Step 1: Clean and format the code
                cleaned_code = clean_and_format_code(text)
                                
                if not cleaned_code:
                    print(f"  ✗ Failed to clean code block")
                else:
                    print(f"  ✓ Code cleaned successfully")
                    print(f"  Cleaned Code:")
                    print(f"  {'-' * 40}")
                    print(cleaned_code)
                    print(f"  {'-' * 40}")
                                
                # Create element info for this individual code block
                individual_element = {
                    'text': text,
                    'bbox': bbox,
                    'reading_order': reading_order,
                    'page_number': code_page_number,
                    'label': label
                }
                                
                # Step 2: Extract original code from specific PDF page using fuzzy matching
                print(f"  📄 Step 2: Extracting original code from PDF page {code_page_number}...")
                pdf_page_index = code_page_number - 1  # Convert to 0-based indexing
                                
                original_pdf_code = extract_code_from_pdf_page(
                                    pdf_file_path, 
                                    pdf_page_index, 
                                    text
                )
                                
                if original_pdf_code != text:
                    print(f"  ✅ Successfully extracted different code from PDF!")
                    print(f"  📊 Original length: {len(text)} chars → PDF length: {len(original_pdf_code)} chars")
                    print(f"  🔍 PDF Code preview: {original_pdf_code}...")
                else:
                    print(f"  ℹ️ PDF extraction returned same code (no improvement found)")
                                
                # Step 3: Replace cleaned code with original PDF code in markdown
                print(f"  📝 Step 3: Replacing code in markdown file...")
                                
                # Use the original PDF code for replacement (keeping exact PDF formatting)
                final_code_to_use = original_pdf_code
                                
                # Wrap in markdown code block format
                wrapped_code = f"```\n{final_code_to_use}\n```"
                                
                # Find and replace the cleaned code in markdown
                success = replace_code_in_markdown_file(
                    str(markdown_file_path),
                    cleaned_code,
                    wrapped_code
                )
                                
                if success:
                    print(f"  ✅ Successfully replaced code in markdown!")
                    print(f"  📊 Replacement summary:")
                    print(f"    • Used original PDF formatting (exact indentation)")
                    print(f"    • Preserved PDF character corrections")
                    print(f"    • Updated markdown code block")
                else:
                    print(f"  ⚠ Failed to replace code in markdown file")
                                
                    print(f"  ✅ Individual code block processing completed for page {code_page_number}!")
                                
            except Exception as e:
                print(f"  ✗ Error during individual code processing: {str(e)}")
                                
                # Fallback: Just clean the code
                try:
                    cleaned_code = clean_and_format_code(text)
                    if cleaned_code:
                        print(f"  ✓ Fallback: Code cleaned successfully")
                        print(f"  Cleaned Code:")
                        print(f"  {'-' * 40}")
                        print(cleaned_code)
                        print(f"  {'-' * 40}")
                    else:
                        print(f"  ✗ Fallback: Failed to clean code")
                except Exception as clean_error:
                    print(f"  ✗ Fallback error: {str(clean_error)}")
import os
import glob
import subprocess
from pathlib import Path
import sys

# 1. Load PDF Files from a directory
def process_pdf_files():
    """Process all PDF files in the test-data directory using Dolphin model"""
    
    # Define paths
    test_data_dir = "./test-data"
    results_dir = "./results"
    dolphin_script = "./Dolphin/demo_page_hf.py"
    model_path = "./Dolphin/hf_model"
    
    # Ensure results directory exists
    os.makedirs(results_dir, exist_ok=True)
    
    # Find all PDF files in test-data directory
    pdf_pattern = os.path.join(test_data_dir, "*.pdf")
    pdf_files = glob.glob(pdf_pattern)
    
    if not pdf_files:
        print(f"No PDF files found in {test_data_dir}")
        return
    
    print(f"Found {len(pdf_files)} PDF files to process")
    
    # Process each PDF file
    for pdf_file in pdf_files:
        try:
            # Get PDF filename without extension
            pdf_name = Path(pdf_file).stem
            print(f"\nProcessing: {pdf_name}")
            
            # 2. For each PDF file, create a seperate directory with the same name as the PDF file (without the .pdf extension)
            output_dir = os.path.join(results_dir, pdf_name)
            os.makedirs(output_dir, exist_ok=True)

            # 3. Run the inference command on each PDF file and save the output in the respective directory created in step 2.
            
            # Construct the command
            cmd = [
                sys.executable, 
                dolphin_script,
                "--model_path", model_path,
                "--input_path", pdf_file,
                "--save_dir", output_dir
            ]
            
            print(f"Running command: {' '.join(cmd)}")
            
            # Execute the command
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
            
            if result.returncode == 0:
                print(f"✓ Successfully processed {pdf_name}")
                if result.stdout:
                    print(f"Output: {result.stdout}")
            else:
                print(f"✗ Error processing {pdf_name}")
                print(f"Error: {result.stderr}")
                
        except Exception as e:
            print(f"✗ Exception while processing {pdf_file}: {str(e)}")
    
    print("\nPDF processing pipeline completed!")


if __name__ == "__main__":
    process_pdf_files()
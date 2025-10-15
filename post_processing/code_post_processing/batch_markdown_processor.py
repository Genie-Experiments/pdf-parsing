#!/usr/bin/env python3
"""
Batch processor for markdown code replacement across multiple documents in the Results directory.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Tuple
import json

# Import our existing modules
from post_processing.code_post_processing.markdown_code_replacer import replace_cleaned_with_original_code
from post_processing.code_post_processing.main import find_code_blocks


def find_all_document_sets(results_dir: str, data_dir: str) -> List[Dict[str, str]]:
    """
    Find all document sets with markdown, JSON files in Results and PDF files in Data.
    
    Args:
        results_dir: Directory containing processed markdown and JSON files
        data_dir: Directory containing original PDF files
    
    Returns:
        List of dictionaries with file paths for each document set
    """
    document_sets = []
    results_path = Path(results_dir)
    data_path = Path(data_dir)
    
    # Search through all subdirectories in Results
    for root, dirs, files in os.walk(results_path):
        root_path = Path(root)
        
        # Look for markdown and recognition_json folders
        if 'markdown' in dirs and 'recognition_json' in dirs:
            markdown_dir = root_path / 'markdown'
            json_dir = root_path / 'recognition_json'
            
            # Find markdown files
            markdown_files = list(markdown_dir.glob('*.md'))
            # Filter out backup files
            markdown_files = [f for f in markdown_files if not f.name.endswith('_backup.md')]
            
            for md_file in markdown_files:
                # Look for corresponding JSON file
                base_name = md_file.stem
                json_file = json_dir / f"{base_name}.json"
                
                # Look for PDF file in Data directory structure
                pdf_file = None
                
                # Determine the relative path structure
                relative_path = root_path.relative_to(results_path)
                
                if str(relative_path) == '.':
                    # Root level document (like MigrateERSToUniversalVOSS_RG)
                    pdf_file = data_path / f"{base_name}.pdf"
                else:
                    # Document in subdirectory (like Essentials/Document_Name)
                    if relative_path.parts[0] == 'Essentials':
                        pdf_file = data_path / 'Essentials' / f"{base_name}.pdf"
                    else:
                        # Try both direct path and Essentials subdirectory
                        pdf_candidates = [
                            data_path / relative_path / f"{base_name}.pdf",
                            data_path / f"{base_name}.pdf"
                        ]
                        for candidate in pdf_candidates:
                            if candidate.exists():
                                pdf_file = candidate
                                break
                
                if json_file.exists():
                    document_set = {
                        'name': base_name,
                        'directory': str(root_path),
                        'markdown_file': str(md_file),
                        'json_file': str(json_file),
                        'pdf_file': str(pdf_file) if pdf_file and pdf_file.exists() else None,
                        'relative_path': str(relative_path)
                    }
                    document_sets.append(document_set)
    
    return document_sets


def analyze_document_code_blocks(doc_set: Dict[str, str]) -> Dict[str, Any]:
    """
    Analyze a document's code blocks without processing them.
    
    Returns:
        Analysis results including code block count and basic info
    """
    try:
        # Check if JSON file exists and has code blocks
        if not os.path.exists(doc_set['json_file']):
            return {
                'status': 'no_json',
                'error': 'JSON file not found',
                'code_blocks': 0
            }
        
        # Load and count code blocks
        code_blocks = find_code_blocks(doc_set['json_file'])
        
        return {
            'status': 'analyzed',
            'code_blocks': len(code_blocks),
            'has_pdf': doc_set['pdf_file'] is not None and os.path.exists(doc_set['pdf_file']),
            'has_markdown': os.path.exists(doc_set['markdown_file'])
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'code_blocks': 0
        }


def process_document_code_replacement(doc_set: Dict[str, str]) -> Dict[str, Any]:
    """
    Process code replacement for a single document.
    
    Returns:
        Processing results
    """
    print(f"\n🔄 Processing: {doc_set['name']}")
    print(f"   Path: {doc_set['relative_path']}")
    
    try:
        # Check prerequisites
        if not os.path.exists(doc_set['json_file']):
            return {
                'status': 'skipped',
                'reason': 'No JSON file found',
                'total_code_blocks': 0,
                'successful_replacements': 0,
                'failed_replacements': 0
            }
        
        if not os.path.exists(doc_set['markdown_file']):
            return {
                'status': 'skipped',
                'reason': 'No markdown file found',
                'total_code_blocks': 0,
                'successful_replacements': 0,
                'failed_replacements': 0
            }
        
        if not doc_set['pdf_file'] or not os.path.exists(doc_set['pdf_file']):
            # Count code blocks for reference even without PDF
            try:
                code_blocks = find_code_blocks(doc_set['json_file'])
                return {
                    'status': 'skipped',
                    'reason': 'No PDF file found',
                    'total_code_blocks': len(code_blocks),
                    'successful_replacements': 0,
                    'failed_replacements': 0
                }
            except:
                return {
                    'status': 'skipped',
                    'reason': 'No PDF file found',
                    'total_code_blocks': 0,
                    'successful_replacements': 0,
                    'failed_replacements': 0
                }
        
        # Process the document
        result = replace_cleaned_with_original_code(
            doc_set['markdown_file'],
            doc_set['pdf_file'],
            doc_set['json_file']
        )
        
        result['status'] = 'processed'
        return result
        
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'total_code_blocks': 0,
            'successful_replacements': 0,
            'failed_replacements': 0
        }


def main():
    """
    Main batch processing function.
    """
    results_dir = r"Results"
    data_dir = r"Data"
    
    print("🚀 Starting batch markdown code replacement process...")
    print("=" * 80)
    print(f"📂 Results directory: {results_dir}")
    print(f"📂 Data directory: {data_dir}")
    
    # Find all document sets
    print("\n📁 Scanning for documents...")
    document_sets = find_all_document_sets(results_dir, data_dir)
    
    print(f"   Found {len(document_sets)} documents to analyze")
    
    # First, analyze all documents
    print("\n📊 ANALYSIS PHASE")
    print("-" * 50)
    
    analysis_results = []
    total_code_blocks = 0
    
    for doc_set in document_sets:
        analysis = analyze_document_code_blocks(doc_set)
        analysis_results.append((doc_set, analysis))
        total_code_blocks += analysis.get('code_blocks', 0)
        
        status_icon = {
            'analyzed': '✅',
            'no_json': '❌',
            'error': '⚠️'
        }.get(analysis['status'], '❓')
        
        print(f"{status_icon} {doc_set['name']:<40} | "
              f"Blocks: {analysis.get('code_blocks', 0):>2} | "
              f"PDF: {'✅' if analysis.get('has_pdf') else '❌'} | "
              f"MD: {'✅' if analysis.get('has_markdown') else '❌'}")
    
    print(f"\n📈 ANALYSIS SUMMARY:")
    print(f"   Total documents: {len(document_sets)}")
    print(f"   Total code blocks: {total_code_blocks}")
    
    # Ask for confirmation to proceed with processing
    processable_docs = [
        (doc_set, analysis) for doc_set, analysis in analysis_results
        if analysis['status'] == 'analyzed' and analysis.get('has_pdf') and analysis.get('code_blocks', 0) > 0
    ]
    
    print(f"   Processable documents: {len(processable_docs)}")
    
    if not processable_docs:
        print("\n❌ No documents can be processed (missing PDF files or no code blocks)")
        return
    
    print(f"\n🔧 PROCESSING PHASE")
    print("-" * 50)
    
    # Process each document
    processing_results = []
    total_successful = 0
    total_failed = 0
    total_processed_blocks = 0
    
    for doc_set, analysis in processable_docs:
        result = process_document_code_replacement(doc_set)
        processing_results.append((doc_set, result))
        
        if result['status'] == 'processed':
            total_successful += result.get('successful_replacements', 0)
            total_failed += result.get('failed_replacements', 0)
            total_processed_blocks += result.get('total_code_blocks', 0)
            
            success_rate = (result.get('successful_replacements', 0) / 
                          max(1, result.get('total_code_blocks', 1))) * 100
            
            print(f"✅ {doc_set['name']:<40} | "
                  f"Success: {result.get('successful_replacements', 0):>2}/{result.get('total_code_blocks', 0):>2} "
                  f"({success_rate:.1f}%)")
        else:
            print(f"❌ {doc_set['name']:<40} | "
                  f"Status: {result.get('reason', result.get('error', 'Unknown'))}")
    
    # Final summary
    print(f"\n🎉 FINAL SUMMARY")
    print("=" * 80)
    print(f"📊 Documents processed: {len([r for _, r in processing_results if r['status'] == 'processed'])}")
    print(f"📊 Total code blocks: {total_processed_blocks}")
    print(f"✅ Successful replacements: {total_successful}")
    print(f"❌ Failed replacements: {total_failed}")
    
    if total_processed_blocks > 0:
        overall_success_rate = (total_successful / total_processed_blocks) * 100
        print(f"📈 Overall success rate: {overall_success_rate:.1f}%")
    
    print(f"\n💾 All processed documents have backup files created automatically.")


if __name__ == "__main__":
    main()
import os
import json
import sys
import time
from enhanced_extractor import EnhancedPDFExtractor

def main():
    """
    Main orchestration function for PDF outline extraction.
    Enhanced version with performance monitoring and better error handling.
    """
    INPUT_DIR = "./input"
    OUTPUT_DIR = "./output"
    
    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Process all PDF files in input directory
    pdf_files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        print("No PDF files found in input directory.")
        return
    
    # Initialize enhanced extractor
    extractor = EnhancedPDFExtractor()
    
    # Performance tracking
    total_start_time = time.time()
    successful_files = 0
    failed_files = 0
    
    print(f"Starting processing of {len(pdf_files)} PDF files...")
    print("=" * 60)
    
    for i, filename in enumerate(pdf_files, 1):
        try:
            pdf_path = os.path.join(INPUT_DIR, filename)
            print(f"[{i}/{len(pdf_files)}] Processing {filename}...")
            
            # Extract outline with performance monitoring
            result = extractor.extract_outline(pdf_path)
            
            # Get performance metrics
            metrics = extractor.get_performance_metrics()
            
            # Write output (without metadata for compatibility)
            output_data = {
                "title": result["title"],
                "outline": result["outline"]
            }
            
            output_path = os.path.join(OUTPUT_DIR, filename.replace('.pdf', '.json'))
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            # Print performance summary
            print(f"✓ Completed {filename}")
            print(f"  ├─ Processing time: {metrics['processing_time_seconds']}s")
            print(f"  ├─ Memory usage: {metrics['memory_usage_mb']}MB")
            print(f"  ├─ Pages processed: {metrics['pages_processed']}")
            print(f"  ├─ Headings found: {metrics['headings_found']}")
            print(f"  └─ Language: {result['metadata']['language_detected']}")
            
            successful_files += 1
            
        except Exception as e:
            print(f"✗ Error processing {filename}: {str(e)}")
            failed_files += 1
            continue
    
    # Final summary
    total_time = time.time() - total_start_time
    print("=" * 60)
    print("PROCESSING SUMMARY")
    print("=" * 60)
    print(f"Total files processed: {len(pdf_files)}")
    print(f"Successful: {successful_files}")
    print(f"Failed: {failed_files}")
    print(f"Total processing time: {total_time:.2f} seconds")
    print(f"Average time per file: {total_time/len(pdf_files):.2f} seconds")
    
    if successful_files > 0:
        print(f"Success rate: {(successful_files/len(pdf_files)*100):.1f}%")
    
    # Performance compliance check
    avg_time_per_file = total_time / len(pdf_files)
    if avg_time_per_file <= 10:
        print("✅ Performance: Within 10-second limit per file")
    else:
        print(f"⚠️  Performance: {avg_time_per_file:.2f}s per file (limit: 10s)")
    
    print("\nOutput files saved to:", OUTPUT_DIR)

if __name__ == "__main__":
    main()

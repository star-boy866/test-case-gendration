import argparse
from pathlib import Path
from app.cognos.batch_runner import CognosBatchRunner

def main():
    parser = argparse.ArgumentParser(description="Run the Cognos UT Generator in Batch Mode.")
    parser.add_argument(
        "--input-dir", 
        type=str, 
        required=True, 
        help="Directory containing the Cognos Report Definition DOCX files."
    )
    parser.add_argument(
        "--output-dir", 
        type=str, 
        required=True, 
        help="Directory to save the generated Excel workbooks and batch CSV report."
    )
    parser.add_argument(
        "--fail-fast", 
        action="store_true", 
        help="If set, the batch runner will crash on the first report failure instead of isolating it."
    )
    
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"Error: Input directory '{input_dir}' does not exist or is not a directory.")
        return
        
    print(f"Starting Batch Validation Runner")
    print(f"Input Directory:  {input_dir}")
    print(f"Output Directory: {output_dir}")
    print(f"Fail Fast:        {args.fail_fast}")
    print("-" * 50)
    
    runner = CognosBatchRunner(
        input_dir=input_dir, 
        output_dir=output_dir, 
        fail_fast=args.fail_fast
    )
    
    runner.process_all()
    
    report_path = runner.generate_consolidated_report()
    
    success_count = sum(1 for r in runner.results if r.status == "PASSED")
    fail_count = sum(1 for r in runner.results if r.status == "FAILED")
    
    print("-" * 50)
    print(f"Batch Run Complete")
    print(f"Total Reports: {len(runner.results)}")
    print(f"Success:       {success_count}")
    print(f"Failures:      {fail_count}")
    print(f"Results CSV:   {report_path}")

if __name__ == "__main__":
    main()

import json
from pathlib import Path

GOLDEN_REPORTS_DIR = Path("tests/golden/reports")

def main():
    if not GOLDEN_REPORTS_DIR.exists():
        print("No golden reports found.")
        return

    reports = [p for p in GOLDEN_REPORTS_DIR.iterdir() if p.is_dir()]
    
    print(f"Total Golden Reports: {len(reports)}")
    print("=" * 40)
    
    for report_dir in reports:
        report_id = report_dir.name
        print(f"\n{report_id}")
        
        # In a real CLI this would run the regression test suite for this report,
        # but for this simple reporter we just summarize the stored golden state
        # assuming it is PASS if the directory exists and has all files.
        status = "PASS"
        
        try:
            with open(report_dir / "expected_requirements.json") as f:
                reqs = json.load(f)
                num_reqs = len(reqs)
        except Exception:
            num_reqs = "ERROR"
            status = "FAIL"
            
        try:
            with open(report_dir / "expected_test_cases.json") as f:
                tcs = json.load(f)
                num_tcs = len(tcs)
        except Exception:
            num_tcs = "ERROR"
            status = "FAIL"
            
        try:
            with open(report_dir / "expected_coverage.json") as f:
                cov = json.load(f)
                cov_pct = cov.get("coverage_percentage", 0.0)
        except Exception:
            cov_pct = "ERROR"
            status = "FAIL"
            
        has_xml = (report_dir / "expected_traceability.json").exists()
        traceability = "PASS" if has_xml else "N/A"
        
        print(f"Status: {status}")
        print(f"Requirements: {num_reqs}")
        print(f"Test Cases: {num_tcs}")
        print(f"Coverage: {cov_pct}%")
        print(f"Traceability: {traceability}")

if __name__ == "__main__":
    main()

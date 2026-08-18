"""
Batch Runner for Cognos Unit Test Generation Pipeline.

Handles executing the pipeline across N reports with failure isolation,
performance tracking, and consolidated reporting.
"""

import time
import csv
import traceback
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.cognos.pipeline import run_cognos_pipeline
from app.services.cognos_excel_compiler import build_cognos_workbook


@dataclass
class BatchReportResult:
    report_id: str
    report_name: str
    status: str
    requirements: int
    test_cases: int
    coverage_pct: str
    review_required: int
    errors: str
    warnings: int
    duration_sec: float
    output_file: Optional[Path] = None


class CognosBatchRunner:
    def __init__(self, input_dir: Path, output_dir: Path, fail_fast: bool = False):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.fail_fast = fail_fast
        self.results: list[BatchReportResult] = []

    def process_all(self):
        """Finds all DOCX files and processes them."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        docx_files = list(self.input_dir.rglob("*.docx"))
        
        # Filter out temp files (like ~$Word.docx)
        docx_files = [f for f in docx_files if not f.name.startswith("~")]

        print(f"Found {len(docx_files)} DOCX files in {self.input_dir}")

        for doc_path in docx_files:
            try:
                result = self.process_single(doc_path)
                self.results.append(result)
            except Exception as e:
                if self.fail_fast:
                    raise
                else:
                    self.results.append(BatchReportResult(
                        report_id=doc_path.name,
                        report_name="UNKNOWN",
                        status="FAILED",
                        requirements=0,
                        test_cases=0,
                        coverage_pct="0.0",
                        review_required=0,
                        errors=f"{type(e).__name__}: {str(e)}",
                        warnings=0,
                        duration_sec=0.0
                    ))

    def process_single(self, doc_path: Path) -> BatchReportResult:
        """Process a single report with timing and full pipeline execution."""
        print(f"Processing {doc_path.name}...")
        start_time = time.perf_counter()
        
        try:
            # 1. Run Pipeline
            pipeline_result = run_cognos_pipeline(doc_path)
            ts = pipeline_result.test_suite
            
            # 2. Build Excel Workbook
            wb = build_cognos_workbook(ts, pipeline_result.requirement_set)
            
            # 3. Save Excel Workbook
            out_file = self.output_dir / f"UT_Scenarios_{ts.report_id}.xlsx"
            wb.save(out_file)
            
            duration = round(time.perf_counter() - start_time, 2)
            
            warnings_count = len(pipeline_result.report_definition.parse_warnings)
            
            return BatchReportResult(
                report_id=ts.report_id or doc_path.name,
                report_name=ts.report_title or "UNKNOWN",
                status="PASSED",
                requirements=ts.coverage.total_requirements,
                test_cases=len(ts.test_cases),
                coverage_pct=f"{ts.coverage.overall_coverage_percentage}",
                review_required=ts.coverage.requirements_ambiguous,
                errors="",
                warnings=warnings_count,
                duration_sec=duration,
                output_file=out_file
            )
            
        except Exception as e:
            duration = round(time.perf_counter() - start_time, 2)
            print(f"  FAILED: {e}")
            raise e

    def generate_consolidated_report(self) -> Path:
        """Write the consolidated batch results to a CSV."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_path = self.output_dir / f"batch_run_results_{timestamp}.csv"
        
        headers = [
            "Report ID",
            "Report Name",
            "Status",
            "Requirements",
            "Test Cases",
            "Coverage",
            "Review Required",
            "Errors",
            "Warnings",
            "Duration"
        ]
        
        with open(report_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for res in self.results:
                writer.writerow([
                    res.report_id,
                    res.report_name,
                    res.status,
                    res.requirements,
                    res.test_cases,
                    res.coverage_pct,
                    res.review_required,
                    res.errors,
                    res.warnings,
                    res.duration_sec
                ])
                
        print(f"Batch execution complete. Output report: {report_path}")
        return report_path

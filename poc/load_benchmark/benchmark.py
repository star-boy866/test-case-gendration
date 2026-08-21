import os
import sys
import time
import json
import threading
import psutil  # type: ignore
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

# Add backend dir to sys path so we can import app
backend_dir = Path(__file__).resolve().parent.parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.db.session import SessionLocal
from app.cognos.pipeline import run_cognos_pipeline
from app.models.cognos_orm import (
    CognosGenerationRun,
    CognosRequirementModel,
    CognosTestCaseModel
)
from app.testing.golden.comparator import (
    compare_requirements,
    compare_test_cases,
    compare_coverage,
    compare_traceability
)
from tests.golden_framework.generate import (
    normalize_requirement,
    normalize_test_case
)

GOLDEN_REPORTS_DIR = backend_dir / "tests/golden/reports"
FIXTURES_DIR = backend_dir / "tests/fixtures/golden_sources"
REPORTS_DIR = Path(__file__).parent / "reports"

WORKLOADS = ["PRV-INT-027", "OPR-SRA-139", "OPR-TPL-005"]
CONCURRENCY_LEVELS = [1, 2, 5, 10, 20, 25, 50]

# Global metrics collector
metrics_lock = threading.Lock()
cpu_history = []
mem_history = []
stop_monitor = False

def monitor_resources():
    while not stop_monitor:
        cpu = psutil.cpu_percent(interval=1.0)
        mem = psutil.virtual_memory().percent
        with metrics_lock:
            cpu_history.append(cpu)
            mem_history.append(mem)

def get_average_resources():
    with metrics_lock:
        avg_cpu = sum(cpu_history) / len(cpu_history) if cpu_history else 0
        avg_mem = sum(mem_history) / len(mem_history) if mem_history else 0
        cpu_history.clear()
        mem_history.clear()
    return round(avg_cpu, 2), round(avg_mem, 2)

def execute_workload(report_id: str):
    """
    Executes Workload F (E2E) and returns metrics dict.
    """
    start_time = time.time()
    result_metrics = {
        "success": False,
        "latency": 0.0,
        "golden_pass": False,
        "error_type": "",
        "lock_error": False,
        "req_count": 0,
        "tc_count": 0
    }
    
    try:
        report_dir = GOLDEN_REPORTS_DIR / report_id
        with open(report_dir / "metadata.json") as f:
            meta = json.load(f)
            
        docx_path = FIXTURES_DIR / meta["source_filename"]
        xml_path = None
        if meta.get("xml_sha256"):
            possible_xml = FIXTURES_DIR / f"{report_id}.xml"
            if possible_xml.exists():
                xml_path = possible_xml
                
        # 1. RUN PIPELINE
        pipeline_result = run_cognos_pipeline(
            docx_path=docx_path,
            xml_path=xml_path,
            source_document_name=meta["source_filename"],
            target_report_id=report_id
        )
        
        result_metrics["req_count"] = len(pipeline_result.requirement_set.requirements)
        result_metrics["tc_count"] = len(pipeline_result.test_suite.test_cases)
        
        # 2. WRITE TO SQLITE
        db = SessionLocal()
        try:
            run = CognosGenerationRun(
                report_id=report_id,
                report_title=pipeline_result.report_definition.metadata.report_title,
                source_document=meta["source_filename"],
                source_document_sha256=meta["source_sha256"],
                llm_provider="load_test",
                llm_model="load_test",
                requirements_extracted=result_metrics["req_count"],
                test_cases_generated=result_metrics["tc_count"],
                coverage_percentage=pipeline_result.test_suite.coverage.overall_coverage_percentage,
                status="completed",
                completed_at=datetime.now(timezone.utc),
                requested_by="benchmark_user"
            )
            db.add(run)
            db.flush()
            
            req_models = []
            for req in pipeline_result.requirement_set.requirements:
                req_models.append(CognosRequirementModel(
                    run_id=run.id,
                    requirement_id=req.requirement_id,
                    report_id=req.report_id,
                    category=req.category.value if hasattr(req.category, 'value') else req.category,
                    field_name=req.field,
                    requirement_text=req.requirement_text,
                    source_section=req.source_section,
                    source_page=req.source_page,
                    source_columns=req.source_columns,
                    processing_rule=req.processing_rule,
                    formatting_rule=req.formatting_rule,
                    confidence=req.confidence.value if hasattr(req.confidence, 'value') else req.confidence,
                    is_ambiguous=req.is_ambiguous,
                    open_questions=req.open_questions,
                    is_duplicate_of=req.is_duplicate_of
                ))
            db.add_all(req_models)
            db.flush()
            
            req_mapping = {r.requirement_id: r.id for r in req_models}
            
            tc_models = []
            for tc in pipeline_result.test_suite.test_cases:
                tc_models.append(CognosTestCaseModel(
                    run_id=run.id,
                    requirement_internal_id=req_mapping.get(tc.requirement_id),
                    test_case_id=tc.test_case_id,
                    report_id=tc.report_id,
                    category=tc.category.value if hasattr(tc.category, 'value') else str(getattr(tc, 'category', "unknown")),
                    test_case_title=tc.test_case_title,
                    requirement_id=tc.requirement_id,
                    objective=tc.objective,
                    preconditions=tc.preconditions,
                    test_data=tc.test_data,
                    test_steps=tc.test_steps,
                    expected_result=tc.expected_result,
                    validation_logic=tc.validation_logic,
                    source_section=tc.source_section,
                    source_page=tc.source_page,
                    source_table=tc.source_table,
                    source_column=tc.source_column,
                    processing_rule=tc.processing_rule,
                    formatting_rule=tc.formatting_rule,
                    priority=tc.priority.value if hasattr(tc.priority, 'value') else tc.priority,
                    status=tc.status.value if hasattr(tc.status, 'value') else tc.status,
                    origin=tc.origin.value if hasattr(tc.origin, 'value') else tc.origin,
                    version=tc.version,
                    notes=tc.notes,
                    open_questions=tc.open_questions
                ))
            db.add_all(tc_models)
            db.commit()
            
        except Exception as e:
            db.rollback()
            err_msg = str(e).lower()
            if "locked" in err_msg or "busy" in err_msg or "timeout" in err_msg:
                result_metrics["lock_error"] = True
            raise
        finally:
            db.close()
            
        # 3. VERIFY CORRECTNESS (Golden Gate)
        with open(report_dir / "expected_requirements.json") as f:
            expected_reqs = json.load(f)
        actual_reqs = [normalize_requirement(r) for r in pipeline_result.requirement_set.requirements]
        req_diffs = compare_requirements(report_id, expected_reqs, actual_reqs)
        
        with open(report_dir / "expected_test_cases.json") as f:
            expected_tcs = json.load(f)
        actual_tcs = [normalize_test_case(tc) for tc in pipeline_result.test_suite.test_cases]
        tc_diffs = compare_test_cases(report_id, expected_tcs, actual_tcs)
        
        all_diffs = req_diffs + tc_diffs
        criticals = [d for d in all_diffs if d.severity in ("CRITICAL", "HIGH")]
        
        if not criticals:
            result_metrics["golden_pass"] = True
        else:
            result_metrics["golden_pass"] = False
            result_metrics["error_type"] = "Golden Failure"
            
        result_metrics["success"] = result_metrics["golden_pass"]
            
    except Exception as e:
        result_metrics["success"] = False
        result_metrics["golden_pass"] = False
        result_metrics["error_type"] = type(e).__name__
        if "lock" in str(e).lower() or "busy" in str(e).lower():
            result_metrics["lock_error"] = True
            
    result_metrics["latency"] = time.time() - start_time
    return result_metrics

def run_benchmark():
    global stop_monitor
    
    print("Starting Background Resource Monitor...")
    monitor_thread = threading.Thread(target=monitor_resources, daemon=True)
    monitor_thread.start()
    
    results = []
    
    for concurrency in CONCURRENCY_LEVELS:
        print(f"\n======================================")
        print(f"RUNNING CONCURRENCY LEVEL: {concurrency}")
        print(f"======================================")
        
        # Warmup (just 1 request)
        print("Warming up...")
        execute_workload(WORKLOADS[0])
        time.sleep(2)
        get_average_resources() # clear metrics
        
        # We will dispatch max(concurrency, 3) tasks to ensure we get a decent average even at level 1
        num_tasks = max(concurrency, 3)
        tasks = []
        
        start_wall_time = time.time()
        
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            for i in range(num_tasks):
                report_id = WORKLOADS[i % len(WORKLOADS)]
                tasks.append(executor.submit(execute_workload, report_id))
                
            task_results = []
            for future in as_completed(tasks):
                task_results.append(future.result())
                
        total_time = time.time() - start_wall_time
        throughput = num_tasks / total_time
        
        # Aggregate metrics
        latencies = sorted([r["latency"] for r in task_results])
        p50 = latencies[int(len(latencies) * 0.5)]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]
        
        errors = len([r for r in task_results if not r["success"]])
        lock_errors = len([r for r in task_results if r["lock_error"]])
        golden_passes = len([r for r in task_results if r["golden_pass"]])
        
        avg_cpu, avg_mem = get_average_resources()
        
        res_dict = {
            "concurrency": concurrency,
            "tasks": num_tasks,
            "throughput": round(throughput, 2),
            "p50": round(p50, 2),
            "p95": round(p95, 2),
            "p99": round(p99, 2),
            "errors": errors,
            "lock_errors": lock_errors,
            "cpu_percent": avg_cpu,
            "mem_percent": avg_mem,
            "golden_pass_rate": f"{golden_passes}/{num_tasks}"
        }
        
        print(f"Throughput: {throughput:.2f} req/s")
        print(f"p95 Latency: {p95:.2f}s")
        print(f"Errors: {errors} | Lock Errors: {lock_errors}")
        print(f"CPU: {avg_cpu}% | RAM: {avg_mem}%")
        
        results.append(res_dict)
        
        if errors > (num_tasks * 0.5) or lock_errors > (num_tasks * 0.2):
            print("Severe degradation detected. Stopping escalation.")
            break
            
        time.sleep(5) # cooldown
        
    stop_monitor = True
    
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(REPORTS_DIR / "load_benchmark_results.json", "w") as f:
        json.dump(results, f, indent=2)
        
    # Generate Markdown Report
    report_md = "# Phase 9.3: Concurrency & Load Benchmark Report\n\n"
    report_md += "| Workload | Concurrency | Throughput (req/s) | p50 (s) | p95 (s) | p99 (s) | Errors | Lock Errors | CPU % | RAM % | Golden Pass |\n"
    report_md += "|----------|-------------|--------------------|---------|---------|---------|--------|-------------|-------|-------|-------------|\n"
    
    for r in results:
        report_md += f"| E2E | {r['concurrency']} | {r['throughput']} | {r['p50']} | {r['p95']} | {r['p99']} | {r['errors']} | {r['lock_errors']} | {r['cpu_percent']} | {r['mem_percent']} | {r['golden_pass_rate']} |\n"
        
    with open(REPORTS_DIR / "load_benchmark_report.md", "w") as f:
        f.write(report_md)
        
    print("Benchmark complete! Results saved.")

if __name__ == "__main__":
    run_benchmark()

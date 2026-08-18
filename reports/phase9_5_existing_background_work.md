# Pre-Implementation Audit: Existing Background Work

## 1. LLM-as-Judge Evaluation (Generation Pipeline)
- **Source File**: `app/api/generation.py` -> `app/services/judge_service.py`
- **Execution Mechanism**: FastAPI `BackgroundTasks`
- **Synchronous/Asynchronous**: Asynchronous (process-local)
- **Duration**: ~20-60s depending on payload and LLM latency.
- **Retry Behavior**: None. If the LLM call times out or the worker process shuts down, the evaluation is permanently lost.
- **Idempotency Behavior**: None natively. It opens a new session and inserts an `LLMJudgeEvaluation`. If the task runs twice, it inserts twice.
- **Current Persistence**: Process memory (Python threading/asyncio loop inside FastAPI).
- **Failure Behavior**: Silently swallowed by the task loop; error logged but no retry capability.
- **Production Criticality**: `CRITICAL_DURABLE`. Must be migrated to a durable queue.

## 2. Cognos Report Batch Processor
- **Source File**: `app/cognos/batch_processor.py`
- **Execution Mechanism**: `concurrent.futures.ThreadPoolExecutor`
- **Synchronous/Asynchronous**: Synchronous from the caller's perspective (it blocks until the entire thread pool finishes), but executes parallel internal tasks.
- **Duration**: Potentially minutes depending on the batch size.
- **Retry Behavior**: The batch processor catches exceptions within `process_single_report_safe` and marks the specific report as `FAILED`, continuing with others. No automatic retry across batches.
- **Idempotency Behavior**: Re-running overwrites local files. 
- **Current Persistence**: Process-local threads.
- **Failure Behavior**: The error is aggregated into the Batch Summary Excel. 
- **Production Criticality**: `CRITICAL_DURABLE` (when migrated to a web API, right now it acts as an internal module / script). Will require a true batch-job execution pattern.

## 3. SharePoint Sync & Notify (Export Service)
- **Source File**: `app/services/export_service.py` -> `sync_and_notify`
- **Execution Mechanism**: Synchronous execution directly within the HTTP request lifecycle.
- **Synchronous/Asynchronous**: Synchronous.
- **Duration**: ~5-15s (Network latency for SharePoint API and SMTP).
- **Retry Behavior**: None. The system catches `SharePointSyncError` and `EmailSendError` and returns them as strings in the `ExportResponse`, forcing the user to retry manually.
- **Idempotency Behavior**: None. A manual retry attempts to upload and email again.
- **Current Persistence**: None during flight.
- **Failure Behavior**: Logs an `AuditLogEntry` for `_FAILED` and returns partial success to the client.
- **Production Criticality**: `CRITICAL_DURABLE`. To prevent the UI from freezing during network hiccups, this must be pushed to a durable background queue with its own idempotency controls.

## Summary
The only true fire-and-forget background execution currently running is the **LLM-as-Judge**, which relies dangerously on FastAPI's ephemeral `BackgroundTasks`. The export mechanisms are synchronous and fragile against network latency. Batch processing uses a thread pool but blocks the main thread. We must implement a robust Celery + PostgreSQL Outbox pattern to support these.

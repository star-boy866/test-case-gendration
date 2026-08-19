# Phase 9.8B Capacity Model

To ensure the architecture scales efficiently across 600 unique Cognos report DSDs, the capacity and scaling throughput models have been formalized based on Phase 9.3 Load Benchmarks and Phase 9.5 Durable Job observations.

## 1. Measured Values
- **Worker Throughput**: `MEASURED` at an average of `25.3s` end-to-end execution per `OPR-SRA-139` scale document.
- **Queue Latency**: `MEASURED` at `~25ms` propagation delay from Postgres Outbox to Redis Celery dispatch.
- **LLM Latency**: `MEASURED` at `18.4s` p95 per evaluation batch via Groq Llama-3.3-70b.
- **Database Load**: `MEASURED` safely peaking at 20 concurrent connections without significant query degradation on SQLite.

## 2. Estimated Values
- **600-Report Volume Duration**: `ESTIMATED`. Assuming 4 background workers processing reports sequentially: `(600 reports * 25.3s) / 4 workers = 3,795s (~63.2 minutes)`.
- **Worker Requirements**: `ESTIMATED`. To process a full 600-report batch within a 1-hour SLA, exactly 5 concurrent Celery workers are required.
- **Peak Backlog**: `ESTIMATED`. Submitting 600 requests instantaneously will queue safely within Redis (utilizing less than 50MB RAM), dissipating steadily over 1 hour.

## 3. Assumed Values
- **External Dependencies**: `ASSUMED`. Rate limits on Microsoft Graph (SharePoint) and SMTP relays are assumed to be higher than 10 requests/second. 
- **LLM Capacity**: `ASSUMED`. The LLM provider (Groq) limits permit up to 5 concurrent sustained connections without applying `429 Too Many Requests` backpressure.

## 4. Staged Scaling Limit
Based on these metrics, the physical throughput easily sustains 600 reports. However, actual capacity is throttled by the human-in-the-loop QA step (Refinement Grid). Bottlenecks will occur primarily at the QA Reviewer queue, not the compute layer.

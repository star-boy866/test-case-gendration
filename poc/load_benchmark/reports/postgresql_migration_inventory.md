# PostgreSQL Migration Inventory

This document surveys the repository to determine the current persistence footprint and identify the scope of the Phase 9.4 migration to PostgreSQL.

## 1. Engine and Session Architecture
- **Location:** `app/db/session.py`
- **Current Pattern:** 
  ```python
  engine = create_engine(f"sqlite:///{settings.SQLITE_DB_PATH}", connect_args={"check_same_thread": False})
  SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
  ```
- **Migration Requirements:** We need to parse a deployment environment variable (`DATABASE_URL`) to support both `sqlite:///` for dev/test and `postgresql+psycopg://` for production.

## 2. ORM Models (app/models/)
The following SQLAlchemy DeclarativeBase models exist:
- `CognosGenerationRun`, `CognosRequirementModel`, `CognosTestCaseModel` (`cognos_orm.py`)
- `AuditLogEntry` (`audit.py`)
- `CacheEntry` (`cache.py`)
- `LLMJudgeEvaluation` (`evaluation.py`)
- `ExportJob` (`export.py`)
- `SourceDocument`, `KBTable`, `KBColumn`, `KBJoin`, `KBValidValue`, `KBBusinessRule`, `UnstructuredNote` (`knowledge_base.py`)
- `RefinementLog`, `RefinedRequirement` (`refinement.py`)
- `User` (`user.py`)

## 3. SQLite-Specific Patterns / Types Discovered
1. **JSON Fields:** Currently implemented via SQLite-compatible strings or `sqlalchemy.JSON`. PostgreSQL can natively support `JSONB` for improved indexing/querying if needed, though standard `JSON` mapping works compatibly.
2. **Boolean Fields:** SQLite uses `1/0` integer mapping for booleans; SQLAlchemy abstracts this, but PostgreSQL enforces strict boolean types. Need to verify that we are not assigning ints to boolean model attributes anywhere.
3. **No Raw SQL:** A grep for `session.execute(text(` revealed 0 results, confirming we are successfully using the SQLAlchemy ORM abstraction completely.
4. **Metadata Initialization:** There is no alembic directory. The repository appears to rely on `Base.metadata.create_all(bind=engine)` at startup.

## 4. Transaction Boundaries
- All inserts observed (e.g. `/upload-and-generate`, Export Service, Refinement Service) use a pattern of `db.add(...)` followed by `db.commit()`.
- API endpoints receive `db = Depends(get_db)`, ensuring `db.close()` occurs in the `finally:` block of the context manager.
- Exceptions during generation currently do `db.rollback()` within `upload_and_generate`.

## 5. Audit Log Integrity
The `AuditLogEntry` model handles the tamper-evident hash chain. Because PostgreSQL provides much stricter concurrency controls, moving to PostgreSQL will fundamentally improve the guarantees on the hash-chain generation without needing SQLite write-locks.

## 6. Migration Scope
To implement Phase 9.4 safely:
1. Initialize Alembic (`alembic init`).
2. Add a conditional `DATABASE_URL` loader in `app/core/config.py`.
3. Create the initial Base migration.
4. Set PostgreSQL connection pooling arguments (e.g., `pool_size`, `max_overflow`).

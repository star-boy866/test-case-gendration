-- ==============================================================================
-- Cognos Test Case Studio — Primary PostgreSQL Schema (Supabase Production)
-- Migration 001: Initial Architecture, Provenance, Learning & Governance Schema
-- ==============================================================================

-- 1. AUTH & ACCESS CONTROL
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(150) UNIQUE NOT NULL,
    email VARCHAR(255),
    hashed_password VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'tester' NOT NULL,
    status VARCHAR(50) DEFAULT 'ACTIVE' NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    must_change_password BOOLEAN DEFAULT FALSE NOT NULL,
    mfa_enabled BOOLEAN DEFAULT FALSE NOT NULL,
    failed_login_attempts INTEGER DEFAULT 0 NOT NULL,
    locked_until TIMESTAMP WITH TIME ZONE,
    last_login_at TIMESTAMP WITH TIME ZONE,
    last_password_change_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);

CREATE TABLE IF NOT EXISTS password_history (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    is_system_role BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS permissions (
    id SERIAL PRIMARY KEY,
    code VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(150) NOT NULL,
    description TEXT,
    module VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ip_address VARCHAR(100),
    user_agent TEXT,
    device_name VARCHAR(150),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_activity_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_authenticated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE,
    revoked_reason VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_sessions_token ON user_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_active ON user_sessions(is_active);

-- 2. SOURCE DOCUMENTS & PROVENANCE
CREATE TABLE IF NOT EXISTS source_documents (
    id SERIAL PRIMARY KEY,
    document_uuid VARCHAR(100) UNIQUE NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_hash VARCHAR(100) NOT NULL,
    document_type VARCHAR(50) DEFAULT 'DOCX' NOT NULL,
    profile VARCHAR(50),
    uploaded_by VARCHAR(150) NOT NULL,
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    page_count INTEGER,
    parser_version VARCHAR(50),
    file_path TEXT
);

CREATE INDEX IF NOT EXISTS idx_source_doc_hash ON source_documents(file_hash);

CREATE TABLE IF NOT EXISTS source_document_versions (
    id SERIAL PRIMARY KEY,
    source_document_id INTEGER NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
    version_number INTEGER DEFAULT 1 NOT NULL,
    file_hash VARCHAR(100) NOT NULL,
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    created_by VARCHAR(150) NOT NULL
);

CREATE TABLE IF NOT EXISTS source_sections (
    id SERIAL PRIMARY KEY,
    source_document_id INTEGER NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
    section_name VARCHAR(255) NOT NULL,
    heading_level INTEGER,
    start_page INTEGER,
    end_page INTEGER,
    content_snippet TEXT
);

CREATE TABLE IF NOT EXISTS source_snapshots (
    id SERIAL PRIMARY KEY,
    source_document_id INTEGER REFERENCES source_documents(id) ON DELETE SET NULL,
    run_id INTEGER NOT NULL,
    scenario_id VARCHAR(100),
    evidence_id VARCHAR(255) NOT NULL,
    page_number INTEGER,
    semantic_target VARCHAR(255),
    crop_box JSONB,
    renderer VARCHAR(100),
    crop_version VARCHAR(50),
    snapshot_hash VARCHAR(100),
    is_semantic_crop BOOLEAN DEFAULT TRUE NOT NULL,
    file_path TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snapshot_run ON source_snapshots(run_id);
CREATE INDEX IF NOT EXISTS idx_snapshot_evidence ON source_snapshots(evidence_id);

-- 3. TEST CASE STUDIO WORKFLOW
CREATE TABLE IF NOT EXISTS cognos_generation_runs (
    id SERIAL PRIMARY KEY,
    report_id VARCHAR(100) NOT NULL,
    report_title VARCHAR(255),
    source_document VARCHAR(255) NOT NULL,
    source_document_path TEXT,
    source_document_sha256 VARCHAR(100),
    job_id VARCHAR(100),
    llm_provider VARCHAR(50),
    llm_model VARCHAR(100),
    report_definition_json JSONB,
    requirements_extracted INTEGER DEFAULT 0,
    test_cases_generated INTEGER DEFAULT 0,
    coverage_percentage FLOAT DEFAULT 0.0,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'running',
    error_message TEXT,
    requested_by VARCHAR(150) NOT NULL,
    work_type VARCHAR(50),
    work_item_id VARCHAR(100),
    work_item_title VARCHAR(255)
);

CREATE INDEX IF NOT EXISTS idx_cognos_runs_report ON cognos_generation_runs(report_id);
CREATE INDEX IF NOT EXISTS idx_cognos_runs_status ON cognos_generation_runs(status);

CREATE TABLE IF NOT EXISTS cognos_requirements (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES cognos_generation_runs(id) ON DELETE CASCADE,
    requirement_id VARCHAR(100) NOT NULL,
    report_id VARCHAR(100) NOT NULL,
    category VARCHAR(100) NOT NULL,
    field_name VARCHAR(150) NOT NULL,
    requirement_text TEXT NOT NULL,
    source_section VARCHAR(255) NOT NULL,
    source_page INTEGER,
    source_columns JSONB,
    processing_rule TEXT,
    formatting_rule TEXT,
    confidence VARCHAR(50) NOT NULL,
    is_ambiguous BOOLEAN DEFAULT FALSE,
    open_questions JSONB,
    is_duplicate_of VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_cognos_req_run ON cognos_requirements(run_id);
CREATE INDEX IF NOT EXISTS idx_cognos_req_reqid ON cognos_requirements(requirement_id);

CREATE TABLE IF NOT EXISTS cognos_test_cases (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES cognos_generation_runs(id) ON DELETE CASCADE,
    test_case_id VARCHAR(100) NOT NULL,
    report_id VARCHAR(100) NOT NULL,
    category VARCHAR(100) NOT NULL,
    test_case_title VARCHAR(255) NOT NULL,
    requirement_id VARCHAR(100),
    objective TEXT NOT NULL,
    preconditions TEXT,
    test_data TEXT,
    test_steps TEXT NOT NULL,
    expected_result TEXT NOT NULL,
    validation_logic TEXT,
    validation_sql TEXT,
    source_section VARCHAR(255) NOT NULL,
    source_page INTEGER,
    source_table VARCHAR(150),
    source_column VARCHAR(150),
    processing_rule TEXT,
    formatting_rule TEXT,
    priority VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'Generated',
    origin VARCHAR(50) NOT NULL,
    version INTEGER DEFAULT 1,
    notes TEXT,
    open_questions TEXT,
    evidence_references JSONB,
    scenario_order INTEGER DEFAULT 0,
    review_status VARCHAR(50) DEFAULT 'GENERATED',
    review_comments TEXT,
    reviewer VARCHAR(150),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    issue_type VARCHAR(100),
    issue_comment TEXT,
    duplicate_of_id VARCHAR(100),
    execution_method VARCHAR(100) DEFAULT 'Scheduled',
    execution_tool VARCHAR(100) DEFAULT 'IWA',
    edit_history JSONB
);

CREATE INDEX IF NOT EXISTS idx_cognos_tc_run ON cognos_test_cases(run_id);
CREATE INDEX IF NOT EXISTS idx_cognos_tc_tcid ON cognos_test_cases(test_case_id);

CREATE TABLE IF NOT EXISTS test_case_assignments (
    id SERIAL PRIMARY KEY,
    file_id VARCHAR(100) UNIQUE NOT NULL,
    run_id INTEGER NOT NULL REFERENCES cognos_generation_runs(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    assigned_by_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'ASSIGNED' NOT NULL,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_tc_assign_run ON test_case_assignments(run_id);
CREATE INDEX IF NOT EXISTS idx_tc_assign_user ON test_case_assignments(user_id);

-- 4. SCENARIO LIFECYCLE & VERSIONING
CREATE TABLE IF NOT EXISTS generated_scenarios (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL,
    test_case_id VARCHAR(100) NOT NULL,
    scenario_name VARCHAR(255) NOT NULL,
    methodology VARCHAR(100),
    section VARCHAR(255),
    target_field VARCHAR(150),
    evidence_scope VARCHAR(100),
    risk_level VARCHAR(50),
    description TEXT,
    status VARCHAR(50) DEFAULT 'GENERATED' NOT NULL,
    created_by VARCHAR(150) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_gen_scenarios_run ON generated_scenarios(run_id);
CREATE INDEX IF NOT EXISTS idx_gen_scenarios_tc ON generated_scenarios(test_case_id);

CREATE TABLE IF NOT EXISTS scenario_versions (
    id SERIAL PRIMARY KEY,
    scenario_id INTEGER NOT NULL REFERENCES generated_scenarios(id) ON DELETE CASCADE,
    test_case_id VARCHAR(100),
    version_number INTEGER DEFAULT 1 NOT NULL,
    content_json JSONB NOT NULL,
    source VARCHAR(50) NOT NULL,
    changed_by VARCHAR(150) NOT NULL,
    change_reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scen_ver_scen ON scenario_versions(scenario_id);
CREATE INDEX IF NOT EXISTS idx_scen_ver_tc ON scenario_versions(test_case_id);

CREATE TABLE IF NOT EXISTS scenario_feedback (
    id SERIAL PRIMARY KEY,
    scenario_id INTEGER NOT NULL REFERENCES generated_scenarios(id) ON DELETE CASCADE,
    user_id INTEGER,
    username VARCHAR(150) NOT NULL,
    feedback_type VARCHAR(50) NOT NULL,
    comment TEXT,
    changed_fields JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS scenario_reviews (
    id SERIAL PRIMARY KEY,
    scenario_id INTEGER REFERENCES generated_scenarios(id) ON DELETE CASCADE,
    test_case_id VARCHAR(100) NOT NULL,
    run_id INTEGER NOT NULL,
    reviewer_id INTEGER,
    reviewer_username VARCHAR(150) NOT NULL,
    review_status VARCHAR(50) NOT NULL,
    review_comments TEXT,
    issue_type VARCHAR(100),
    issue_comment TEXT,
    reviewed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS scenario_evidence (
    id SERIAL PRIMARY KEY,
    scenario_id INTEGER REFERENCES generated_scenarios(id) ON DELETE CASCADE,
    test_case_id VARCHAR(100) NOT NULL,
    evidence_id VARCHAR(255) NOT NULL,
    snapshot_id INTEGER REFERENCES source_snapshots(id) ON DELETE SET NULL,
    reference_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS scenario_execution_results (
    id SERIAL PRIMARY KEY,
    scenario_id INTEGER REFERENCES generated_scenarios(id) ON DELETE CASCADE,
    run_id INTEGER NOT NULL,
    status VARCHAR(50) DEFAULT 'NOT_RUN' NOT NULL,
    execution_method VARCHAR(100),
    execution_tool VARCHAR(100),
    executed_by VARCHAR(150),
    executed_at TIMESTAMP WITH TIME ZONE,
    notes TEXT
);

-- 5. AI GENERATION & LEARNING CANDIDATES
CREATE TABLE IF NOT EXISTS generation_metadata (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL,
    scenario_id VARCHAR(100),
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    prompt_version VARCHAR(50),
    template_version VARCHAR(50),
    temperature FLOAT,
    generation_duration_ms INTEGER,
    retrieval_count INTEGER DEFAULT 0,
    retrieved_example_ids JSONB,
    input_metadata JSONB,
    output_metadata JSONB,
    validation_status VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS retrieval_events (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL,
    query_text TEXT,
    top_k INTEGER DEFAULT 3,
    retrieved_ids JSONB,
    scores JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS model_evaluations (
    id SERIAL PRIMARY KEY,
    scenario_id VARCHAR(100),
    evaluator VARCHAR(100) NOT NULL,
    score FLOAT NOT NULL,
    criteria_scores JSONB,
    evaluation_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS prompt_versions (
    id SERIAL PRIMARY KEY,
    prompt_name VARCHAR(150) UNIQUE NOT NULL,
    version VARCHAR(50) NOT NULL,
    prompt_text TEXT NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS learning_candidates (
    id SERIAL PRIMARY KEY,
    scenario_id INTEGER REFERENCES generated_scenarios(id) ON DELETE CASCADE,
    test_case_id VARCHAR(100) NOT NULL,
    source_version_id INTEGER,
    quality_status VARCHAR(50) DEFAULT 'QUALIFIED' NOT NULL,
    approval_status VARCHAR(50) DEFAULT 'APPROVED' NOT NULL,
    evaluation_score FLOAT,
    selected_for_learning BOOLEAN DEFAULT TRUE NOT NULL,
    selected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    selected_by VARCHAR(150) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_learning_cand_sel ON learning_candidates(selected_for_learning);

-- 6. IMMUTABLE AUDIT TRAIL
CREATE TABLE IF NOT EXISTS audit_events (
    id SERIAL PRIMARY KEY,
    occurred_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    actor_user_id INTEGER,
    actor_username VARCHAR(150) NOT NULL,
    actor_role VARCHAR(50) NOT NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(100),
    resource_id VARCHAR(150),
    run_id INTEGER,
    scenario_id VARCHAR(100),
    request_id VARCHAR(100),
    ip_address VARCHAR(100),
    user_agent TEXT,
    success BOOLEAN DEFAULT TRUE NOT NULL,
    details JSONB
);

CREATE INDEX IF NOT EXISTS idx_audit_occurred ON audit_events(occurred_at);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_events(actor_username);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_events(action);
CREATE INDEX IF NOT EXISTS idx_audit_run ON audit_events(run_id);

CREATE TABLE IF NOT EXISTS login_events (
    id SERIAL PRIMARY KEY,
    occurred_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    username VARCHAR(150) NOT NULL,
    user_id INTEGER,
    ip_address VARCHAR(100),
    user_agent TEXT,
    success BOOLEAN NOT NULL,
    failure_reason VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS security_events (
    id SERIAL PRIMARY KEY,
    occurred_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    severity VARCHAR(50) DEFAULT 'MEDIUM' NOT NULL,
    actor_username VARCHAR(150),
    ip_address VARCHAR(100),
    details JSONB
);

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    user_id VARCHAR(150) NOT NULL,
    session_id INTEGER,
    event_type VARCHAR(100) NOT NULL,
    detail TEXT,
    file_sha256 VARCHAR(100),
    chain_hash VARCHAR(100)
);

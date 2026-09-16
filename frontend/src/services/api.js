import axios from "axios";

// Vite dev server proxies /api -> http://localhost:8000 (see vite.config.js)
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // generation calls can involve a local LLM, allow more time
  withCredentials: true, // Send httpOnly cookies alongside Bearer token
});

// --- Auth token storage ---------------------------------------------------
const TOKEN_KEY = "healthcare_nl_testgen_token";

export const getStoredToken = () => localStorage.getItem(TOKEN_KEY);
export const setStoredToken = (token) => localStorage.setItem(TOKEN_KEY, token);
export const clearStoredToken = () => localStorage.removeItem(TOKEN_KEY);

/**
 * Centrally cleans up all transient Test Case Studio / Cognos workspace state.
 * Called on logout, session expiration (401), and explicit workspace reset.
 * Does NOT delete user preferences or authentication keys.
 */
export const clearCognosWorkspaceState = () => {
  try {
    localStorage.removeItem("cognos_active_run_id");
    localStorage.removeItem("cognos_active_result");
    localStorage.removeItem("cognos_project_context");
    sessionStorage.removeItem("cognos_active_run_id");
    sessionStorage.removeItem("cognos_active_result");

    // Remove any dynamic evidence annotations/crop saved to localStorage
    const keysToRemove = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith("cognos_evidence_annotations_")) {
        keysToRemove.push(key);
      }
    }
    keysToRemove.forEach((k) => localStorage.removeItem(k));
  } catch (err) {
    console.error("Failed to clear Cognos workspace state:", err);
  }
};

api.interceptors.request.use((config) => {
  if (!config.headers.Authorization) {
    const token = getStoredToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

// A 401 means the session is missing/expired/invalid — clear it so the app
// doesn't keep retrying with a dead token, and let the caller's own
// error handling (AuthContext) decide what to show/redirect to.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearStoredToken();
      clearCognosWorkspaceState();
    }
    return Promise.reject(error);
  }
);

export const checkHealth = () => api.get("/health");

// --- Core Auth & RBAC API Endpoints ----------------------------------------
export const login = ({ username, password }) =>
  api.post("/auth/login", { username, password });

export const verifyMfa = ({ temp_token, code }) =>
  api.post("/auth/verify-mfa", { temp_token, code });

export const setupMfa = () =>
  api.post("/auth/mfa/setup");

export const confirmMfa = ({ code }) =>
  api.post("/auth/mfa/confirm", { code });

export const changePassword = (
  { current_password, new_password, username, temp_token } = {},
  tempToken = null
) => {
  let token = tempToken || temp_token;
  if (!token) {
    try {
      token = sessionStorage.getItem("temp_auth_token") || null;
    } catch {}
  }

  let user = username;
  if (!user) {
    try {
      user =
        sessionStorage.getItem("temp_auth_user") ||
        localStorage.getItem("healthcare_nl_testgen_last_user") ||
        null;
    } catch {}
  }

  const headers = token ? { Authorization: `Bearer ${token}` } : {};
  return api.post(
    "/auth/change-password",
    {
      current_password,
      new_password,
      username: user,
      temp_token: token,
    },
    { headers }
  );
};

export const submitAccessRequest = ({ username, password, requested_role, reason }) =>
  api.post("/auth/access-request", { username, password, requested_role, reason });

export const getRequestStatus = () =>
  api.get("/auth/access-request/status");

export const logout = () =>
  api.post("/auth/logout");

export const logoutAll = () =>
  api.post("/auth/logout-all");

export const listSessions = () =>
  api.get("/auth/sessions");

export const revokeSession = (sessionId) =>
  api.delete(`/auth/sessions/${encodeURIComponent(sessionId)}`);

export const reauthenticate = ({ password, mfa_code }) =>
  api.post("/auth/reauthenticate", { password, mfa_code });

export const getMe = () => api.get("/auth/me");

// --- Admin RBAC Approvals & Management -------------------------------------
export const listApprovals = (params = {}) =>
  api.get("/admin/approvals", { params });

export const seedDemoRequest = () =>
  api.post("/admin/approvals/demo-seed");

export const approveRequest = (requestId, { reason, admin_password, mfa_code }) =>
  api.post(`/admin/approvals/${requestId}/approve`, {
    reason,
    admin_password,
    mfa_code,
  });

export const rejectRequest = (requestId, { reason, admin_password, mfa_code }) =>
  api.post(`/admin/approvals/${requestId}/reject`, {
    reason,
    admin_password,
    mfa_code,
  });

export const listAdminUsers = () =>
  api.get("/admin/users");

export const createAdminUser = ({ username, password, role }) =>
  api.post("/admin/users", { username, password, role });

export const updateUserStatus = (userId, { status, reason, admin_password, mfa_code }) =>
  api.patch(`/admin/users/${userId}/status`, {
    status,
    reason,
    admin_password,
    mfa_code,
  });

export const updateUserRole = (userId, { role, reason, admin_password, mfa_code }) =>
  api.patch(`/admin/users/${userId}/role`, {
    role,
    reason,
    admin_password,
    mfa_code,
  });

export const getAdminAuditLogs = (params = {}) =>
  api.get("/admin/audit-logs", { params });

// Legacy helper aliases for backward compatibility
export const registerFirstAdmin = ({ username, password }) =>
  api.post("/auth/register", { username, password, role: "admin" });

export const createUser = ({ username, password, role }) =>
  api.post("/auth/users", { username, password, role });

export const listUsers = () => api.get("/admin/users");

// Phase 1
export const uploadDocument = ({ file, reportId, crId }) => {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("report_id", reportId);
  if (crId) formData.append("cr_id", crId);
  return api.post("/ingestion/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

export const getKnowledgeBase = (reportId) =>
  api.get(`/ingestion/knowledge-base/${encodeURIComponent(reportId)}`);

// Phase 2
export const getGatekeeperScope = (reportId) =>
  api.get(`/gatekeeper/scope/${encodeURIComponent(reportId)}`);

// Requires 'approver' role or higher server-side — confirmed_by is now
// always the authenticated identity, never client-supplied (Phase 9).
export const confirmGatekeeper = ({ reportId, crId, crDescription }) =>
  api.post("/gatekeeper/confirm", {
    report_id: reportId,
    cr_id: crId,
    cr_description: crDescription,
  });

// Phase 4/5
export const runGeneration = ({ reportId, requirement }) =>
  api.post("/generation/run", {
    report_id: reportId,
    natural_language_requirement: requirement,
  });

// Phase 6
export const getRefinementGrid = (sessionId) =>
  api.get(`/refinement/${sessionId}`);

export const addManualRow = (sessionId, { testScenario, detailedTestSteps, expectedResults, verificationSql, category }) =>
  api.post(`/refinement/${sessionId}/rows`, {
    test_scenario: testScenario,
    detailed_test_steps: detailedTestSteps,
    expected_results: expectedResults,
    verification_sql: verificationSql,
    category,
  });

export const updateRefinementRow = (sessionId, rowId, fields) =>
  api.patch(`/refinement/${sessionId}/rows/${rowId}`, fields);

export const deleteRefinementRow = (sessionId, rowId) =>
  api.delete(`/refinement/${sessionId}/rows/${rowId}`);

// Phase 7/8
// exported_by is now always the authenticated identity (Phase 9); requires
// 'approver' role or higher server-side.
export const finalizeExport = ({ sessionId, syncToSharePoint, emailDistributionList, qualityScore }) =>
  api.post("/export/finalize", {
    session_id: sessionId,
    sync_to_sharepoint: !!syncToSharePoint,
    email_distribution_list: emailDistributionList && emailDistributionList.length > 0 ? emailDistributionList : null,
    quality_score: qualityScore ?? null,
  });

// Phase 7/8/9: a plain <a href> download would NOT carry the Authorization
// header (browser navigation doesn't run through axios's interceptor), and
// this endpoint now requires auth — so downloads must be fetched as a blob
// via axios and then saved client-side, not linked to directly.
export const downloadExport = async (sessionId) => {
  const response = await api.get(`/export/${sessionId}/download`, {
    responseType: "blob",
  });
  const contentDisposition = response.headers["content-disposition"] || "";
  const match = contentDisposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : `export-${sessionId}.xlsx`;

  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

// Phase 10
export const getJudgeEvaluation = (sessionId) =>
  api.get(`/generation/${sessionId}/judge-evaluation`);

// Cognos Report Generation
export const detectDsdFormat = (file) => {
  const formData = new FormData();
  formData.append("file", file);
  return api.post("/cognos/detect-dsd-format", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

export const uploadCognosDocument = ({ file, dsdProfile = "AUTO", workType = "", workItemId = "", workItemTitle = "" }) => {
  const formData = new FormData();
  formData.append("file", file);
  if (dsdProfile) {
    formData.append("dsd_profile", dsdProfile);
  }
  if (workType) {
    formData.append("work_type", workType);
  }
  if (workItemId) {
    formData.append("work_item_id", workItemId);
  }
  if (workItemTitle) {
    formData.append("work_item_title", workItemTitle);
  }
  return api.post("/cognos/upload-and-generate", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
};

export const downloadCognosExport = async (runId) => {
  const response = await api.get(`/cognos/runs/${runId}/export/excel`, {
    responseType: "blob",
  });
  const contentDisposition = response.headers["content-disposition"] || "";
  const match = contentDisposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : `Cognos_Export_${runId}.xlsx`;

  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

// --- Cognos HITL (Human-in-the-Loop) Review APIs ---
export const getCognosRun = (runId) =>
  api.get(`/cognos/runs/${runId}`);

export const getLatestCognosRun = () =>
  api.get(`/cognos/runs-latest`);

export const getRunTestCases = (runId) =>
  api.get(`/cognos/runs/${runId}/test-cases`);

export const reviewTestCase = (runId, testCaseId, payload) =>
  api.patch(`/cognos/runs/${runId}/test-cases/${encodeURIComponent(testCaseId)}/review`, payload);

export const suggestCorrection = (runId, testCaseId, payload) =>
  api.post(`/cognos/runs/${runId}/test-cases/${encodeURIComponent(testCaseId)}/suggest-correction`, payload);

export const suggestMissingScenario = (runId, { whatToTest, dsdReference }) =>
  api.post(`/cognos/runs/${runId}/suggest-missing-scenario`, {
    what_to_test: whatToTest,
    dsd_reference: dsdReference,
  });

export const addMissingScenario = (runId, scenario) =>
  api.post(`/cognos/runs/${runId}/add-scenario`, { scenario });

// --- Test Case File Assignment & Security APIs ---
export const getTesterAssignedFiles = () =>
  api.get("/cognos/tester/assigned-files");

export const viewAssignedFileTestCases = (fileId) =>
  api.get(`/cognos/files/${encodeURIComponent(fileId)}/view`);

export const downloadAssignedFile = async (fileId, preferredFilename = null) => {
  const response = await api.get(`/cognos/files/${encodeURIComponent(fileId)}/download`, {
    responseType: "blob",
  });
  const contentDisposition = response.headers["content-disposition"] || "";
  const match = contentDisposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : (preferredFilename || `Test_Cases_${fileId}.xlsx`);

  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

export const getAllAssignments = () =>
  api.get("/admin/assignments");

export const createAssignment = ({ run_id, user_id, notes }) =>
  api.post("/admin/assignments", { run_id, user_id, notes });

export const revokeAssignment = (assignmentId, reason) =>
  api.post(`/admin/assignments/${assignmentId}/revoke`, { reason });

export const deleteTestCaseRun = (runId, reason) =>
  api.delete(`/admin/runs/${runId}`, { params: { reason } });

// ── Database Explorer & Governance API ────────────────────────────────────────
export const getDatabaseTables = () =>
  api.get("/admin/database/tables");

export const getTableSchema = (tableName) =>
  api.get(`/admin/database/${encodeURIComponent(tableName)}/schema`);

export const getTableRows = (tableName, params = {}) =>
  api.get(`/admin/database/${encodeURIComponent(tableName)}/rows`, { params });

export const exportTableRows = async (tableName, format = "csv") => {
  const response = await api.get(`/admin/database/${encodeURIComponent(tableName)}/export`, {
    params: { format },
    responseType: "blob",
  });
  const ext = format === "json" ? "json" : "csv";
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement("a");
  link.href = url;
  link.download = `${tableName}_export.${ext}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

export const getDatabaseAuditSummary = () =>
  api.get("/admin/database/audit-summary");

export const getScenarioLearningSummary = () =>
  api.get("/admin/learning/summary");

export default api;


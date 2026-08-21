import axios from "axios";

// Vite dev server proxies /api -> http://localhost:8000 (see vite.config.js)
export const api = axios.create({
  baseURL: "/api",
  timeout: 60000, // generation calls can involve a local LLM, allow more time
});

// --- Auth token storage (Phase 9) -----------------------------------------
// This is a real, separately-deployed SPA (not a claude.ai artifact), so
// localStorage is the standard place for this — the usual XSS-vs-httpOnly-
// cookie tradeoff applies same as it would for any React app; a future
// hardening pass could move to an httpOnly cookie + CSRF token instead.
const TOKEN_KEY = "healthcare_nl_testgen_token";

export const getStoredToken = () => localStorage.getItem(TOKEN_KEY);
export const setStoredToken = (token) => localStorage.setItem(TOKEN_KEY, token);
export const clearStoredToken = () => localStorage.removeItem(TOKEN_KEY);

api.interceptors.request.use((config) => {
  const token = getStoredToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// A 401 means the token is missing/expired/invalid — clear it so the app
// doesn't keep retrying with a dead token, and let the caller's own
// error handling (AuthContext) decide what to show/redirect to.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearStoredToken();
    }
    return Promise.reject(error);
  }
);

export const checkHealth = () => axios.get("/health");

// --- Auth (Phase 9) ---------------------------------------------------------
export const login = ({ username, password }) =>
  api.post("/auth/login", { username, password });

// Only succeeds while the users table is empty (bootstrap account, always
// admin) — see api/auth.py's register() docstring. Every subsequent
// account must be created by an admin via createUser().
export const registerFirstAdmin = ({ username, password }) =>
  api.post("/auth/register", { username, password, role: "admin" });

export const getMe = () => api.get("/auth/me");

export const createUser = ({ username, password, role }) =>
  api.post("/auth/users", { username, password, role });

export const listUsers = () => api.get("/auth/users");

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
export const uploadCognosDocument = ({ file }) => {
  const formData = new FormData();
  formData.append("file", file);
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

export default api;

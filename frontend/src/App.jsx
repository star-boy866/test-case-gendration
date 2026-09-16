import { Routes, Route, Navigate } from "react-router-dom";
import StepShell from "./components/StepShell.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import FirstLoginPasswordChangePage from "./pages/FirstLoginPasswordChangePage.jsx";
import MfaSetupPage from "./pages/MfaSetupPage.jsx";
import MfaVerifyPage from "./pages/MfaVerifyPage.jsx";
import AccessRequestPage from "./pages/AccessRequestPage.jsx";
import PendingApprovalPage from "./pages/PendingApprovalPage.jsx";
import AdminApprovalsPage from "./pages/AdminApprovalsPage.jsx";
import UsersManagementPage from "./pages/UsersManagementPage.jsx";
import SessionsPage from "./pages/SessionsPage.jsx";
import AuditLogPage from "./pages/AuditLogPage.jsx";
import CognosDashboard from "./pages/CognosDashboard.jsx";
import TesterDashboard from "./pages/TesterDashboard.jsx";
import DatabaseExplorerPage from "./pages/DatabaseExplorerPage.jsx";
import { WorkflowProvider } from "./context/WorkflowContext.jsx";
import { AuthProvider, useAuth } from "./context/AuthContext.jsx";

function RequireAuth({ children, minRole = null }) {
  const { user, loading, isAdmin, isTester } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-900 text-sm text-slate-400">
        Loading…
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (user.status === "PENDING") {
    return <Navigate to="/pending-approval" replace />;
  }

  if (user.must_change_password) {
    return <Navigate to="/change-password" replace />;
  }

  // If route requires admin and user is not an admin, redirect to Test Case Studio
  if (minRole === "admin" && !isAdmin) {
    return <Navigate to="/cognos" replace />;
  }

  if (minRole === "tester" && !isTester && !isAdmin) {
    return <Navigate to="/pending-approval" replace />;
  }

  return children;
}

function AuthenticatedRoutes() {
  const { user, isAdmin } = useAuth();

  return (
    <RequireAuth>
      <WorkflowProvider>
        <StepShell>
          <Routes>
            {/* Server-determined default route based on approved role */}
            <Route path="/" element={<Navigate to="/cognos" replace />} />

            {/* Auxiliary Tester Dashboard */}
            <Route
              path="/tester-dashboard"
              element={
                <RequireAuth minRole="tester">
                  <TesterDashboard />
                </RequireAuth>
              }
            />

            {/* Auxiliary Tester Test Cases Workspace */}
            <Route
              path="/tester-dashboard/test-cases"
              element={
                <RequireAuth minRole="tester">
                  <TesterDashboard />
                </RequireAuth>
              }
            />

            {/* Primary Cognos Studio (Accessible to Testers and Admins) */}
            <Route
              path="/cognos"
              element={
                <RequireAuth minRole="tester">
                  <CognosDashboard />
                </RequireAuth>
              }
            />

            {/* Admin Approvals Dashboard */}
            <Route
              path="/admin/approvals"
              element={
                <RequireAuth minRole="admin">
                  <AdminApprovalsPage />
                </RequireAuth>
              }
            />

            {/* Admin User Management */}
            <Route
              path="/admin/users"
              element={
                <RequireAuth minRole="admin">
                  <UsersManagementPage />
                </RequireAuth>
              }
            />

            {/* Admin Security & Audit Log Viewer */}
            <Route
              path="/admin/audit-logs"
              element={
                <RequireAuth minRole="admin">
                  <AuditLogPage />
                </RequireAuth>
              }
            />

            {/* Admin Database Explorer (Read-Only Application Data & Learning) */}
            <Route
              path="/admin/database"
              element={
                <RequireAuth minRole="admin">
                  <DatabaseExplorerPage />
                </RequireAuth>
              }
            />

            {/* Device & Session Management (Admin only) */}
            <Route
              path="/sessions"
              element={
                <RequireAuth minRole="admin">
                  <SessionsPage />
                </RequireAuth>
              }
            />

            {/* Legacy redirects */}
            <Route path="/users" element={<Navigate to="/admin/users" replace />} />
            <Route path="/gatekeeper" element={<Navigate to="/cognos" replace />} />
            <Route path="/refinement" element={<Navigate to="/cognos" replace />} />
            <Route path="/export" element={<Navigate to="/cognos" replace />} />

            {/* Catch-all */}
            <Route path="*" element={<Navigate to="/cognos" replace />} />
          </Routes>
        </StepShell>
      </WorkflowProvider>
    </RequireAuth>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        {/* Pre-Authentication & Registration Routes */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/request-access" element={<AccessRequestPage />} />
        <Route path="/pending-approval" element={<PendingApprovalPage />} />
        <Route path="/change-password" element={<FirstLoginPasswordChangePage />} />
        <Route path="/mfa-setup" element={<MfaSetupPage />} />
        <Route path="/mfa-verify" element={<MfaVerifyPage />} />

        {/* Protected Application Routes */}
        <Route path="/*" element={<AuthenticatedRoutes />} />
      </Routes>
    </AuthProvider>
  );
}

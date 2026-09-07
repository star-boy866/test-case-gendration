import { Routes, Route, Navigate } from "react-router-dom";
import StepShell from "./components/StepShell.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import UsersPage from "./pages/UsersPage.jsx";
import CognosDashboard from "./pages/CognosDashboard.jsx";
import { WorkflowProvider } from "./context/WorkflowContext.jsx";
import { AuthProvider, useAuth } from "./context/AuthContext.jsx";

function RequireAuth({ children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-slate-400">
        Loading…
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

function AuthenticatedRoutes() {
  return (
    <RequireAuth>
      <WorkflowProvider>
        <StepShell>
          <Routes>
            {/* Primary Standalone Product: Cognos Test Case Studio */}
            <Route path="/" element={<Navigate to="/cognos" replace />} />
            <Route path="/cognos" element={<CognosDashboard />} />
            <Route path="/users" element={<UsersPage />} />

            {/* Legacy workflow routes safely redirect to Cognos Test Case Studio */}
            <Route path="/gatekeeper" element={<Navigate to="/cognos" replace />} />
            <Route path="/refinement" element={<Navigate to="/cognos" replace />} />
            <Route path="/export" element={<Navigate to="/cognos" replace />} />

            {/* Catch-all fallback */}
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
        <Route path="/login" element={<LoginPage />} />
        <Route path="/*" element={<AuthenticatedRoutes />} />
      </Routes>
    </AuthProvider>
  );
}

import { Routes, Route, Navigate } from "react-router-dom";
import StepShell from "./components/StepShell.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import IngestionPage from "./pages/IngestionPage.jsx";
import GatekeeperPage from "./pages/GatekeeperPage.jsx";
import RefinementPage from "./pages/RefinementPage.jsx";
import ExportPage from "./pages/ExportPage.jsx";
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

function WorkflowRoutes() {
  return (
    <RequireAuth>
      <WorkflowProvider>
        <StepShell>
          <Routes>
            <Route path="/" element={<IngestionPage />} />
            <Route path="/gatekeeper" element={<GatekeeperPage />} />
            <Route path="/refinement" element={<RefinementPage />} />
            <Route path="/export" element={<ExportPage />} />
            <Route path="/users" element={<UsersPage />} />
            <Route path="/cognos" element={<CognosDashboard />} />
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
        <Route path="/*" element={<WorkflowRoutes />} />
      </Routes>
    </AuthProvider>
  );
}

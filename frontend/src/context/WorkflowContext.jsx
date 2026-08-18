import { createContext, useContext, useState } from "react";

const WorkflowContext = createContext(null);

export function WorkflowProvider({ children }) {
  const [reportId, setReportId] = useState("");
  const [crId, setCrId] = useState("");
  const [sessionId, setSessionId] = useState(null);

  return (
    <WorkflowContext.Provider
      value={{ reportId, setReportId, crId, setCrId, sessionId, setSessionId }}
    >
      {children}
    </WorkflowContext.Provider>
  );
}

export function useWorkflow() {
  const ctx = useContext(WorkflowContext);
  if (!ctx) {
    throw new Error("useWorkflow must be used within a WorkflowProvider");
  }
  return ctx;
}

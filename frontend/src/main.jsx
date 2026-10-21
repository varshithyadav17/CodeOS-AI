import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { Toaster } from "sonner";
import App from "./App";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { WorkspaceProvider } from "./context/WorkspaceContext";
import { AIProvider } from "./context/AIContext";
import "./index.css";

function Session() {
  const { user } = useAuth();
  return <WorkspaceProvider key={user?.id || "guest"}><AIProvider><App /></AIProvider></WorkspaceProvider>;
}

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <Session />
      </AuthProvider>
      <Toaster theme="dark" position="top-right" toastOptions={{ style: { background: "#121212", border: "1px solid rgba(255,255,255,0.1)", color: "#fff" } }} />
    </BrowserRouter>
  </React.StrictMode>
);

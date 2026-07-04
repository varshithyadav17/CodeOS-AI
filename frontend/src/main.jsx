import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { Toaster } from "sonner";
import App from "./App";
import "./index.css";

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <BrowserRouter
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <App />
      <Toaster theme="dark" position="top-right" toastOptions={{ style: { background: "#121212", border: "1px solid rgba(255,255,255,0.1)", color: "#fff" } }} />
    </BrowserRouter>
  </React.StrictMode>
);

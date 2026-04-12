import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../global.css";
import { AuditApp } from "./AuditApp";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AuditApp />
  </StrictMode>,
);

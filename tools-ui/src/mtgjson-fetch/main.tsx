import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../global.css";
import { MtgJsonFetchApp } from "./MtgJsonFetchApp";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <MtgJsonFetchApp />
  </StrictMode>,
);

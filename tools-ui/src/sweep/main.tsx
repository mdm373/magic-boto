import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../global.css";
import { SweepApp } from "./SweepApp";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <SweepApp />
  </StrictMode>,
);

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../global.css";
import { SweepCatchupApp } from "./SweepCatchupApp";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <SweepCatchupApp />
  </StrictMode>,
);

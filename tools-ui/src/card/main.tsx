import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../global.css";
import { CardApp } from "./CardApp";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <CardApp />
  </StrictMode>,
);

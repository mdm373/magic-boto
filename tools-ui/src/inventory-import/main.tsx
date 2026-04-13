import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../global.css";
import { InventoryImportApp } from "./InventoryImportApp";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <InventoryImportApp />
  </StrictMode>,
);

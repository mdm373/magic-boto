import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../global.css";
import "./embed-shell.css";
import { CardCarouselAppV2 } from "./CardCarouselAppV2";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <CardCarouselAppV2 />
  </StrictMode>,
);

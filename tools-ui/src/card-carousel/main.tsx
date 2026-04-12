import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "../global.css";
import { CardCarouselApp } from "./CardCarouselApp";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <CardCarouselApp />
  </StrictMode>,
);

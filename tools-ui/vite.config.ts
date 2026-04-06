import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";

export default defineConfig({
  plugins: [react(), viteSingleFile()],
  build: {
    outDir: "../tools_api/app/mcp_tooling/ui_dist",
    emptyOutDir: false,
    rollupOptions: {
      input: "pages/card.html",
    },
  },
});

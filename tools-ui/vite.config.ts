import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteSingleFile } from "vite-plugin-singlefile";

const target = process.env.VITE_BUILD_TARGET ?? "card";

export default defineConfig({
  plugins: [react(), viteSingleFile()],
  build: {
    outDir: "../tools_api/app/mcp_tooling/ui_dist",
    emptyOutDir: false,
    rollupOptions: {
      input: `pages/${target}.html`,
    },
  },
});

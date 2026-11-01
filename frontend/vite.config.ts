import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { copyFileSync } from "node:fs";

export default defineConfig({
  plugins: [
    react(),
    {
      name: "local-font-licenses",
      closeBundle() {
        for (const font of ["sora", "ibm-plex-sans", "ibm-plex-mono"]) {
          copyFileSync(
            `node_modules/@fontsource/${font}/LICENSE`,
            `../TwitchChannelPointsMiner/dashboard/static/assets/${font}-LICENSE.txt`,
          );
        }
      },
    },
  ],
  build: {
    outDir: "../TwitchChannelPointsMiner/dashboard/static",
    emptyOutDir: true,
  },
  server: { proxy: { "/api": "http://127.0.0.1:5000" } },
});

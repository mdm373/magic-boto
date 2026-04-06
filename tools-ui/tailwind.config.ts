import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}", "./pages/**/*.html"],
  darkMode: ["attribute", "[data-theme='dark']"],
  theme: {
    extend: {},
  },
  plugins: [],
};

export default config;

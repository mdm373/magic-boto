import type { Config } from "tailwindcss";
import typography from "@tailwindcss/typography";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}", "./pages/**/*.html"],
  darkMode: ["selector", "[data-theme='dark']"],
  theme: {
    extend: {
      typography: {
        "sweep-report": {
          css: {
            "--tw-prose-body": "var(--color-text-primary)",
            "--tw-prose-headings": "var(--color-text-primary)",
            "--tw-prose-bold": "var(--color-text-primary)",
            "--tw-prose-counters": "var(--color-text-tertiary)",
            "--tw-prose-bullets": "var(--color-text-secondary)",
            "--tw-prose-quotes": "var(--color-text-secondary)",
            "--tw-prose-quote-borders": "var(--color-border-primary)",
            "--tw-prose-code": "var(--color-text-primary)",
            "--tw-prose-pre-bg": "var(--color-background-secondary)",
            "--tw-prose-th-borders": "var(--color-border-primary)",
            "--tw-prose-td-borders": "var(--color-border-primary)",
            "--tw-prose-hr": "var(--color-border-primary)",
          },
        },
      },
    },
  },
  plugins: [typography],
};

export default config;

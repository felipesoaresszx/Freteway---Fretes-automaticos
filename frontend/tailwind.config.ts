import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { graphite: "var(--color-secondary)", copper: "var(--color-primary)", cream: "var(--color-text)" },
        bg: "var(--color-background)",
        surface: "var(--color-surface)",
        surface2: "color-mix(in srgb, var(--color-surface) 88%, var(--color-text))",
        border: "var(--color-border)",
        text: {
          primary: "var(--color-text)",
          secondary: "var(--color-muted-text)",
        },
        state: {
          success: "#39B978",
          warning: "#E5A83B",
          error: "#E05A5A",
          info: "var(--color-primary)",
        },
      },
      borderRadius: {
        DEFAULT: "0.375rem",
        sm: "0.25rem",
        md: "0.375rem",
        lg: "0.5rem",
        xl: "0.625rem",
      },
      boxShadow: { card: "0 1px 2px rgb(0 0 0 / 0.22), 0 10px 30px rgb(0 0 0 / 0.16)" },
    },
  },
  plugins: [],
} satisfies Config;

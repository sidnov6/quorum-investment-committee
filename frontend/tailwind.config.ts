import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Stripe palette
        brand: {
          DEFAULT: "#635BFF",
          dark: "#4B45C6",
          light: "#7A73FF",
        },
        ink: {
          DEFAULT: "#0A2540",   // Stripe deep navy
          soft: "#425466",
          faint: "#697386",
        },
        surface: {
          DEFAULT: "#FFFFFF",
          subtle: "#F6F9FC",     // Stripe light grey-blue
          line: "#E6EBF1",
        },
        bull: "#0E9F6E",
        bear: "#E02424",
        warn: "#C27803",
        macro: "#637381",
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        card: "0 1px 3px rgba(10,37,64,0.08), 0 8px 24px rgba(10,37,64,0.05)",
        lift: "0 4px 12px rgba(10,37,64,0.10), 0 20px 40px rgba(10,37,64,0.08)",
      },
      borderRadius: {
        xl: "14px",
        "2xl": "20px",
      },
    },
  },
  plugins: [],
};
export default config;

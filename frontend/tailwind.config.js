/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // 来自 Stitch DESIGN.md - 深色主题色板
        background: "#10141a",
        surface: "#141920",
        "surface-container-lowest": "#0d0d18",
        "surface-container-low": "#151b22",
        "surface-container": "#1a2129",
        "surface-container-high": "#222b34",
        "surface-container-highest": "#2d3741",
        "surface-bright": "#35414b",
        border: "#2b3540",
        "outline-variant": "#404752",
        outline: "#8a919e",

        // 主色
        primary: "#a5d8c3",
        "primary-container": "#5ca48d",
        info: "#2080F0",
        success: "#18A058",
        warning: "#F0A020",
        error: "#D03050",

        // 文字
        "text-primary": "#f3f6f7",
        "text-secondary": "#8d9aa6",
        "on-surface": "#dbe4e7",
        "on-surface-variant": "#b4c0c7",
      },
      borderRadius: {
        DEFAULT: "0.25rem",
        lg: "0.375rem",
        xl: "0.5rem",
        full: "9999px",
      },
      spacing: {
        "card-padding": "20px",
        "sidebar-width": "220px",
        "sidebar-collapsed": "64px",
        "container-padding": "24px",
        "stack-gap": "12px",
        gutter: "16px",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      fontSize: {
        "code-label": ["13px", { lineHeight: "16px", fontWeight: "500" }],
        "display-metrics": ["28px", { lineHeight: "34px", letterSpacing: "-0.02em", fontWeight: "700" }],
        "headline-md": ["16px", { lineHeight: "24px", fontWeight: "600" }],
        "nav-item": ["14px", { lineHeight: "20px", fontWeight: "500" }],
        "body-md": ["14px", { lineHeight: "22px", fontWeight: "400" }],
        "body-sm": ["12px", { lineHeight: "18px", fontWeight: "400" }],
        "headline-lg": ["20px", { lineHeight: "28px", fontWeight: "600" }],
      },
    },
  },
  plugins: [],
};

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef4ff",
          100: "#dbe6fe",
          400: "#5b8def",
          500: "#3766e8",
          600: "#274fc7",
          700: "#1f3fa0",
        },
        surface: {
          DEFAULT: "#0b1120",
          raised: "#111a2e",
          border: "#1f2a44",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

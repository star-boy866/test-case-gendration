/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Enterprise healthcare palette placeholder — refine in frontend
        // design passes during later phases.
        brand: {
          50: "#eef4ff",
          100: "#d9e6ff",
          500: "#3366ff",
          600: "#254edb",
          700: "#1c3bb0",
        },
      },
    },
  },
  plugins: [],
};

/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        ink: '#0a0a0a',
        paper: '#f7f7f7'
      }
    },
  },
  plugins: [],
}

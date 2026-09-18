/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        asv: {
          dark: '#0B0F17',
          card: '#111827',
          cardHover: '#1F2937',
          border: '#374151',
          accent: '#06B6D4',
          accentGlow: 'rgba(6, 182, 212, 0.15)',
        }
      }
    },
  },
  plugins: [],
}

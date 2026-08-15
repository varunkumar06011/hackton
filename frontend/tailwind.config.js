/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        restaurant: {
          dark: '#1a1a2e',
          sidebar: '#16213e',
          accent: '#0f3460',
          gold: '#e94560',
        }
      }
    },
  },
  plugins: [],
}

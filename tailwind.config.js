/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#1e40af', // Professional blue
        secondary: '#1f2937', // Dark gray for dark mode
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
  darkMode: 'class',
};
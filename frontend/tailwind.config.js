/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        montreal: [
          '"PP Neue Montreal"',
          '-apple-system',
          '"Helvetica Neue"',
          'Helvetica',
          'Arial',
          'sans-serif',
        ],
      },
      colors: {
        'brand-blue': '#3454d1',
      },
    },
  },
  plugins: [],
}

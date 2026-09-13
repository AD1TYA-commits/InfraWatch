/** @type {import('tailwindcss').Config} */
module.exports = {
  // ThemeProvider toggles dark mode by adding a `.dark` class to <html> (not
  // just following OS prefers-color-scheme) — this must match so `dark:*`
  // utility classes actually respond to the in-app toggle.
  darkMode: "class",
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};

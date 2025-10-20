/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./index.html','./src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        prosto: ["Prosto One", "ui-sans-serif", "system-ui"],
        raleway: ["Raleway", "ui-sans-serif", "system-ui"],
        mono: ["Fragment Mono", "ui-monospace", "SFMono-Regular"],
      },
      colors: {
        gain: "#4aa8ff",
        loss: "#ff65b6",
        ember: "#ff7a1a",
        pulse: "#a16dff",
      },
    }
  },
  plugins: [],
};

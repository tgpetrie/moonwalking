module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bh: {
          bg: "#000000",
          panel: "#000000",
          gold: "#f9c86b",
          goldDim: "#c49b47",
          purple: "#a24bff",
          purpleDim: "#5b2a8e",
          textMain: "#ffffff",
          textSoft: "#ffffffb3",
          textDim: "#ffffff80",
          borderGold: "rgba(249,200,107,0.4)",
          borderPurple: "rgba(162,75,255,0.4)",
          danger: "#ff3b3b",
          chipBg: "#0a0a0f",
        },
        // Back-compat aliases used across components
        dark: '#000000',
        teal: '#00f5b5',
        'teal-300': '#2dd4bf',
        purple: {
          DEFAULT: '#a24bff',
          300: '#caa3ff',
          400: '#b67bff',
          600: '#8a2be2',
          700: '#6b21c8'
        },
        pink: {
          DEFAULT: '#FF69B4',
          300: '#ff9bbf',
          400: '#ff79c7'
        },
        fuchsia: {
          400: '#d946ef'
        }
      },
      fontFamily: {
        sans: ["Raleway", "system-ui", "sans-serif"],
        mono: ["Raleway", "system-ui", "sans-serif"],
        bhTitle: ["Raleway", "system-ui", "sans-serif"],
        bhMono: ["Raleway", "system-ui", "sans-serif"],
        ui: ["Raleway", "system-ui", "sans-serif"],
      },
      boxShadow: {
        glowGold: "0 0 30px rgba(249,200,107,0.35)",
        glowPurple: "0 0 30px rgba(162,75,255,0.35)",
      },
      backgroundImage: {
        bunny: "url('/bhabit-bunny.svg')",
      },
    },
  },
  plugins: [],
};

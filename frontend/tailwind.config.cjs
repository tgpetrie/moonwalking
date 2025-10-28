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
      },
      fontFamily: {
        bhTitle: ["Raleway", "system-ui", "sans-serif"],
        bhMono: ["'Fragment Mono'", "ui-monospace", "monospace"],
        ui: ["Inter","system-ui","sans-serif"],
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

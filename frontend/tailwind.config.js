/** BHABIT Tailwind Design Tokens — Final */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        // main UI font everywhere
        sans: ["Raleway", "system-ui", "sans-serif"],

        // override "mono" to ALSO be Raleway so we don't get Fragment Mono / monospace
        mono: ["Raleway", "system-ui", "sans-serif"],
      },
      colors: {
        bg: "#000000",
        surface: "rgba(22,22,28,0.65)",
        line: "rgba(255,255,255,0.08)",
        text: "#FFFFFF",
        textDim: "rgba(255,255,255,0.6)",
        gold: "#FFB84D",
        purple: "#D46CFF",
        orange: "#FF7A3D",
        blue: "#4FD1FF",
        success: "#5BF7A5",
        error: "#FF6B81",
      },
      backgroundImage: {
        "banner-top":
          "linear-gradient(to right, rgba(255,184,77,0.08), rgba(212,108,255,0.08))",
        "banner-bottom":
          "linear-gradient(to right, rgba(212,108,255,0.08), rgba(79,209,255,0.08))",
        "row-hover-up":
          "linear-gradient(to right, rgba(255,184,77,0.25), rgba(255,184,77,0.05))",
        "row-hover-down":
          "linear-gradient(to right, rgba(212,108,255,0.25), rgba(212,108,255,0.05))",
      },
      boxShadow: {
        glowGold: "0 0 16px rgba(249,200,107,.5)",
        glowPurple: "0 0 16px rgba(162,75,255,.5)",
      },
      borderRadius: {
        xl: "1rem",
        "2xl": "1.25rem",
      },
    },
  },
  plugins: [],
};

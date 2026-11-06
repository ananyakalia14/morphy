module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: { ink: "#000000", paper: "#FFFFFF", cobalt: "#0047FF" },
      boxShadow: { hard: "5px 5px 0 #000", active: "7px 7px 0 #0047FF" },
    },
  },
};

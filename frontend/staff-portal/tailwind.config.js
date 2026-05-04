/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: "#0F2B3C",
        teal: "#0D9488",
        "teal-soft": "#F0FDFA",
        slate: {
          DEFAULT: "#64748B",
          50: "#F8FAFC",
          100: "#F1F5F9",
          200: "#E2E8F0",
          700: "#334155",
          900: "#0F172A",
        },
        coral: "#EF4444",
        amber: "#F59E0B",
      },
      boxShadow: {
        clinical: "0 12px 30px rgba(15, 43, 60, 0.08)",
      },
    },
  },
  plugins: [],
};

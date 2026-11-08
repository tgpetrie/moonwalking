export default [
  {
    files: ["frontend/**/*.{js,jsx,cjs,mjs}"],
    rules: {
      "no-dupe-args": "error",
      "no-dupe-class-members": "error",
      "no-dupe-keys": "error",
      "no-import-assign": "error",
      "no-invalid-regexp": "error",
      "no-unreachable": "error",
      "no-unsafe-finally": "error",
    },
  },
  {
    files: ["frontend/**/*.{js,jsx}"],
    languageOptions: {
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
  },
];

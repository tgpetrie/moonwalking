// Minimal flat config for the pre-commit eslint hook (ESLint 9+).
//
// It imports nothing on purpose: pre-commit installs ESLint in its own node
// environment, and a config that imports plugins can't resolve them from the
// repo root. Only core rules are used, and only ones that catch real bugs, so
// touching a legacy file doesn't surface a wall of style warnings.

export default [
  {
    ignores: [
      "**/node_modules/**",
      "**/dist/**",
      "frontend/src/legacy/**",
      "frontend/src/legacy913/**",
      "frontend/src/playground/**",
    ],
  },
  {
    files: ["frontend/**/*.{js,jsx,mjs,cjs}"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "module",
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    linterOptions: { reportUnusedDisableDirectives: "off" },
    rules: {
      "no-debugger": "error",
      "no-dupe-keys": "error",
      "no-dupe-args": "error",
      "no-duplicate-case": "error",
      "no-unreachable": "error",
    },
  },
  {
    files: ["frontend/**/*.cjs"],
    languageOptions: { sourceType: "commonjs" },
  },
];

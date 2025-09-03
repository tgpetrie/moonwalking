import js from '@eslint/js';
import reactPlugin from 'eslint-plugin-react';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import reactHooks from 'eslint-plugin-react-hooks';
import sonarjs from 'eslint-plugin-sonarjs';

export default [
  js.configs.recommended,
  {
    plugins: {
      react: reactPlugin,
      'jsx-a11y': jsxA11y,
      'react-hooks': reactHooks,
      sonarjs,
    },
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        window: true,
        document: true,
        console: true,
        navigator: true,
        localStorage: true,
        setTimeout: true,
        clearTimeout: true,
        setInterval: true,
        clearInterval: true,
        fetch: true,
        AbortController: true,
        process: true,
        performance: true,
      },
      parserOptions: {
        ecmaFeatures: {
          jsx: true,
        },
      },
    },
    rules: {
      'react/react-in-jsx-scope': 'off',
      'react/prop-types': 'off',
      'jsx-a11y/no-onchange': 'off',
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      'sonarjs/cognitive-complexity': 'warn',
      // Add more rules as needed for React 19
    },
    settings: {
      react: {
        version: 'detect',
      },
    },
  },
];

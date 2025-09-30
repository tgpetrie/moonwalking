const js = require('@eslint/js');
const globals = require('globals');
const react = require('eslint-plugin-react');
const reactHooks = require('eslint-plugin-react-hooks');

const baseGlobals = {
  ...globals.browser,
  ...globals.node,
  WebSocketPair: 'readonly'
};

module.exports = [
  {
    ignores: [
      'node_modules/',
      'dist/',
      'build/',
      'frontend/dist/',
      'frontend/dist/**',
      'frontend/public/vendor/',
      'frontend/public/vendor/**',
      'frontend/public/assets/',
      'frontend/public/assets/**',
      'frontend/public/icons/',
      'frontend/public/icons/**',
      'frontend/public/fonts/',
      'frontend/public/fonts/**',
      '**/*.original.jsx',
      'dev-evidence/',
      '*.log',
      '.venv/',
      '.history/',
      '.history-quarantine/',
      '.history_quarantine/',
      '**/.history/**',
      '**/.history-quarantine/**',
      '**/.history_quarantine/**',
      'snapshots/',
      'static-demo/',
      'original-design/',
      'workers/',
      'cbmo4ers-edge/',
      'Watchlist__SAVED_BEFORE_REVERT.jsx'
    ]
  },
  js.configs.recommended,
  {
    files: ['**/*.js', '**/*.mjs', '**/*.cjs', '**/*.jsx'],
    languageOptions: {
      ecmaVersion: 2024,
      sourceType: 'module',
      globals: baseGlobals
    },
    rules: {
      'no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_', caughtErrorsIgnorePattern: '^_' }],
      'no-empty': ['error', { allowEmptyCatch: true }]
    }
  },
  {
    files: ['frontend/src/**/*.js', 'frontend/src/**/*.jsx'],
    plugins: {
      react,
      'react-hooks': reactHooks
    },
    languageOptions: {
      ecmaVersion: 2024,
      sourceType: 'module',
      parserOptions: {
        ecmaFeatures: {
          jsx: true
        }
      },
      globals: {
        ...globals.browser,
        WebSocketPair: 'readonly'
      }
    },
    settings: {
      react: {
        version: 'detect'
      }
    },
    rules: {
      'react/react-in-jsx-scope': 'off',
      'react/jsx-uses-react': 'error',
      'react/jsx-uses-vars': 'error',
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'off'
    }
  }
];

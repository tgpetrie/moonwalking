module.exports = [
  {
    ignores: ['dist/**', 'node_modules/**'],
  },
  {
    files: ['**/*.js', '**/*.jsx'],
    languageOptions: {
      parser: require('@babel/eslint-parser'),
      parserOptions: {
        requireConfigFile: false,
        ecmaVersion: 2024,
        sourceType: 'module',
        ecmaFeatures: { jsx: true }
      }
    },
    plugins: {
      react: require('eslint-plugin-react'),
      'react-hooks': require('eslint-plugin-react-hooks'),
      'sonarjs': require('eslint-plugin-sonarjs')
    },
    settings: { react: { version: 'detect' } },
    rules: {
      // Keep rules permissive for now; CI can tighten these later
      'react/react-in-jsx-scope': 'off'
    }
  }
];

import js from '@eslint/js';
import globals from 'globals';
export default [
  { ignores: ['dist/**', 'node_modules/**', 'public/**'] },
  js.configs.recommended,
  { files: ['src/**/*.js'], languageOptions: { globals: globals.browser },
    rules: { 'no-unused-vars': ['warn', { argsIgnorePattern: '^_' }] } },
];

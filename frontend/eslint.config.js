import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";

export default [
  { ignores: ["dist/**"] },
  js.configs.recommended,
  reactHooks.configs.flat.recommended,
  {
    files: ["**/*.{js,jsx}"],
    languageOptions: {
      ecmaVersion: "latest",
      globals: globals.browser,
      parserOptions: {
        ecmaFeatures: { jsx: true },
        sourceType: "module",
      },
    },
    plugins: {
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactRefresh.configs.vite.rules,
      "no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^[A-Z_]" }],
    },
  },
  {
    files: ["src/i18n.jsx", "src/main.jsx"],
    rules: {
      // These entry modules intentionally export non-component helpers alongside providers.
      "react-refresh/only-export-components": "off",
    },
  },
  {
    files: [
      "src/pages/ProjectEditor.jsx",
      "src/pages/SchedulePage.jsx",
      "src/pages/SettingsPage.jsx",
    ],
    rules: {
      // These effects intentionally synchronize editable UI state with project/API state.
      "react-hooks/set-state-in-effect": "off",
    },
  },
];

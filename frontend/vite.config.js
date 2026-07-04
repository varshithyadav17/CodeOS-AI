import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

// Standalone Vite configuration.
// - Replaces the previous Create React App + CRACO setup.
// - Keeps the `@/` alias used throughout the codebase.
// - Treats any `.js` file inside `src/` as JSX so existing components
//   that still use the `.js` extension keep working without renames.
// - The dev server listens on the port reported by `process.env.PORT`
//   when present (so platform-managed previews can override it),
//   otherwise on the standard Vite port 5173.
export default defineConfig(({ mode }) => {
  // Load env vars from .env / .env.local so they are visible to the
  // config (Vite normally only exposes them to client code).
  loadEnv(mode, process.cwd(), '');
  const port = Number(process.env.PORT) || 5173;

  return {
    plugins: [
      react({
        include: /\.(js|jsx|ts|tsx)$/,
      }),
    ],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    esbuild: {
      loader: 'jsx',
      include: /src\/.*\.(js|jsx)$/,
      exclude: [],
    },
    optimizeDeps: {
      esbuildOptions: {
        loader: { '.js': 'jsx' },
      },
    },
    server: {
      host: '0.0.0.0',
      port,
      strictPort: false,
      // Allow the platform preview proxy host (and any future host) to
      // reach the dev server; Vite 5 blocks unknown hosts by default.
      allowedHosts: true,
    },
    preview: {
      host: '0.0.0.0',
      port: 4173,
    },
    build: {
      outDir: 'dist',
      sourcemap: false,
      // 1500 previously masked a single ~740KB (226KB gzip) bundle instead
      // of prompting a fix. Route/panel-level code splitting (see App.jsx,
      // RepoDetail.js) now does the real work; this stays close to Vite's
      // default so a future regression is caught again.
      chunkSizeWarningLimit: 600,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (!id.includes('node_modules')) return undefined;
            // reactflow only loads with the Knowledge Graph / Architecture
            // panels, but is large enough to deserve its own cacheable
            // chunk rather than riding along with whichever route pulls
            // it in first.
            if (id.includes('reactflow')) return 'vendor-reactflow';
            if (id.includes('@radix-ui')) return 'vendor-radix';
            if (id.includes('react-markdown') || id.includes('react-syntax') || id.includes('remark') || id.includes('rehype') || id.includes('micromark') || id.includes('mdast') || id.includes('unist') || id.includes('unified')) return 'vendor-markdown';
            if (id.includes('/react/') || id.includes('/react-dom/') || id.includes('scheduler')) return 'vendor-react';
            return undefined;
          },
        },
      },
    },
  };
});

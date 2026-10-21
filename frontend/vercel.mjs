// Keep browser requests same-origin for session and Google challenge cookies.
const backendOrigin = process.env.RENDER_BACKEND_ORIGIN;
if (!backendOrigin) {
  throw new Error('Set RENDER_BACKEND_ORIGIN to the existing HTTPS Render service origin before deploying.');
}
const backend = new URL(backendOrigin);
if (backend.protocol !== 'https:' || backend.username || backend.password ||
    backend.pathname !== '/' || backend.search || backend.hash) {
  throw new Error('RENDER_BACKEND_ORIGIN must be an HTTPS origin without credentials, path, query, or fragment.');
}
if (process.env.VITE_BACKEND_URL) {
  throw new Error('Remove VITE_BACKEND_URL on Vercel; API requests use the same-origin Render proxy.');
}

export const config = {
  framework: 'vite',
  buildCommand: 'npm run build',
  outputDirectory: 'dist',
  rewrites: [
    { source: '/api/:path*', destination: `${backend.origin}/api/:path*` },
    { source: '/(.*)', destination: '/index.html' },
  ],
  headers: [
    { source: '/(.*)', headers: [
      { key: 'Cross-Origin-Opener-Policy', value: 'same-origin-allow-popups' },
      { key: 'X-Content-Type-Options', value: 'nosniff' },
      { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
    ] },
    { source: '/api/:path*', headers: [
      { key: 'Cache-Control', value: 'no-store' },
      { key: 'x-vercel-enable-rewrite-caching', value: '0' },
    ] },
  ],
};

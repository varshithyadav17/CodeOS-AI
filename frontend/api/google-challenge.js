import { createHmac, randomBytes } from 'node:crypto';
import { Buffer } from 'node:buffer';

const lifetime = 600;
const headers = {
  'Cache-Control': 'private, no-store, max-age=0',
  'X-CodeOS-Auth-Source': 'vercel',
};
const encode = value => Buffer.from(JSON.stringify(value)).toString('base64url');

// Setup is independent of the API, Google and the database. Only FastAPI
// verifies the Google ID token and can create an application session.
export function GET(request) {
  const origin = request.headers.get('origin');
  if (request.headers.get('sec-fetch-site') === 'cross-site'
      || (origin && origin !== new URL(request.url).origin)) {
    return Response.json({ detail: 'Request origin is not allowed.' }, { status: 403, headers });
  }

  const clientId = (process.env.GOOGLE_CLIENT_ID || '').trim();
  if (!clientId) return Response.json({ enabled: false }, { headers });
  const key = process.env.GOOGLE_CHALLENGE_SECRET || '';
  if (key.length < 32 || !/^[0-9]+-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com$/.test(clientId)) {
    console.error('google_challenge_configuration_missing_or_invalid');
    return Response.json({ detail: 'Google sign-in setup is temporarily unavailable.' }, { status: 503, headers });
  }

  const nonce = randomBytes(32).toString('base64url');
  const issuedAt = Math.floor(Date.now() / 1000);
  const claims = { sub: nonce, iss: 'codeos-ai', aud: 'codeos-google', iat: issuedAt, exp: issuedAt + lifetime };
  const unsigned = `${encode({ alg: 'HS256', typ: 'JWT' })}.${encode(claims)}`;
  const signature = createHmac('sha256', key).update(unsigned).digest('base64url');
  return Response.json({ enabled: true, client_id: clientId, nonce, expires_in: lifetime }, { headers: {
    ...headers,
    'Set-Cookie': `codeos_google_nonce=${unsigned}.${signature}; Max-Age=${lifetime}; Path=/api/auth; HttpOnly; Secure; SameSite=Lax`,
  } });
}

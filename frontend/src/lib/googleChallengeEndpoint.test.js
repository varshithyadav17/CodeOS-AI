import test from 'node:test';
import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import { Buffer } from 'node:buffer';
import { GET } from '../../api/google-challenge.js';

const key = 'isolated-challenge-endpoint-test-secret-over-32-characters';
const clientId = '12345-isolated.apps.googleusercontent.com';
const origin = 'https://example.vercel.app';
const request = headers => new Request(origin + '/api/auth/google/challenge', { headers });

function configure(t) {
  const previous = {
    GOOGLE_CHALLENGE_SECRET: process.env.GOOGLE_CHALLENGE_SECRET,
    GOOGLE_CLIENT_ID: process.env.GOOGLE_CLIENT_ID,
  };
  process.env.GOOGLE_CHALLENGE_SECRET = key;
  process.env.GOOGLE_CLIENT_ID = clientId;
  t.after(() => {
    for (const [name, value] of Object.entries(previous)) {
      if (value === undefined) delete process.env[name];
      else process.env[name] = value;
    }
  });
}

test('independent setup issues an uncacheable, short-lived browser challenge', async t => {
  configure(t);
  const response = GET(request({ origin, 'sec-fetch-site': 'same-origin' }));
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('x-codeos-auth-source'), 'vercel');
  assert.match(response.headers.get('cache-control'), /no-store/);
  const cookie = response.headers.get('set-cookie');
  assert.match(cookie, /^codeos_google_nonce=.*; Max-Age=600; Path=\/api\/auth; HttpOnly; Secure; SameSite=Lax$/);
  const [head, payload, signature] = cookie.split(';')[0].split('=')[1].split('.');
  assert.equal(signature, createHmac('sha256', key).update(`${head}.${payload}`).digest('base64url'));
  const claims = JSON.parse(Buffer.from(payload, 'base64url').toString());
  const body = await response.json();
  assert.deepEqual(body, { enabled: true, client_id: clientId, nonce: claims.sub, expires_in: 600 });
  assert.equal(claims.aud, 'codeos-google');
  assert.equal(claims.iss, 'codeos-ai');
  assert.equal(claims.exp - claims.iat, 600);
  assert.notEqual((await GET(request()).json()).nonce, body.nonce);
});

test('cross-site requests cannot overwrite the browser challenge', t => {
  configure(t);
  for (const headers of [{ 'sec-fetch-site': 'cross-site' }, { origin: 'https://untrusted.example' }]) {
    const response = GET(request(headers));
    assert.equal(response.status, 403);
    assert.equal(response.headers.get('set-cookie'), null);
  }
});

test('the setup endpoint does not issue a cookie without a valid configuration', async t => {
  configure(t);
  delete process.env.GOOGLE_CLIENT_ID;
  const disabled = GET(request());
  assert.deepEqual(await disabled.json(), { enabled: false });
  assert.equal(disabled.headers.get('set-cookie'), null);
  process.env.GOOGLE_CLIENT_ID = clientId;
  delete process.env.GOOGLE_CHALLENGE_SECRET;
  t.mock.method(console, 'error', () => {});
  const response = GET(request());
  assert.equal(response.status, 503);
  assert.equal(response.headers.get('set-cookie'), null);
});

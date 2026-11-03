import test from 'node:test';
import assert from 'node:assert/strict';
import { googleFailure, googleRetrySeconds, requestGoogleChallenge } from './googleRecovery.js';
const limited = delay => ({ response: { status: 429, headers: delay === undefined ? {} : { 'retry-after': delay } }, message: 'Request failed with status code 429', isAxiosError: true });
test('short throttling waits for Retry-After and recovers with one fresh challenge', async () => {
  let calls = 0; const waits = [];
  const result = await requestGoogleChallenge(async () => { if (++calls === 1) throw limited('3'); return { nonce: 'fresh' }; }, async ms => waits.push(ms));
  assert.deepEqual(result, { nonce: 'fresh' }); assert.equal(calls, 2); assert.deepEqual(waits, [3000]);
});
test('long cooldown returns immediately instead of flooding or blocking setup', async () => {
  let calls = 0;
  await assert.rejects(requestGoogleChallenge(async () => { calls++; throw limited('120'); }, () => assert.fail('Must not wait in setup')));
  assert.equal(calls, 1); assert.equal(googleFailure(limited('120')).retryAfter, 120);
  assert.match(googleFailure(limited('120')).message, /temporarily rate-limited/);
});
test('repeated 429s are bounded and never expose Axios error copy', async () => {
  let calls = 0;
  await assert.rejects(requestGoogleChallenge(async () => { calls++; throw limited(); }, async () => {}));
  assert.equal(calls, 2); assert.equal(googleFailure(limited()).retryAfter, 30);
  assert.doesNotMatch(googleFailure(limited()).message, /status code/);
});
test('Retry-After supports dates, zero, malformed and missing values', () => {
  const now = Date.parse('2026-11-03T12:00:00Z');
  assert.equal(googleRetrySeconds(limited('Tue, 03 Nov 2026 12:00:40 GMT'), 30, now), 40);
  assert.equal(googleRetrySeconds(limited('0')), 1);
  assert.equal(googleRetrySeconds(limited('invalid')), 30);
});
test('credential and configuration errors are not automatically retried', async () => {
  let calls = 0; const invalid = { response: { status: 401, data: { detail: 'Invalid Google credential' } } };
  await assert.rejects(requestGoogleChallenge(async () => { calls++; throw invalid; }, () => assert.fail('Do not retry')));
  assert.equal(calls, 1); assert.equal(googleFailure(invalid).message, 'Invalid Google credential');
});
test('upstream downtime retries once and timeout errors provide readable recovery', async () => {
  let calls = 0;
  const result = await requestGoogleChallenge(async () => { if (++calls === 1) throw { response: { status: 503 } }; return 'ready'; }, async ms => assert.equal(ms, 2000));
  assert.equal(result, 'ready'); assert.equal(googleFailure({code:'ECONNABORTED'}).retryAfter, 5);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { isActionableMemory, memoryChatDraft, sortMemories } from './engineeringMemory.js';

test('priority keeps actionable findings ahead of closed critical findings without mutating input', () => {
  const items = [
    { id: 'closed', status: 'resolved', severity: 'critical' },
    { id: 'low', status: 'open', severity: 'low' },
    { id: 'high', status: 'open', severity: 'high', updated_at: '2026-10-31' },
    { id: 'working', status: 'in_progress', severity: 'high', updated_at: '2026-10-20' },
  ];
  assert.deepEqual(sortMemories(items).map(item => item.id), ['working', 'high', 'low', 'closed']);
  assert.equal(items[0].id, 'closed');
  assert.equal(isActionableMemory(items[0]), false);
  assert.equal(isActionableMemory(items[3]), true);
});

test('recent order allows revisiting recently updated resolved findings', () => {
  const items = [{ id: 'old', updated_at: '2026-10-01', status: 'open' }, { id: 'new', updated_at: '2026-11-01', status: 'resolved' }, { id: 'missing' }];
  assert.deepEqual(sortMemories(items, 'recent').map(item => item.id), ['new', 'old', 'missing']);
});

test('chat draft includes saved evidence and recommendation with bounded size and a request to verify', () => {
  const draft = memoryChatDraft({ title: 'Token validation', file_path: 'auth.py', description: 'Check the expiry time.' }, 'Add expiry tests.');
  assert.match(draft, /Finding: Token validation/);
  assert.match(draft, /File: auth.py/);
  assert.match(draft, /Check the expiry time/);
  assert.match(draft, /Add expiry tests/);
  assert.match(draft, /Verify whether it still applies/);
  const largeDraft = memoryChatDraft({ title: 'a'.repeat(2000), file_path: 'b'.repeat(4000), description: 'c'.repeat(20000) }, 'd'.repeat(10000));
  assert.ok(largeDraft.length < 12000);
  assert.ok(!memoryChatDraft({ title: 'Decision' }).includes('undefined'));
});

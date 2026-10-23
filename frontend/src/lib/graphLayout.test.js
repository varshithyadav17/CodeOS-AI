import test from 'node:test';
import assert from 'node:assert/strict';
import { connectedIds, dependencyPositions, filePositions } from './graphLayout.js';
const node = (id, file_path = `${id}.py`, type = 'function') => ({ id, file_path, type });
const edge = (source_id, target_id) => ({ source_id, target_id });
function assertNoOverlap(positions) {
  const all = Object.values(positions);
  for (let i = 0; i < all.length; i++) for (let j = i + 1; j < all.length; j++) {
    assert.ok(Math.abs(all[i].x - all[j].x) >= 210 || Math.abs(all[i].y - all[j].y) >= 94, `Nodes ${i}, ${j} overlap`);
  }
}
test('dependency chains run left to right with cycles and disconnected components intact', () => {
  const nodes = 'abcdef'.split('').map(id => node(id));
  const edges = [edge('a','b'), edge('b','c'), edge('c','b'), edge('c','d'), edge('f','f'), edge('outside','a')];
  const positions = dependencyPositions(nodes, edges);
  assert.equal(Object.keys(positions).length, 6);
  assert.ok(positions.a.x < positions.b.x && positions.a.x < positions.c.x);
  assert.ok(positions.d.x > positions.b.x && positions.d.x > positions.c.x);
  assertNoOverlap(positions);
  assert.deepEqual(dependencyPositions([...nodes].reverse(), edges), positions);
});
test('dense file clusters and dependency views have no overlapping cards', () => {
  const nodes = Array.from({length: 200}, (_, i) => node(String(i), `group${Math.floor(i / 35)}.py`, i % 35 === 0 ? 'file' : 'function'));
  assertNoOverlap(filePositions(nodes));
  assertNoOverlap(dependencyPositions(nodes, nodes.slice(1).map(n => edge('0', n.id))));
  assert.equal(Object.keys(filePositions(nodes)).length, nodes.length);
});
test('focus includes incoming, outgoing and self, without unrelated nodes', () => {
  assert.deepEqual([...connectedIds('b', [edge('a','b'), edge('b','c'), edge('b','b'), edge('d','e')])].sort(), ['a','b','c']);
});

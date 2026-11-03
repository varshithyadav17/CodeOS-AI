const severityRank = { critical: 0, high: 1, medium: 2, low: 3, info: 4 };
export const isActionableMemory = item => ['open', 'in_progress'].includes(item.status);
export function sortMemories(items, order = 'priority') {
  const updated = item => Date.parse(item.updated_at || item.created_at || '') || 0;
  return [...items].sort((a, b) => {
    if (order === 'recent') return updated(b) - updated(a);
    return Number(isActionableMemory(b)) - Number(isActionableMemory(a))
      || (severityRank[a.severity] ?? 5) - (severityRank[b.severity] ?? 5)
      || Number(b.status === 'in_progress') - Number(a.status === 'in_progress')
      || updated(b) - updated(a);
  });
}
export function memoryChatDraft(memory, recommendation = '') {
  return [
    'Check this saved finding against the current indexed repository. Verify whether it still applies, explain the relevant code, and suggest a fix or next step with file-and-line citations. Treat the saved finding as context to verify.',
    `Finding: ${String(memory.title || '').slice(0, 300)}`,
    memory.file_path ? `File: ${String(memory.file_path).slice(0, 1000)}` : '',
    memory.description ? `Saved context:\n${String(memory.description).slice(0, 3000)}` : '',
    recommendation ? `Original suggestion:\n${String(recommendation).slice(0, 1500)}` : '',
  ].filter(Boolean).join('\n\n');
}

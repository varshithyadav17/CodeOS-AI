import { Link } from 'react-router-dom';
import ArrowUpRight from '../assets/icons/arrow-up-right.svg?react';
import GitBranch from '../assets/icons/git-branch.svg?react';
import MessageSquare from '../assets/icons/message-square.svg?react';
import PlusIcon from '../assets/icons/plus.svg?react';
import { useFetch } from '../hooks/useFetch';
import { SkeletonList } from '../components/Skeleton';
import { ErrorState } from '../components/EmptyState';
import { repositoryStatusLabel } from '../lib/repositoryStatus';
import { isActionableMemory, sortMemories } from '../lib/engineeringMemory';
import './workspace.css';

function ActivityFeed({ items }) {
  return <ol className="activity-feed">{items.length ? items.slice(0, 8).map(item => <li key={item.id}>
    <span className="activity-dot" /><div><p>{item.message}</p><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })}</time></div>
  </li>) : <li className="workspace-muted">Your imports, questions and reviews will appear here.</li>}</ol>;
}

export default function Dashboard() {
  const { data: stats, loading, error, retry } = useFetch('/stats');
  const repoResult = useFetch('/repos');
  const memoryResult = useFetch('/memory?limit=200');
  const repos = [...(repoResult.data || [])].sort((a, b) => (Date.parse(b.updated_at) || 0) - (Date.parse(a.updated_at) || 0));
  const ready = repos.filter(repo => repo.status === 'ready');
  const attention = repos.filter(repo => ['failed', 'delete_failed', 'waiting_embeddings'].includes(repo.status));
  const findings = sortMemories(memoryResult.data || []).filter(isActionableMemory).slice(0, 3);
  const repoNames = new Map(repos.map(repo => [repo.id, repo.name]));
  return <div className="workspace-page dashboard-page" data-testid="dashboard-root">
    <header className="workspace-page-heading"><div><h1>Dashboard</h1><p>Your repositories, recent work, and what needs attention.</p></div>
      <Link to="/repositories" data-testid="dashboard-add-repo" className="workspace-primary">Add repository <PlusIcon width={14} height={14} aria-hidden="true" /></Link>
    </header>
    {error && <ErrorState message={error} onRetry={retry} testId="dashboard-error" />}
    {!error && loading && <SkeletonList rows={5} rowClassName="h-16" />}
    {!error && !loading && <>
      <section className="workspace-overview" aria-label="Workspace overview">
        <div className="workspace-overview-main"><span className="workspace-eyebrow">Indexed workspace</span>
          <div className="workspace-big-metric" data-testid="stat-files"><strong>{(stats?.files_indexed || 0).toLocaleString()}</strong><span>source files</span></div>
          <div className="workspace-repo-total" data-testid="stat-repos"><strong>{stats?.repos_count || 0}</strong> {stats?.repos_count === 1 ? 'repository' : 'repositories'}{!repoResult.loading && !repoResult.error && <><span className="workspace-dot-divider">·</span> {ready.length} ready to explore</>}</div>
          <div className="workspace-overview-foot">{stats?.repos_count ? 'Open a repository to trace code, ask questions, or start a review.' : 'Bring in your first repository to build a searchable view of your code.'}</div>
        </div>
        <div className="workspace-overview-side"><div className="workspace-graph-totals"><span className="workspace-eyebrow">Code graph</span>
          <div data-testid="stat-nodes"><strong>{(stats?.nodes || 0).toLocaleString()}</strong><span>symbols & files</span></div>
          <div className="workspace-small-metrics"><span data-testid="stat-edges">{(stats?.edges || 0).toLocaleString()} relationships</span><span data-testid="stat-chunks">{(stats?.chunks || 0).toLocaleString()} indexed chunks</span></div>
        </div><div className="workspace-chat-total"><MessageSquare width={18} height={18} aria-hidden="true" /><div><strong data-testid="stat-llm">{stats?.llm_calls || 0}</strong><span>chat answers grounded in your code</span></div></div></div>
      </section>
      <div className="dashboard-columns"><div className="dashboard-main-column">
        <section className="workspace-section" aria-labelledby="recent-repos-title"><div className="workspace-section-heading"><div><span className="workspace-eyebrow">Pick up your work</span><h2 id="recent-repos-title">Recently updated repositories</h2></div><Link to="/repositories" className="workspace-text-link">View all <ArrowUpRight width={13} height={13} /></Link></div>
          {repoResult.error ? <ErrorState message={repoResult.error} onRetry={repoResult.retry} compact /> : repoResult.loading ? <SkeletonList rows={3} /> : repos.length ? <ul className="dashboard-repos">{repos.slice(0, 5).map(repo => <li key={repo.id}><Link to={`/repositories/${repo.id}`} data-testid={`dashboard-repo-${repo.id}`}><div className="workspace-repo-icon"><GitBranch width={17} height={17} aria-hidden="true" /></div><div className="dashboard-repo-info"><strong>{repo.name}</strong><span>{repo.stats?.files || 0} files · {repo.stats?.nodes || 0} graph nodes</span></div><span className={`workspace-status ${repo.status === 'ready' ? 'is-ready' : 'is-pending'}`}>{repositoryStatusLabel(repo.status)}</span><ArrowUpRight className="dashboard-repo-arrow" width={16} height={16} aria-hidden="true" /></Link></li>)}</ul> : <div className="workspace-blank"><h3>A home for your codebases</h3><p>Connect GitHub or upload a ZIP. Your files, graph, reviews and saved findings stay together.</p><Link to="/repositories" className="workspace-text-link">Import your first repository →</Link></div>}
          {attention.length > 0 && <p className="workspace-attention">{attention.length} {attention.length === 1 ? 'repository needs' : 'repositories need'} attention. <Link to="/repositories">Check import status →</Link></p>}
        </section>
        <section className="workspace-section dashboard-findings" aria-labelledby="dashboard-findings-title"><div className="workspace-section-heading"><div><span className="workspace-eyebrow">From Engineering Memory</span><h2 id="dashboard-findings-title">Open work to revisit</h2></div><Link to="/memory?status=open" className="workspace-text-link">View memory <ArrowUpRight width={13} height={13} /></Link></div>
          {memoryResult.error ? <ErrorState message={memoryResult.error} onRetry={memoryResult.retry} compact /> : memoryResult.loading ? <SkeletonList rows={2} /> : findings.length ? <ul className="dashboard-findings-list">{findings.map(item => <li key={item.id}><Link to={`/memory?repo=${item.repo_id}&item=${item.id}`}><span className={`memory-severity-dot severity-${item.severity}`} /><div><strong>{item.title}</strong><span>{repoNames.get(item.repo_id) || 'Repository'} · {item.category.replaceAll('_', ' ')}</span></div><span className="workspace-text-link">Review →</span></Link></li>)}</ul> : <div className="workspace-blank compact"><p>No open findings saved yet. Save review findings or a note to keep the next step close to the code.</p></div>}
        </section>
      </div><aside className="workspace-section dashboard-activity"><div className="workspace-section-heading"><div><span className="workspace-eyebrow">Latest updates</span><h2>Activity</h2></div></div><ActivityFeed items={stats?.recent_activity || []} /></aside></div>
    </>}
  </div>;
}

import { Link } from 'react-router-dom';
import ArrowUpRight from '../assets/icons/arrow-up-right.svg?react';
import GitBranch from '../assets/icons/git-branch.svg?react';
import MessageSquare from '../assets/icons/message-square.svg?react';
import Network from '../assets/icons/network.svg?react';
import Layers from '../assets/icons/layers.svg?react';
import { hasParsedWorkspace } from '../lib/repositoryStatus';
import './workspace-overview.css';

const format = value => (value || 0).toLocaleString();

// A decorative illustration of code intelligence, not a fabricated repository graph.
function CodeAtlas() {
  return <div className="overview-atlas" aria-hidden="true"><svg viewBox="0 0 480 300" fill="none">
    <defs>
      <linearGradient id="atlas-floor" x1="240" y1="100" x2="240" y2="290" gradientUnits="userSpaceOnUse"><stop stopColor="#65DCEB" stopOpacity=".25"/><stop offset="1" stopColor="#65DCEB" stopOpacity="0"/></linearGradient>
      <linearGradient id="atlas-chip" x1="190" y1="95" x2="300" y2="222" gradientUnits="userSpaceOnUse"><stop stopColor="#1D6174"/><stop offset="1" stopColor="#101F46"/></linearGradient>
      <linearGradient id="atlas-top" x1="180" y1="110" x2="290" y2="170" gradientUnits="userSpaceOnUse"><stop stopColor="#85F1F2" stopOpacity=".7"/><stop offset="1" stopColor="#6B8EF3" stopOpacity=".3"/></linearGradient>
      <radialGradient id="atlas-aura"><stop stopColor="#3AADC5" stopOpacity=".28"/><stop offset="1" stopColor="#2239A2" stopOpacity="0"/></radialGradient>
      <filter id="atlas-glow" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="3"/></filter>
    </defs>
    <ellipse cx="240" cy="171" rx="218" ry="124" fill="url(#atlas-aura)"/>
    <g stroke="url(#atlas-floor)" strokeWidth=".7">
      <path d="m34 192 206-114 206 114-206 114L34 192Z"/><path d="m64 208 206-114M94 225 300 111M124 241 330 127M154 258 360 144M184 275 390 160M34 192 240 306M64 176 270 290M94 159 300 273M124 143 330 257M154 126 360 240M184 110 390 224M214 93 420 207"/>
    </g>
    <g stroke="#68B7D2" strokeOpacity=".55" strokeWidth="1.1"><path d="M111 94v28l71 40M367 79v39l-64 42M378 231v-19l-82-45M102 223v-16l79-44"/><path d="M239 63v41M240 216v42" strokeDasharray="3 5"/></g>
    <g stroke="#8BECEE" strokeWidth="2" filter="url(#atlas-glow)" opacity=".7"><path d="m111 122 71 40M367 118l-64 42M296 167l82 45M181 163l-79 44"/></g>
    <path d="m161 171 79-45 80 45-80 45-79-45Z" fill="#151D40" stroke="#6076CA" strokeOpacity=".4"/>
    <path d="m161 171v11l79 46 80-46v-11l-80 45-79-45Z" fill="#152745" stroke="#4F98B9" strokeOpacity=".5"/>
    <path d="m177 143 63-36 64 36-64 37-63-37Z" fill="url(#atlas-chip)" stroke="url(#atlas-top)" strokeWidth="1.5"/>
    <path d="M177 143v19l63 37 64-37v-19l-64 37-63-37Z" fill="#153147" stroke="#63C8D5" strokeOpacity=".6"/>
    <path d="m187 143 53-30 54 30-54 31-53-31Z" fill="#6ED8E4" fillOpacity=".08" stroke="#81D9E7" strokeOpacity=".25"/>
    <path d="m226 135-9 7 9 7m28-14 9 7-9 7m-11-17-6 21" stroke="#B4FFFF" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="m195 176 45 26 47-27M204 190l36 20 36-20" stroke="#76D8E4" strokeOpacity=".5"/>
    <g fill="#ADF5F1"><circle cx="177" cy="143" r="2"/><circle cx="304" cy="143" r="2"/><circle cx="240" cy="107" r="2"/><circle cx="240" cy="199" r="2"/></g>
    <g><rect x="51" y="51" width="119" height="57" rx="9" fill="#101E36" stroke="#45778C"/><rect x="51" y="51" width="119" height="57" rx="9" fill="#64D1D9" fillOpacity=".025"/><rect x="62" y="62" width="23" height="23" rx="5" fill="#224651"/><path d="M69 68h7l3 3v9H69V68Zm7 0v4h3" stroke="#91E4E5" strokeWidth="1.1"/><text x="94" y="73" fill="#B2CFDD" fontSize="11">Source</text><path d="M94 84h30m-30 6h18" stroke="#477587" strokeWidth="2" strokeLinecap="round"/></g>
    <g><rect x="316" y="32" width="112" height="59" rx="9" fill="#111D38" stroke="#4F65A8"/><rect x="327" y="44" width="23" height="23" rx="5" fill="#29365D"/><path d="m334 50-4 5 4 5m9-10 4 5-4 5m-4-11-2 13" stroke="#A8BBF8" strokeWidth="1.2" strokeLinecap="round"/><text x="359" y="55" fill="#B9CBE8" fontSize="11">Symbols</text><path d="M359 66h41m-41 6h23" stroke="#536A9B" strokeWidth="2" strokeLinecap="round"/></g>
    <g><rect x="324" y="221" width="112" height="48" rx="9" fill="#10243A" stroke="#376F8B"/><path d="M339 240h16m-16 6h10m-10-12h6" stroke="#78D1DC" strokeWidth="1.5" strokeLinecap="round"/><text x="365" y="243" fill="#9FC7D5" fontSize="10">Context</text><path d="M365 252h37" stroke="#3A687D" strokeWidth="2" strokeLinecap="round"/></g>
    <g><rect x="42" y="218" width="125" height="49" rx="9" fill="#101F32" stroke="#4C718A"/><path d="M56 234h8v8h-8v-8Zm12 12h8v8h-8v-8Zm-8-4v8h8" stroke="#86CAD6" strokeWidth="1.2"/><text x="87" y="240" fill="#A9C7D7" fontSize="10">Relationships</text><path d="M87 250h43" stroke="#4F6B83" strokeWidth="2" strokeLinecap="round"/></g>
    <g fill="#A3EBF0"><circle cx="239" cy="63" r="2.5"/><circle cx="240" cy="258" r="2.5"/><circle cx="111" cy="122" r="2"/><circle cx="367" cy="118" r="2"/></g>
  </svg></div>;
}

export default function WorkspaceOverview({ stats, repositories, reposLoading, reposError }) {
  const available = repositories.filter(hasParsedWorkspace);
  const target = available[0];
  return <section className="workspace-signal" aria-labelledby="workspace-overview-title" data-testid="workspace-overview">
    <div className="overview-beam" aria-hidden="true"/>
    <div className="overview-composition">
      <div className="overview-story"><div className="overview-kicker"><span aria-hidden="true"/>Repository intelligence</div>
        <h2 id="workspace-overview-title">Your code,<br/><span>connected.</span></h2>
        <div className="overview-file-count" data-testid="stat-files"><strong>{format(stats.files_indexed)}</strong><span>source files<br/>in your workspace</span></div>
        <div className="overview-repo-count" data-testid="stat-repos"><GitBranch width={12} height={12} aria-hidden="true"/><span><strong>{format(stats.repos_count)}</strong> {stats.repos_count === 1 ? 'repository' : 'repositories'}</span>{!reposLoading && !reposError && <><span className="overview-separator">/</span><span>{available.length} ready to explore</span></>}</div>
      </div>
      <CodeAtlas/>
      <div className="overview-graph-count"><div className="overview-graph-icon"><Network width={20} height={20} aria-hidden="true"/></div><span className="overview-graph-label">Your code graph</span><strong data-testid="stat-nodes">{format(stats.nodes)}</strong><span className="overview-graph-description">symbols &amp; files,<br/>connected through your code</span><span className="overview-graph-note">Trace the bigger picture.</span></div>
    </div>
    <div className="overview-bottom"><div className="overview-metric" data-testid="stat-edges"><GitBranch width={16} height={16} aria-hidden="true"/><div><strong>{format(stats.edges)}</strong><span>relationships</span></div></div><div className="overview-metric" data-testid="stat-chunks"><Layers width={16} height={16} aria-hidden="true"/><div><strong>{format(stats.chunks)}</strong><span>indexed chunks</span></div></div><div className="overview-metric" data-testid="stat-llm"><MessageSquare width={16} height={16} aria-hidden="true"/><div><strong>{format(stats.llm_calls)}</strong><span>AI chat answers</span></div></div><Link to={target ? `/repositories/${target.id}?tab=graph` : '/repositories'} data-testid="overview-explore" className="overview-explore">{target ? 'Explore your graph' : stats.repos_count ? 'Open repositories' : 'Import a repository'}<ArrowUpRight width={15} height={15} aria-hidden="true"/></Link></div>
  </section>;
}

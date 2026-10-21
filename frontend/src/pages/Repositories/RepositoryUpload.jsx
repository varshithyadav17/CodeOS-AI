import { useState } from "react";
import { toast } from "sonner";
import Loader2Icon from "../../assets/icons/loader-2.svg?react";
import UploadIcon from "../../assets/icons/upload.svg?react";
import FolderOpenIcon from "../../assets/icons/folder-open.svg?react";
import GithubIcon from "../../assets/icons/github.svg?react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Label } from "../../components/ui/label";
import { useWorkspace } from "../../context/WorkspaceContext";

/** The two "add a repository" forms: clone from GitHub, or upload a ZIP.
 * Both write into WorkspaceContext's repositories list. */
export default function RepositoryUpload() {
  const { addGithubRepo, uploadZipRepo } = useWorkspace();
  const [url, setUrl] = useState("");
  const [branch, setBranch] = useState("");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [file, setFile] = useState(null);

  const addGithub = async (e) => {
    e.preventDefault();
    if (!url.trim()) return;
    setBusy(true);
    try {
      await addGithubRepo(url.trim(), branch.trim(), token.trim());
      toast.success("Repository queued for ingestion");
      setUrl(""); setBranch(""); setToken("");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to add repository");
    } finally {
      setBusy(false);
    }
  };

  const uploadZip = async () => {
    if (!file) return;
    if (file.size > 200 * 1024 * 1024) { toast.error("ZIP must be 200 MB or smaller."); return; }
    setBusy(true);
    try {
      await uploadZipRepo(file);
      toast.success("ZIP uploaded — ingestion started");
      setFile(null);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <form onSubmit={addGithub} className="glass-panel border border-white/10 rounded-xl p-5" data-testid="add-github-form">
        <div className="flex items-center gap-2 mb-3">
          <GithubIcon width={18} height={18} className="text-white/70" aria-hidden="true" />
          <h2 className="text-sm font-medium tracking-tight" style={{ fontFamily: "Chivo" }}>Add from GitHub</h2>
        </div>
        <div className="space-y-3">
          <div>
            <Label htmlFor="github-url" className="text-[10px] uppercase tracking-[0.18em] mono text-white/50">Repository URL</Label>
            <Input
              id="github-url"
              data-testid="github-url-input"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://github.com/owner/repo.git"
              className="glass-panel-soft border-white/10 mono text-xs rounded-xl focus-visible:border-[#3FC8E8] focus-visible:ring-1 focus-visible:ring-[#3FC8E8] mt-1"
            />
          </div>
          <div>
            <Label htmlFor="github-branch" className="text-[10px] uppercase tracking-[0.18em] mono text-white/50">Branch (optional)</Label>
            <Input
              id="github-branch"
              data-testid="github-branch-input"
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
              placeholder="main"
              className="glass-panel-soft border-white/10 mono text-xs rounded-xl focus-visible:border-[#3FC8E8] focus-visible:ring-1 focus-visible:ring-[#3FC8E8] mt-1"
            />
          </div>
          <div>
            <Label htmlFor="github-token" className="text-[10px] uppercase mono text-white/50">Access token (private repositories only)</Label>
            <Input id="github-token" type="password" autoComplete="off" value={token} onChange={(e) => setToken(e.target.value)} placeholder="Fine-grained token with repository contents read access" className="glass-panel-soft border-white/10 mt-1 text-xs" />
          </div>
          <Button data-testid="add-github-button" type="submit" disabled={busy} className="bg-gradient-to-b from-[#52D4F0] to-[#3FC8E8] hover:brightness-105 text-black">
            {busy ? <Loader2Icon width={14} height={14} className="animate-spin" aria-hidden="true" /> : "Clone & ingest"}
          </Button>
        </div>
      </form>

      <div className="glass-panel border border-white/10 rounded-xl p-5" data-testid="upload-zip-card">
        <div className="flex items-center gap-2 mb-3">
          <UploadIcon width={16} height={16} className="text-white/70" aria-hidden="true" />
          <h2 className="text-sm font-medium tracking-tight" style={{ fontFamily: "Chivo" }}>Upload ZIP</h2>
        </div>
        <label className="block border-2 border-dashed border-white/10 hover:border-white/30 transition-colors duration-150 rounded-sm p-6 text-center cursor-pointer focus-within:border-[#3FC8E8]">
          <input
            data-testid="zip-file-input"
            type="file"
            accept=".zip"
            className="hidden"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            aria-label="Choose a ZIP file to upload"
          />
          <FolderOpenIcon width={22} height={22} className="mx-auto text-white/40 mb-2" aria-hidden="true" />
          <div className="text-xs text-white/60">{file ? file.name : "Choose a .zip up to 200 MB"}</div>
        </label>
        <Button data-testid="upload-zip-button" onClick={uploadZip} disabled={!file || busy} className="bg-gradient-to-b from-[#52D4F0] to-[#3FC8E8] hover:brightness-105 text-black mt-3">
          {busy ? <Loader2Icon width={14} height={14} className="animate-spin" aria-hidden="true" /> : "Upload & ingest"}
        </Button>
      </div>
    </div>
  );
}

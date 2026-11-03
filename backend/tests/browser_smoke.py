"""Run with frontend :5173 and tests/ui_server.py :8000 in the same environment."""
import asyncio
import io
import json
import os
import re
from pathlib import Path
import zipfile
from playwright.async_api import async_playwright, expect


GIS_TEST_SCRIPT = """
window.google = { accounts: { id: {
  initialize(config) { window.__gisConfig = config; },
  renderButton(container) {
    const button = document.createElement('button');
    button.type = 'button'; button.dataset.testid = 'google-test-button';
    button.textContent = 'Continue with Google';
    button.style.cssText = 'width:100%;padding:10px;background:white;color:black;border-radius:4px';
    button.onclick = () => window.__gisConfig.callback({ credential: JSON.stringify({
      sub: 'browser-google-subject', email: 'google-browser@gmail.com', name: 'Google Browser',
      email_verified: true, nonce: window.__gisConfig.nonce, ...window.__googleIdentity
    }) });
    container.replaceChildren(button);
  },
  disableAutoSelect() {}
} } };
"""


async def accept_dialog(dialog):
    await dialog.accept()


async def save_screenshot(page, variable):
    if path := os.getenv(variable):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        await expect(page.locator("[data-sonner-toast]")).to_have_count(0, timeout=7000)
        await page.get_by_role("heading", level=1).click()
        await page.screenshot(path=path, full_page=True, animations="disabled")


async def main():
    errors=[]
    checks=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(channel=os.getenv("CODEOS_BROWSER_CHANNEL"),executable_path=os.getenv("CODEOS_BROWSER_EXECUTABLE"),headless=True,args=["--no-sandbox"])
        browser_version=browser.version
        page=await browser.new_page(viewport={"width":1440,"height":1000})
        page.on("pageerror",lambda error:errors.append(str(error)))
        await page.route("https://accounts.google.com/gsi/client", lambda route: route.fulfill(content_type="application/javascript", body=GIS_TEST_SCRIPT))
        await page.goto("http://127.0.0.1:5173/login")
        await page.get_by_test_id("auth-mode-toggle").click()
        await page.get_by_test_id("signup-name-input").fill("Browser Tester")
        await page.get_by_test_id("auth-email-input").fill("browser@example.com")
        await page.get_by_test_id("auth-password-input").fill("browser-password-123")
        await page.get_by_test_id("auth-submit-button").click()
        await expect(page.get_by_test_id("dashboard-root")).to_be_visible(timeout=15000)
        await expect(page.get_by_role("heading", name="Dashboard", exact=True)).to_be_visible()
        await expect(page.locator("main")).not_to_contain_text("browser@example.com")
        await expect(page.locator("main")).not_to_contain_text("v1.0.0")
        await page.get_by_test_id("nav-repositories").click()
        await expect(page.get_by_role("heading", name="Repositories", exact=True)).to_be_visible()
        checks.append("Signup opens Dashboard with clean page headings and no email/version banner")
        data=io.BytesIO()
        with zipfile.ZipFile(data,"w") as archive:
            archive.writestr("auth.py","def authenticate(token):\n    return token == 'allowed'\n")
            archive.writestr("api.py","from auth import authenticate\n\ndef login(token):\n    return authenticate(token)\n")
            archive.writestr("many.py", "\n".join(f"def sample_{i}():\n    return {i}\n" for i in range(125)))
        await page.get_by_test_id("zip-file-input").set_input_files({"name":"browser-repo.zip","mimeType":"application/zip","buffer":data.getvalue()})
        await page.get_by_test_id("upload-zip-button").click()
        await expect(page.get_by_text("ready",exact=True)).to_be_visible(timeout=20000)
        await page.get_by_test_id("nav-dashboard").click()
        await expect(page.get_by_test_id("stat-repos")).to_contain_text("1")
        await expect(page.get_by_test_id("stat-files")).to_contain_text("3")
        await expect(page.get_by_text("Uploaded browser-repo", exact=True)).to_be_visible()
        await page.route("**/api/stats", lambda route: route.fulfill(status=503, content_type="application/json", body='{"detail":"Statistics temporarily unavailable"}'))
        await page.reload()
        await expect(page.get_by_test_id("dashboard-error")).to_contain_text("Statistics temporarily unavailable")
        await page.unroute("**/api/stats")
        await page.get_by_test_id("dashboard-error").get_by_role("button", name="Retry").click()
        await expect(page.get_by_test_id("stat-files")).to_contain_text("3")
        await save_screenshot(page, "CODEOS_QA_DASHBOARD_SCREENSHOT")
        await page.set_viewport_size({"width":390,"height":844})
        assert await page.locator("main").evaluate("el => el.scrollWidth <= el.clientWidth + 1"), "Mobile dashboard overflows horizontally"
        await save_screenshot(page, "CODEOS_QA_DASHBOARD_MOBILE_SCREENSHOT")
        await page.set_viewport_size({"width":1440,"height":1000})
        checks.append("Dashboard uses actual repository counts and activity, recovers from errors, and fits mobile")
        await page.get_by_test_id("dashboard-add-repo").click()
        await page.get_by_role("link",name="browser-repo",exact=True).click()
        repo_id = page.url.rsplit("/", 1)[-1]
        await expect(page.get_by_test_id("tab-files")).to_be_visible(timeout=15000)
        checks.append("ZIP upload, background ingestion, status polling")
        await page.get_by_test_id("tab-timeline").click()
        await expect(page.get_by_test_id("timeline-unavailable")).to_be_visible()
        checks.append("ZIP repository timeline explains that Git history is unavailable")
        history = [{"sha": "abc123456789", "message": "Improve authentication", "author": "Test Author", "date": "2026-10-21T10:00:00Z", "insertions": 4, "deletions": 1}]
        history.append({"sha": "boundary1234", "message": "Shallow boundary", "author": "Test Author", "date": "2026-10-20T10:00:00Z", "stats_available": False})
        timeline = {
            "commits": {"available": True, "shallow": True, "commits": history},
            "hotspots": {"items": [{"path": "auth.py", "changes": 2, "authors": 1, "insertions": 4, "deletions": 1}]},
            "contributors": {"items": [{"author": "Test Author", "email": "author@example.test", "commits": 2, "stats_available": False}]},
            "complexity": {"trend": [{"from": "2026-10-20", "to": "2026-10-21", "commits": 2, "churn": 5},
                {"from": "2026-10-19", "to": "2026-10-20", "commits": 1, "stats_available": False}]},
            "file": {"history": history},
        }
        async def timeline_response(route):
            endpoint = route.request.url.rsplit("/", 1)[-1].split("?", 1)[0]
            await route.fulfill(content_type="application/json", body=json.dumps(timeline[endpoint]))
        timeline_pattern = f"**/api/repos/{repo_id}/timeline/**"
        await page.route(timeline_pattern, lambda route: route.fulfill(status=503, content_type="application/json", body='{"detail":"History temporarily unavailable"}'))
        await page.get_by_test_id("tab-files").click()
        await page.get_by_test_id("tab-timeline").click()
        await expect(page.get_by_test_id("timeline-error")).to_contain_text("History temporarily unavailable")
        await page.unroute(timeline_pattern)
        await page.route(timeline_pattern, timeline_response)
        await page.get_by_test_id("timeline-error").get_by_role("button", name="Retry").click()
        await expect(page.get_by_test_id("timeline-scope")).to_contain_text("shallow clone")
        await expect(page.get_by_test_id("timeline-commits")).to_contain_text("Improve authentication")
        await expect(page.get_by_test_id("timeline-commits")).to_contain_text("Change counts unavailable")
        await page.get_by_role("searchbox", name="Search timeline").fill("absent")
        await expect(page.get_by_text("No matching history", exact=True)).to_be_visible()
        await page.get_by_test_id("timeline-view-contributors").click()
        await expect(page.get_by_text("author@example.test", exact=True)).to_be_visible()
        await expect(page.get_by_test_id("timeline-root")).to_contain_text("2 commits · Change counts unavailable")
        await page.get_by_test_id("timeline-view-complexity").click()
        await expect(page.get_by_test_id("timeline-churn")).to_contain_text("5 lines")
        await expect(page.get_by_test_id("timeline-churn")).to_contain_text("Churn unavailable")
        await page.get_by_test_id("timeline-view-hotspots").click()
        await page.get_by_role("button", name="auth.py", exact=True).click()
        await expect(page.get_by_label("File", exact=True)).to_have_value("auth.py")
        await expect(page.get_by_test_id("timeline-commits")).to_contain_text("Improve authentication")
        await page.get_by_role("button", name="Open current source").click()
        await expect(page.get_by_test_id("file-content-pre")).to_contain_text("def authenticate")
        await page.unroute(timeline_pattern)
        checks.append("Timeline snapshot fixture: commits, search, hotspots, contributors, churn, file history, source navigation and retry")
        await page.get_by_test_id("tab-files").click()
        await page.get_by_test_id("file-auth.py").click()
        await expect(page.get_by_test_id("file-content-pre")).to_contain_text("def authenticate",timeout=10000)
        checks.append("Archive-backed file browser")
        await page.get_by_test_id("tab-graph").click()
        await expect(page.locator(".react-flow__node").first).to_be_visible(timeout=10000)
        positions=await page.locator(".react-flow__node").evaluate_all("nodes => nodes.map(n => n.style.transform)")
        assert len(set(positions))>1,"Graph nodes overlap"
        checks.append("Graph rendering and distinct node positions")
        await page.get_by_test_id("graph-next").click()
        await expect(page.get_by_test_id("graph-page-status")).to_contain_text("Nodes 121",timeout=10000)
        await page.get_by_test_id("graph-previous").click()
        await expect(page.get_by_test_id("graph-page-status")).to_contain_text("Nodes 1–",timeout=10000)
        checks.append("Graph pagination reaches later nodes and returns to the first page")
        await page.get_by_test_id("graph-search").fill("authenticate")
        await expect(page.get_by_test_id("graph-visible-count")).to_have_text("1")
        await page.locator(".react-flow__node").first.click()
        await expect(page.get_by_test_id("graph-inspector")).to_contain_text("authenticate")
        await page.get_by_test_id("graph-focus").click()
        await expect(page.get_by_test_id("graph-focus")).to_have_attribute("aria-pressed", "true")
        assert 1 < int(await page.get_by_test_id("graph-visible-count").inner_text()) < 120
        await page.get_by_test_id("graph-layout-dependencies").click()
        await expect(page.get_by_test_id("graph-layout-dependencies")).to_have_attribute("aria-pressed", "true")
        await expect(page.locator(".react-flow__edge path[marker-end]").first).to_be_attached()
        if os.getenv("CODEOS_QA_GRAPH_SCREENSHOT"):
            await page.locator(".code-map").screenshot(path=os.environ["CODEOS_QA_GRAPH_SCREENSHOT"])
        await page.get_by_test_id("graph-open-source").click()
        await expect(page.get_by_test_id("file-content-pre")).to_contain_text("def authenticate")
        await page.get_by_test_id("tab-graph").click()
        await page.get_by_test_id("graph-node-type").select_option("file")
        await expect(page.get_by_test_id("graph-visible-count")).to_have_text("3")
        await page.get_by_test_id("graph-search").fill("no-such-symbol-unique")
        await expect(page.get_by_test_id("graph-reset")).to_be_visible()
        await page.get_by_test_id("graph-reset").click()
        await expect(page.get_by_test_id("graph-visible-count")).to_have_text("120")
        checks.append("Graph search, symbol filters, connection focus, directional layout, inspector, source navigation and empty-state reset")

        await page.get_by_test_id("tab-chat").click()
        await page.get_by_test_id("chat-input").fill("Where is authentication handled and what calls it?")
        await page.get_by_test_id("chat-send-button").click()
        await expect(page.get_by_test_id("chat-evidence")).to_be_visible(timeout=15000)
        await expect(page.get_by_test_id("chat-relationships")).to_be_visible()
        checks.append("Chat response with source evidence and graph relationships")
        if os.getenv("CODEOS_QA_SCREENSHOT"):
            await page.screenshot(path=os.environ["CODEOS_QA_SCREENSHOT"],full_page=True)
        await page.get_by_test_id("chat-evidence").locator("summary").first.click()
        await page.get_by_role("button",name="Open source file").first.click()
        await expect(page.get_by_test_id("file-content-pre")).to_contain_text("def ",timeout=10000)
        checks.append("Evidence opens the matching source file")
        await page.get_by_test_id("workspace-reingest").click()
        await expect(page.get_by_test_id("workspace-repo-status")).to_have_text("ready",timeout=20000)
        checks.append("Re-ingestion refreshes the active workspace")
        await page.get_by_test_id("tab-arch").click()
        await expect(page.get_by_test_id("arch-graph")).to_be_visible(timeout=10000)
        await page.get_by_test_id("arch-view-dependency").click()
        await expect(page.get_by_test_id("arch-graph").locator(".react-flow__node").first).to_be_visible(timeout=10000)
        checks.append("Architecture and dependency views render")
        await page.get_by_test_id("tab-docs").click()
        await expect(page.get_by_test_id("docs-empty")).to_be_visible()
        await page.get_by_test_id("docs-generate").click()
        await expect(page.get_by_test_id("docs-content")).to_contain_text("Authentication", timeout=15000)
        await page.get_by_test_id("docs-generate").click()
        await expect(page.get_by_test_id("docs-generate")).to_have_text("Regenerate draft")
        await expect(page.get_by_test_id("docs-export")).to_have_text("Export all (1)")
        async with page.expect_download() as download_info:
            await page.get_by_test_id("docs-export").click()
        download = await download_info.value
        with zipfile.ZipFile(await download.path()) as archive:
            assert len(archive.namelist()) == 1
            assert b"Authentication" in archive.read(archive.namelist()[0])
        checks.append("Documentation generation, regeneration and ZIP export")
        await page.reload()
        await page.get_by_test_id("tab-docs").click()
        await expect(page.get_by_test_id("docs-content")).to_contain_text("Authentication")
        if os.getenv("CODEOS_QA_DOCS_SCREENSHOT"):
            await page.screenshot(path=os.environ["CODEOS_QA_DOCS_SCREENSHOT"], full_page=True)
        checks.append("Saved documentation survives a page reload")
        await page.get_by_test_id("tab-review").click()
        await page.get_by_test_id("run-review-button").click()
        await expect(page.get_by_test_id("review-status")).to_have_text("done",timeout=20000)
        await expect(page.get_by_test_id("review-summary")).to_contain_text("Review complete")
        await expect(page.locator('[data-testid^="agent-card-"]')).to_have_count(6)
        checks.append("Background code review completes with all six specialist reports")
        await page.get_by_test_id("review-import-memory").click()
        await expect(page.get_by_test_id("review-import-memory")).to_contain_text("Saved to Memory")
        other_response = await page.request.post("http://127.0.0.1:5173/api/repos/upload", multipart={"file": {"name": "other-project.zip", "mimeType": "application/zip", "buffer": data.getvalue()}})
        assert other_response.status == 202
        other_repo = (await other_response.json())["id"]
        other_note = await page.request.post("http://127.0.0.1:5173/api/memory", data={"repo_id": other_repo, "category": "decision", "title": "Different project decision", "description": "Keep this decision in its own project.", "severity": "info"})
        assert other_note.status == 200
        await page.get_by_test_id("workspace-memory").click()
        await expect(page.get_by_test_id("memory-filter-repo")).to_have_value(repo_id)
        await expect(page.get_by_test_id("memory-grid").locator("button")).to_have_count(6,timeout=10000)
        await page.get_by_test_id("memory-filter-repo").select_option("")
        await expect(page.get_by_test_id("memory-grid").locator("button")).to_have_count(7)
        await page.get_by_test_id("memory-filter-repo").select_option(other_repo)
        await expect(page.get_by_test_id("memory-grid").locator("button")).to_have_count(1)
        await expect(page.get_by_text("Different project decision", exact=True)).to_be_visible()
        await page.get_by_test_id("memory-filter-repo").select_option(repo_id)
        await expect(page.get_by_test_id("memory-grid").locator("button")).to_have_count(6)
        await page.get_by_test_id("memory-grid").locator("button").first.click()
        await expect(page.get_by_test_id("memory-recommendation")).to_contain_text("Test expired and malformed tokens")
        if path := os.getenv("CODEOS_QA_MEMORY_DETAIL_SCREENSHOT"):
            await page.get_by_role("dialog").screenshot(path=path, animations="disabled")
        await page.keyboard.press("Escape")
        await page.get_by_test_id("nav-dashboard").click()
        await page.locator(".dashboard-findings-list a").first.click()
        await expect(page.get_by_test_id("memory-drawer")).to_be_visible()
        await expect(page.get_by_test_id("memory-filter-repo")).to_have_value(repo_id)
        await expect(page.get_by_test_id("memory-recommendation")).to_be_visible()
        await page.keyboard.press("Escape")
        checks.append("Dashboard finding links open the matching project and memory detail")
        checks.append("Repository memory scopes exclude other projects and retain original review recommendations")
        await page.get_by_test_id("memory-filter-category").select_option("architecture")
        await expect(page.get_by_test_id("memory-grid").locator("button")).to_have_count(1)
        await page.get_by_test_id("memory-filter-category").select_option("")
        checks.append("Review findings persist without duplicates and support category filters")
        await page.get_by_test_id("memory-new-button").click()
        await expect(page.get_by_test_id("memory-create-repo")).to_have_value(repo_id)
        await page.get_by_test_id("memory-create-title").fill("Browser token note")
        await page.get_by_test_id("memory-create-description").fill("Follow up on token validation.")
        await page.get_by_test_id("memory-create-filepath").fill("auth.py")
        await page.get_by_test_id("memory-create-submit").click()
        await expect(page.get_by_test_id("memory-create-modal")).not_to_be_visible()
        await page.get_by_test_id("memory-search").fill("token")
        await page.get_by_test_id("memory-filter-category").select_option("note")
        await expect(page.get_by_test_id("memory-grid").locator("button")).to_have_count(1)
        quick_status = page.get_by_test_id("memory-grid").locator("select")
        await quick_status.select_option("in_progress")
        await expect(quick_status).to_have_value("in_progress")
        await expect(page.get_by_test_id("memory-stat-in_progress")).to_contain_text("1")
        await page.get_by_text("Browser token note",exact=True).click()
        await page.get_by_test_id("memory-status-resolved").click()
        await expect(page.get_by_test_id("memory-status-resolved")).to_have_attribute("aria-pressed","true")
        await page.keyboard.press("Escape")
        await expect(page.get_by_test_id("memory-stat-resolved")).to_contain_text("1")
        await page.get_by_test_id("memory-filter-status").select_option("open")
        await expect(page.get_by_test_id("memory-empty")).to_be_visible()
        await page.get_by_test_id("memory-filter-status").select_option("resolved")
        await expect(page.get_by_text("Browser token note",exact=True)).to_be_visible()
        checks.append("Project-aware memory creation, combined filters, quick status changes, and counts")
        await page.get_by_test_id("memory-filter-status").select_option("")
        await page.get_by_test_id("memory-filter-category").select_option("")
        await page.get_by_test_id("memory-search").fill("")
        await expect(page.get_by_test_id("memory-grid").locator("button")).to_have_count(7)
        await save_screenshot(page, "CODEOS_QA_MEMORY_SCREENSHOT")
        await page.set_viewport_size({"width":390,"height":844})
        assert await page.locator("main").evaluate("el => el.scrollWidth <= el.clientWidth + 1"), "Mobile memory overflows horizontally"
        await save_screenshot(page, "CODEOS_QA_MEMORY_MOBILE_SCREENSHOT")
        await page.set_viewport_size({"width":1440,"height":1000})
        ai_requests = []
        page.on("request", lambda request: ai_requests.append(request.url) if request.method == "POST" and "/chat" in request.url else None)
        await page.get_by_text("Browser token note", exact=True).click()
        await page.get_by_test_id("memory-check-ai").click()
        await expect(page.get_by_test_id("chat-input")).to_have_value(re.compile("Browser token note"))
        await expect(page.get_by_test_id("chat-input")).to_have_value(re.compile("Follow up on token validation"))
        assert "Follow" not in page.url and "memoryContext" not in page.url
        assert not ai_requests, "Checking a saved finding must only open a draft, not send automatically"
        await page.get_by_test_id("workspace-memory").click()
        await expect(page.get_by_test_id("memory-filter-repo")).to_have_value(repo_id)
        checks.append("Memory fits mobile and Check with AI opens a project-bound draft without sending")
        await page.get_by_text("Browser token note",exact=True).click()
        await page.get_by_test_id("memory-open-workspace").click()
        await page.get_by_test_id("tab-files").click()
        await expect(page.get_by_test_id("file-content-pre")).to_contain_text("def authenticate",timeout=10000)
        checks.append("Saved finding opens its repository and source file")
        deleted_other = await page.request.delete(f"http://127.0.0.1:5173/api/repos/{other_repo}")
        assert deleted_other.status == 202
        for _ in range(40):
            if (await page.request.get(f"http://127.0.0.1:5173/api/repos/{other_repo}")).status == 404:
                break
            await asyncio.sleep(.1)
        else:
            raise AssertionError("Other project fixture was not deleted")
        await page.reload()
        await expect(page.get_by_test_id("repo-detail-root")).to_be_visible(timeout=15000)
        checks.append("HttpOnly session survives a page reload")
        await page.get_by_test_id("nav-repositories").click()
        await page.set_viewport_size({"width":390,"height":844})
        await expect(page.get_by_test_id("upload-zip-button")).to_be_visible()
        assert await page.locator("main").evaluate("el => el.scrollWidth <= el.clientWidth + 1"), "Mobile page overflows horizontally"
        checks.append("Mobile repository controls and navigation fit the viewport")
        await page.set_viewport_size({"width":1440,"height":1000})
        page.once("dialog",accept_dialog)
        await page.get_by_test_id(f"repo-delete-{repo_id}").click()
        await expect(page.get_by_test_id(f"repo-item-{repo_id}")).not_to_be_visible(timeout=20000)
        await page.get_by_test_id("nav-memory").click()
        await expect(page.get_by_test_id("memory-empty")).to_be_visible(timeout=10000)
        checks.append("Repository deletion completes and removes related saved findings")
        await page.get_by_test_id("nav-repositories").click()
        paused_zip = io.BytesIO()
        with zipfile.ZipFile(paused_zip, "w") as archive:
            archive.writestr("pause.py", "# CODEOS_QUOTA_TEST\ndef paused_example():\n    return 1\n")
        await page.get_by_test_id("zip-file-input").set_input_files({"name": "quota-paused.zip", "mimeType": "application/zip", "buffer": paused_zip.getvalue()})
        await page.get_by_test_id("upload-zip-button").click()
        await expect(page.get_by_text("AI indexing paused", exact=True)).to_be_visible(timeout=20000)
        await page.get_by_role("link", name="quota-paused", exact=True).click()
        paused_id = page.url.rsplit("/", 1)[-1]
        await expect(page.get_by_test_id("knowledge-graph")).to_be_visible()
        await expect(page.get_by_test_id("workspace-reingest")).to_be_disabled()
        await page.get_by_test_id("tab-files").click()
        await page.get_by_test_id("file-pause.py").click()
        await expect(page.get_by_test_id("file-content-pre")).to_contain_text("paused_example")
        await page.get_by_test_id("tab-chat").click()
        await expect(page.get_by_test_id("ai-indexing-notice")).to_contain_text("resume automatically")
        await page.get_by_test_id("tab-arch").click()
        await expect(page.get_by_test_id("arch-graph").locator(".react-flow__node").first).to_be_visible()
        await page.get_by_test_id("tab-graph").click()
        await page.set_viewport_size({"width":390,"height":844})
        if os.getenv("CODEOS_QA_GRAPH_MOBILE_SCREENSHOT"):
            await expect(page.get_by_test_id("tab-graph")).to_have_attribute("data-state", "active")
            await page.get_by_test_id("knowledge-graph").screenshot(path=os.environ["CODEOS_QA_GRAPH_MOBILE_SCREENSHOT"], animations="disabled")
        overflow = await page.locator("main").evaluate("""el => ({width:el.clientWidth, scroll:el.scrollWidth,
          outside:[...el.querySelectorAll('*')].filter(n=>{const r=n.getBoundingClientRect();return r.right>innerWidth+1 && r.width>0 && !n.closest('.react-flow')}).slice(0,12).map(n=>({tag:n.tagName,cls:n.className,width:n.getBoundingClientRect().width}))})""")
        assert overflow['scroll'] <= overflow['width'] + 1, f"Mobile graph overflows horizontally: {overflow}"
        await page.set_viewport_size({"width":1440,"height":1000})
        await page.get_by_test_id("nav-repositories").click()
        page.once("dialog", accept_dialog)
        await page.get_by_test_id(f"repo-delete-{paused_id}").click()
        await expect(page.get_by_test_id(f"repo-item-{paused_id}")).not_to_be_visible(timeout=20000)
        checks.append("Quota-paused import retains graph, source and architecture; AI notice, mobile map, and safe deletion work")

        await page.get_by_test_id("logout-button").click()
        await expect(page.get_by_test_id("auth-form")).to_be_visible(timeout=15000)
        checks.append("Logout clears session and workspace")
        await page.get_by_test_id("auth-email-input").fill("browser@example.com")
        await page.get_by_test_id("auth-password-input").fill("browser-password-123")
        await page.get_by_test_id("auth-submit-button").click()
        await expect(page.get_by_test_id("dashboard-root")).to_be_visible(timeout=15000)
        checks.append("Existing account signs back into Dashboard after logout")
        await page.route("**/api/auth/logout", lambda route: route.fulfill(status=503, content_type="application/json", body='{"detail":"Temporary outage"}'))
        await page.get_by_test_id("logout-button").click()
        await expect(page.get_by_text("Sign out failed. Your session is still active. Please try again.")).to_be_visible()
        await expect(page.get_by_test_id("dashboard-root")).to_be_visible()
        await page.unroute("**/api/auth/logout")
        checks.append("Failed logout keeps the session visible and offers recovery")
        await page.get_by_test_id("logout-button").click()
        await page.get_by_test_id("google-test-button").click()
        await expect(page.get_by_test_id("user-name")).to_have_text("Google Browser")
        google_user = (await (await page.request.get("http://127.0.0.1:5173/api/auth/me")).json())["user"]["id"]
        checks.append("Google callback exchanges a browser-bound credential for a session")
        await page.get_by_test_id("logout-button").click()
        await page.get_by_test_id("google-test-button").click()
        await expect(page.get_by_test_id("user-name")).to_have_text("Google Browser")
        assert (await (await page.request.get("http://127.0.0.1:5173/api/auth/me")).json())["user"]["id"] == google_user
        checks.append("Google sign-in works again after logout without a page reload")
        await page.get_by_test_id("logout-button").click()
        await page.evaluate("window.__googleIdentity = { email: 'browser@example.com', sub: 'linked-local-subject' }")
        await page.get_by_test_id("google-test-button").click()
        await expect(page.get_by_test_id("google-link-form")).to_be_visible()
        await page.get_by_label("CodeOS password", exact=True).fill("wrong")
        await page.get_by_role("button", name="Connect Google and sign in").click()
        await expect(page.get_by_role("alert")).to_contain_text("Incorrect CodeOS password")
        await page.get_by_label("CodeOS password", exact=True).fill("browser-password-123")
        await page.get_by_role("button", name="Connect Google and sign in").click()
        await expect(page.get_by_test_id("user-name")).to_have_text("Browser Tester")
        checks.append("Existing local account links Google only after a correct password")
        await page.get_by_test_id("logout-button").click()
        await page.evaluate("window.__googleIdentity = { nonce: 'wrong-browser' }")
        await page.get_by_test_id("google-test-button").click()
        await expect(page.get_by_role("alert")).to_contain_text("does not match this browser")
        await page.get_by_role("button", name="Refresh Google sign-in").click()
        await expect(page.get_by_role("alert")).not_to_be_visible()
        checks.append("A mismatched Google nonce is rejected with a refresh action")
        await page.set_viewport_size({"width":390,"height":844})
        assert await page.locator("body").evaluate("el => el.scrollWidth <= window.innerWidth + 1"), "Mobile login overflows"
        if os.getenv("CODEOS_QA_LOGIN_SCREENSHOT"):
            await page.screenshot(path=os.environ["CODEOS_QA_LOGIN_SCREENSHOT"], full_page=True)
        checks.append("Mobile login and Google sign-in fit the viewport")
        blocked = await browser.new_page()
        await blocked.route("https://accounts.google.com/gsi/client", lambda route: route.abort())
        await blocked.goto("http://127.0.0.1:5173/login")
        await expect(blocked.get_by_role("alert")).to_contain_text("could not load", timeout=20000)
        await expect(blocked.get_by_test_id("auth-submit-button")).to_be_enabled()
        await expect(blocked.get_by_test_id("google-unavailable-button")).to_be_disabled()
        await blocked.close()
        checks.append("Blocked Google script shows recovery while email sign-in remains usable")
        recovering = await browser.new_page()
        recovering.on("pageerror", lambda error: errors.append(str(error)))
        await recovering.route("https://accounts.google.com/gsi/client", lambda route: route.fulfill(content_type="application/javascript", body=GIS_TEST_SCRIPT))
        calls = 0
        async def once_limited(route):
            nonlocal calls
            calls += 1
            if calls == 1:
                await route.fulfill(status=429, headers={"Retry-After": "1"}, content_type="application/json", body='{"detail":"Too many requests"}')
            else:
                await route.continue_()
        await recovering.route("**/api/auth/google/challenge", once_limited)
        await recovering.goto("http://127.0.0.1:5173/login")
        await expect(recovering.get_by_test_id("google-test-button")).to_be_visible(timeout=15000)
        assert calls == 2
        await expect(recovering.get_by_role("alert")).not_to_be_visible()
        await recovering.close()
        checks.append("Google setup recovers automatically after a short HTTP 429 without a reload")
        throttled = await browser.new_page()
        throttled.on("pageerror", lambda error: errors.append(str(error)))
        await throttled.clock.install()
        await throttled.route("https://accounts.google.com/gsi/client", lambda route: route.fulfill(content_type="application/javascript", body=GIS_TEST_SCRIPT))
        await throttled.route("**/api/auth/google/challenge", lambda route: route.fulfill(status=429, headers={"Retry-After": "30"}, content_type="application/json", body='{"detail":"Too many requests"}'))
        await throttled.goto("http://127.0.0.1:5173/login")
        await expect(throttled.get_by_role("alert")).to_contain_text("temporarily rate-limited")
        await expect(throttled.get_by_test_id("google-refresh")).to_be_disabled()
        await expect(throttled.get_by_test_id("auth-submit-button")).to_be_enabled()
        await throttled.clock.fast_forward(31000)
        await expect(throttled.get_by_test_id("google-refresh")).to_be_enabled()
        await throttled.unroute("**/api/auth/google/challenge")
        await throttled.get_by_test_id("google-refresh").click()
        await expect(throttled.get_by_test_id("google-test-button")).to_be_visible(timeout=15000)
        await throttled.close()
        checks.append("Google rate-limit countdown respects Retry-After, prevents repeated refreshes and preserves email sign-in")
        unconfigured = await browser.new_page()
        await unconfigured.route("**/api/auth/google/challenge", lambda route: route.fulfill(content_type="application/json", body='{"enabled":false}'))
        await unconfigured.goto("http://127.0.0.1:5173/login")
        await expect(unconfigured.get_by_test_id("google-unavailable-button")).to_be_visible()
        await expect(unconfigured.get_by_test_id("google-unavailable-button")).to_be_disabled()
        await expect(unconfigured.get_by_test_id("auth-submit-button")).to_be_enabled()
        await unconfigured.close()
        checks.append("Missing Google configuration keeps the Google option visible and email login enabled")
        assert not errors,errors
        await browser.close()
    report={"status":"passed","checks":checks,"uncaught_browser_errors":errors,"browser_channel":os.getenv("CODEOS_BROWSER_CHANNEL") or "chromium","browser_version":browser_version,"providers":"SQLite, in-memory graph, real Qdrant local, deterministic embeddings and AI stub; GIS JavaScript and Google verifier stubs; populated Timeline views use explicit HTTP fixtures"}
    if os.getenv("CODEOS_BROWSER_REPORT"):
        Path(os.environ["CODEOS_BROWSER_REPORT"]).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    asyncio.run(main())

"""Run with frontend :5173 and tests/ui_server.py :8000 in the same environment."""
import asyncio
import io
import json
import os
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


async def main():
    errors=[]
    checks=[]
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,args=["--no-sandbox"])
        page=await browser.new_page(viewport={"width":1440,"height":1000})
        page.on("pageerror",lambda error:errors.append(str(error)))
        await page.route("https://accounts.google.com/gsi/client", lambda route: route.fulfill(content_type="application/javascript", body=GIS_TEST_SCRIPT))
        await page.goto("http://127.0.0.1:5173/login")
        await page.get_by_test_id("auth-mode-toggle").click()
        await page.get_by_test_id("signup-name-input").fill("Browser Tester")
        await page.get_by_test_id("auth-email-input").fill("browser@example.com")
        await page.get_by_test_id("auth-password-input").fill("browser-password-123")
        await page.get_by_test_id("auth-submit-button").click()
        await expect(page.get_by_test_id("repos-root")).to_be_visible(timeout=15000)
        checks.append("Signup and authenticated navigation")
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
        checks.append("Dashboard uses actual repository counts and activity, with error recovery")
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
        await page.get_by_test_id("nav-memory").click()
        await expect(page.get_by_test_id("memory-grid").locator("button")).to_have_count(6,timeout=10000)
        await page.get_by_test_id("memory-filter-category").select_option("architecture")
        await expect(page.get_by_test_id("memory-grid").locator("button")).to_have_count(1)
        await page.get_by_test_id("memory-filter-category").select_option("")
        checks.append("Review findings persist without duplicates and support category filters")
        await page.get_by_test_id("memory-new-button").click()
        await page.get_by_test_id("memory-create-title").fill("Browser token note")
        await page.get_by_test_id("memory-create-description").fill("Follow up on token validation.")
        await page.get_by_test_id("memory-create-filepath").fill("auth.py")
        await page.get_by_test_id("memory-create-submit").click()
        await expect(page.get_by_test_id("memory-create-modal")).not_to_be_visible()
        await page.get_by_test_id("memory-search").fill("token")
        await page.get_by_test_id("memory-filter-category").select_option("note")
        await expect(page.get_by_test_id("memory-grid").locator("button")).to_have_count(1)
        await page.get_by_text("Browser token note",exact=True).click()
        await page.get_by_test_id("memory-status-resolved").click()
        await expect(page.get_by_test_id("memory-status-resolved")).to_have_attribute("aria-pressed","true")
        await page.keyboard.press("Escape")
        await expect(page.get_by_test_id("memory-stat-resolved")).to_contain_text("1")
        await page.get_by_test_id("memory-filter-status").select_option("open")
        await expect(page.get_by_test_id("memory-empty")).to_be_visible()
        await page.get_by_test_id("memory-filter-status").select_option("resolved")
        await expect(page.get_by_text("Browser token note",exact=True)).to_be_visible()
        checks.append("Memory creation, combined search filters, status changes, and counts")
        await page.get_by_text("Browser token note",exact=True).click()
        await page.get_by_test_id("memory-open-workspace").click()
        await page.get_by_test_id("tab-files").click()
        await expect(page.get_by_test_id("file-content-pre")).to_contain_text("def authenticate",timeout=10000)
        checks.append("Saved finding opens its repository and source file")
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
        await page.get_by_test_id("logout-button").click()
        await expect(page.get_by_test_id("auth-form")).to_be_visible(timeout=15000)
        checks.append("Logout clears session and workspace")
        await page.get_by_test_id("auth-email-input").fill("browser@example.com")
        await page.get_by_test_id("auth-password-input").fill("browser-password-123")
        await page.get_by_test_id("auth-submit-button").click()
        await expect(page.get_by_test_id("repos-empty")).to_be_visible(timeout=15000)
        checks.append("Existing account signs back in after logout")
        await page.route("**/api/auth/logout", lambda route: route.fulfill(status=503, content_type="application/json", body='{"detail":"Temporary outage"}'))
        await page.get_by_test_id("logout-button").click()
        await expect(page.get_by_text("Sign out failed. Your session is still active. Please try again.")).to_be_visible()
        await expect(page.get_by_test_id("repos-root")).to_be_visible()
        await page.unroute("**/api/auth/logout")
        checks.append("Failed logout keeps the session visible and offers recovery")
        await page.get_by_test_id("logout-button").click()
        await page.get_by_test_id("google-test-button").click()
        await expect(page.get_by_test_id("user-email")).to_have_text("google-browser@gmail.com")
        google_user = (await (await page.request.get("http://127.0.0.1:5173/api/auth/me")).json())["user"]["id"]
        checks.append("Google callback exchanges a browser-bound credential for a session")
        await page.get_by_test_id("logout-button").click()
        await page.get_by_test_id("google-test-button").click()
        await expect(page.get_by_test_id("user-email")).to_have_text("google-browser@gmail.com")
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
        await expect(page.get_by_test_id("user-email")).to_have_text("browser@example.com")
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
    report={"status":"passed","checks":checks,"uncaught_browser_errors":errors,"providers":"SQLite, in-memory graph, real Qdrant local, deterministic embeddings and AI stub; GIS JavaScript and Google verifier stubs; populated Timeline views use explicit HTTP fixtures"}
    if os.getenv("CODEOS_BROWSER_REPORT"):
        Path(os.environ["CODEOS_BROWSER_REPORT"]).write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report,indent=2))


if __name__=="__main__":
    asyncio.run(main())

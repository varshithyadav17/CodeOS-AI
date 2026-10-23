"""Opt-in live UI smoke test. Creates and deletes only its own QA repository."""
import asyncio
import io
import json
import re
import secrets
import uuid
import zipfile
from pathlib import Path
from playwright.async_api import async_playwright, expect
ORIGIN = 'https://codeos-ai-two.vercel.app'
QA = Path('qa')
QA.mkdir(exist_ok=True)


async def main():
    email = 'codeos-ui-' + uuid.uuid4().hex[:12] + '@example.com'
    password = secrets.token_urlsafe(28)
    checks, errors, auth_http = [], [], []
    repo_id = None
    report = {'origin': ORIGIN, 'providers': 'actual production API and stores; no substituted responses'}
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel='chrome', headless=True, args=['--no-sandbox'])
        page = await browser.new_page(viewport={'width': 1440, 'height': 1000})
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('response', lambda r: auth_http.append({'path': r.url.split('/api')[-1], 'status': r.status})
                if '/api/auth/' in r.url else None)
        def record(name):
            checks.append(name)
            print('PASS ' + name, flush=True)
        try:
            await page.goto(ORIGIN + '/login', wait_until='domcontentloaded', timeout=60000)
            await page.get_by_test_id('auth-mode-toggle').click()
            await page.get_by_test_id('signup-name-input').fill('Production UI QA')
            await page.get_by_test_id('auth-email-input').fill(email)
            await page.get_by_test_id('auth-password-input').fill(password)
            await page.get_by_test_id('auth-submit-button').click()
            await expect(page.get_by_test_id('repos-root')).to_be_visible(timeout=120000)
            record('Production signup and authenticated browser navigation')
            source = io.BytesIO()
            with zipfile.ZipFile(source, 'w') as z:
                z.writestr('auth.py', 'def authenticate(token):\n    return token == "allowed"\n')
                z.writestr('api.py', 'from auth import authenticate\n\ndef login(token):\n    return authenticate(token)\n')
                z.writestr('README.md', '# Production UI verification\n')
            await page.get_by_test_id('zip-file-input').set_input_files({'name': 'production-ui-qa.zip', 'mimeType': 'application/zip', 'buffer': source.getvalue()})
            await page.get_by_test_id('upload-zip-button').click()
            await expect(page.get_by_text('ready', exact=True)).to_be_visible(timeout=180000)
            await page.get_by_role('link', name='production-ui-qa', exact=True).click()
            await expect(page).to_have_url(re.compile(r'/repositories/[0-9a-f-]+$'))
            repo_id = page.url.rsplit('/', 1)[-1]
            await page.get_by_test_id('tab-graph').click()
            await expect(page.get_by_role('heading', name='Code map', exact=True)).to_be_visible(timeout=60000)
            record('Real ZIP ingestion and deployed code map')
            await page.get_by_test_id('graph-search').fill('authenticate')
            await expect(page.get_by_test_id('graph-visible-count')).to_have_text('1')
            await page.locator('.react-flow__node').first.click()
            await expect(page.get_by_test_id('graph-inspector')).to_contain_text('authenticate')
            await page.get_by_test_id('graph-focus').click()
            await page.get_by_test_id('graph-layout-dependencies').click()
            await expect(page.get_by_test_id('graph-visible-count')).to_have_text('3')
            await page.locator('.code-map').screenshot(path=str(QA / 'production-graph.png'), animations='disabled')
            record('Graph search, inspector, connection focus and directional layout')
            await page.get_by_test_id('graph-open-source').click()
            await expect(page.get_by_test_id('file-content-pre')).to_contain_text('def authenticate', timeout=60000)
            await page.get_by_test_id('tab-arch').click()
            await page.get_by_test_id('arch-view-dependency').click()
            await expect(page.get_by_test_id('arch-graph').locator('.react-flow__node').first).to_be_visible(timeout=60000)
            record('Source navigation and Neo4j architecture view')
            await page.get_by_test_id('tab-graph').click()
            await page.set_viewport_size({'width': 390, 'height': 844})
            await expect(page.get_by_test_id('knowledge-graph')).to_be_visible()
            assert await page.locator('main').evaluate('el => el.scrollWidth <= el.clientWidth + 1')
            await page.get_by_test_id('knowledge-graph').screenshot(path=str(QA / 'production-graph-mobile.png'), animations='disabled')
            record('Production mobile graph fits viewport')
            await page.reload(wait_until='domcontentloaded')
            await expect(page.get_by_test_id('repo-detail-root')).to_be_visible(timeout=60000)
            record('Production cookie session survives reload')
            await page.set_viewport_size({'width': 1440, 'height': 1000})
            await page.get_by_test_id('nav-repositories').click()
            page.once('dialog', lambda dialog: dialog.accept())
            await page.get_by_test_id('repo-delete-' + repo_id).click()
            await expect(page.get_by_test_id('repo-item-' + repo_id)).not_to_be_visible(timeout=60000)
            record('Tracked repository deletion through production UI')
            await page.get_by_test_id('logout-button').click()
            await expect(page.get_by_test_id('auth-form')).to_be_visible(timeout=60000)
            await page.get_by_test_id('auth-email-input').fill(email)
            await page.get_by_test_id('auth-password-input').fill(password)
            await page.get_by_test_id('auth-submit-button').click()
            await expect(page.get_by_test_id('repos-root')).to_be_visible(timeout=120000)
            record('Production logout and email sign-in again')
            assert not errors, errors
            report['status'] = 'passed'
        except Exception as exc:
            report.update(status='failed', error=str(exc).split('Call log:')[0][:700])
            await page.screenshot(path=str(QA / 'production-ui-failure.png'), full_page=True)
            raise
        finally:
            # This account and repository are generated inside the test; no
            # existing user credentials, repositories or sessions are used.
            session = await page.request.post(ORIGIN + '/api/auth/login', data={'email': email, 'password': password})
            if session.ok:
                if not repo_id:
                    owned = await page.request.get(ORIGIN + '/api/repos')
                    if owned.ok:
                        repo_id = next((r['id'] for r in await owned.json() if r['name'] == 'production-ui-qa'), None)
                if repo_id:
                    await page.request.delete(ORIGIN + '/api/repos/' + repo_id)
                    for _ in range(30):
                        response = await page.request.get(ORIGIN + '/api/repos/' + repo_id)
                        if response.status == 404:
                            report['qa_repository_deleted'] = True
                            break
                        await asyncio.sleep(2)
            await page.request.post(ORIGIN + '/api/auth/logout')
            report.update(checks=checks, uncaught_errors=errors, auth_http=auth_http,
                          personal_google_consent='not_attempted', browser=browser.version)
            (QA / 'production-ui-report.json').write_text(json.dumps(report, indent=2))
            print(json.dumps(report, indent=2))
            await browser.close()


asyncio.run(main())

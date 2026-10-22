"""Inspect the public login and real Google button without signing into an account.

No browser routes or Google responses are substituted. This check is optional
in CI because external Google/Vercel availability must not block API releases.
"""
import asyncio
import json
import os
import re

from playwright.async_api import async_playwright


ORIGIN = "https://codeos-ai-two.vercel.app"


async def main():
    report = {"origin": ORIGIN, "personal_google_consent": "not_attempted"}
    errors = []
    google_errors = []
    button_responses = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            channel=os.getenv("CODEOS_BROWSER_CHANNEL", "chrome"), headless=True,
            args=["--no-sandbox"],
        )
        report["browser"] = browser.version
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: google_errors.append(message.text)
                if "GSI_LOGGER" in message.text and re.search(
                    r"not allowed|invalid_client|client.*not found|origin_mismatch", message.text, re.I
                ) else None)
        page.on("response", lambda response: button_responses.append(response.status)
                if response.url.startswith("https://accounts.google.com/gsi/button?") else None)
        try:
            # Vercel may still be promoting the main-branch build when CI starts.
            for attempt in range(12):
                response = await page.goto(ORIGIN + "/login", wait_until="domcontentloaded", timeout=60000)
                if await page.get_by_test_id("google-official-button").count():
                    break
                if attempt == 11:
                    raise RuntimeError("The current public frontend has not appeared")
                await asyncio.sleep(5)
            report["login_http"] = response.status
            await page.get_by_test_id("auth-submit-button").wait_for(state="visible")
            challenge = await page.request.get(ORIGIN + "/api/auth/google/challenge", timeout=60000)
            config = await challenge.json()
            report["challenge_http"] = challenge.status
            report["google_enabled"] = bool(config.get("enabled"))
            report["client_id_valid"] = bool(re.fullmatch(
                r"[0-9]+-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com", config.get("client_id", "")
            ))
            official = page.get_by_test_id("google-official-button")
            await official.locator('iframe[src^="https://accounts.google.com/gsi/"]').first.wait_for(
                state="visible", timeout=45000
            )
            await asyncio.sleep(2)
            report["real_google_iframe_visible"] = True
            report["google_button_http"] = button_responses
            report["google_origin_errors"] = len(google_errors)
            report["uncaught_errors"] = len(errors)
            report["passed"] = (
                response.status == 200 and challenge.status == 200
                and report["google_enabled"] and report["client_id_valid"]
                and 200 in button_responses and not google_errors and not errors
            )
        except Exception as exc:
            report["passed"] = False
            report["error"] = str(exc).split("Call log:")[0][:500]
        finally:
            await browser.close()
    print(json.dumps(report, indent=2))
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as output:
            output.write("### Public login diagnostic\n\n```json\n" + json.dumps(report, indent=2) + "\n```\n")
    raise SystemExit(0 if report.get("passed") else 1)


if __name__ == "__main__":
    asyncio.run(main())

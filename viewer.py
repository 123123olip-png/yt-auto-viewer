import os
import random
import time
import urllib.request
import json

from playwright.sync_api import sync_playwright

# --- CONFIG ---------------------------------------------------------------
VIDEOS = [
    "https://www.youtube.com/shorts/Jei2QU2evXg",
]
ROUNDS = 3
MIN_WATCH = 40
MAX_WATCH = 95
NOTIFY_TELEGRAM = True
BOT_TOKEN = "8770717900:AAH6-btNwFmEpu5RvCJ2iVAyFBbmEIyAAvo"
CHAT_ID = "8887654380"
# --------------------------------------------------------------------------

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

VIEWPORTS = [(1280, 720), (1366, 768), (1440, 900), (1920, 1080)]

results = []


def dismiss_consent(page):
    """US datacenter IPs sometimes get a cookie consent wall."""
    for label in ("Accept all", "Reject all", "Accept"):
        try:
            page.click(f'button:has-text("{label}")', timeout=2500)
            return
        except Exception:
            continue


def watch(page, url, seconds):
    """Force playback, sample progress, count loops. Returns (max_seconds, loops)."""
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    time.sleep(3)
    dismiss_consent(page)

    # JS play() is far more reliable than clicking — on Shorts a click toggles pause
    page.evaluate("""() => {
        const v = document.querySelector('video');
        if (v) { v.muted = true; v.play().catch(() => {}); }
    }""")

    max_t = 0.0
    last_t = 0.0
    loops = 0
    deadline = time.time() + seconds

    while time.time() < deadline:
        try:
            t = page.evaluate(
                "() => { const v = document.querySelector('video'); return v ? (v.currentTime || 0) : 0; }"
            )
            t = float(t or 0)
        except Exception:
            t = last_t

        if t < last_t - 1.0:      # time jumped backwards = it looped
            loops += 1
        if t > max_t:
            max_t = t
        last_t = t
        time.sleep(2)

    return max_t, loops


def notify(text):
    if not NOTIFY_TELEGRAM or "YOUR_CHAT_ID" in CHAT_ID:
        return
    try:
        payload = json.dumps({
            "chat_id": CHAT_ID,
            "text": text,
            "disable_notification": True,
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=20).read()
    except Exception as e:
        print("telegram failed:", e)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=[
            "--autoplay-policy=no-user-gesture-required",
            "--mute-audio",
            "--no-sandbox",
        ])

        for r in range(ROUNDS):
            for url in VIDEOS:
                ctx = browser.new_context(
                    user_agent=random.choice(USER_AGENTS),
                    viewport={"width": random.choice(VIEWPORTS)[0],
                              "height": random.choice(VIEWPORTS)[1]},
                    locale="en-US",
                )
                page = ctx.new_page()
                target = random.randint(MIN_WATCH, MAX_WATCH)
                is_short = "/shorts/" in url
                threshold = 5 if is_short else 25

                try:
                    played, loops = watch(page, url, target)
                    ok = played >= threshold or loops >= 1
                    tag = "OK  " if ok else "FAIL"
                    line = f"{tag} {played:6.1f}s  loops={loops}  {url}"
                except Exception as e:
                    line = f"ERR  {url}  {e}"

                print(line, flush=True)
                results.append(line)
                ctx.close()
                time.sleep(random.randint(4, 12))

        browser.close()

    good = sum(1 for r in results if r.startswith("OK"))
    summary = (
        f"auto-viewer finished\n{good}/{len(results)} played properly\n\n"
        + "\n".join(results)
    )
    print(summary)
    notify(summary)


if __name__ == "__main__":
    main()

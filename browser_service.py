"""
browser_service.py
Universal browser automation engine powered by Playwright.
Provides commands to open the browser, inspect pages, and autofill forms.
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime
from playwright.sync_api import sync_playwright

USER_DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", "C:\\"), "LocalBrowserAgent", "Session")
os.makedirs(USER_DATA_DIR, exist_ok=True)

STATE_FILE = os.path.join(USER_DATA_DIR, "state.json")


def open_browser(url: str = "https://ewf.companieshouse.gov.uk"):
    """Opens a visible Google Chrome window on the user's screen."""
    print(f"Opening browser at: {url}")
    with sync_playwright() as p:
        try:
            # Try launching with native Google Chrome
            context = p.chromium.launch_persistent_context(
                user_data_dir=USER_DATA_DIR,
                headless=False,
                channel="chrome",
                args=["--start-maximized", "--remote-debugging-port=9222"],
                no_viewport=True
            )
        except Exception:
            # Fallback to Chromium or Edge
            try:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=USER_DATA_DIR,
                    headless=False,
                    channel="msedge",
                    args=["--start-maximized", "--remote-debugging-port=9222"],
                    no_viewport=True
                )
            except Exception:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=USER_DATA_DIR,
                    headless=False,
                    args=["--start-maximized", "--remote-debugging-port=9222"],
                    no_viewport=True
                )

        page = context.pages[0] if context.pages else context.new_page()
        page.goto(url)
        print(f"Browser opened successfully: {page.title()} ({page.url})")
        print("Browser is ready on screen. Keeping window open...")

        # Keep browser open and listening for tasks
        while True:
            time.sleep(1)
            # Check if there is a pending action in state.json
            if os.path.exists(STATE_FILE):
                try:
                    with open(STATE_FILE, "r") as f:
                        action_data = json.load(f)
                    
                    action = action_data.get("action")
                    if action == "fill_aa02":
                        params = action_data.get("params", {})
                        execute_fill_aa02(context, params)
                        os.remove(STATE_FILE)
                    elif action == "screenshot":
                        execute_screenshot(context)
                        os.remove(STATE_FILE)
                    elif action == "inspect":
                        execute_inspect(context)
                        os.remove(STATE_FILE)
                    elif action == "close":
                        os.remove(STATE_FILE)
                        break
                except Exception as e:
                    print(f"Error handling action: {e}")


def execute_fill_aa02(context, params):
    """Executes the AA02 form filling on the active tab."""
    unpaid = params.get("unpaid", "1")
    cash = params.get("cash", "0")
    shares = params.get("shares", "1")
    s_class = params.get("share_class", "Ordinary")
    value = params.get("value", "1")
    date_str = params.get("date", datetime.now().strftime("%d/%m/%Y"))

    # Find Companies House tab or active tab
    target_page = None
    for p in context.pages:
        if "companieshouse.gov.uk" in p.url.lower() or "aa02" in p.url.lower():
            target_page = p
            break
    if not target_page:
        target_page = context.pages[-1]

    print(f"Targeting page: {target_page.title()} ({target_page.url})")

    # Fill via DOM
    target_page.evaluate(f"""() => {{
        function findInputByText(textMatch) {{
            const allElements = Array.from(document.querySelectorAll('label, td, div, span, p'));
            for (const el of allElements) {{
                if (el.textContent.includes(textMatch)) {{
                    let container = el.closest('tr') || el.closest('.form-group') || el.parentElement;
                    if (container) {{
                        const input = container.querySelector('input[type="text"], input:not([type])');
                        if (input) return input;
                    }}
                }}
            }}
            return null;
        }}

        // 1. Unpaid capital
        const unpaidInput = findInputByText('Called up share capital not paid') || document.querySelector('input[name*="unpaid"], input[id*="unpaid"]');
        if (unpaidInput) {{
            unpaidInput.value = '{unpaid}';
            unpaidInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
            unpaidInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}

        // 2. Cash at bank
        const cashInput = findInputByText('Cash at bank and in hand') || document.querySelector('input[name*="cash"], input[id*="cash"]');
        if (cashInput) {{
            cashInput.value = '{cash}';
            cashInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
            cashInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}

        // 3. Issued Share Capital Section
        const shareSection = Array.from(document.querySelectorAll('div, table, fieldset')).find(el => 
            el.textContent.includes('Issued share capital')
        );

        if (shareSection) {{
            const inputs = shareSection.querySelectorAll('input[type="text"], input:not([type])');
            if (inputs.length >= 4) {{
                inputs[0].value = '{shares}';
                inputs[0].dispatchEvent(new Event('input', {{ bubbles: true }}));
                inputs[0].dispatchEvent(new Event('change', {{ bubbles: true }}));

                inputs[1].value = '{s_class}';
                inputs[1].dispatchEvent(new Event('input', {{ bubbles: true }}));
                inputs[1].dispatchEvent(new Event('change', {{ bubbles: true }}));

                inputs[2].value = '{value}';
                inputs[2].dispatchEvent(new Event('input', {{ bubbles: true }}));
                inputs[2].dispatchEvent(new Event('change', {{ bubbles: true }}));

                inputs[3].value = '{str(int(shares) * int(value) if shares.isdigit() and value.isdigit() else "1")}';
                inputs[3].dispatchEvent(new Event('input', {{ bubbles: true }}));
                inputs[3].dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}
        }}

        // 4. Approval Date
        const dateInput = findInputByText('Date of approval of accounts') || 
                          findInputByText('approval') ||
                          document.querySelector('input[name*="approvalDate"], input[id*="approvalDate"], input[name*="date"]');
        if (dateInput) {{
            dateInput.value = '{date_str}';
            dateInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
            dateInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
        }}

        // 5. Statutory Checkboxes
        const checkboxes = Array.from(document.querySelectorAll('input[type="checkbox"]'));
        checkboxes.forEach(cb => {{
            const labelText = (cb.parentElement ? cb.parentElement.textContent : '') + (cb.closest('div') ? cb.closest('div').textContent : '');
            if (labelText.includes('section 476') || 
                labelText.includes('accounting records') || 
                labelText.includes('small companies')) {{
                cb.checked = true;
                cb.dispatchEvent(new Event('change', {{ bubbles: true }}));
            }}
        }});
    }}""")
    print("✔ AA02 form filled successfully!")


def execute_screenshot(context):
    page = context.pages[-1]
    screenshot_path = os.path.join(os.path.dirname(__file__), "tab_preview.png")
    page.screenshot(path=screenshot_path)
    print(f"✔ Screenshot saved: {screenshot_path}")


def execute_inspect(context):
    page = context.pages[-1]
    print(f"Active Page: {page.title()} ({page.url})")


def send_action(action: str, params: dict = None):
    """Sends an action request to the running browser service."""
    data = {"action": action, "params": params or {}}
    with open(STATE_FILE, "w") as f:
        json.dump(data, f)
    print(f"Action '{action}' sent to browser agent.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["start", "fill", "screenshot", "inspect", "close"], default="start", nargs="?")
    parser.add_argument("--url", default="https://ewf.companieshouse.gov.uk")
    parser.add_argument("--unpaid", default="1")
    parser.add_argument("--cash", default="0")
    parser.add_argument("--shares", default="1")
    parser.add_argument("--class", dest="share_class", default="Ordinary")
    parser.add_argument("--value", default="1")
    parser.add_argument("--date", default=None)

    args = parser.parse_args()

    if args.command == "start":
        open_browser(args.url)
    elif args.command == "fill":
        send_action("fill_aa02", {
            "unpaid": args.unpaid,
            "cash": args.cash,
            "shares": args.shares,
            "share_class": args.share_class,
            "value": args.value,
            "date": args.date or datetime.now().strftime("%d/%m/%Y")
        })
    elif args.command == "screenshot":
        send_action("screenshot")
    elif args.command == "inspect":
        send_action("inspect")
    elif args.command == "close":
        send_action("close")

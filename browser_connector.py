"""
browser_connector.py
Connects to an existing Chrome/Edge browser session via Chrome DevTools Protocol (CDP).
"""

import sys
from typing import Optional, List
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page


class BrowserConnector:
    def __init__(self, cdp_url: str = "http://127.0.0.1:9222"):
        self.cdp_url = cdp_url
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None

    def connect(self) -> BrowserContext:
        """Connects to the browser instance running on port 9222."""
        self.playwright = sync_playwright().start()
        
        # Try 127.0.0.1 first, then localhost fallback
        for url in [self.cdp_url, "http://localhost:9222"]:
            try:
                self.browser = self.playwright.chromium.connect_over_cdp(url)
                if self.browser and self.browser.contexts:
                    self.context = self.browser.contexts[0]
                    return self.context
            except Exception:
                continue

        if self.playwright:
            self.playwright.stop()
            self.playwright = None
            
        raise ConnectionError(
            "Could not connect to Chrome.\n"
            "Please make sure you clicked 'Step 1: Open Browser' first!"
        )

    def get_pages(self) -> List[Page]:
        """Returns all open pages/tabs."""
        if not self.context:
            self.connect()
        return self.context.pages

    def find_page_by_url(self, url_substring: str) -> Optional[Page]:
        """Finds the first tab matching a given URL substring (e.g. 'companieshouse.gov.uk')."""
        pages = self.get_pages()
        for page in pages:
            if url_substring.lower() in page.url.lower():
                return page
        return None

    def get_active_or_first_page(self) -> Page:
        """Returns the first available tab."""
        pages = self.get_pages()
        if not pages:
            return self.context.new_page()
        return pages[-1]

    def close(self):
        """Cleanly releases playwright resources without closing the user's browser."""
        if self.playwright:
            self.playwright.stop()
            self.playwright = None

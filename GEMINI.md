# Accounting Hub Portal Design & Interaction Guardrails

## 1. Zero Horizontal Scrolling for Navigation
- **Never** use `overflow-x-auto` or single-line scrolling containers for navigation tabs, bank accounts, or tool switchers.
- All tabs must be **100% visible at a single glance**.
- Use responsive wrapping layouts (`flex flex-wrap items-stretch gap-2` or responsive CSS grids) with card-style buttons (`flex-1 min-w-[170px]`) so tabs adapt cleanly to the screen without cutting off any bank.

## 2. One Pile Per Bank Account
- Keep bank identity, sort codes, account numbers, roadblock issue banners, interactive to-do checklists, transactions ledger, and real source documents in **one unified view per bank account**.
- Do not split bank details/tasks into one tab and statements into another.

## 3. Zero Assumed Data (Strict Reality Only)
- **Never assume or extrapolate any data**, including financial figures, operational details, transactions, dates, sort codes, account numbers, or balances.
- Always display `"Needs Updating ✏️"` or prompt for verification unless explicitly confirmed from real source documents or verified user input.
- Never invent placeholder metrics, mock figures, or fabricate missing records under any circumstances.

## 4. ADHD Brevity in Responses
- Always keep chat responses to **1–2 plain English sentences maximum**.

## 5. Mandatory Verification & Glitch Checking
- **Always** run automated tests, inspect error logs, and perform interactive glitch checks on any code change or update before reporting completion to the user.
- Verify element bindings, event listeners, API endpoints, and server health checks proactively to ensure zero regressions.

## 6. Strict Scope Focus & Zero Drift
- Only change the exact element, function, or line block requested by the user.
- **Never drift** into editing other sections, pages, components, or styles unless explicitly instructed.

## 7. Mobile Viewport & Layout Verification
- **Always** test mobile views for spacing, sizing, and text wrapping whenever changes are made.
- Ensure **zero overhang** of text, cards, buttons, or containers on mobile screens.

## 8. Mandatory Functional Legal Footer on New Apps
- Whenever a new app or project is created, **always automatically include a fully functional footer** with all essential legal sections already built and interactive.
- Must include working modals, drawers, or views for: **Privacy Policy**, **Terms of Service**, **Cookie Notice / Preferences**, **Company / Contact Details**, and **Copyright**.

## 9. Proactive Local Preview & Live Link
- **Always ensure the local preview server (`server.py` on port 5500) is running** at the start of any conversation or session. If it is not running or has stopped, immediately launch it in the background (`python server.py`).
- **Always provide the active clickable preview link (`http://localhost:5500/`)** in your initial or relevant response so the user can immediately open and view the portal without having to prompt for it.

## 10. Mandatory Triple-Check Accuracy (Numbers, Dates & Facts)
- Whenever entering, calculating, or updating information (financial figures, currency balances, transaction amounts, statutory dates, deadlines, Companies House numbers, UTRs, or factual operational statements), **always triple-check their accuracy against the original source documents or verified user input**.
- Rigorously cross-reference exact digits, date formatting, and factual statements before committing any changes or displaying them in the portal.
- If any ambiguity or discrepancy is found, explicitly flag it for verification rather than guessing or approximating.

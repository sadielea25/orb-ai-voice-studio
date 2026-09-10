# 🏢 Companies House & GOV.UK Form Assistant

A visual, desktop application to automatically fill online forms (such as Companies House AA02 Dormant Accounts) with zero terminal commands required.

---

## 🖱️ How to Use (100% Visual / Clickable)

### 1. Launch the Visual Assistant
Double-click:
```text
START_AGENT_APP.bat
```
*(This opens the visual window on your desktop)*

---

### 2. Click "🌐 Open Browser"
Inside the app, click the blue **"🌐 Open Browser"** button.
* This will launch your Chrome / Edge browser in automation mode.
* In that browser, log in to **Companies House WebFiling** and navigate to your **AA02 Dormant Accounts** form.

---

### 3. Click "⚡ Autofill Form Now"
Inside the app, click the green **"⚡ Autofill Form Now"** button.
* The assistant instantly populates:
  - **Share Capital:** 1 Ordinary share @ £1
  - **Assets:** £1 Unpaid share capital, £0 Cash
  - **Approval Date:** Today's date
  - **Statutory Statements:** All audit exemption declarations confirmed
* Look at your browser window to review the form, and click **VALIDATE AND CONTINUE**!

---

## 📁 Files in This Folder

* **`START_AGENT_APP.bat`**: **Double-click this** to launch the visual interface.
* **`gui_app.py`**: The graphical desktop application.
* **`launch_browser.bat`**: Helper script that opens Chrome/Edge on port 9222.
* **`fill_aa02.py`**: Backend script for AA02 form filling.
* **`agent.py`**: Command-line interactive tool.

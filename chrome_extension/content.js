// content.js - High-Precision Auto-Filler & Auto-Speaker

console.log("🚀 AI Assistant Voice & Filler Bridge Active!");

let isBusy = false;

// Speak text out loud through laptop speakers using natural Web Speech API
function speakTextAloud(text) {
    try {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = "en-GB";
        utterance.rate = 1.0;
        utterance.pitch = 1.0;
        window.speechSynthesis.speak(utterance);
        console.log("🔊 Spoke aloud:", text);
    } catch (e) {
        console.error("Speech error:", e);
    }
}

// Poll local bridge server every 1 second
setInterval(async () => {
    if (isBusy) return;

    try {
        const response = await fetch("http://127.0.0.1:8765/command", {
            method: "GET",
            headers: { "Content-Type": "application/json" }
        });

        if (!response.ok) return;

        const data = await response.json();
        if (data && data.action && data.action !== "none") {
            isBusy = true;
            console.log("⚡ Received command:", data);

            let result = "ok";
            if (data.action === "speak") {
                speakTextAloud(data.params?.text || "Hello!");
                result = "Spoke text aloud";
            } else if (data.action === "fill_aa02") {
                result = executeStrictSemanticFill(data.params || {});
                speakTextAloud("I have filled out all the fields on your dormant accounts form. Please review and click validate.");
            } else if (data.action === "click_validate") {
                result = clickValidateButton();
                speakTextAloud("I clicked validate and continue for you.");
            }

            await fetch("http://127.0.0.1:8765/report", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ action: data.action, status: "success", result: result })
            });

            isBusy = false;
        }
    } catch (e) {}
}, 1000);

function applyValue(inp, value) {
    if (!inp) return;
    inp.focus();
    inp.value = value;
    inp.setAttribute("value", value);
    inp.style.backgroundColor = "#dcfce7";
    inp.style.borderColor = "#16a34a";
    inp.style.borderWidth = "2px";
    ['focus', 'keydown', 'keypress', 'input', 'keyup', 'change', 'blur'].forEach(evt => {
        inp.dispatchEvent(new Event(evt, { bubbles: true }));
    });
}

function findInputByExactLabel(labelPattern) {
    const allLabels = Array.from(document.querySelectorAll('label, td, th, div, span, p'));
    for (const el of allLabels) {
        const text = el.innerText ? el.innerText.trim() : el.textContent.trim();
        if (text.length < 80 && labelPattern.test(text)) {
            const container = el.closest('tr') || el.closest('.form-group') || el.parentElement;
            if (container) {
                const inp = container.querySelector('input[type="text"], input:not([type]), input[type="date"]');
                if (inp) return inp;
            }
        }
    }
    return null;
}

function executeStrictSemanticFill(params) {
    const d = new Date();
    const todayStr = `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`;

    // 1. Assets
    const unpaidInp = findInputByExactLabel(/called up share capital not paid/i) || 
                      document.querySelector('input[name*="unpaid" i], input[id*="unpaid" i]');
    if (unpaidInp) applyValue(unpaidInp, '1');

    const cashInp = findInputByExactLabel(/cash at bank and in hand/i) || 
                    document.querySelector('input[name*="cash" i], input[id*="cash" i]');
    if (cashInp) applyValue(cashInp, '0');

    // 2. Share Capital Table
    const shareSec = Array.from(document.querySelectorAll('div, table, fieldset')).find(el => 
        /issued share capital/i.test(el.textContent) && /number of shares/i.test(el.textContent)
    );
    if (shareSec) {
        const inputs = shareSec.querySelectorAll('input[type="text"], input:not([type])');
        if (inputs.length >= 4) {
            applyValue(inputs[0], '1');         // Number of shares
            applyValue(inputs[1], 'Ordinary');  // Share class
            applyValue(inputs[2], '1');         // Value per share
            applyValue(inputs[3], '1');         // Current period total
        }
    }

    // 3. Date of Approval of Accounts
    const dateInp = findInputByExactLabel(/date of approval/i) || 
                    document.querySelector('input[name*="approval" i], input[id*="approval" i]');
    if (dateInp) applyValue(dateInp, todayStr);

    // 4. Director Forename (SADIE) & Surname (MINIFEE)
    const dirSections = Array.from(document.querySelectorAll('tr, .form-group, div')).filter(el => 
        /director's name/i.test(el.textContent) && !/additional/i.test(el.textContent)
    );
    let dirInputs = [];
    dirSections.forEach(sec => {
        Array.from(sec.querySelectorAll('input[type="text"], input:not([type])')).forEach(i => {
            if (!dirInputs.includes(i)) dirInputs.push(i);
        });
    });

    if (dirInputs.length >= 2) {
        applyValue(dirInputs[0], 'SADIE');
        applyValue(dirInputs[1], 'MINIFEE');
    }

    // 5. Checkboxes
    document.querySelectorAll('input[type="checkbox"]').forEach(cb => {
        const text = ((cb.parentElement?.textContent || '') + ' ' + (cb.closest('div, tr, p')?.textContent || '')).toLowerCase();
        if (text.includes('agent for a person') || text.includes('acted as an agent')) {
            cb.checked = false;
        } else {
            cb.checked = true;
        }
        cb.dispatchEvent(new Event('change', { bubbles: true }));
    });

    return "Strict fill complete";
}

function clickValidateButton() {
    const btn = Array.from(document.querySelectorAll('input[type="submit"], button')).find(b => 
        (b.value || b.textContent || '').toLowerCase().includes('validate') || (b.value || b.textContent || '').toLowerCase().includes('continue')
    );
    if (btn) {
        btn.click();
        return "Clicked validate button";
    }
    return "Validate button not found";
}

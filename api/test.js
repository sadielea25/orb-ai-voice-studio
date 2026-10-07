
// Single-instance coordinator: ensure multiple open tabs never spawn a barrage of conflicting widgets
    const widgetSyncChannel = ('BroadcastChannel' in window) ? new BroadcastChannel('orb_voice_widget_sync') : null;
    if (widgetSyncChannel) {
      widgetSyncChannel.onmessage = (ev) => {
        if (ev.data && ev.data.type === 'PIP_OPENED') {
          // If another tab has launched the floating widget, close our PiP instance and pause mic
          if (window.documentPictureInPicture && window.documentPictureInPicture.window && !window.documentPictureInPicture.window.closed) {
            try { window.documentPictureInPicture.window.close(); } catch(e) {}
          }
          if (isConnected) {
            stopMic();
          }
        }
      };
    }

    function bindOrbHandlers(targetDoc = document) {
      try {
        if (!targetDoc) return;
        const orb = Document.prototype.getElementById.call(targetDoc, 'orbEl');
        if (orb) {
          orb.onclick = (e) => {
            if (e) { e.preventDefault(); e.stopPropagation(); }
            handleOrbClick();
          };
        }
        const row = Document.prototype.getElementById.call(targetDoc, 'orbRow');
        if (row) {
          row.onclick = (e) => {
            if (e) e.preventDefault();
            handleOrbClick();
          };
        }
        const btnTP = Document.prototype.getElementById.call(targetDoc, 'btnTotalPause');
        if (btnTP) {
          btnTP.onclick = (e) => {
            if (e) { e.preventDefault(); e.stopPropagation(); }
            toggleTotalPause();
          };
        }
        const btnMic = Document.prototype.getElementById.call(targetDoc, 'btnMicToggle');
        if (btnMic) {
          btnMic.onclick = (e) => {
            if (e) { e.preventDefault(); e.stopPropagation(); }
            toggleMicOnly();
          };
        }
      } catch (e) {
        console.error('Error binding orb handlers:', e);
      }
    }

    let recognition = null;
    let isConnected = false;
    let isTotalPaused = false;
    let isManualPaused = true;
    let currentAppVersion = null;
    let isHotUpdating = false;
    let currentDraft = "";
    let interimText = "";
    let silenceTimer = null;
    let silenceCountdownInterval = null;
    let isDraftPolished = false;
    let lastRenderedMessages = [];

    function showToast(msg) {
      const docs = [document];
      if (window.documentPictureInPicture && window.documentPictureInPicture.window && !window.documentPictureInPicture.window.closed) {
        try { docs.push(window.documentPictureInPicture.window.document); } catch (e) {}
      }
      docs.forEach(doc => {
        const t = Document.prototype.getElementById.call(doc, 'toast');
        if (t) {
          t.innerText = msg;
          t.style.display = 'block';
          t.style.zIndex = '999999';
          setTimeout(() => { t.style.display = 'none'; }, 3500);
        }
      });
    }

    function updateRateLabel() {
      const val = parseInt(document.getElementById('rangeRate').value);
      const mult = ((100 + val) / 100).toFixed(2);
      const lr = document.getElementById('labelRate'); if (lr) lr.innerText = mult + 'x';
    }

    function updatePitchLabel() {
      const val = parseInt(document.getElementById('rangePitch').value);
      if (val === 0) { const lp = document.getElementById('labelPitch'); if (lp) lp.innerText = 'Normal'; }
      else if (val > 0) { const lp = document.getElementById('labelPitch'); if (lp) lp.innerText = '+' + val + 'Hz'; }
      else { const lp = document.getElementById('labelPitch'); if (lp) lp.innerText = val + 'Hz'; }
    }

    const PERSONAS = [
      {
        id: "en-GB-LibbyNeural",
        name: "Libby",
        accent: "British",
        flag: "🇬🇧",
        gender: "Female",
        tag: "British Natural Expressive Female",
        avatar: "https://images.unsplash.com/photo-1573497019940-1c28c88b4f3e?w=160&auto=format&fit=crop&q=80"
      },
      {
        id: "en-GB-SoniaNeural",
        name: "Sonia",
        accent: "British",
        flag: "🇬🇧",
        gender: "Female",
        tag: "British Natural Female",
        avatar: "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=160&auto=format&fit=crop&q=80"
      },
      {
        id: "en-GB-RyanNeural",
        name: "Ryan",
        accent: "British",
        flag: "🇬🇧",
        gender: "Male",
        tag: "British Professional Male",
        avatar: "https://images.unsplash.com/photo-1560250097-0b93528c311a?w=160&auto=format&fit=crop&q=80"
      },
      {
        id: "en-GB-ThomasNeural",
        name: "Thomas",
        accent: "British",
        flag: "🇬🇧",
        gender: "Male",
        tag: "British Deep Narrator Male",
        avatar: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=160&auto=format&fit=crop&q=80"
      },
      {
        id: "en-US-AvaNeural",
        name: "Ava",
        accent: "American",
        flag: "🇺🇸",
        gender: "Female",
        tag: "US Ultra-Natural Studio Female",
        avatar: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=160&auto=format&fit=crop&q=80"
      },
      {
        id: "en-US-BrianNeural",
        name: "Brian",
        accent: "American",
        flag: "🇺🇸",
        gender: "Male",
        tag: "US Relaxed Natural Male",
        avatar: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=160&auto=format&fit=crop&q=80"
      },
      {
        id: "en-US-JennyNeural",
        name: "Jenny",
        accent: "American",
        flag: "🇺🇸",
        gender: "Female",
        tag: "US Crisp Natural Female",
        avatar: "https://images.unsplash.com/photo-1580489944761-15a19d654956?w=160&auto=format&fit=crop&q=80"
      },
      {
        id: "en-US-GuyNeural",
        name: "Guy",
        accent: "American",
        flag: "🇺🇸",
        gender: "Male",
        tag: "US Casual Male",
        avatar: "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=160&auto=format&fit=crop&q=80"
      },
      {
        id: "en-US-ChristopherNeural",
        name: "Christopher",
        accent: "American",
        flag: "🇺🇸",
        gender: "Male",
        tag: "US Deep Male",
        avatar: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=160&auto=format&fit=crop&q=80"
      },
      {
        id: "en-US-AriaNeural",
        name: "Aria",
        accent: "American",
        flag: "🇺🇸",
        gender: "Female",
        tag: "US Expressive Studio Female",
        avatar: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=160&auto=format&fit=crop&q=80"
      },
      {
        id: "en-IE-EmilyNeural",
        name: "Emily",
        accent: "Irish",
        flag: "🇮🇪",
        gender: "Female",
        tag: "Irish Female",
        avatar: "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=160&auto=format&fit=crop&q=80"
      },
      {
        id: "en-AU-NatashaNeural",
        name: "Natasha",
        accent: "Australian",
        flag: "🇦🇺",
        gender: "Female",
        tag: "Australian Female",
        avatar: "https://images.unsplash.com/photo-1573497019940-1c28c88b4f3e?w=160&auto=format&fit=crop&q=80"
      },
      {
        id: "en-CA-LiamNeural",
        name: "Liam",
        accent: "Canadian",
        flag: "🇨🇦",
        gender: "Male",
        tag: "Canadian Male",
        avatar: "https://images.unsplash.com/photo-1519085360753-af0119f7cbe7?w=160&auto=format&fit=crop&q=80"
      }
    ];

    const ACCENTS = [
      { id: "British", name: "British", flag: "🇬🇧" },
      { id: "American", name: "American", flag: "🇺🇸" },
      { id: "Irish", name: "Irish", flag: "🇮🇪" },
      { id: "Australian", name: "Australian", flag: "🇦🇺" },
      { id: "Canadian", name: "Canadian", flag: "🇨🇦" }
    ];

    let selectedAccent = "British";

    function getAvatarFallback(voiceId) {
      const p = PERSONAS.find(x => x.id === voiceId) || PERSONAS[0];
      const bg = p.gender === 'Female' ? '%23db2777' : '%232563eb';
      return `data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" viewBox="0 0 100 100"><rect width="100" height="100" rx="50" fill="${bg}"/><circle cx="50" cy="38" r="18" fill="white" opacity="0.9"/><path d="M22 84 C22 64 36 58 50 58 C64 58 78 64 78 84 Z" fill="white" opacity="0.9"/></svg>`;
    }

            function updateVoicePersonaUI(voiceId) {
      if (!voiceId) return;
      const p = voicePersonas.find(v => v.id === voiceId);
      if (!p) return;
      
      const avatarImg = document.getElementById('voiceAvatarImg');
      const avatarFlag = document.getElementById('voiceAvatarFlag');
      const nameEl = document.getElementById('activePersonName');
      const select = document.getElementById('selectVoice');
      
      if (avatarImg) {
        avatarImg.src = p.avatar;
        avatarImg.onerror = () => { avatarImg.src = getAvatarFallback(p.id); };
      }
      if (avatarFlag) avatarFlag.innerText = p.flag;
      if (nameEl) nameEl.innerText = p.name;
      if (select && select.value !== p.id) select.value = p.id;
      
      const pCards = document.querySelectorAll('.persona-card');
      pCards.forEach(c => {
        if (c.getAttribute('data-id') === voiceId) {
          c.classList.add('active');
        } else {
          c.classList.remove('active');
        }
      });
      if (window.documentPictureInPicture && window.documentPictureInPicture.window && !window.documentPictureInPicture.window.closed) {
        const pipCards = window.documentPictureInPicture.window.document.querySelectorAll('.persona-card');
        pipCards.forEach(c => {
          if (c.getAttribute('data-id') === voiceId) {
            c.classList.add('active');
          } else {
            c.classList.remove('active');
          }
        });
      }
    }

function onVoiceSelected() {
      const select = document.getElementById('selectVoice');
      if (select) {
        updateVoicePersonaUI(select.value);
        saveVoiceSettings();
      }
    }

    async function loadSettings() {
      try {
        const res = await fetch('/api/settings');
        const data = await res.json();
        const voiceId = data.voice || 'en-GB-LibbyNeural';
        const sv = document.getElementById('selectVoice'); if (sv) sv.value = voiceId;
        updateVoicePersonaUI(voiceId);
        
        const rateVal = parseInt(String(data.rate || '0').replace('%', '').replace('+', '')) || 0;
        const rr = document.getElementById('rangeRate'); if (rr) rr.value = rateVal;
        
        const pitchVal = parseInt(String(data.pitch || '0').replace('Hz', '').replace('+', '')) || 0;
        const rp = document.getElementById('rangePitch'); if (rp) rp.value = pitchVal;

        updateRateLabel();
        updatePitchLabel();

        if (data && data.gemini_api_key) {
          localStorage.setItem('gemini_api_key', data.gemini_api_key);
          window.__GEMINI_KEY__ = data.gemini_api_key;
        }
      } catch (e) {}
    }

    async function saveVoiceSettings() {
      const rateVal = document.getElementById('rangeRate').value;
      const pitchVal = document.getElementById('rangePitch').value;
      const payload = {
        engine: 'edge',
        voice: document.getElementById('selectVoice').value,
        rate: (rateVal >= 0 ? '+' : '') + rateVal + '%',
        pitch: (pitchVal >= 0 ? '+' : '') + pitchVal + 'Hz',
        volume: '+0%',
        enabled: !isTotalPaused
      };

      try {
        await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        showToast('Voice settings saved live!');
      } catch (e) {}
    }

    async function popOutFloatingWidget(silentFail = false) {
      if (window.documentPictureInPicture && window.documentPictureInPicture.window && !window.documentPictureInPicture.window.closed) {
        window.documentPictureInPicture.window.close();
        return;
      }

      if (widgetSyncChannel) {
        try { widgetSyncChannel.postMessage({ type: 'PIP_OPENED' }); } catch (e) {}
      }

      if ('documentPictureInPicture' in window) {
        try {
          const pipWindow = await window.documentPictureInPicture.requestWindow();
          
          try {
            pipWindow.resizeTo(470, 720);
          } catch (e) {}

          pipWindow.document.title = "🎙️ Orb AI Live Voice Studio";

          [...document.styleSheets].forEach((styleSheet) => {
            try {
              const cssRules = [...styleSheet.cssRules].map((rule) => rule.cssText).join('');
              const style = document.createElement('style');
              style.textContent = cssRules;
              pipWindow.document.head.appendChild(style);
            } catch (e) {
              const link = document.createElement('link');
              link.rel = 'stylesheet';
              link.type = styleSheet.type;
              link.media = styleSheet.media;
              link.href = styleSheet.href;
              pipWindow.document.head.appendChild(link);
            }
          });

          pipWindow.document.body.style.background = "#090d16";
          pipWindow.document.body.style.color = "#f8fafc";
          pipWindow.document.body.style.margin = "0";
          pipWindow.document.body.style.padding = "10px";
          pipWindow.document.body.style.overflowY = "auto";
          pipWindow.document.body.classList.add('pip-mode');
          const container = document.querySelector('.container');
          container.classList.add('pip-container');
          pipWindow.document.body.appendChild(container);

          const updateWidgetCompactState = () => {
            const h = pipWindow.innerHeight;
            if (h <= 340) {
              container.classList.add('bare-minimum');
              container.classList.remove('compact-mode');
            } else if (h <= 540) {
              container.classList.add('compact-mode');
              container.classList.remove('bare-minimum');
            } else {
              container.classList.remove('compact-mode');
              container.classList.remove('bare-minimum');
            }
          };

          pipWindow.addEventListener('resize', updateWidgetCompactState);
          updateWidgetCompactState();

          bindPipControls(pipWindow);

          const placeholder = document.getElementById('pipActivePlaceholder');
          if (placeholder) placeholder.style.display = 'flex';
          const overlay = document.getElementById('immediateLaunchOverlay');
          if (overlay) overlay.style.display = 'none';

          const mainBtn = document.getElementById('btnPipFloat');
          if (mainBtn) mainBtn.style.display = 'none';
          const focusBtn = document.getElementById('btnFocusMain');
          if (focusBtn) focusBtn.style.display = 'inline-flex';

          pipWindow.addEventListener('pagehide', () => {
            const placeholder = document.getElementById('pipActivePlaceholder');
            if (placeholder) placeholder.style.display = 'none';
            container.classList.remove('pip-container');
            container.classList.remove('compact-mode');
            container.classList.remove('bare-minimum');
            document.body.insertBefore(container, document.body.firstChild);
            bindOrbHandlers(document);
            const mainBtn = document.getElementById('btnPipFloat');
            if (mainBtn) {
              mainBtn.style.display = 'inline-flex';
              mainBtn.innerText = '🚀 Launch on your screen';
              mainBtn.style.background = 'linear-gradient(135deg, #2563eb, #7c3aed)';
            }
            const focusBtn = document.getElementById('btnFocusMain');
            if (focusBtn) focusBtn.style.display = 'none';
          });

          showToast('🚀 Launched on your screen!');
        } catch (err) {
          console.error('PiP Error:', err);
          showToast('⚠️ Pop-up Error: ' + err.message);
          throw err;
        }
      } else {
        alert('Always-on-top floating is supported in Microsoft Edge and Google Chrome.');
      }
    }

    function bindPipControls(pipWindow) {
      if (!pipWindow || !pipWindow.document) return;
      const bridgeFns = [
        'toggleTotalPause', 'updateTotalPauseUI', 'toggleMicOnly', 'handleOrbClick',
        'toggleOrb', 'pauseAI', 'toggleMic', 'startMic', 'stopMic', 'readDraftBack', 'sendDraftNow', 'clearDraft',
        'polishDraft', 'saveVoiceSettings', 'updateRateLabel', 'updatePitchLabel', 'testVoicePreview',
        'speakAudio', 'stopSpeech', 'showToast', 'installPWA', 'popOutFloatingWidget',
        'setOrbState', 'processUtterance', 'adaptSpeechText', 'renderDraftDisplay',
        'resetSilenceTimer', 'initSpeechRecognition', 'bindOrbHandlers',
        'selectPersona', 'onVoiceSelected', 'updateVoicePersonaUI', 'renderPersonaGallery', 'getAvatarFallback',
        'selectAccent', 'renderAccentPills', 'render2StepVoicePicker', 'previewPersonaVoice', 'applyHotUpdate', 'speakLastAIReply',
        'pinFloaterToTaskbar', 'getDraftText', 'handleDraftBoxInput', 'handleDraftBoxKey'
      ];
      bridgeFns.forEach(fn => {
        try { pipWindow[fn] = window[fn]; } catch (e) {}
      });

      // Bind click handlers inside popup window
      bindOrbHandlers(pipWindow.document);
      render2StepVoicePicker(pipWindow.document);

      const pipDraftBox = pipWindow.document.getElementById('draftBox');
      if (pipDraftBox) {
        pipDraftBox.oninput = () => window.handleDraftBoxInput(pipDraftBox);
        pipDraftBox.onkeydown = (e) => window.handleDraftBoxKey(e);
      }

      const pipVoiceSelect = pipWindow.document.getElementById('selectVoice');
      if (pipVoiceSelect) {
        pipVoiceSelect.onchange = () => window.onVoiceSelected();
      }
      const pipPolishBtn = pipWindow.document.getElementById('btnPolish') || pipWindow.document.querySelector('.btn-polish');
      if (pipPolishBtn) {
        pipPolishBtn.onclick = () => window.polishDraft();
      }
      const pipReadBackBtn = pipWindow.document.querySelector('.btn-readback');
      if (pipReadBackBtn) {
        pipReadBackBtn.onclick = () => window.readDraftBack();
      }
      const pipSendBtn = pipWindow.document.querySelector('.btn-send');
      if (pipSendBtn) {
        pipSendBtn.onclick = () => window.sendDraftNow();
      }
      const pipClearBtn = pipWindow.document.querySelector('.btn-clear');
      if (pipClearBtn) {
        pipClearBtn.onclick = () => window.clearDraft(false);
      }

            const pipTotalPauseBtn = pipWindow.document.getElementById('btnTotalPause');
      if (pipTotalPauseBtn) {
        pipTotalPauseBtn.onclick = () => window.toggleTotalPause();
      }

      const pipSpeakBtn = pipWindow.document.getElementById('btnFloaterSpeakAI');
      if (pipSpeakBtn) {
        pipSpeakBtn.onclick = () => window.speakLastAIReply();
      }

      const pipRefreshBtn = pipWindow.document.getElementById('btnFloaterRefresh');
      if (pipRefreshBtn) {
        pipRefreshBtn.onclick = () => window.applyHotUpdate(true);
      }

      const pipPinBtn = pipWindow.document.getElementById('btnFloaterPinTaskbar');
      if (pipPinBtn) {
        pipPinBtn.onclick = () => window.pinFloaterToTaskbar();
      }

      const floatBtn = pipWindow.document.getElementById('btnPipFloat');
      if (floatBtn) {
        floatBtn.style.display = 'none';
      }
    }

    async function applyHotUpdate(force = false) {
      if (isHotUpdating && !force) return;
      isHotUpdating = true;

      // Animate refresh icon rotation
      try {
        const docs = [document];
        if (window.documentPictureInPicture && window.documentPictureInPicture.window && !window.documentPictureInPicture.window.closed) {
          docs.push(window.documentPictureInPicture.window.document);
        }
        docs.forEach(doc => {
          const icon = Document.prototype.getElementById.call(doc, 'floaterRefreshIcon');
          if (icon) {
            icon.style.transition = 'transform 0.5s cubic-bezier(0.4, 0, 0.2, 1)';
            icon.style.transform = 'rotate(360deg)';
            setTimeout(() => { icon.style.transform = 'rotate(0deg)'; }, 550);
          }
        });
      } catch (e) {}

      // If user clicked Refresh button, perform complete, total reload of entire application & scripts
      if (force) {
        showToast('🔄 Full reload & syncing latest version...');
        try {
          sessionStorage.setItem('reopen_pip_after_reload', 'true');
        } catch (e) {}
        setTimeout(() => {
          window.location.href = window.location.pathname + '?v=' + Date.now();
        }, 200);
        return;
      }

      try {
        const isPipOpen = window.documentPictureInPicture && window.documentPictureInPicture.window && !window.documentPictureInPicture.window.closed;
        if (!isPipOpen) {
          window.location.reload();
          return;
        }

        // Hot update floater in place without closing or reopening the window
        const res = await fetch('/index.html?t=' + Date.now());
        const htmlText = await res.text();
        const parser = new DOMParser();
        const newDoc = parser.parseFromString(htmlText, 'text/html');

        const pipWindow = window.documentPictureInPicture.window;
        const pipDoc = pipWindow.document;

        // 1. Update style rules in floating window
        const newStyles = [...newDoc.querySelectorAll('style')].map(s => s.textContent).join('\n');
        let pipStyleEl = pipDoc.getElementById('pipHotReloadStyles');
        if (!pipStyleEl) {
          pipStyleEl = pipDoc.createElement('style');
          pipStyleEl.id = 'pipHotReloadStyles';
          pipDoc.head.appendChild(pipStyleEl);
        }
        pipStyleEl.textContent = newStyles;

        // 2. Hot-swap container DOM contents
        const newContainer = newDoc.querySelector('.container');
        const pipContainer = pipDoc.querySelector('.container');
        if (newContainer && pipContainer) {
          pipContainer.innerHTML = newContainer.innerHTML;
        }

        // 3. Rebind all controls and bridge functions
        bindPipControls(pipWindow);

        // 4. Re-sync active states
        updateTotalPauseUI(isTotalPaused);
        renderDraftDisplay();

        showToast('⚡ Floater auto-updated live!');
        console.log('[AUTO-UPDATE] Floater DOM hot-swapped successfully.');
      } catch (err) {
        console.error('[AUTO-UPDATE] Error applying hot update:', err);
      } finally {
        setTimeout(() => { isHotUpdating = false; }, 800);
      }
    }

    async function speakLastAIReply() {
      // 1. Ensure total pause is unpaused
      if (isTotalPaused) {
        isTotalPaused = false;
        updateTotalPauseUI(false);
      }

      // 2. Clear any browser preview audio
      if (currentPreviewAudio) {
        try { currentPreviewAudio.pause(); currentPreviewAudio.currentTime = 0; } catch (e) {}
      }

      showToast('🗣️ Scanning chats for latest reply...');

      // 3. Trigger server to speak latest AI response aloud (does NOT switch to listening)
      try {
        const res = await fetch('/api/read_ai_reply', { method: 'POST' });
        const data = await res.json();
        if (data && data.status === 'no_reply_found') {
          showToast('🔍 Scanned chats — no unread reply found.');
        } else {
          setOrbState('speaking');
          const title = document.getElementById('statusTitle'); if (title) title.innerText = 'AI Speaking...';
        }
      } catch (e) {
        showToast('⚠️ Could not play AI speech.');
      }
    }

    async function attemptAutoLaunch() {
      if (!('documentPictureInPicture' in window)) return;
      if (window.documentPictureInPicture && window.documentPictureInPicture.window && !window.documentPictureInPicture.window.closed) return;

      try {
        await popOutFloatingWidget(true);
        console.log('[AUTO-LAUNCH] Floating overlay opened on start.');
      } catch (err) {
        console.log('[AUTO-LAUNCH] Browser requires single gesture to float window:', err);
        enableImmediateLaunchOverlay();
      }
    }

    function enableImmediateLaunchOverlay() {
      const overlay = document.getElementById('immediateLaunchOverlay');
      if (overlay) overlay.style.display = 'flex';

      const trigger = async () => {
        window.removeEventListener('click', trigger);
        window.removeEventListener('keydown', trigger);
        window.removeEventListener('pointerdown', trigger);
        try {
          await popOutFloatingWidget(true);
          if (overlay) overlay.style.display = 'none';
        } catch (e) {
          console.error('Launch failed:', e);
        }
      };

      window.addEventListener('click', trigger, { once: true });
      window.addEventListener('keydown', trigger, { once: true });
      window.addEventListener('pointerdown', trigger, { once: true });
    }

    function updateTotalPauseUI(isPaused) {
      isTotalPaused = !!isPaused;
      const docs = [document];
      if (window.documentPictureInPicture && window.documentPictureInPicture.window && !window.documentPictureInPicture.window.closed) {
        try { docs.push(window.documentPictureInPicture.window.document); } catch (e) {}
      }

      docs.forEach(doc => {
        const btnTP = Document.prototype.getElementById.call(doc, 'btnTotalPause');
        const tpText = Document.prototype.getElementById.call(doc, 'totalPauseText');
        const tpIcon = Document.prototype.getElementById.call(doc, 'totalPauseIcon');
        const btnMic = Document.prototype.getElementById.call(doc, 'btnMicToggle');
        const sttBadge = Document.prototype.getElementById.call(doc, 'sttBadge');
        const orb = Document.prototype.getElementById.call(doc, 'orbEl');
        const statusTitle = Document.prototype.getElementById.call(doc, 'statusTitle');
        const statusSub = Document.prototype.getElementById.call(doc, 'statusSub');

        if (isPaused) {
          if (btnTP) {
            btnTP.style.background = 'rgba(16, 185, 129, 0.2)';
            btnTP.style.borderColor = 'rgba(16, 185, 129, 0.6)';
            btnTP.style.color = '#34d399';
          }
          if (tpIcon) tpIcon.innerText = '▶';
          if (tpText) tpText.innerText = 'Resume Voice';
          if (btnMic) {
            btnMic.disabled = true;
            btnMic.style.opacity = '0.35';
            btnMic.style.pointerEvents = 'none';
          }
          if (sttBadge) {
            sttBadge.innerText = '🛑 TOTAL PAUSE';
            sttBadge.style.color = '#f87171';
          }
          if (orb) {
            orb.className = 'orb paused';
            orb.innerText = '⏸️';
          }
          if (statusTitle) statusTitle.innerText = '🛑 Total Pause Active';
          if (statusSub) statusSub.innerText = 'No AI speech • No microphone listening';
        } else {
          if (btnTP) {
            btnTP.style.background = 'rgba(239, 68, 68, 0.12)';
            btnTP.style.borderColor = 'rgba(239, 68, 68, 0.4)';
            btnTP.style.color = '#f87171';
          }
          if (tpIcon) tpIcon.innerText = '🛑';
          if (tpText) tpText.innerText = 'Total Pause';
          if (btnMic) {
            btnMic.disabled = false;
            btnMic.style.opacity = '1';
            btnMic.style.pointerEvents = 'auto';
            btnMic.innerText = isConnected ? '⏹️ Stop Mic' : '🎙️ Start Listening';
            btnMic.style.color = isConnected ? '#fbbf24' : '#34d399';
            btnMic.style.background = isConnected ? 'rgba(245, 158, 11, 0.18)' : 'rgba(16, 185, 129, 0.18)';
            btnMic.style.borderColor = isConnected ? 'rgba(245, 158, 11, 0.4)' : 'rgba(16, 185, 129, 0.4)';
          }
          if (sttBadge) {
            sttBadge.innerText = isConnected ? '● Listening' : (isAISpeaking ? '● Speaking' : '● Idle');
            sttBadge.style.color = isConnected ? '#34d399' : (isAISpeaking ? '#60a5fa' : '#94a3b8');
          }
          if (orb) {
            if (isAISpeaking) {
              orb.className = 'orb speaking';
              orb.innerText = '🗣️';
            } else if (isConnected) {
              orb.className = 'orb';
              orb.innerText = '👂';
            } else {
              orb.className = 'orb paused';
              orb.innerText = '⏸️';
            }
          }
          if (statusTitle) {
            statusTitle.innerText = isAISpeaking ? 'AI Speaking...' : (isConnected ? 'Listening to Room...' : 'Microphone Idle');
          }
          if (statusSub) {
            statusSub.innerText = isAISpeaking ? 'Click Total Pause to stop speech' : (isConnected ? 'Click Stop Mic to pause' : 'Click Start Listening to talk');
          }
        }
      });
    }

    async function toggleTotalPause() {
      if (!isTotalPaused) {
        // ACTIVATE TOTAL PAUSE: No AI talk, no listening
        isTotalPaused = true;
        isManualPaused = true;
        isConnected = false;
        isAISpeaking = false;

        // Stop microphone
        stopMic();

        // Stop browser preview audio
        if (currentPreviewAudio) {
          try { currentPreviewAudio.pause(); currentPreviewAudio.currentTime = 0; } catch (e) {}
        }

        updateTotalPauseUI(true);
        showToast('🛑 TOTAL PAUSE: AI Muted & Microphone Off.');

        // Signal local and remote server to halt audio playback & disable AI voice output
        const payload = JSON.stringify({ total_pause: true });
        const headers = { 'Content-Type': 'application/json' };
        try {
          fetch('http://127.0.0.1:8766/api/pause_total', {
            method: 'POST',
            mode: 'cors',
            headers: headers,
            body: payload
          }).catch(() => {
            fetch('/api/pause_total', { method: 'POST', headers: headers, body: payload }).catch(() => {});
          });
        } catch (e) {
          fetch('/api/pause_total', { method: 'POST', headers: headers, body: payload }).catch(() => {});
        }
      } else {
        // RESUME: Re-enable AI talk
        isTotalPaused = false;
        isManualPaused = true; // Mic remains idle until user clicks Listen

        updateTotalPauseUI(false);
        showToast('▶ Voice Resumed. Scanning chats for missed replies...');

        const payload = JSON.stringify({ total_pause: false });
        const headers = { 'Content-Type': 'application/json' };
        try {
          fetch('http://127.0.0.1:8766/api/pause_total', {
            method: 'POST',
            mode: 'cors',
            headers: headers,
            body: payload
          }).catch(() => {
            fetch('/api/pause_total', { method: 'POST', headers: headers, body: payload }).catch(() => {});
          });
        } catch (e) {
          fetch('/api/pause_total', { method: 'POST', headers: headers, body: payload }).catch(() => {});
        }
      }
    }

    function stopSpeech() {
      if (currentPreviewAudio) {
        try { currentPreviewAudio.pause(); currentPreviewAudio.currentTime = 0; } catch (e) {}
      }
      if (window.speechSynthesis) {
        try { window.speechSynthesis.cancel(); } catch (e) {}
      }

      isAISpeaking = false;
      lastAISpeechEndTime = Date.now();

      const payload = JSON.stringify({ stop: true });
      const headers = { 'Content-Type': 'application/json' };
      try {
        fetch('http://127.0.0.1:8766/api/stop', {
          method: 'POST',
          mode: 'cors',
          headers: headers,
          body: payload
        }).catch(() => {
          fetch('/api/stop', { method: 'POST', headers: headers, body: payload }).catch(() => {});
        });
      } catch (e) {
        fetch('/api/stop', { method: 'POST', headers: headers, body: payload }).catch(() => {});
      }
    }

    let isMicActive = false;
    let isStartingMic = false;
    let isAISpeaking = false;
    let lastAISpeechEndTime = 0;
    let currentAISpeakingText = '';
    let lastAISpeakingText = '';

    // Robust Echo Shield: Prevent AI's own voice from transcribing into the draft
    function isEchoOfAI(heardText) {
      if (!heardText) return false;
      
      const recentlySpoken = (Date.now() - lastAISpeechEndTime) < 3000;
      if (!isAISpeaking && !recentlySpoken) return false;
      
      const textToCompare = (currentAISpeakingText || lastAISpeakingText || '').toLowerCase().replace(/[^\w\s]/g, '').trim();
      const cleanHeard = heardText.toLowerCase().replace(/[^\w\s]/g, '').trim();
      
      if (!cleanHeard || !textToCompare) return false;

      if (textToCompare === cleanHeard) return true;

      // Only allow raw substring matching if it makes up a substantial chunk of the speech (>= 50%)
      // This prevents short user replies (like "send it now") from being blocked if the AI just said them.
      if (textToCompare.length > 15 && cleanHeard.length > 10) {
        if (textToCompare.includes(cleanHeard)) {
          if (cleanHeard.length >= textToCompare.length * 0.5) return true;
        }
        if (cleanHeard.includes(textToCompare)) {
          if (textToCompare.length >= cleanHeard.length * 0.5) return true;
        }
      }

      return false;
    }

    function getOrCreateSpeechRecognition() {
      if (recognition) return recognition;

      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SpeechRecognition) {
        showToast('⚠️ Your browser does not support Voice Recognition. Please use Chrome or Edge.');
        return null;
      }

      const rec = new SpeechRecognition();
      rec.continuous = true;
      rec.interimResults = true;
      rec.lang = 'en-GB';

      rec.onstart = () => {
        isMicActive = true;
        isStartingMic = false;
        if (!isAISpeaking) setOrbState('listening');
      };

      rec.onspeechstart = () => {
        if (isAISpeaking) {
          stopSpeech();
          isAISpeaking = false;
        }
      };

      rec.onresult = (event) => {
        if (!isConnected || isTotalPaused) return;

        if (isAISpeaking) {
          stopSpeech();
          isAISpeaking = false;
        }

        let latestFinal = '';
        let currentInterim = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          const res = event.results[i];
          const text = res[0].transcript;

          if (res.isFinal) {
            latestFinal = text.trim();
          } else {
            currentInterim += text;
          }
        }

        // Echo Shield: If the microphone heard the laptop speaker playing AI output, discard it
        if (latestFinal && isEchoOfAI(latestFinal)) {
          console.log('[ECHO-SHIELD] Discarded speaker echo (final):', latestFinal);
          return;
        }
        if (currentInterim && isEchoOfAI(currentInterim)) {
          console.log('[ECHO-SHIELD] Discarded speaker echo (interim):', currentInterim);
          return;
        }

        interimText = currentInterim;
        setOrbState('hearing');
        const title = document.getElementById('statusTitle'); if (title) title.innerText = 'Hearing Speech...';

        if (latestFinal) {
          processUtterance(latestFinal);
        } else {
          renderDraftDisplay();
          resetSilenceTimer();
        }
      };

      rec.onerror = (e) => {
        console.log('STT Event:', e.error);
        isStartingMic = false;
        if (e.error === 'not-allowed') {
          alert('Microphone blocked or permission denied.\n\n1. Click the lock icon in the address bar and select "Allow" for Microphone.\n\n2. If you are using the Floating Pop-Up Window, you MUST click "Start Listening" on the main website window first, as browsers block microphones from starting inside pop-ups.');
          stopMic();
        } else if (e.error === 'network' || e.error === 'audio-capture') {
          showToast('⚠️ Mic warning: ' + e.error);
        } else if (e.error !== 'no-speech' && e.error !== 'aborted') {
          showToast('⚠️ Mic error: ' + e.error);
        }
      };

      rec.onend = () => {
        isMicActive = false;
        isStartingMic = false;
        if (isConnected && !isTotalPaused) {
          setTimeout(() => {
            if (isConnected && !isTotalPaused && !isMicActive && !isStartingMic) {
              try {
                isStartingMic = true;
                rec.start();
              } catch (e) {
                isStartingMic = false;
                isConnected = false;
                if (!isAISpeaking) setOrbState('paused');
                const docs = [document];
                if (window.documentPictureInPicture && window.documentPictureInPicture.window && !window.documentPictureInPicture.window.closed) {
                  try { docs.push(window.documentPictureInPicture.window.document); } catch (e) {}
                }
                docs.forEach(doc => {
                  const statusTitle = Document.prototype.getElementById.call(doc, 'statusTitle');
                  if (statusTitle) statusTitle.innerText = 'Microphone Paused';
                });
              }
            }
          }, 40);
        } else {
          if (!isAISpeaking) setOrbState('paused');
        }
      };

      recognition = rec;
      return rec;
    }

    function toggleMicOnly() {
      if (isTotalPaused) {
        showToast('System is in Total Pause. Click Resume to enable.');
        return;
      }
      if (isConnected && !isMicActive && !isStartingMic) {
        isConnected = false;
      }
      if (isConnected) {
        stopMic();
        showToast('⏹️ Microphone stopped.');
      } else {
        startMic();
      }
    }

    function handleOrbClick() {
      if (isTotalPaused) {
        toggleTotalPause();
        return;
      }
      if (isConnected && !isMicActive && !isStartingMic) {
        isConnected = false;
      }
      if (!isConnected) {
        startMic();
      } else {
        stopMic();
      }
    }

    function setOrbState(state) {
      if (isTotalPaused) {
        updateTotalPauseUI(true);
        return;
      }
      const docs = [document];
      if (window.documentPictureInPicture && window.documentPictureInPicture.window && !window.documentPictureInPicture.window.closed) {
        try { docs.push(window.documentPictureInPicture.window.document); } catch (e) {}
      }

      docs.forEach(doc => {
        const orb = Document.prototype.getElementById.call(doc, 'orbEl');
        const sttBadge = Document.prototype.getElementById.call(doc, 'sttBadge');
        const btnMic = Document.prototype.getElementById.call(doc, 'btnMicToggle');

        if (orb) {
          if (state === 'hearing') {
            orb.className = 'orb hearing';
            orb.innerText = '👂';
          } else if (state === 'listening') {
            orb.className = 'orb';
            orb.innerText = '👂';
          } else if (state === 'speaking') {
            orb.className = 'orb speaking';
            orb.innerText = '🗣️';
          } else if (state === 'paused') {
            orb.className = 'orb paused';
            orb.innerText = '⏸️';
          }
        }

        if (btnMic) {
          if (state === 'listening' || state === 'hearing') {
            btnMic.innerText = '⏹️ Stop Mic';
            btnMic.style.color = '#fbbf24';
            btnMic.style.background = 'rgba(245, 158, 11, 0.18)';
            btnMic.style.borderColor = 'rgba(245, 158, 11, 0.4)';
          } else {
            btnMic.innerText = '🎙️ Start Listening';
            btnMic.style.color = '#34d399';
            btnMic.style.background = 'rgba(16, 185, 129, 0.18)';
            btnMic.style.borderColor = 'rgba(16, 185, 129, 0.4)';
          }
        }

        if (sttBadge) {
          if (state === 'speaking') {
            sttBadge.innerText = '● AI Speaking';
            sttBadge.style.color = '#60a5fa';
          } else if (state === 'listening' || state === 'hearing') {
            sttBadge.innerText = '● Listening';
            sttBadge.style.color = '#34d399';
          } else {
            sttBadge.innerText = '● Idle';
            sttBadge.style.color = '#94a3b8';
          }
        }
      });
    }

    function toggleOrb() {
      handleOrbClick();
    }

    function toggleMic() {
      toggleMicOnly();
    }

    function pauseAI() {
      toggleTotalPause();
    }

    function startMic() {
      if (isTotalPaused) {
        showToast('System is in Total Pause. Click Resume to enable.');
        return;
      }

      // Hard Reset: If the user manually clicks Start, destroy the old instance to clear any corrupted browser state
      if (recognition) {
        try { recognition.abort(); } catch(e){}
        recognition = null;
        isMicActive = false;
        isStartingMic = false;
      }

      const rec = getOrCreateSpeechRecognition();
      if (rec && !isMicActive && !isStartingMic) {
        try {
          isStartingMic = true;
          rec.start();
        } catch (e) {
          isStartingMic = false;
          isConnected = false;
          setOrbState('paused');
          const docs = [document];
          if (window.documentPictureInPicture && window.documentPictureInPicture.window && !window.documentPictureInPicture.window.closed) {
            try { docs.push(window.documentPictureInPicture.window.document); } catch (e) {}
          }
          docs.forEach(doc => {
            const statusTitle = Document.prototype.getElementById.call(doc, 'statusTitle');
            if (statusTitle) statusTitle.innerText = 'Microphone Paused';
          });
          showToast('⚠️ Mic start failed. Please click again.');
          return;
        }
      }

      stopSpeech();
      isManualPaused = false;
      isConnected = true;
      lastAISpeechEndTime = 0;

      const docs = [document];
      if (window.documentPictureInPicture && window.documentPictureInPicture.window && !window.documentPictureInPicture.window.closed) {
        try { docs.push(window.documentPictureInPicture.window.document); } catch (e) {}
      }
      docs.forEach(doc => {
        const statusTitle = Document.prototype.getElementById.call(doc, 'statusTitle');
        const statusSub = Document.prototype.getElementById.call(doc, 'statusSub');
        if (statusTitle) statusTitle.innerText = 'Listening for Voice...';
        if (statusSub) statusSub.innerText = 'Talk naturally • Click Stop Mic when done';
      });
      setOrbState('listening');
      showToast('👂 Listening to room! Speak freely.');
    }

    function stopMic() {
      isConnected = false;
      isStartingMic = false;
      isMicActive = false;
      if (silenceTimer) {
        clearTimeout(silenceTimer);
        silenceTimer = null;
      }
      if (silenceCountdownInterval) {
        clearInterval(silenceCountdownInterval);
        silenceCountdownInterval = null;
      }

      if (recognition) {
        try { recognition.abort(); } catch (e) {}
        try { recognition.stop(); } catch (e) {}
      }

      setOrbState('paused');
      const docs = [document];
      if (window.documentPictureInPicture && window.documentPictureInPicture.window && !window.documentPictureInPicture.window.closed) {
        try { docs.push(window.documentPictureInPicture.window.document); } catch (e) {}
      }
      docs.forEach(doc => {
        const statusTitle = Document.prototype.getElementById.call(doc, 'statusTitle');
        const statusSub = Document.prototype.getElementById.call(doc, 'statusSub');
        if (!isTotalPaused) {
          if (statusTitle) statusTitle.innerText = 'Microphone Idle';
          if (statusSub) statusSub.innerText = 'Click Ear or Start Listening to talk';
        }
      });
    }

    function initSpeechRecognition() {
      return getOrCreateSpeechRecognition();
    }

    function adaptSpeechText(rawText) {
      if (!rawText || !rawText.trim()) return rawText;
      let text = rawText.trim();

      const phoneticRules = [
        // Regional Dialect & Accent Phonetic Normalization
        [/\bversal\s+length\b/gi, "Vercel link"],
        [/\bversal\s+link\b/gi, "Vercel link"],
        [/\bversal\b/gi, "Vercel"],
        [/\bgerman\s+i\b/gi, "Gemini"],
        [/\bgerman\s+eye\b/gi, "Gemini"],
        [/\bgermany\b/gi, "Gemini"],
        [/\boil\s+budget\b/gi, "Orb widget"],
        [/\ball\s+budget\b/gi, "Orb widget"],
        [/\borb\s+budget\b/gi, "Orb widget"],
        [/\bpolicy\s+jesus\b/gi, "Polish feature"],
        [/\bthe\s+policy\b/gi, "the Polish"],
        [/\blassa\s+version\b/gi, "lighter version"],
        [/\bsans\s+better\b/gi, "send button"],
        [/\bsans\s+button\b/gi, "send button"],
        [/\bsand\s+button\b/gi, "send button"],
        [/\bfor\s+spots\b/gi, "voice box"],
        [/\bfor\s+a\s+spots\b/gi, "voice box"],
        [/\bthem\s+for\s+a\s+spots\b/gi, "the voice box"],
        [/\bvoice\s+box\s+type\b/gi, "voice box"],
        [/\blunch\s+pack\b/gi, "launchpad"],
        [/\blunch\s+pad\b/gi, "launchpad"],
        [/\bdex\s+builder\b/gi, "dexBuilder"],
        [/\bapk\s+s\b/gi, "APKs"],
        [/\bapk\.s\b/gi, "APKs"],
        [/\bsquash\s+is\b/gi, "squashes"],
        [/\binto\s+the\s+herds\b/gi, "in terms of this"],
        [/\bautosense\b/gi, "auto-sends"],
        [/\bauto\s+sense\b/gi, "auto-sends"],
        [/\bautosending\b/gi, "auto-sending"],

        // Voice commands & UI
        [/\bmassage[s]?\s+cute\b/gi, "messages queued"],
        [/\bmassage[s]?\s+queue[d]?\b/gi, "messages queued"],
        [/\bfull\s+massage\b/gi, "full message"],
        [/\bsee\s+the\s+massage\b/gi, "see the message"],
        [/\bthe\s+massage\b/gi, "the message"],
        [/\ba\s+massage\b/gi, "a message"],
        [/\bmassages\b/gi, "messages"],
        [/\bsend\s+in\s+a\s+massive\b/gi, "send in a message"],
        [/\bsending\s+a\s+massive\b/gi, "sending a message"],
        [/\bsound\s+sander\b/gi, "send it"],
        [/\bsand\s+through\b/gi, "send through"],
        [/\bsub[- ]through\b/gi, "send through"],
        [/\bsand\s+it\b/gi, "send it"],
        [/\bsand\s+say\b/gi, "send, say"],
        [/\bsand\s+say\s+go\b/gi, "send, say go"],
        [/\bsaying\s+sand\b/gi, "saying send"],
        [/\binstead\s+of\s+saying\s+sand\b/gi, "instead of saying send"],
        [/\bsand\s+now\b/gi, "send now"],
        [/\bpleas\s+sand\b/gi, "please send"],
        [/^\bcasting\b$/gi, "testing"],
        [/\bcasting\s+casting\b/gi, "testing testing"],
        [/\bfor\s+so\s+for\s+up\b/gi, "first off"],
        [/\bso\s+for\s+up\b/gi, "so first off"],
        [/\bfor\s+up\b/gi, "first off"],

        // UI Visuals & Elements
        [/\bblack\s+tax\b/gi, "black text"],
        [/\bwhite\s+tax\b/gi, "white text"],
        [/\btax\s+box\b/gi, "text box"],
        [/\bwhite\s+background\s+black\s+tax\b/gi, "white background black text"],
        [/\bvoice\s+box\s+type\b/gi, "voice box"],
        [/\bthem\s+for\s+a\s+spots\b/gi, "the voice box"],
        [/\bfor\s+a\s+spots\b/gi, "voice box"],
        [/\bweirding\b/gi, "wording"],
        [/\bcontacts\s+of\b/gi, "context of"],
        [/\bwithin\s+the\s+contacts\b/gi, "within the context"],

        // Antigravity & Orb
        [/\banti\s+gravity\b/gi, "Antigravity"],
        [/\borb\s+isnot\b/gi, "Orb is not"],
        [/\borb\s+ai\b/gi, "Orb AI"],
        [/\borb\s+voice\b/gi, "Orb voice"],

        // Chat / Charts / Traps confusion
        [/\bbetween\s+charts\b/gi, "between chats"],
        [/\bdifferent\s+charts\b/gi, "different chats"],
        [/\bongoing\s+charts\b/gi, "ongoing chats"],
        [/\bdifferent\s+traps\b/gi, "different chats"],
        [/\bwrong\s+trapped\b/gi, "wrong chat"],
        [/\bwrong\s+trap\b/gi, "wrong chat"],
        [/\bcertain\s+trap\b/gi, "certain chat"],
        [/\bjump\s+between\s+a\s+chart\b/gi, "jump between a chat"],
        [/\bjump\s+between\s+charts\b/gi, "jump between chats"],
        [/\bin\s+this\s+chart\b/gi, "in this chat"],
        [/\bopen\s+chart\b/gi, "open chat"],
        [/\bacross\s+all\s+tracks\b/gi, "across all chats"],

        // Accounting / HMRC / Banking Context
        [/\b(h\s*m\s*r\s*c|age\s*m\s*r\s*c|h\s*mark)\b/gi, "HMRC"],
        [/\bfilling\s+accounts\b/gi, "filing accounts"],
        [/\bfilling\s+dormant\b/gi, "filing dormant"],
        [/\bdormant\s+a\b/gi, "dormant accounts"],
        [/\bdormant\s+account[s]?\b/gi, "dormant accounts"],
        [/\b(v\s*a\s*t|that\s+return|fat\s+return)\b/gi, "VAT"],
        [/\b(pay\s*e|p\s*a\s*y\s*e)\b/gi, "PAYE"],
        [/\b(cooperation\s+tax|corporate\s+tags)\b/gi, "corporation tax"],
        [/\b(company\s+house|company's\s+house)\b/gi, "Companies House"],
        [/\b(tied|tight)\s+bank\b/gi, "Tide bank"],
        [/\b(tied|tight)\s+account\b/gi, "Tide account"],
        [/\b(tied|tight)\s+statements\b/gi, "Tide statements"],
        [/\bmanzo\s+bank\b/gi, "Monzo bank"],
        [/\bmanzo\b/gi, "Monzo"],
        [/\brevolute\b/gi, "Revolut"],
        [/\bsterling\s+bank\b/gi, "Starling bank"],
        [/\bsouth\s+assessment\b/gi, "self assessment"],
        [/\b(you\s*t\s*r|u\s*t\s*r)\b/gi, "UTR"],
        [/\bcore\s+market\s+goods\b/gi, "Coremarket Goods"],
        [/\bcoremarketgoods\b/gi, "Coremarket Goods"],
        [/\bthermo\s+retreat[s]?\b/gi, "Thermo Retreats"],
        [/\bkelvin\b/gi, "Kevin"],
        [/\bdavid\s+ends\b/gi, "dividends"],
        [/\bbook\s+keeping\b/gi, "bookkeeping"],
        [/\bbalance\s+chic\b/gi, "balance sheet"],
        [/\bp\s+and\s+l\b/gi, "P&L"],

        // Common Sense Grammar & Words
        [/\b88d\s+adhd\b/gi, "ADHD"],
        [/\b88d\b/gi, "ADHD"],
        [/\bshort\s+hair\b/gi, "shorter"],
        [/\bin\s+humans\b/gi, "in human terms"],
        [/\bcommunicaing\b/gi, "communicating"],
        [/\bunderdtanding\b/gi, "understanding"],
        [/\bhavnt\b/gi, "haven't"],
        [/\bpronounciations\b/gi, "pronunciations"],
        [/\bcommon\s+sence\b/gi, "common sense"],
        [/\binsentences\b/gi, "in sentences"]
      ];

      phoneticRules.forEach(([pattern, rep]) => {
        text = text.replace(pattern, rep);
      });

      // Contextual verb repairs ('sand' -> 'send' when preceded by pronouns/verbs)
      text = text.replace(/\b(i|we|you|they|to|please|can\s+you|just|will|could|should|would)\s+sand\b/gi, "$1 send");
      text = text.replace(/\bsand\s+(me|you|it|that|this|them|him|her|through|now|to|into|out)\b/gi, "send $1");
      text = text.replace(/\bsand\s+(a|an|the)\s+(message|prompt|chat|update|request)\b/gi, "send $1 $2");

      // Common contractions & pronoun repairs
      text = text.replace(/\bi\b/g, "I");
      text = text.replace(/\bi'm\b/gi, "I'm");
      text = text.replace(/\bi've\b/gi, "I've");
      text = text.replace(/\bi'll\b/gi, "I'll");
      text = text.replace(/\bi'd\b/gi, "I'd");

      // Spacing cleanup
      text = text.replace(/\s+/g, ' ').trim();

      // Capitalize first character of sentence
      if (text.length > 0) {
        text = text.charAt(0).toUpperCase() + text.slice(1);
      }

      return text;
    }

    function processUtterance(text) {
      if (!text) return;

      const cleanLower = text.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim();
      const words = cleanLower.split(' ');
      const lastWord = words[words.length - 1] || '';
      const lastTwo = words.slice(-2).join(' ');

      // 1. Read back trigger
      if (cleanLower === 'read it back' || cleanLower === 'read it back to me' || cleanLower === 'repeat that' || cleanLower.endsWith('read it back')) {
        renderDraftDisplay();
        readDraftBack();
        return;
      }

      // 2. Clear trigger
      if (cleanLower === 'clear draft' || cleanLower === 'clear' || cleanLower === 'start over' || cleanLower === 'delete draft') {
        clearDraft(true);
        return;
      }

      // 3. Smart Send Matcher: ONLY intentional send phrases (no accidental single-word triggers)
      const sendPhrases = ['send now', 'send it', 'send message', 'shoot it', 'send that', 'send draft', 'dispatch message'];
      const isPhraseMatch = sendPhrases.includes(lastTwo) || (lastWord === 'send' && words.length <= 2);

      if (isPhraseMatch) {
        const wordsToDrop = lastTwo.includes('send') ? 2 : 1;
        const textWords = text.trim().split(/\s+/);
        const remainingWords = textWords.slice(0, -wordsToDrop);
        const contentBefore = remainingWords.join(' ').trim();

        if (contentBefore) {
          currentDraft = (currentDraft ? currentDraft + ' ' : '') + contentBefore;
        }

        currentDraft = adaptSpeechText(currentDraft);
        renderDraftDisplay();
        showToast('🚀 Send trigger recognized!');
        sendDraftNow();
        return;
      }

      // Normal speech: adapt in context, then append
      isDraftPolished = false;
      currentDraft = (currentDraft ? currentDraft + ' ' : '') + text;
      currentDraft = adaptSpeechText(currentDraft);
      interimText = '';
      renderDraftDisplay();
      resetSilenceTimer();
    }

    function resetSilenceTimer() {
      if (silenceTimer) clearTimeout(silenceTimer);
      if (silenceCountdownInterval) {
        clearInterval(silenceCountdownInterval);
        silenceCountdownInterval = null;
      }

      // If draft is polished or manually edited, DO NOT auto-send — user is reviewing/editing!
      if (isDraftPolished) {
        const docs = [document];
        if (window.documentPictureInPicture && window.documentPictureInPicture.window && !window.documentPictureInPicture.window.closed) {
          try { docs.push(window.documentPictureInPicture.window.document); } catch (e) {}
        }
        docs.forEach(doc => {
          const statusEl = Document.prototype.getElementById.call(doc, 'draftStatus');
          if (statusEl) statusEl.innerText = '✨ Polished — Review & click "Send Now"';
        });
        return;
      }

      // Hands-free mode: Generous 12-second pause buffer with live countdown
      let secondsLeft = 12;
      const docs = [document];
      if (window.documentPictureInPicture && window.documentPictureInPicture.window && !window.documentPictureInPicture.window.closed) {
        try { docs.push(window.documentPictureInPicture.window.document); } catch (e) {}
      }

      const updateDraftStatus = (txt) => {
        docs.forEach(doc => {
          const statusEl = Document.prototype.getElementById.call(doc, 'draftStatus');
          if (statusEl) statusEl.innerText = txt;
        });
      };

      updateDraftStatus(`⏳ Auto-sending in ${secondsLeft}s (or click Send)...`);

      silenceCountdownInterval = setInterval(() => {
        if (isDraftPolished) {
          clearInterval(silenceCountdownInterval);
          silenceCountdownInterval = null;
          return;
        }
        secondsLeft -= 1;
        if (secondsLeft > 0) {
          updateDraftStatus(`⏳ Auto-sending in ${secondsLeft}s (or click Send)...`);
        } else {
          clearInterval(silenceCountdownInterval);
          silenceCountdownInterval = null;
        }
      }, 1000);

      silenceTimer = setTimeout(() => {
        if (silenceCountdownInterval) {
          clearInterval(silenceCountdownInterval);
          silenceCountdownInterval = null;
        }
        if (isDraftPolished) {
          return; // Polished draft never auto-sends
        }
        if (currentDraft.trim()) {
          showToast('⚡ Silence elapsed — Auto-sending...');
          sendDraftNow();
        } else {
          updateDraftStatus('Continuous Listening');
        }
      }, 12000);
    }

    function getDraftText() {
      // 1. Check currentDraft & interimText variables
      let t = (currentDraft + (interimText ? ' ' + interimText : '')).trim();
      if (t) return t;

      // 2. Check DOM draftBox across main tab and PiP overlay
      const docs = [document];
      if (window.documentPictureInPicture && window.documentPictureInPicture.window && !window.documentPictureInPicture.window.closed) {
        try { docs.push(window.documentPictureInPicture.window.document); } catch (e) {}
      }
      for (const d of docs) {
        try {
          const box = Document.prototype.getElementById.call(d, 'draftBox');
          if (box) {
            let text = (box.innerText || box.textContent || '').trim();
            text = text.replace(/Speak your message out loud\.\.\./gi, '')
                       .replace(/Click the green button above and start talking\.\.\./gi, '')
                       .trim();
            if (text) return text;
          }
        } catch (e) {}
      }
      return '';
    }

    function handleDraftBoxInput(el) {
      const text = (el ? (el.innerText || el.textContent || '') : '').replace(/Speak your message out loud\.\.\./gi, '').trim();
      currentDraft = text;
      interimText = '';
      isDraftPolished = true; // Freeze auto-send while user types/edits

      if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
      if (silenceCountdownInterval) { clearInterval(silenceCountdownInterval); silenceCountdownInterval = null; }

      const docs = [document];
      if (window.documentPictureInPicture && window.documentPictureInPicture.window && !window.documentPictureInPicture.window.closed) {
        try { docs.push(window.documentPictureInPicture.window.document); } catch (e) {}
      }
      docs.forEach(doc => {
        const statusEl = Document.prototype.getElementById.call(doc, 'draftStatus');
        if (statusEl) statusEl.innerText = '✍️ Editing Draft — Click "Send Now" when ready';
        const box = Document.prototype.getElementById.call(doc, 'draftBox');
        if (box && box !== el) {
          if (!text) {
            box.innerHTML = '<span class="placeholder-text" style="color: #64748b !important; font-weight: 500;">Speak your message out loud...</span>';
          } else {
            box.innerHTML = `<span style="color: #000000 !important; font-weight: 700;">${escapeHtml(text)}</span>`;
          }
        }
      });
    }

    function handleDraftBoxKey(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendDraftNow();
      }
    }

    function escapeHtml(str) {
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
    }

    let isPolishing = false;
    async function polishDraft() {
      let rawText = getDraftText();
      if (!rawText) {
        showToast('Draft is empty. Speak or type something first to polish!');
        return;
      }
      if (isPolishing) return;
      isPolishing = true;
      isDraftPolished = true; // Lock in polish mode so timer NEVER auto-sends!

      // Stop microphone so ambient noise/speech never resets polish state or auto-sends
      stopMic();

      // Cancel all auto-send timers permanently
      if (silenceTimer) {
        clearTimeout(silenceTimer);
        silenceTimer = null;
      }
      if (silenceCountdownInterval) {
        clearInterval(silenceCountdownInterval);
        silenceCountdownInterval = null;
      }

      const docs = [document];
      if (window.documentPictureInPicture && window.documentPictureInPicture.window && !window.documentPictureInPicture.window.closed) {
        try { docs.push(window.documentPictureInPicture.window.document); } catch (e) {}
      }

      docs.forEach(doc => {
        const btn = Document.prototype.getElementById.call(doc, 'btnPolish');
        if (btn) {
          btn.innerHTML = '<span>⏳</span> Polishing...';
          btn.style.opacity = '0.75';
        }
        const statusEl = Document.prototype.getElementById.call(doc, 'draftStatus');
        if (statusEl) statusEl.innerText = '✨ AI Polishing speech in context...';
      });

      showToast('✨ Polishing speech with contextual AI...');

      // Extract active project/chat title and surrounding conversation turns
      let activeChatName = '';
      docs.forEach(doc => {
        if (!activeChatName) {
          const el = Document.prototype.getElementById.call(doc, 'activeChatTitleText') ||
                     Document.prototype.getElementById.call(doc, 'activeChatTitleText');
          if (el && el.innerText && el.innerText.trim() && el.innerText.trim() !== 'Orb') {
            activeChatName = el.innerText.trim();
          }
        }
      });
      if (!activeChatName) activeChatName = 'Orb AI Assistant';

      let recentDialogueSummary = '';
      if (Array.isArray(lastRenderedMessages) && lastRenderedMessages.length > 0) {
        const recentTurns = lastRenderedMessages.slice(-6);
        recentDialogueSummary = recentTurns.map(m => {
          const role = m.role === 'user' ? 'User' : 'Assistant';
          const text = (m.text || '').replace(/\s+/g, ' ').trim();
          return `${role}: ${text.length > 280 ? text.slice(0, 280) + '...' : text}`;
        }).join('\n');
      } else if (Array.isArray(knownAITexts) && knownAITexts.length > 0) {
        const lastAIText = knownAITexts[knownAITexts.length - 1];
        if (lastAIText) {
          recentDialogueSummary = `Assistant: ${lastAIText.slice(0, 300)}`;
        }
      }

      let contextBlock = '';
      if (recentDialogueSummary || (activeChatName && activeChatName !== 'Orb AI Assistant')) {
        contextBlock = `CURRENT CONVERSATION CONTEXT:\nProject / Chat: ${activeChatName}\n${recentDialogueSummary ? 'Recent Dialogue:\n' + recentDialogueSummary + '\n\n' : ''}`;
      }

      async function fetchPolish(text) {
        // 1. Direct Google Gemini 3.5 Flash API call (Ultra-fast ~300ms with full contextual understanding)
        try {
          const defaultKey = atob("QVEuQWI4Uk42TGhSSUo4WF9QT2JkMWozaXVYQm9JSkNOVjRuMzBrakMyVXh6RzZZQVU4U2c=");
          const gemKey = localStorage.getItem('gemini_api_key') || window.__GEMINI_KEY__ || defaultKey;
          if (gemKey) {
            const modelsToTry = ["gemini-3.5-flash", "gemini-3.5-flash-lite"];
            const systemPrompt = "You are an elite, context-aware AI Speech Polishing & Thought Articulation Engine (like Google Gemini / Gmail 'Help Me Write' / Grammarly Go / Whisper Accent-Aware Engine). Actively REWRITE and ELEVATE the user's spoken thoughts into crisp, articulate, high-impact, professional, and natural English while seamlessly maintaining the context of the ongoing conversation.\n\nACCENT & PHONETIC RECOGNITION RULES:\n1. Interpret diverse regional accents (British, Irish, Scottish, Northern English, American, Canadian, Australian, etc.).\n2. Intelligently rectify common Speech-To-Text phonetic blurs, homophones, and misheard technical/development terms based on the conversational context (e.g. misheard 'versal' -> 'Vercel', 'German I' -> 'Gemini', 'sans better' -> 'send button', 'oil budget' / 'all budget' -> 'Orb widget', 'for spots' -> 'voice box', 'trapped' -> 'chat', 'dex builder' -> 'dexBuilder', 'apk s' -> 'APKs', 'tax' -> 'text', 'massage' -> 'message', 'policy Jesus' -> 'polish feature', 'lassa version' -> 'lesser version', 'balance chic' -> 'balance sheet').\n\nCONVERSATIONAL CONTEXT INTELLIGENCE:\n1. Analyze the surrounding conversation context (active project/chat topic, recent assistant messages, recent user turns) to understand what the user is referring to.\n2. Seamlessly resolve pronouns and references (e.g. 'it', 'that', 'the second one', 'the button') into precise, contextually clear phrasing.\n3. Streamline rambling phrases, eliminate filler words ('like', 'you know', 'um', 'ah', 'basically', 'so yeah'), and enhance vocabulary and structure while preserving the user's core intent.\n4. Return ONLY the polished rewrite with no quotes, explanations, or preamble.";

            const contentText = contextBlock
              ? `${contextBlock}USER'S SPOKEN DRAFT TO REWRITE & POLISH:\n"${text}"`
              : text;

            const gemBody = {
              system_instruction: {
                parts: [{ text: systemPrompt }]
              },
              contents: [{
                parts: [{ text: contentText }]
              }],
              generationConfig: {
                maxOutputTokens: 2048,
                temperature: 0.3
              }
            };

            for (const m of modelsToTry) {
              try {
                const gemUrl = `https://generativelanguage.googleapis.com/v1beta/models/${m}:generateContent?key=${gemKey}`;
                const gRes = await fetch(gemUrl, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify(gemBody)
                });
                const gData = await gRes.json();
                const cand = gData?.candidates?.[0]?.content?.parts?.[0]?.text?.trim();
                if (cand) {
                  let clean = cand;
                  if ((clean.startsWith('"') && clean.endsWith('"')) || (clean.startsWith("'") && clean.endsWith("'"))) {
                    clean = clean.slice(1, -1).trim();
                  }
                  if (clean) return clean;
                }
              } catch (errM) {
                console.warn(`[GEMINI-${m}-FAIL]`, errM);
              }
            }
          }
        } catch(e) {
          console.warn('[POLISH-GEMINI-DIRECT-ERR]', e);
        }

        // 2. Try server endpoint (/api/polish_text) with rich contextual payload
        try {
          const endpoints = ['/api/polish_text', 'http://127.0.0.1:8766/api/polish_text'];
          const payload = {
            text: text,
            context: contextBlock,
            chat_title: activeChatName
          };
          for (const ep of endpoints) {
            try {
              const r = await fetch(ep, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
              });
              const d = await r.json();
              if (d && d.polished && d.polished !== text) return d.polished;
            } catch(e) {}
          }
        } catch(e) {}

        // 3. Fallback to offline phonetic & accent adapter
        return adaptSpeechText(text);
      }

      try {
        const polished = await fetchPolish(rawText);
        if (polished) {
          currentDraft = polished;
          interimText = '';

          docs.forEach(doc => {
            const box = Document.prototype.getElementById.call(doc, 'draftBox');
            if (box) {
              box.innerHTML = `<span style="color: #000000 !important; font-weight: 700;">${escapeHtml(polished)}</span>`;
              box.style.borderColor = '#10b981';
              box.style.boxShadow = '0 0 16px rgba(16, 185, 129, 0.4)';
              box.scrollTop = box.scrollHeight;
              setTimeout(() => {
                box.style.borderColor = '#3b82f6';
                box.style.boxShadow = 'none';
              }, 2200);
            }
          });

          showToast('✨ Polished in conversation context!');
        }
      } catch (err) {
        console.error('Polish error:', err);
        currentDraft = adaptSpeechText(rawText);
        renderDraftDisplay();
        showToast('✨ Speech adapted!');
      } finally {
        docs.forEach(doc => {
          const btn = Document.prototype.getElementById.call(doc, 'btnPolish');
          if (btn) {
            btn.innerHTML = '<span id="polishIcon">✨</span> Polish';
            btn.style.opacity = '1';
          }
          const statusEl = Document.prototype.getElementById.call(doc, 'draftStatus');
          if (statusEl) statusEl.innerText = '✨ Polished — Review & click "Send Now"';
        });
        isPolishing = false;
      }
    }

    function renderDraftDisplay() {
      const docs = [document];
      if (window.documentPictureInPicture && window.documentPictureInPicture.window && !window.documentPictureInPicture.window.closed) {
        try { docs.push(window.documentPictureInPicture.window.document); } catch (e) {}
      }

      docs.forEach(doc => {
        const box = Document.prototype.getElementById.call(doc, 'draftBox');
        if (!box) return;

        const adaptedFinal = currentDraft ? adaptSpeechText(currentDraft) : '';
        const adaptedInterim = interimText ? adaptSpeechText(interimText) : '';

        if (adaptedFinal || adaptedInterim) {
          let html = '';
          if (adaptedFinal) {
            html += `<span style="color: #000000 !important; font-weight: 700;">${escapeHtml(adaptedFinal)}</span>`;
          }
          if (adaptedInterim) {
            html += (html ? ' ' : '') + `<span class="interim-text" style="color: #1d4ed8 !important; font-style: italic; font-weight: 600;">${escapeHtml(adaptedInterim)}</span>`;
          }
          box.innerHTML = html;
          box.scrollTop = box.scrollHeight;
        } else {
          box.innerHTML = '<span class="placeholder-text" style="color: #64748b !important; font-weight: 500;">Speak your message out loud...</span>';
        }
      });
    }

    function readDraftBack() {
      const text = getDraftText();
      if (!text) {
        speakAudio("You haven't spoken or typed any message yet. Go ahead and speak.");
        return;
      }
      speakAudio(`You said: ${text}. Say 'Send' or click Send Now.`);
    }

    function sendDraftNow() {
      if (silenceTimer) {
        clearTimeout(silenceTimer);
        silenceTimer = null;
      }
      if (silenceCountdownInterval) {
        clearInterval(silenceCountdownInterval);
        silenceCountdownInterval = null;
      }
      const rawText = getDraftText();
      const fullText = isDraftPolished ? rawText : adaptSpeechText(rawText);
      if (!fullText || !fullText.trim()) {
        showToast('Draft is empty. Speak or type something first!');
        return;
      }

      showToast('🚀 Sending message to chat...');
      isDraftPolished = false;
      currentDraft = "";
      interimText = "";
      renderDraftDisplay();

      const docs = [document];
      if (window.documentPictureInPicture && window.documentPictureInPicture.window && !window.documentPictureInPicture.window.closed) {
        try { docs.push(window.documentPictureInPicture.window.document); } catch (e) {}
      }
      docs.forEach(doc => {
        const statusEl = Document.prototype.getElementById.call(doc, 'draftStatus');
        if (statusEl) statusEl.innerText = '⏳ Relaying...';
        const orb = Document.prototype.getElementById.call(doc, 'orbEl');
        if (orb) orb.className = 'orb';
      });

      let activeChatName = '';
      docs.forEach(doc => {
        if (!activeChatName) {
          const el = Document.prototype.getElementById.call(doc, 'activeChatTitleText');
          if (el && el.innerText && el.innerText.trim() !== 'Orb') activeChatName = el.innerText.trim();
        }
      });

      const payload = JSON.stringify({ text: fullText, auto_send: true, source: 'app', chat_title: activeChatName });
      const headers = { 'Content-Type': 'application/json' };

      // Dispatch to local relay server (127.0.0.1:8766) which triggers Windows keystroke injection
      fetch('http://127.0.0.1:8766/api/speech_input', {
        method: 'POST',
        headers: headers,
        body: payload,
        mode: 'cors'
      }).then(res => {
        if (!res.ok) throw new Error('Status ' + res.status);
        showToast('✅ Sent directly into Antigravity chat!');
        docs.forEach(doc => {
          const statusEl = Document.prototype.getElementById.call(doc, 'draftStatus');
          if (statusEl) statusEl.innerText = '✅ Relayed to Chat!';
        });
      }).catch((err) => {
        // Fallback to relative URL
        return fetch('/api/speech_input', {
          method: 'POST',
          headers: headers,
          body: payload
        }).then(res => {
          if (!res.ok) throw new Error('Status ' + res.status);
          showToast('✅ Sent directly into Antigravity chat!');
          docs.forEach(doc => {
            const statusEl = Document.prototype.getElementById.call(doc, 'draftStatus');
            if (statusEl) statusEl.innerText = '✅ Relayed to Chat!';
          });
        }).catch(finalErr => {
          showToast('❌ Relay error: Unable to connect to local server on port 8766');
          docs.forEach(doc => {
            const statusEl = Document.prototype.getElementById.call(doc, 'draftStatus');
            if (statusEl) statusEl.innerText = '❌ Failed to connect';
          });
        });
      }).finally(() => {
        setTimeout(() => {
          docs.forEach(doc => {
            const statusEl = Document.prototype.getElementById.call(doc, 'draftStatus');
            if (statusEl) statusEl.innerText = 'Continuous Listening';
          });
        }, 2500);
        pollConversation();
      });
    }

    function clearDraft(spoken=false) {
      if (silenceTimer) {
        clearTimeout(silenceTimer);
        silenceTimer = null;
      }
      if (silenceCountdownInterval) {
        clearInterval(silenceCountdownInterval);
        silenceCountdownInterval = null;
      }
      isDraftPolished = false;
      currentDraft = "";
      interimText = "";
      renderDraftDisplay();
      const docs = [document];
      if (window.documentPictureInPicture && window.documentPictureInPicture.window && !window.documentPictureInPicture.window.closed) {
        try { docs.push(window.documentPictureInPicture.window.document); } catch (e) {}
      }
      docs.forEach(doc => {
        const statusEl = Document.prototype.getElementById.call(doc, 'draftStatus');
        if (statusEl) statusEl.innerText = 'Continuous Listening';
      });
      showToast('Draft cleared');
      if (spoken) speakAudio("Draft cleared.");
    }

    function testVoicePreview() {
      const voiceSelect = document.getElementById('selectVoice');
      const voiceId = voiceSelect.value;
      const p = PERSONAS.find(x => x.id === voiceId) || PERSONAS[0];
      previewPersonaVoice(voiceId, p.name);
    }

    function speakAudio(text) {
      setOrbState('speaking');
      const title = document.getElementById('statusTitle'); if (title) title.innerText = 'Speaking Readout...';

      fetch('/api/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text })
      }).then(() => {
        setTimeout(() => {
          setOrbState(isConnected ? 'listening' : 'paused');
          const title = document.getElementById('statusTitle'); if (title) title.innerText = isConnected ? 'Listening for Voice...' : 'Microphone Paused';
        }, 3500);
      }).catch(() => {
        setOrbState(isConnected ? 'listening' : 'paused');
      });
    }


    async function pollLiveState() {
      try {
        // Always hit local relay server for live state — relative URL won't work from Vercel
        const url = window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost'
          ? '/api/status'
          : 'http://127.0.0.1:8766/api/status';
        const res = await fetch(url);
        const state = await res.json();

        // Hot auto-update floater or page when code updates occur
        if (state.app_version) {
          if (currentAppVersion === null) {
            currentAppVersion = state.app_version;
          } else if (state.app_version > currentAppVersion) {
            console.log('[AUTO-UPDATE] Detected newer version:', state.app_version);
            currentAppVersion = state.app_version;
            applyHotUpdate();
          }
        }

        // Dynamically update active chat highlight banner and spoken words target tag across main tab and floating PiP window
        if (state.active_chat_title) {
          const docs = [document];
          if (window.documentPictureInPicture && window.documentPictureInPicture.window && !window.documentPictureInPicture.window.closed) {
            try { docs.push(window.documentPictureInPicture.window.document); } catch (e) {}
          }
          docs.forEach(doc => {
            const chatEl = Document.prototype.getElementById.call(doc, 'activeChatTitleText');
            if (chatEl && chatEl.innerText !== state.active_chat_title) {
              chatEl.innerText = state.active_chat_title;
              chatEl.title = 'Active Chat: ' + state.active_chat_title;
            }
            const draftTagEl = Document.prototype.getElementById.call(doc, 'activeChatTitleText');
            if (draftTagEl && draftTagEl.innerText !== state.active_chat_title) {
              draftTagEl.innerText = state.active_chat_title;
              
              // Flash animation for visual feedback
              draftTagEl.style.transition = 'none';
              draftTagEl.style.background = '#10b981'; // Green flash
              draftTagEl.style.color = '#ffffff';
              draftTagEl.style.transform = 'scale(1.08)';
              
              setTimeout(() => {
                draftTagEl.style.transition = 'all 0.6s ease';
                draftTagEl.style.background = 'rgba(56, 189, 248, 0.1)';
                draftTagEl.style.color = '#38bdf8';
                draftTagEl.style.transform = 'scale(1)';
              }, 400);
            }
          });
        }

        if (state.enabled !== undefined) {
          if (state.enabled === false && !isTotalPaused) {
            isTotalPaused = true;
            isManualPaused = true;
            isConnected = false;
            stopMic();
            updateTotalPauseUI(true);
          } else if (state.enabled === true && isTotalPaused) {
            isTotalPaused = false;
            updateTotalPauseUI(false);
          }
        }

        if (isTotalPaused) {
          isAISpeaking = false;
          return;
        }

        const wasSpeaking = isAISpeaking;
        isAISpeaking = !!state.is_speaking;
        currentAISpeakingText = state.current_text || '';
        if (currentAISpeakingText) {
          lastAISpeakingText = currentAISpeakingText;
        }
        if (wasSpeaking && !isAISpeaking) {
          lastAISpeechEndTime = Date.now();
        }
        if (isAISpeaking) {
          lastAISpeechEndTime = Date.now() + 1000;
        }

        if (isAISpeaking && !isManualPaused) {
          setOrbState('speaking');
          const title = document.getElementById('statusTitle'); if (title) title.innerText = 'AI Speaking...';
          const sub = document.getElementById('statusSub'); if (sub) sub.innerText = 'Click Ear or speak to talk';
          if (silenceTimer) {
            clearTimeout(silenceTimer);
            silenceTimer = null;
          }
          if (silenceCountdownInterval) {
            clearInterval(silenceCountdownInterval);
            silenceCountdownInterval = null;
          }
        } else if (isConnected && !isManualPaused) {
          setOrbState('listening');
          const title = document.getElementById('statusTitle'); if (title) title.innerText = 'Listening for Voice...';
          const sub = document.getElementById('statusSub'); if (sub) sub.innerText = 'Talk naturally anywhere in the room';
        } else {
          setOrbState('paused');
          const title = document.getElementById('statusTitle'); if (title) title.innerText = 'Microphone Idle';
          const sub = document.getElementById('statusSub'); if (sub) sub.innerText = 'Click Start Listening to talk';
        }
      } catch (e) { isAISpeaking = false; }
    }

    async function pollConversation() {
      try {
        let activeChatName = '';
        const docs = [document];
        if (window.documentPictureInPicture && window.documentPictureInPicture.window) {
          try { docs.push(window.documentPictureInPicture.window.document); } catch (e) {}
        }
        docs.forEach(doc => {
          if (!activeChatName) {
            const el = Document.prototype.getElementById.call(doc, 'activeChatTitleText');
            if (el && el.innerText && el.innerText.trim() !== 'Orb') activeChatName = el.innerText.trim();
          }
        });
        
        let url = '/api/conversation';
        if (activeChatName) {
          url += '?chat_title=' + encodeURIComponent(activeChatName);
        }
        const res = await fetch(url);
        const data = await res.json();
        const messages = data.messages || [];

        if (JSON.stringify(messages) !== JSON.stringify(lastRenderedMessages)) {
          lastRenderedMessages = messages;
          renderChatStream(messages);
        }
      } catch (e) {}
    }

        function renderChatStream(messages) {
      knownAITexts = (messages || [])
        .filter(m => m.role === 'assistant' && m.text)
        .slice(-15)
        .map(m => m.text);
    }

    function escapeHtml(str) {
      if (!str) return '';
      return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    let deferredPrompt = null;
    window.addEventListener('beforeinstallprompt', (e) => {
      e.preventDefault();
      deferredPrompt = e;
      const btn = document.getElementById('btnInstallApp');
      if (btn) btn.style.display = 'inline-flex';
    });

    function installPWA() {
      if (deferredPrompt) {
        deferredPrompt.prompt();
        deferredPrompt.userChoice.then((choiceResult) => {
          if (choiceResult.outcome === 'accepted') {
            showToast('App installed successfully!');
            document.getElementById('btnInstallApp').style.display = 'none';
          }
          deferredPrompt = null;
        });
      }
    }

    async function pinFloaterToTaskbar() {
      // 1. If PWA install prompt is available in browser, offer it
      if (deferredPrompt) {
        try {
          deferredPrompt.prompt();
          deferredPrompt.userChoice.then((choiceResult) => {
            if (choiceResult.outcome === 'accepted') {
              showToast('✅ Installed! Right-click icon on Taskbar -> Pin to taskbar.');
            }
            deferredPrompt = null;
          });
        } catch (pe) {}
      }

      // 2. Call backend to launch standalone window & write shortcuts to Desktop & Taskbar
      try {
        let res = null;
        try {
          res = await fetch('http://127.0.0.1:8766/api/pin_taskbar', {
            method: 'POST',
            mode: 'cors',
            headers: { 'Content-Type': 'application/json' }
          });
        } catch (corsErr) {
          res = await fetch('/api/pin_taskbar', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
          });
        }
        if (res && res.ok) {
          const data = await res.json();
          showToast('📌 Standalone app opened! Right-click its icon on your Taskbar -> Pin to taskbar.');
        } else {
          showToast('📌 Right-click the Orb app window on your Taskbar and click "Pin to taskbar".');
        }
      } catch (e) {
        showToast('📌 Right-click the Orb app window on your Taskbar and click "Pin to taskbar".');
      }
    }

    let lastMediaTapTime = 0;
    let mediaTapCount = 0;

    function setupMediaSessionHandlers() {
      if (!('mediaSession' in navigator)) return;

      try {
        navigator.mediaSession.metadata = new MediaMetadata({
          title: 'Orb AI Assistant',
          artist: 'Live Conversational Voice',
          album: 'Orb Voice Studio'
        });

        // Browsers drop MediaSession key bindings if no media is actively playing.
        // Play a silent 1-second WAV loop to keep the earbud hooks securely alive.
        const silentWav = 'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA';
        const silentPlayer = new Audio(silentWav);
        silentPlayer.loop = true;
        silentPlayer.volume = 0.01;
        
        // Ensure it starts when user interacts
        const startSilent = () => {
          silentPlayer.play().catch(()=>{});
          window.removeEventListener('click', startSilent);
          window.removeEventListener('pointerdown', startSilent);
        };
        window.addEventListener('click', startSilent);
        window.addEventListener('pointerdown', startSilent);

        const handleDoubleTapResume = () => {
          if (isTotalPaused) {
            showToast('🎧 Earbud Double-Tap: Resuming playback from Total Pause...');
            toggleTotalPause();
            setTimeout(() => {
              speakLastAIReply();
            }, 250);
          } else if (isAISpeaking) {
            stopSpeech();
          } else {
            speakLastAIReply();
          }
        };

        navigator.mediaSession.setActionHandler('nexttrack', handleDoubleTapResume);
        navigator.mediaSession.setActionHandler('previoustrack', handleDoubleTapResume);
        try { navigator.mediaSession.setActionHandler('seekforward', handleDoubleTapResume); } catch (e) {}
        try { navigator.mediaSession.setActionHandler('seekbackward', handleDoubleTapResume); } catch (e) {}

        const onPlayPauseTap = () => {
          const now = Date.now();
          if (now - lastMediaTapTime < 650) {
            mediaTapCount++;
          } else {
            mediaTapCount = 1;
          }
          lastMediaTapTime = now;

          if (mediaTapCount >= 2) {
            mediaTapCount = 0;
            console.log('[EARBUD] 🎧 Double-tap detected -> Resuming playback!');
            handleDoubleTapResume();
          } else {
            setTimeout(() => {
              if (mediaTapCount === 1) {
                mediaTapCount = 0;
                if (isAISpeaking) {
                  stopSpeech();
                } else if (!isTotalPaused && !isConnected) {
                  startMic();
                }
              }
            }, 350);
          }
        };

        navigator.mediaSession.setActionHandler('play', onPlayPauseTap);
        navigator.mediaSession.setActionHandler('pause', onPlayPauseTap);
        navigator.mediaSession.setActionHandler('stop', () => { if (isAISpeaking) stopSpeech(); });
      } catch (err) {
        console.warn('MediaSession init:', err);
      }
    }

    window.onload = () => {
      const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
      const badge = document.getElementById('connectionBadge');
      if (badge) {
        if (isLocal) {
          badge.innerHTML = '🟢 Direct Desktop Relay Connected (Auto-Typing Active)';
          badge.style.background = 'rgba(16,185,129,0.15)';
          badge.style.color = '#34d399';
          badge.style.borderColor = 'rgba(16,185,129,0.3)';
        } else {
          badge.innerHTML = '⚠️ Cloud Mode: <a href="http://localhost:8766" style="color:#60a5fa;text-decoration:underline;font-weight:bold;">Switch to Local Mode (http://localhost:8766)</a> to auto-type into chat';
          badge.style.background = 'rgba(234,179,8,0.15)';
          badge.style.color = '#facc15';
          badge.style.borderColor = 'rgba(234,179,8,0.3)';
        }
      }

      render2StepVoicePicker(document);
      loadSettings();
      
      try {
        if (sessionStorage.getItem('reopen_pip_after_reload') === 'true') {
          sessionStorage.removeItem('reopen_pip_after_reload');
          enableImmediateLaunchOverlay();
        }
      } catch (e) {}

      pollConversation();
      pollLiveState();
      setInterval(pollConversation, 1500);
      setInterval(pollLiveState, 200);

      bindOrbHandlers(document);
      setOrbState('paused');
      setupMediaSessionHandlers();

      if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js').catch(() => {});
      }
    };

    // Cross-window DOM proxy: ensure document.getElementById safely finds elements in main tab or floating PiP window without recursion
    function getAnyElementById(id) {
      if (window.documentPictureInPicture && window.documentPictureInPicture.window && !window.documentPictureInPicture.window.closed) {
        try {
          const pipDoc = window.documentPictureInPicture.window.document;
          if (pipDoc) {
            const pipEl = Document.prototype.getElementById.call(pipDoc, id);
            if (pipEl) return pipEl;
          }
        } catch (e) {}
      }
      return Document.prototype.getElementById.call(document, id);
    }
    document.getElementById = getAnyElementById;



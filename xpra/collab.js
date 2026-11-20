(() => {
  const STYLE = `
    .tm-collab-button{color:#fff;background:#303647;border:0;border-radius:8px;padding:8px 12px;font:700 14px system-ui,sans-serif;cursor:pointer}
    .tm-collab-button:disabled{cursor:not-allowed;opacity:.65}.tm-collab-button.tm-control-self{background:#16845b}
    .tm-control-status{padding:5px 8px;color:#d8deeb;background:#10121a;border:1px solid #343b4d;border-radius:6px;font:600 12px system-ui,sans-serif;white-space:nowrap}
    .tm-panel{box-sizing:border-box;position:fixed;z-index:9000;top:48px;right:0;bottom:0;width:min(340px,100vw);display:none;flex-direction:column;background:#171a23;color:#f5f5f7;border-left:1px solid #343b4d;font:14px system-ui,sans-serif}
    .tm-panel.tm-open{display:flex}.tm-panel *{box-sizing:border-box}.tm-panel-head{padding:14px;border-bottom:1px solid #343b4d}.tm-panel h2{margin:0 0 10px;font-size:18px}.tm-profile{display:grid;grid-template-columns:1fr 42px auto;gap:7px}.tm-profile input[type=text]{min-width:0;padding:8px;color:#fff;background:#10121a;border:1px solid #4b5368;border-radius:6px;font:inherit}.tm-profile input[type=color]{width:42px;height:36px;padding:2px;background:#10121a;border:1px solid #4b5368;border-radius:6px}.tm-profile button,.tm-send{padding:8px 11px;color:#fff;background:#7c5cff;border:0;border-radius:6px;font-weight:700;cursor:pointer}
    .tm-users{padding:8px 14px;border-bottom:1px solid #343b4d;color:#b8c0d4;font-size:13px}.tm-user{display:inline-flex;align-items:center;gap:5px;margin:3px 8px 3px 0}.tm-dot{width:9px;height:9px;border-radius:50%}.tm-controller-badge{padding:1px 4px;color:#fff;background:#16845b;border-radius:3px;font-size:10px;font-weight:800;text-transform:uppercase}
    .tm-messages{flex:1;overflow:auto;padding:12px 14px}.tm-message{margin:0 0 12px;overflow-wrap:anywhere}.tm-message-meta{margin-bottom:2px;font-size:12px;color:#9fa8bc}.tm-message-name{font-weight:800}.tm-message-body{color:#fff;white-space:pre-wrap}
    .tm-chat-form{display:flex;gap:7px;padding:12px;border-top:1px solid #343b4d}.tm-chat-form input{min-width:0;flex:1;padding:9px;color:#fff;background:#10121a;border:1px solid #4b5368;border-radius:6px;font:16px system-ui,sans-serif}
    .tm-upload-dialog{position:fixed;z-index:10000;inset:0;display:none;place-items:center;background:#0009;color:#fff;font:14px system-ui,sans-serif}.tm-upload-dialog.tm-open{display:grid}.tm-upload-card{width:min(360px,calc(100vw - 32px));padding:22px;background:#171a23;border:1px solid #4b5368;border-radius:10px;box-shadow:0 16px 50px #000}.tm-upload-card h2{margin:0 0 8px}.tm-upload-card p{color:#c6ccda}.tm-upload-file{position:absolute;width:1px;height:1px;overflow:hidden;opacity:0;clip:rect(0 0 0 0)}.tm-upload-actions{display:flex;gap:8px;margin-top:16px}.tm-upload-actions button,.tm-upload-actions label{display:inline-block;padding:9px 13px;color:#fff;background:#7c5cff;border:0;border-radius:6px;font-weight:700;cursor:pointer}.tm-upload-actions .tm-upload-cancel{background:#303647}.tm-upload-actions .tm-disabled{pointer-events:none;opacity:.65}
    .tm-download-dialog{position:fixed;z-index:10010;inset:0;display:none;place-items:center;background:#0009;color:#fff;font:14px system-ui,sans-serif}.tm-download-dialog.tm-open{display:grid}.tm-download-card{width:min(680px,calc(100vw - 32px));max-height:min(650px,calc(100vh - 40px));display:flex;flex-direction:column;padding:22px;background:#171a23;border:1px solid #4b5368;border-radius:10px;box-shadow:0 16px 50px #000}.tm-download-head{display:flex;align-items:center;gap:12px}.tm-download-head h2{margin:0;flex:1}.tm-download-close{padding:7px 11px;color:#fff;background:#303647;border:0;border-radius:6px;font-weight:700;cursor:pointer}.tm-download-note{margin:8px 0;color:#c6ccda}.tm-download-files{overflow:auto;border:1px solid #343b4d;border-radius:7px}.tm-download-section{position:sticky;top:0;z-index:1;padding:7px 10px;color:#fff;background:#303647;border-bottom:1px solid #4b5368;font-size:12px;font-weight:800;text-transform:uppercase;letter-spacing:.06em}.tm-download-row{display:grid;grid-template-columns:minmax(0,1fr) auto auto;align-items:center;gap:12px;padding:9px 10px;border-bottom:1px solid #2d3240}.tm-download-row:last-child{border-bottom:0}.tm-download-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.tm-download-meta{color:#9fa8bc;font-size:12px}.tm-download-save{padding:7px 10px;color:#fff;background:#7c5cff;border-radius:6px;text-decoration:none;font-weight:700}.tm-download-empty{padding:18px;color:#c6ccda}
    .tm-control-dialog{position:fixed;z-index:10020;right:18px;top:66px;display:none;width:min(360px,calc(100vw - 36px));padding:18px;color:#fff;background:#171a23;border:1px solid #68738d;border-radius:10px;box-shadow:0 12px 38px #000b;font:14px system-ui,sans-serif}.tm-control-dialog.tm-open{display:block}.tm-control-dialog h2{margin:0 0 7px;font-size:17px}.tm-control-dialog p{margin:0;color:#cbd1df}.tm-control-requester{font-weight:800}.tm-control-actions{display:flex;gap:8px;margin-top:14px}.tm-control-actions button{padding:9px 13px;color:#fff;background:#7c5cff;border:0;border-radius:6px;font-weight:700;cursor:pointer}.tm-control-actions .tm-control-keep{background:#303647}
    .tm-cursor-layer,.tm-input-blocker{position:fixed;z-index:8500;pointer-events:none;overflow:hidden}.tm-input-blocker{z-index:8400;display:none;pointer-events:auto;cursor:not-allowed}.tm-cursor{position:absolute;left:0;top:0;will-change:transform;filter:drop-shadow(1px 2px 1px #0008)}.tm-cursor-shape{width:0;height:0;border-left:8px solid transparent;border-right:8px solid transparent;border-bottom:20px solid var(--cursor-color);transform:rotate(-35deg);transform-origin:center}.tm-cursor-label{display:inline-block;margin:1px 0 0 10px;padding:2px 5px;color:#fff;background:var(--cursor-color);border-radius:4px;font:bold 11px system-ui,sans-serif;white-space:nowrap}
    @media(min-width:601px){body.tm-chat-open iframe{width:calc(100% - 340px)}}
    @media(max-width:600px){.tm-panel{width:100vw}.tm-collab-button{padding:8px}.tm-control-status{display:none}.tm-control-label{display:none}}
  `;

  function mount({iframe, bar, exclusiveControl = true}) {
    if (!iframe || !bar || document.querySelector('.tm-panel')) return;
    const style = document.createElement('style');
    style.textContent = STYLE;
    document.head.append(style);

    let nickname = localStorage.getItem('temporaman_nickname') || `Guest ${Math.floor(100 + Math.random() * 900)}`;
    let color = localStorage.getItem('temporaman_color') || `hsl(${Math.floor(Math.random() * 360)} 72% 55%)`;
    if (!color.startsWith('#')) {
      const canvas = document.createElement('canvas').getContext('2d');
      canvas.fillStyle = color;
      color = canvas.fillStyle;
    }
    let socket, ownId, controllerId = null, users = [], cursorPending = null, cursorFrame = 0;
    let pendingRequester = null, lastControlRequest = 0;
    const cursors = new Map();

    const toggle = document.createElement('button');
    toggle.className = 'tm-collab-button';
    toggle.type = 'button';
    toggle.textContent = 'Chat';
    const control = document.createElement('button');
    control.className = 'tm-collab-button';
    control.type = 'button';
    control.innerHTML = '<span class="tm-control-label">Take control</span>';
    const paste = document.createElement('button');
    paste.className = 'tm-collab-button';
    paste.type = 'button';
    paste.textContent = 'Paste';
    paste.title = 'Paste copied text into the focused studio field';
    paste.disabled = true;
    const filesButton = document.createElement('button');
    filesButton.className = 'tm-collab-button';
    filesButton.type = 'button';
    filesButton.textContent = 'Files →';
    filesButton.title = 'Save a Temporaman file to this computer';
    const controlStatus = document.createElement('span');
    controlStatus.className = 'tm-control-status';
    controlStatus.textContent = 'Control: nobody';
    bar.insertBefore(toggle, bar.children[1] || null);
    bar.insertBefore(controlStatus, toggle.nextSibling);
    bar.insertBefore(control, controlStatus.nextSibling);
    bar.insertBefore(paste, control.nextSibling);
    bar.insertBefore(filesButton, paste.nextSibling);
    if (!exclusiveControl) {
      control.style.display = 'none';
      controlStatus.style.display = 'none';
      paste.disabled = false;
    }

    const panel = document.createElement('aside');
    panel.className = 'tm-panel tm-open';
    panel.innerHTML = `
      <div class="tm-panel-head"><h2>Temporaman Shrine</h2><div class="tm-profile">
        <input class="tm-nickname" type="text" maxlength="24" aria-label="Nickname">
        <input class="tm-color" type="color" aria-label="Cursor color">
        <button class="tm-save" type="button">Set</button>
      </div></div>
      <div class="tm-users"></div>
      <div class="tm-messages" aria-live="polite"></div>
      <form class="tm-chat-form"><input maxlength="500" autocomplete="off" aria-label="Chat message"><button class="tm-send">Send</button></form>`;
    document.body.append(panel);
    document.body.classList.add('tm-chat-open');
    const uploadDialog = document.createElement('div');
    uploadDialog.className = 'tm-upload-dialog';
    uploadDialog.innerHTML = `<div class="tm-upload-card" role="dialog" aria-modal="true" aria-labelledby="tm-upload-title">
      <h2 id="tm-upload-title">Upload a sample</h2>
      <p class="tm-upload-status">Choose an audio file from this device. Maximum size: 10 MB.</p>
      <input class="tm-upload-file" id="tm-upload-file" type="file" accept="audio/*,.wav,.flac,.mp3,.ogg,.opus,.aif,.aiff,.m4a,.caf,.au">
      <div class="tm-upload-actions"><label class="tm-upload-choose" for="tm-upload-file">Choose file</label><button class="tm-upload-cancel" type="button">Cancel</button></div>
    </div>`;
    document.body.append(uploadDialog);
    const downloadDialog = document.createElement('div');
    downloadDialog.className = 'tm-download-dialog';
    downloadDialog.innerHTML = `<div class="tm-download-card" role="dialog" aria-modal="true" aria-labelledby="tm-download-title">
      <div class="tm-download-head"><h2 id="tm-download-title">Save a file to this computer</h2><button class="tm-download-close" type="button">Close</button></div>
      <p class="tm-download-note">Exports are shown first, followed by imported source files.</p>
      <div class="tm-download-files"><div class="tm-download-empty">Loading files…</div></div>
    </div>`;
    document.body.append(downloadDialog);
    const controlDialog = document.createElement('div');
    controlDialog.className = 'tm-control-dialog';
    controlDialog.innerHTML = `<h2>Someone wants control</h2>
      <p><span class="tm-control-requester"></span> is trying to use the studio. Hand control over?</p>
      <div class="tm-control-actions"><button class="tm-control-grant" type="button">Hand over control</button><button class="tm-control-keep" type="button">Keep control</button></div>`;
    document.body.append(controlDialog);
    const cursorLayer = document.createElement('div');
    cursorLayer.className = 'tm-cursor-layer';
    const blocker = document.createElement('div');
    blocker.className = 'tm-input-blocker';
    document.body.append(cursorLayer, blocker);
    blocker.style.display = exclusiveControl ? 'block' : 'none';

    const nicknameInput = panel.querySelector('.tm-nickname');
    const colorInput = panel.querySelector('.tm-color');
    const usersBox = panel.querySelector('.tm-users');
    const messages = panel.querySelector('.tm-messages');
    const chatForm = panel.querySelector('.tm-chat-form');
    const chatInput = chatForm.querySelector('input');
    const uploadInput = uploadDialog.querySelector('.tm-upload-file');
    const uploadStatus = uploadDialog.querySelector('.tm-upload-status');
    const uploadChoose = uploadDialog.querySelector('.tm-upload-choose');
    const downloadFiles = downloadDialog.querySelector('.tm-download-files');
    nicknameInput.value = nickname;
    colorInput.value = color;

    function send(message) {
      if (socket && socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message));
    }
    function requestControl() {
      if (!controllerId) {
        send({type:'control', action:'take'});
        return;
      }
      if (controllerId === ownId) return;
      const now = Date.now();
      if (now - lastControlRequest < 1500) return;
      lastControlRequest = now;
      send({type:'control', action:'request'});
      const owner = users.find(user => user.id === controllerId);
      controlStatus.textContent = `Asked ${owner ? owner.nickname : 'controller'} for control…`;
    }
    function showControlRequest(requester) {
      pendingRequester = requester;
      const name = controlDialog.querySelector('.tm-control-requester');
      name.textContent = requester.nickname;
      name.style.color = requester.color;
      controlDialog.classList.add('tm-open');
    }
    function answerControlRequest(action) {
      if (!pendingRequester) return;
      send({type:'control', action, target:pendingRequester.id});
      pendingRequester = null;
      controlDialog.classList.remove('tm-open');
    }
    controlDialog.querySelector('.tm-control-grant').addEventListener('click', () => answerControlRequest('grant'));
    controlDialog.querySelector('.tm-control-keep').addEventListener('click', () => answerControlRequest('deny'));
    function showUploadDialog() {
      uploadStatus.textContent = 'Choose an audio file from this device. Maximum size: 10 MB.';
      uploadChoose.classList.remove('tm-disabled');
      uploadDialog.classList.add('tm-open');
    }
    function formatBytes(size) {
      if (size < 1024) return `${size} B`;
      if (size < 1048576) return `${(size / 1024).toFixed(1)} KB`;
      return `${(size / 1048576).toFixed(1)} MB`;
    }
    async function showDownloadDialog() {
      downloadDialog.classList.add('tm-open');
      downloadFiles.innerHTML = '<div class="tm-download-empty">Loading files…</div>';
      try {
        const response = await fetch('/temporaman/files', {cache:'no-store'});
        if (!response.ok) throw new Error('file list unavailable');
        const payload = await response.json();
        downloadFiles.replaceChildren();
        if (!payload.files.length) {
          downloadFiles.innerHTML = '<div class="tm-download-empty">There are no files to download yet.</div>';
          return;
        }
        for (const area of ['exports', 'imports']) {
          const files = payload.files.filter(file => file.area === area);
          if (!files.length) continue;
          const section = document.createElement('div');
          section.className = 'tm-download-section';
          section.textContent = area;
          downloadFiles.append(section);
          files.forEach(file => {
            const row = document.createElement('div');
            row.className = 'tm-download-row';
            const name = document.createElement('span');
            name.className = 'tm-download-name';
            name.textContent = file.name;
            name.title = file.name;
            const meta = document.createElement('span');
            meta.className = 'tm-download-meta';
            meta.textContent = formatBytes(file.size);
            const save = document.createElement('a');
            save.className = 'tm-download-save';
            save.textContent = 'Save to computer';
            save.href = `/temporaman/download?area=${encodeURIComponent(file.area)}&name=${encodeURIComponent(file.name)}`;
            row.append(name, meta, save);
            downloadFiles.append(row);
          });
        }
      } catch (_) {
        downloadFiles.innerHTML = '<div class="tm-download-empty">Could not load files. Try again.</div>';
      }
    }
    downloadDialog.querySelector('.tm-download-close').addEventListener('click', () => downloadDialog.classList.remove('tm-open'));
    filesButton.addEventListener('click', showDownloadDialog);
    uploadDialog.querySelector('.tm-upload-cancel').addEventListener('click', () => uploadDialog.classList.remove('tm-open'));
    uploadInput.addEventListener('change', async () => {
      const file = uploadInput.files[0];
      if (!file) return;
      if (file.size > 10 * 1024 * 1024) {
        uploadStatus.textContent = 'That file is larger than 10 MB.';
        uploadInput.value = '';
        return;
      }
      uploadChoose.classList.add('tm-disabled');
      uploadStatus.textContent = `Uploading ${file.name}…`;
      const form = new FormData();
      form.append('sample', file);
      try {
        const response = await fetch('/temporaman/upload', {method:'POST', body:form});
        if (!response.ok) throw new Error('upload failed');
        uploadStatus.textContent = `${file.name} is ready in Temporaman.`;
        window.setTimeout(() => uploadDialog.classList.remove('tm-open'), 1200);
      } catch (_) {
        uploadStatus.textContent = 'Upload failed. Please try again.';
      } finally {
        uploadInput.value = '';
        uploadChoose.classList.remove('tm-disabled');
      }
    });
    function updateBounds() {
      const rect = iframe.getBoundingClientRect();
      for (const element of [cursorLayer, blocker]) {
        element.style.left = `${rect.left}px`;
        element.style.top = `${rect.top}px`;
        element.style.width = `${rect.width}px`;
        element.style.height = `${rect.height}px`;
      }
    }
    function renderPresence() {
      usersBox.replaceChildren();
      users.forEach(user => {
        const item = document.createElement('span');
        item.className = 'tm-user';
        const dot = document.createElement('span');
        dot.className = 'tm-dot';
        dot.style.background = user.color;
        const name = document.createElement('span');
        name.textContent = user.nickname;
        item.append(dot, name);
        if (exclusiveControl && user.id === controllerId) {
          const badge = document.createElement('span');
          badge.className = 'tm-controller-badge';
          badge.textContent = 'control';
          item.append(badge);
        }
        usersBox.append(item);
      });
      toggle.textContent = `Chat (${users.length})`;
      const controller = users.find(user => user.id === controllerId);
      if (!exclusiveControl) {
        controllerId = null;
        control.style.display = 'none';
        controlStatus.style.display = 'none';
        paste.disabled = false;
        blocker.style.display = 'none';
        controlDialog.classList.remove('tm-open');
        return;
      }
      control.classList.toggle('tm-control-self', controllerId === ownId);
      if (!controllerId) {
        control.disabled = false;
        control.textContent = 'Take exclusive control';
        controlStatus.textContent = 'Control: open — everyone can interact';
      } else if (controllerId === ownId) {
        control.disabled = false;
        control.textContent = 'Release control';
        controlStatus.textContent = `Control: ${controller ? controller.nickname : nickname} (you)`;
      } else {
        control.disabled = false;
        control.textContent = `Ask ${controller ? controller.nickname : 'controller'}`;
        controlStatus.textContent = `Control: ${controller ? controller.nickname : 'someone'}`;
      }
      paste.disabled = Boolean(controllerId && controllerId !== ownId);
      blocker.style.display = controllerId && controllerId !== ownId ? 'block' : 'none';
      if (controllerId !== ownId) {
        pendingRequester = null;
        controlDialog.classList.remove('tm-open');
      }
      if (blocker.style.display === 'block') {
        iframe.blur();
        document.body.tabIndex = -1;
        document.body.focus();
      }
    }
    function addMessage(message) {
      const row = document.createElement('div');
      row.className = 'tm-message';
      const meta = document.createElement('div');
      meta.className = 'tm-message-meta';
      const name = document.createElement('span');
      name.className = 'tm-message-name';
      name.style.color = message.color;
      name.textContent = message.nickname;
      const time = document.createElement('span');
      time.textContent = ` · ${new Date(message.time * 1000).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}`;
      const body = document.createElement('div');
      body.className = 'tm-message-body';
      body.textContent = message.text;
      meta.append(name, time);
      row.append(meta, body);
      messages.append(row);
      messages.scrollTop = messages.scrollHeight;
    }
    function renderCursor(message) {
      let cursor = cursors.get(message.id);
      if (!cursor) {
        cursor = document.createElement('div');
        cursor.className = 'tm-cursor';
        cursor.innerHTML = '<div class="tm-cursor-shape"></div><div class="tm-cursor-label"></div>';
        cursorLayer.append(cursor);
        cursors.set(message.id, cursor);
      }
      cursor.style.setProperty('--cursor-color', message.color);
      cursor.querySelector('.tm-cursor-label').textContent = message.nickname;
      cursor.style.display = message.visible ? 'block' : 'none';
      cursor.style.transform = `translate(${message.x * cursorLayer.clientWidth}px,${message.y * cursorLayer.clientHeight}px)`;
    }
    function queueCursor(x, y, visible = true) {
      cursorPending = {type:'cursor', x:Math.max(0,Math.min(1,x)), y:Math.max(0,Math.min(1,y)), visible};
      if (!cursorFrame) cursorFrame = requestAnimationFrame(() => {
        send(cursorPending);
        cursorPending = null;
        cursorFrame = 0;
      });
    }
    function pointerFromFrame(event) {
      const frameWindow = iframe.contentWindow;
      queueCursor(event.clientX / frameWindow.innerWidth, event.clientY / frameWindow.innerHeight);
    }
    function attachFrameEvents() {
      try {
        const doc = iframe.contentDocument;
        doc.addEventListener('pointermove', pointerFromFrame, true);
        doc.addEventListener('pointerleave', () => send({type:'cursor', x:0, y:0, visible:false}), true);
      } catch (_) {}
    }
    async function pasteIntoStudio() {
      if (controllerId && controllerId !== ownId) return;
      let text;
      try {
        text = await navigator.clipboard.readText();
      } catch (_) {
        text = window.prompt('Paste text or a link here:');
      }
      if (!text) return;
      if (text.length > 65536) {
        window.alert('Clipboard text is too large. Temporaman can paste up to 64 KB at once.');
        return;
      }
      try {
        const doc = iframe.contentDocument;
        const clipboard = doc.getElementById('noVNC_clipboard_text');
        const canvas = doc.querySelector('#noVNC_container > div > canvas');
        if (!clipboard || !canvas) throw new Error('studio is not ready');
        clipboard.value = text;
        clipboard.dispatchEvent(new Event('change', {bubbles:true}));
        paste.textContent = 'Pasting…';
        window.setTimeout(() => {
          canvas.focus();
          const key = (type, value, code, ctrlKey) => canvas.dispatchEvent(new KeyboardEvent(type, {
            key:value, code, ctrlKey, bubbles:true, cancelable:true,
          }));
          key('keydown', 'Control', 'ControlLeft', true);
          key('keydown', 'v', 'KeyV', true);
          key('keyup', 'v', 'KeyV', true);
          key('keyup', 'Control', 'ControlLeft', false);
          paste.textContent = 'Pasted';
          window.setTimeout(() => { paste.textContent = 'Paste'; }, 1200);
        }, 250);
      } catch (error) {
        console.error('Temporaman paste failed:', error);
        paste.textContent = 'Paste failed';
        window.setTimeout(() => { paste.textContent = 'Paste'; }, 1800);
      }
    }
    blocker.addEventListener('pointermove', event => {
      const rect = blocker.getBoundingClientRect();
      queueCursor((event.clientX - rect.left) / rect.width, (event.clientY - rect.top) / rect.height);
    });
    blocker.addEventListener('pointerdown', event => {
      event.preventDefault();
      requestControl();
    });
    blocker.addEventListener('pointerleave', () => send({type:'cursor', x:0, y:0, visible:false}));
    iframe.addEventListener('load', attachFrameEvents);
    try {
      if (iframe.contentDocument && iframe.contentDocument.readyState !== 'loading') attachFrameEvents();
    } catch (_) {}
    window.addEventListener('resize', updateBounds);
    updateBounds();

    function connect() {
      const scheme = location.protocol === 'https:' ? 'wss:' : 'ws:';
      socket = new WebSocket(`${scheme}//${location.host}/temporaman/collab`);
      socket.onopen = () => send({type:'join', nickname, color});
      socket.onmessage = event => {
        const message = JSON.parse(event.data);
        if (message.type === 'welcome') {
          ownId = message.id;
          messages.replaceChildren();
          message.history.forEach(addMessage);
        } else if (message.type === 'presence') {
          users = message.users;
          controllerId = message.controller;
          const active = new Set(users.map(user => user.id));
          for (const [id, cursor] of cursors) if (!active.has(id)) { cursor.remove(); cursors.delete(id); }
          renderPresence();
        } else if (message.type === 'chat') addMessage(message);
        else if (message.type === 'cursor') renderCursor(message);
        else if (message.type === 'upload_request' && (controllerId === ownId || !exclusiveControl)) showUploadDialog();
        else if (message.type === 'download_request') showDownloadDialog();
        else if (message.type === 'control_request' && controllerId === ownId) showControlRequest(message.requester);
        else if (message.type === 'control_response') {
          window.setTimeout(() => {
            controlStatus.textContent = message.accepted
              ? `${message.nickname} handed control to you`
              : `${message.nickname} kept control`;
          }, 0);
          window.setTimeout(renderPresence, 2500);
        }
      };
      socket.onclose = () => setTimeout(connect, 1500);
    }
    connect();

    toggle.addEventListener('click', () => {
      panel.classList.toggle('tm-open');
      document.body.classList.toggle('tm-chat-open', panel.classList.contains('tm-open'));
      updateBounds();
      if (panel.classList.contains('tm-open')) chatInput.focus();
    });
    panel.querySelector('.tm-save').addEventListener('click', () => {
      nickname = nicknameInput.value.trim().slice(0, 24) || nickname;
      color = colorInput.value;
      nicknameInput.value = nickname;
      localStorage.setItem('temporaman_nickname', nickname);
      localStorage.setItem('temporaman_color', color);
      send({type:'profile', nickname, color});
    });
    chatForm.addEventListener('submit', event => {
      event.preventDefault();
      const text = chatInput.value.trim();
      if (text) send({type:'chat', text});
      chatInput.value = '';
    });
    control.addEventListener('click', () => {
      if (controllerId === ownId) send({type:'control', action:'release'});
      else requestControl();
    });
    paste.addEventListener('click', pasteIntoStudio);

    if (!localStorage.getItem('temporaman_nickname')) {
      panel.classList.add('tm-open');
      nicknameInput.focus();
    }
  }

  window.TemporamanCollab = {mount};
})();

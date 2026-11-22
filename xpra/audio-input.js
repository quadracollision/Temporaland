(() => {
  const formats = [
    ['opus-webm', 'audio/webm;codecs=opus'],
    ['opus-ogg', 'audio/ogg;codecs=opus'],
  ];

  function mount(bar) {
    const style = document.createElement('style');
    style.textContent = `
      .tm-recording-input{width:min(28rem,calc(100% - 36px));box-sizing:border-box;
        color:#fff;background:#171a23;border:1px solid #4b5368;border-radius:8px;padding:18px}
      .tm-recording-input::backdrop{background:#0008}
      .tm-recording-input h2{margin:0 0 12px}
      .tm-recording-input select{display:block;width:100%;margin:6px 0}
      .tm-recording-input button{margin:6px 4px 0 0}
      .tm-recording-input p{overflow-wrap:anywhere}
    `;
    document.head.append(style);
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'tm-collab-button';
    toggle.textContent = 'Input';
    bar.insertBefore(toggle, bar.querySelector('#audio'));
    const dialog = document.createElement('dialog');
    dialog.className = 'tm-recording-input';
    dialog.setAttribute('aria-label', 'Recording input');
    dialog.innerHTML = `
      <h2>Recording input</h2>
      <label>Device on this computer
        <select><option value="">Browser-selected input</option></select>
      </label>
      <p role="status">Select an input, or choose it in the browser prompt.</p>
      <button type="button" data-connect>Connect to Audacity</button>
      <button type="button" data-disconnect disabled>Disconnect</button>
      <form method="dialog"><button>Close</button></form>`;
    document.body.append(dialog);
    const select = dialog.querySelector('select');
    const status = dialog.querySelector('[role=status]');
    const connect = dialog.querySelector('[data-connect]');
    const disconnect = dialog.querySelector('[data-disconnect]');
    let stream, socket, recorder, timeout;

    async function listInputs(selected = select.value) {
      const inputs = (await navigator.mediaDevices.enumerateDevices())
        .filter(input => input.kind === 'audioinput' && input.label && input.deviceId);
      select.replaceChildren(new Option('Browser-selected input', ''));
      for (const input of inputs) select.add(new Option(input.label, input.deviceId));
      if (inputs.some(input => input.deviceId === selected)) select.value = selected;
    }

    function stop(message) {
      clearTimeout(timeout);
      if (recorder?.state === 'recording') recorder.stop();
      recorder = null;
      if (socket) {
        socket.onopen = socket.onmessage = socket.onerror = socket.onclose = null;
        socket.close();
        socket = null;
      }
      stream?.getTracks().forEach(track => track.stop());
      stream = null;
      toggle.textContent = 'Input';
      disconnect.disabled = true;
      connect.disabled = select.disabled = false;
      status.textContent = message;
    }

    toggle.addEventListener('click', () => {
      dialog.showModal();
      if (!select.disabled) listInputs().catch(() => {});
    });
    disconnect.addEventListener('click', () => stop('Input disconnected.'));
    window.addEventListener('pagehide', () => stop('Input disconnected.'));

    connect.addEventListener('click', async () => {
      connect.disabled = select.disabled = true;
      status.textContent = 'Waiting for the browser to open the input…';
      let expired = false;
      try {
        const format = formats.find(([, mime]) => window.MediaRecorder?.isTypeSupported(mime));
        if (!format || !navigator.mediaDevices?.getUserMedia) {
          throw new Error('This browser cannot stream an audio input.');
        }
        const [encoding, mimeType] = format;
        const audio = {channelCount:{ideal:2}, echoCancellation:false,
          noiseSuppression:false, autoGainControl:false};
        if (select.value) audio.deviceId = {exact:select.value};
        const opening = navigator.mediaDevices.getUserMedia({audio}).then(candidate => {
          if (expired) candidate.getTracks().forEach(track => track.stop());
          return candidate;
        });
        try {
          stream = await Promise.race([opening, new Promise((_, reject) => {
            timeout = setTimeout(() => {
              expired = true;
              reject(new Error('Audio permission or device startup timed out.'));
            }, 20000);
          })]);
        } finally {
          clearTimeout(timeout);
        }
        const track = stream.getAudioTracks()[0];
        const settings = track.getSettings();
        const device = track.label || 'Browser audio input';
        listInputs(settings.deviceId).catch(() => {});
        recorder = new MediaRecorder(stream, {mimeType, audioBitsPerSecond:160000});
        const url = new URL('/temporaman/audio-input', location.href);
        url.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const connection = socket = new WebSocket(url);
        disconnect.disabled = false;
        status.textContent = `Opened ${device}. Creating the Audacity recording device…`;
        timeout = setTimeout(() => stop('Temporaman did not confirm the recording device.'), 10000);
        track.addEventListener('ended', () => {
          if (socket === connection) stop('The input device disconnected.');
        });
        connection.onopen = () => connection.send(JSON.stringify({
          type:'audio-input', encoding, sampleRate:settings.sampleRate || 48000,
          channels:2, device,
          nickname:localStorage.getItem('temporaman_nickname') || 'Guest',
        }));
        connection.onmessage = event => {
          const message = JSON.parse(event.data);
          if (message.type === 'error') { stop(message.message); return; }
          if (message.type !== 'ready' || recorder.state !== 'inactive') return;
          clearTimeout(timeout);
          status.textContent = `In Audacity, choose Transport → Rescan Audio Devices, then set Audio Setup → Recording Device to ${message.recordingDevice}.`;
          toggle.textContent = 'Input connected';
          recorder.ondataavailable = ({data}) => {
            if (socket !== connection || connection.readyState !== WebSocket.OPEN || !data.size) return;
            if (connection.bufferedAmount + data.size > 128 * 1024) {
              stop('The network could not keep up with the audio stream.');
              return;
            }
            for (let start = 0; start < data.size; start += 16384) {
              connection.send(data.slice(start, start + 16384));
            }
          };
          recorder.onerror = event => stop(event.error?.message || 'The browser stopped recording.');
          try { recorder.start(200); } catch (error) { stop(error.message); }
        };
        connection.onerror = () => stop('Could not reach Temporaman’s recording server.');
        connection.onclose = () => stop('Disconnected from Temporaman’s recording server.');
      } catch (error) {
        stop(`${error.name || 'Input error'} — ${error.message}`);
      }
    });
  }
  window.TemporamanAudioInput = {mount};
})();

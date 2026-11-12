(() => {
    const root = document.querySelector('[data-voice-workspace]');
    if (!root) return;
    const timer = new CreationTimer(root, 'voice');
    const start = document.getElementById('start-btn'), stop = document.getElementById('stop-btn');
    const status = document.getElementById('status');
    const visualizer = root.querySelector('.voice-visualizer');
    const labels = {idle:'Listo para escucharte', requesting:'Activando micrófono', recording:'Escuchando tu voz', processing:'Procesando tu reporte', success:'Reporte creado', error:'Inténtalo de nuevo'};
    const setState = state => {
        visualizer.dataset.voiceState = state;
        visualizer.querySelector('.voice-state-label').textContent = labels[state];
        start.setAttribute('aria-pressed', String(state === 'recording'));
    };
    let recorder, stream, audioContext, animationFrame, recordingLimit, recordedBytes = 0, chunks = [];
    const release = () => {
        cancelAnimationFrame(animationFrame);
        clearTimeout(recordingLimit);
        stream?.getTracks().forEach(track => track.stop());
        if (audioContext) { audioContext.close().catch(() => {}); audioContext = null; }
        visualizer.style.removeProperty('--voice-level');
    };
    const visualizeAudio = async () => {
        try {
            const AudioContextClass = window.AudioContext || window.webkitAudioContext;
            if (!AudioContextClass) return;
            audioContext = new AudioContextClass();
            await audioContext.resume();
            const analyser = audioContext.createAnalyser();
            analyser.fftSize = 256;
            audioContext.createMediaStreamSource(stream).connect(analyser);
            const samples = new Uint8Array(analyser.frequencyBinCount);
            const draw = () => {
                analyser.getByteFrequencyData(samples);
                const level = samples.reduce((sum, value) => sum + value, 0) / samples.length / 128;
                visualizer.style.setProperty('--voice-level', Math.min(1, level).toFixed(3));
                animationFrame = requestAnimationFrame(draw);
            };
            draw();
        } catch (_) { /* La animación base sigue disponible sin análisis de audio. */ }
    };
    start.addEventListener('click', async () => {
        start.disabled = true;
        setState('requesting');
        if (timer.submitted) timer.reset();
        try {
            if (!navigator.mediaDevices || !window.MediaRecorder) throw new Error('Este navegador no admite grabación. Usa el formulario manual.');
            await timer.start();
            stream = await navigator.mediaDevices.getUserMedia({audio:true});
            const mimeType = ['audio/webm;codecs=opus','audio/webm'].find(type => MediaRecorder.isTypeSupported(type));
            if (!mimeType) throw new Error('Este navegador no admite el formato de audio requerido. Usa Chrome o Edge.');
            chunks = []; recordedBytes = 0;
            recorder = new MediaRecorder(stream, {mimeType, audioBitsPerSecond:32000});
            recorder.ondataavailable = event => {
                if (event.data.size) { chunks.push(event.data); recordedBytes += event.data.size; }
                if (recordedBytes > 3500000 && recorder.state === 'recording') recorder.stop();
            };
            recorder.onstop = async () => {
                release(); stop.disabled = true; timer.submitted = true;
                setState('processing');
                status.textContent = 'Transcribiendo y guardando… Mantén esta pantalla abierta.';
                timer.status.textContent = 'Procesando audio y creando la solicitud…';
                const form = new FormData(); form.append('audio', new Blob(chunks, {type:mimeType}), 'grabacion.webm');
                form.append('attempt_id', timer.attempt);
                form.append('request_kind', root.querySelector('[name=request_kind]').value);
                const origin = root.querySelector('[name=origin_area_id]');
                if (origin) form.append('origin_area_id', origin.value);
                try {
                    if (recordedBytes > 3900000) throw new Error('El audio es demasiado grande. Graba un reporte más breve.');
                    const response = await fetch('/api/tickets/voz', {method:'POST', body:form});
                    if (response.redirected) throw new Error('La sesión terminó. Vuelve a ingresar.');
                    const result = await response.json();
                    if (!response.ok) throw new Error(result.error || 'No se pudo crear la solicitud.');
                    timer.finish(result.total_ms, true);
                    setState('success');
                    status.textContent = 'Solicitud creada correctamente. ';
                    const link = document.createElement('a'); link.href = '/tickets/'+result.ticket_id;
                    link.textContent = 'Ver reporte'; status.appendChild(link);
                    window.dispatchEvent(new Event('ti-data-changed'));
                } catch (error) {
                    setState('error');
                    timer.finish(null, false); status.textContent = error.message;
                } finally { start.disabled = false; chunks = []; }
            };
            recorder.start(1000); stop.disabled = false; status.textContent = 'Grabando…';
            recordingLimit = setTimeout(() => { if (recorder.state === 'recording') recorder.stop(); }, 180000);
            setState('recording');
            visualizeAudio();
        } catch (error) {
            setState('error');
            release(); status.textContent = error.message; start.disabled = false;
        }
    });
    stop.addEventListener('click', () => { if (recorder?.state === 'recording') {stop.disabled = true; recorder.stop();} });
    window.addEventListener('pagehide', release);
})();

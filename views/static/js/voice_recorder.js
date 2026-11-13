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
    const showPermissionDenied = error => {
        status.replaceChildren();
        const isPermission = error?.name === 'NotAllowedError' || error?.name === 'PermissionDeniedError';
        const isNotFound = error?.name === 'NotFoundError' || error?.name === 'DevicesNotFoundError';
        const message = isPermission
            ? 'Permiso de micrófono rechazado. No se inició ningún intento medido; habilita el micrófono o usa el '
            : isNotFound
                ? 'No se detectó micrófono disponible. No se inició ningún intento medido; usa el '
                : (error?.message || 'No se pudo activar el micrófono. ');
        status.append(document.createTextNode(message));
        if (isPermission || isNotFound) {
            const manualLink = document.createElement('a');
            manualLink.href = '/tickets/create';
            manualLink.textContent = 'formulario manual';
            status.append(manualLink, document.createTextNode('.'));
        }
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
        if (!root.querySelector('[name=retain_audio]').checked) {
            status.textContent = 'Autoriza la conservación privada del audio antes de iniciar.';
            root.querySelector('[name=retain_audio]').focus();
            return;
        }
        start.disabled = true;
        setState('requesting');
        if (timer.submitted) timer.reset();
        try {
            if (!navigator.mediaDevices || !window.MediaRecorder) throw new Error('Este navegador no admite grabación. Usa el formulario manual.');
            // Solicitar permiso de micrófono ANTES de iniciar el intento medido para evitar falsos intentos o abandonos por rechazo.
            stream = await navigator.mediaDevices.getUserMedia({audio:true});
            const mimeType = ['audio/webm;codecs=opus','audio/webm'].find(type => MediaRecorder.isTypeSupported(type));
            if (!mimeType) throw new Error('Este navegador no admite el formato de audio requerido. Usa Chrome o Edge.');
            await timer.start();
            chunks = []; recordedBytes = 0;
            recorder = new MediaRecorder(stream, {mimeType, audioBitsPerSecond:32000});
            recorder.ondataavailable = event => {
                if (event.data.size) { chunks.push(event.data); recordedBytes += event.data.size; }
                if (recordedBytes > 3500000 && recorder.state === 'recording') recorder.stop();
            };
            recorder.onstop = async () => {
                release(); stop.disabled = true; timer.submitted = true;
                setState('processing');
                status.textContent = 'Enviando audio, transcribiendo y guardando… Mantén esta pantalla abierta.';
                timer.status.textContent = 'Procesando en servidor (audio, clasificación y guardado)…';
                const submitPerf = performance.now();
                const metrics = timer.getClientMetrics();
                const form = new FormData(); form.append('audio', new Blob(chunks, {type:mimeType}), 'grabacion.webm');
                form.append('attempt_id', timer.attempt);
                form.append('retain_audio','1');
                form.append('request_kind', root.querySelector('[name=request_kind]').value);
                if (metrics.pause_count != null) form.append('pause_count', String(metrics.pause_count));
                if (metrics.paused_ms != null) form.append('paused_ms', String(metrics.paused_ms));
                if (metrics.client_prep_ms != null) form.append('client_prep_ms', String(metrics.client_prep_ms));
                const origin = root.querySelector('[name=origin_area_id]');
                if (origin) form.append('origin_area_id', origin.value);
                try {
                    if (recordedBytes > 3900000) throw new Error('El audio es demasiado grande. Graba un reporte más breve.');
                    if (navigator.onLine === false) throw new Error('Sin conexión a internet al enviar el audio.');
                    const response = await fetch('/api/tickets/voz', {
                        method:'POST',
                        body:form,
                        signal: AbortSignal.timeout(45000),
                    });
                    if (response.redirected) throw new Error('La sesión terminó. Vuelve a ingresar.');
                    const result = await response.json();
                    if (!response.ok) throw new Error(result.error || 'No se pudo crear la solicitud.');
                    const roundtripMs = Math.max(0, performance.now() - submitPerf);
                    const browserTotalMs = timer.started !== null ? Math.max(0, performance.now() - timer.started) : null;
                    timer.finish(result.total_ms, true);
                    setState('success');
                    const notas = [];
                    if (result.classification_status === 'provisional') {
                        notas.push('prioridad media provisional sujeta a revisión de TI');
                    }
                    if (result.has_mixed_requests) {
                        notas.push('se detectaron solicitudes múltiples para revisión de TI');
                    }
                    status.textContent = notas.length
                        ? `Solicitud creada (${notas.join('; ')}). `
                        : 'Solicitud creada correctamente. ';
                    const link = document.createElement('a'); link.href = '/tickets/'+result.ticket_id;
                    link.textContent = 'Ver reporte'; status.appendChild(link);
                    timer.confirmBrowser(roundtripMs, browserTotalMs, false);
                    window.dispatchEvent(new Event('ti-data-changed'));
                } catch (error) {
                    const serverState = await timer.checkStatus();
                    if (serverState?.persisted_in_db && serverState.ticket_id) {
                        const roundtripMs = Math.max(0, performance.now() - submitPerf);
                        const browserTotalMs = timer.started !== null ? Math.max(0, performance.now() - timer.started) : null;
                        timer.finish(serverState.total_ms, true, 'Guardado confirmado en BD; respuesta inicial recuperada en navegador.');
                        setState('success');
                        status.textContent = `La respuesta inicial no llegó al navegador, pero tu reporte #${serverState.ticket_id} ya está confirmado en la base de datos. `;
                        const link = document.createElement('a'); link.href = '/tickets/' + serverState.ticket_id;
                        link.textContent = 'Ver reporte'; status.appendChild(link);
                        timer.confirmBrowser(roundtripMs, browserTotalMs, true);
                        window.dispatchEvent(new Event('ti-data-changed'));
                    } else if (serverState?.outcome === 'processing') {
                        setState('processing');
                        status.textContent = 'El servidor sigue procesando tu grabación; espera unos segundos y consulta el resultado antes de grabar otro.';
                    } else if (serverState === null || navigator.onLine === false || error.name === 'TimeoutError') {
                        setState('error');
                        timer.finish(null, false, 'Pérdida de conexión o respuesta tardía sin confirmación de la BD.');
                        status.textContent = 'No se pudo confirmar si el servidor guardó el audio por pérdida de conexión o demora en la red. Verifica en tu listado antes de regrabar.';
                    } else {
                        setState('error');
                        timer.finish(null, false);
                        status.textContent = serverState?.outcome === 'failed'
                            ? `${error.message} (No se guardó ningún ticket en la base de datos.)`
                            : error.message;
                    }
                } finally { start.disabled = false; chunks = []; }
            };
            recorder.start(1000); stop.disabled = false; status.textContent = 'Grabando…';
            recordingLimit = setTimeout(() => { if (recorder.state === 'recording') recorder.stop(); }, 180000);
            setState('recording');
            visualizeAudio();
        } catch (error) {
            setState('error'); release();
            if (error?.name === 'NotAllowedError' || error?.name === 'PermissionDeniedError' || error?.name === 'NotFoundError' || error?.name === 'DevicesNotFoundError') {
                showPermissionDenied(error);
                timer.status.textContent = 'Permiso o micrófono no disponible; intento no contabilizado.';
            } else {
                status.textContent = error.message || 'No se pudo activar el micrófono.';
                if (timer.attempt) {
                    navigator.sendBeacon('/api/measurements/' + timer.attempt + '/abandon', new Blob([JSON.stringify({reason: 'connection_cancelled'})], {type: 'application/json'}));
                    timer.reset();
                }
            }
            start.disabled = false;
        }
    });
    stop.addEventListener('click', () => {
        if (recorder?.state === 'recording') {
            recorder.stop();
        }
    });
})();

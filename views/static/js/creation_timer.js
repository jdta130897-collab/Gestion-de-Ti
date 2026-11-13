class CreationTimer {
    constructor(root, channel) {
        this.root = root; this.channel = channel; this.attempt = null; this.starting = null;
        this.started = null; this.startedEpoch = null; this.submitted = false;
        this.pauseCount = 0; this.pausedMs = 0; this.lastActivityAt = null; this.hiddenSince = null;
        this.value = root.querySelector('[data-timer-value]');
        this.status = root.querySelector('[data-timer-status]');
        this.idleTimer = null;
        if (channel === 'manual') {
            root.addEventListener('input', () => {
                this.recordActivity();
                this.start().catch(() => {});
            });
        }
        document.addEventListener('visibilitychange', () => {
            if (!this.attempt || this.submitted) return;
            const now = performance.now();
            if (document.hidden) {
                this.hiddenSince = now;
            } else if (this.hiddenSince !== null) {
                const delta = now - this.hiddenSince;
                this.hiddenSince = null;
                if (delta >= 1000) {
                    this.pauseCount += 1;
                    this.pausedMs += delta;
                }
                this.lastActivityAt = now;
            }
        });
        window.addEventListener('pagehide', () => {
            if (this.attempt && !this.submitted) {
                const payload = new Blob([JSON.stringify({reason: 'user_abandoned'})], {type: 'application/json'});
                navigator.sendBeacon('/api/measurements/' + this.attempt + '/abandon', payload);
            }
        });
    }
    recordActivity() {
        const now = performance.now();
        if (this.attempt && !this.submitted && this.lastActivityAt !== null) {
            const gap = now - this.lastActivityAt;
            if (gap >= 5000) {
                this.pauseCount += 1;
                this.pausedMs += gap;
            }
        }
        this.lastActivityAt = now;
    }
    getClientMetrics() {
        this.recordActivity();
        const prep = this.started !== null ? Math.max(0, performance.now() - this.started) : null;
        return {
            pause_count: this.pauseCount,
            paused_ms: Math.round(this.pausedMs * 1000) / 1000,
            client_prep_ms: prep !== null ? Math.round(prep * 1000) / 1000 : null,
        };
    }
    async start() {
        if (this.attempt) return this.attempt;
        if (this.starting) return this.starting;
        if (navigator.onLine === false) {
            throw new Error('Sin conexión a internet. Verifica tu red antes de iniciar.');
        }
        this.started = performance.now();
        this.startedEpoch = Date.now();
        this.lastActivityAt = this.started;
        this.pauseCount = 0;
        this.pausedMs = 0;
        this.hiddenSince = null;
        this.starting = (async () => {
            try {
                const response = await fetch('/api/measurements/start', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    signal: AbortSignal.timeout(15000),
                    body: JSON.stringify({channel: this.channel, request_kind: (this.root.querySelector('[name=request_kind]:checked') || this.root.querySelector('[name=request_kind]'))?.value || 'incident', origin_area_id: this.root.querySelector('[name=origin_area_id]')?.value || null})
                });
                if (!response.ok || response.redirected) throw new Error('No se pudo iniciar la medición. Revisa tu sesión y vuelve a intentarlo.');
                const data = await response.json(); this.attempt = data.attempt_id;
                const hiddenInput = this.root.querySelector('[name=attempt_id]');
                if (hiddenInput) hiddenInput.value = this.attempt;
                this.status.textContent = 'Medición en curso (incluye pausas hasta el envío).';
                this.tick = setInterval(() => this.paint(performance.now()-this.started), 100);
                return this.attempt;
            } catch (error) {
                this.status.textContent = error.name === 'TimeoutError' ? 'Tiempo de espera agotado al iniciar medición.' : error.message;
                this.starting = null;
                throw error;
            }
        })();
        return this.starting;
    }
    async checkStatus() {
        if (!this.attempt) return null;
        try {
            const response = await fetch(`/api/measurements/${encodeURIComponent(this.attempt)}/status`, {
                signal: AbortSignal.timeout(8000),
            });
            if (!response.ok) return null;
            return await response.json();
        } catch (_) {
            return null;
        }
    }
    confirmBrowser(roundtripMs, browserTotalMs, recoveredFromStatus = false) {
        if (!this.attempt) return Promise.resolve(null);
        return CreationTimer.sendBrowserConfirm(this.attempt, roundtripMs, browserTotalMs, recoveredFromStatus);
    }
    static async sendBrowserConfirm(attemptId, roundtripMs, browserTotalMs, recoveredFromStatus = false) {
        if (!attemptId) return null;
        try {
            const response = await fetch(`/api/measurements/${encodeURIComponent(attemptId)}/confirm`, {
                method: 'POST',
                keepalive: true,
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    browser_roundtrip_ms: roundtripMs,
                    browser_total_ms: browserTotalMs,
                    recovered_from_status: recoveredFromStatus,
                }),
            });
            if (!response.ok) return null;
            return await response.json();
        } catch (_) {
            return null;
        }
    }
    paint(ms) {
        const seconds = ms/1000;
        this.value.textContent = `${Math.floor(seconds/60).toString().padStart(2,'0')}:${(seconds%60).toFixed(1).padStart(4,'0')}`;
    }
    finish(ms, success, note = null) {
        clearInterval(this.tick);
        this.paint(ms ?? performance.now()-this.started);
        this.status.textContent = note || (success
            ? 'Guardado en servidor confirmado; recepción registrada en navegador.'
            : 'Intento sin éxito. No se contabiliza como creación exitosa.');
    }
    reset() {
        clearInterval(this.tick); this.attempt = null; this.starting = null; this.submitted = false;
        this.pauseCount = 0; this.pausedMs = 0; this.lastActivityAt = null; this.hiddenSince = null;
        const hiddenInput = this.root.querySelector('[name=attempt_id]');
        if (hiddenInput) hiddenInput.value = '';
    }
}
window.CreationTimer = CreationTimer;

(() => {
    try {
        const raw = sessionStorage.getItem('ti_pending_manual_confirm');
        if (raw && window.location.pathname !== '/tickets/create') {
            sessionStorage.removeItem('ti_pending_manual_confirm');
            const pending = JSON.parse(raw);
            if (pending?.attempt_id) {
                const nowEpoch = Date.now();
                const roundtripMs = pending.submit_epoch ? Math.max(0, nowEpoch - pending.submit_epoch) : null;
                const browserTotalMs = pending.started_epoch ? Math.max(0, nowEpoch - pending.started_epoch) : null;
                CreationTimer.sendBrowserConfirm(pending.attempt_id, roundtripMs, browserTotalMs, false);
            }
        }
    } catch (_) { /* Ignorar almacenamiento restringido del navegador. */ }
})();

function setHiddenField(form, name, value) {
    let field = form.querySelector(`input[name="${name}"]`);
    if (!field) {
        field = document.createElement('input');
        field.type = 'hidden';
        field.name = name;
        form.appendChild(field);
    }
    field.value = value == null ? '' : String(value);
}

document.querySelectorAll('form[data-creation-channel="manual"]').forEach(form => {
    const timer = new CreationTimer(form, 'manual');
    form.addEventListener('submit', async event => {
        event.preventDefault();
        if (timer.sending) return;
        if (!form.reportValidity()) return;
        if (navigator.onLine === false) {
            timer.status.textContent = 'Sin conexión a internet. Tu texto se conserva; reconecta e intenta nuevamente.';
            return;
        }
        timer.sending = true;
        try {
            await timer.start();
            timer.submitted = true;
            const metrics = timer.getClientMetrics();
            setHiddenField(form, 'pause_count', metrics.pause_count);
            setHiddenField(form, 'paused_ms', metrics.paused_ms);
            setHiddenField(form, 'client_prep_ms', metrics.client_prep_ms);
            try {
                sessionStorage.setItem('ti_pending_manual_confirm', JSON.stringify({
                    attempt_id: timer.attempt,
                    started_epoch: timer.startedEpoch || Date.now(),
                    submit_epoch: Date.now(),
                }));
            } catch (_) { /* Ignorar si sessionStorage no está disponible. */ }
            timer.status.textContent = 'Enviando y guardando en servidor…';
            form.querySelectorAll('button[type=submit]').forEach(button => button.disabled = true);
            // Enviar directamente: requestSubmit vuelve a disparar este mismo evento.
            // Deshabilitar el botón durante ese ciclo puede cancelar el envío nativo.
            HTMLFormElement.prototype.submit.call(form);
            timer.navigationTimeout = setTimeout(async () => {
                const state = await timer.checkStatus();
                if (state?.persisted_in_db && state.ticket_id) {
                    const roundtripMs = Math.max(0, Date.now() - (timer.startedEpoch || Date.now()));
                    timer.finish(state.total_ms, true, 'Guardado confirmado en servidor; respuesta recuperada en navegador.');
                    timer.confirmBrowser(state.preparation_ms != null ? Math.max(0, roundtripMs - state.preparation_ms) : null, roundtripMs, true);
                    timer.status.innerHTML = '';
                    const text = document.createTextNode(`El navegador no recibió la redirección, pero tu reporte #${state.ticket_id} ya quedó confirmado en la base de datos. `);
                    const link = document.createElement('a');
                    link.href = `/tickets/${state.ticket_id}`;
                    link.textContent = 'Ver reporte';
                    timer.status.append(text, link);
                    window.dispatchEvent(new Event('ti-data-changed'));
                    return;
                }
                timer.sending = false;
                timer.submitted = false;
                try { sessionStorage.removeItem('ti_pending_manual_confirm'); } catch (_) {}
                if (state === null || navigator.onLine === false) {
                    timer.status.textContent = 'No se pudo verificar el estado por pérdida de conexión o respuesta tardía. Puedes reintentar con el mismo intento sin duplicar el reporte.';
                } else if (state?.outcome === 'processing') {
                    timer.status.textContent = 'El servidor sigue procesando el guardado. Espera un momento antes de reintentar.';
                } else {
                    timer.status.textContent = state?.status_message || 'El navegador no recibió confirmación de la base de datos. Puedes reintentar sin duplicar el reporte.';
                }
                form.querySelectorAll('button[type=submit]').forEach(button => button.disabled = false);
            }, 20000);
        } catch (error) {
            timer.sending = false;
            timer.submitted = false;
            timer.status.textContent = error.name === 'TimeoutError'
                ? 'Respuesta tardía al iniciar la medición. Tu texto se conserva; vuelve a guardar.'
                : error.message;
            form.querySelectorAll('button[type=submit]').forEach(button => button.disabled = false);
        }
    });
});

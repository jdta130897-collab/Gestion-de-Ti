class CreationTimer {
    constructor(root, channel) {
        this.root = root; this.channel = channel; this.attempt = null; this.starting = null;
        this.started = null; this.submitted = false;
        this.value = root.querySelector('[data-timer-value]');
        this.status = root.querySelector('[data-timer-status]');
        root.addEventListener('input', () => this.start().catch(() => {}));
        window.addEventListener('pagehide', () => {
            if (this.attempt && !this.submitted) navigator.sendBeacon('/api/measurements/' + this.attempt + '/abandon', '');
        });
    }
    async start() {
        if (this.attempt) return this.attempt;
        if (this.starting) return this.starting;
        this.started = performance.now();
        this.starting = (async () => {
            try {
                const response = await fetch('/api/measurements/start', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({channel: this.channel, request_kind: this.root.querySelector('[name=request_kind]')?.value || 'incident', origin_area_id: this.root.querySelector('[name=origin_area_id]')?.value || null})
                });
                if (!response.ok || response.redirected) throw new Error('No se pudo iniciar la medición. Revisa tu sesión y vuelve a intentarlo.');
                const data = await response.json(); this.attempt = data.attempt_id;
                this.root.querySelector('[name=attempt_id]').value = this.attempt;
                this.status.textContent = 'Medición en curso. El tiempo incluye las pausas.';
                this.tick = setInterval(() => this.paint(performance.now()-this.started), 100);
                return this.attempt;
            } catch (error) {
                this.status.textContent = error.message; this.starting = null; throw error;
            }
        })();
        return this.starting;
    }
    paint(ms) {
        const seconds = ms/1000;
        this.value.textContent = `${Math.floor(seconds/60).toString().padStart(2,'0')}:${(seconds%60).toFixed(1).padStart(4,'0')}`;
    }
    finish(ms, success) {
        clearInterval(this.tick);
        this.paint(ms ?? performance.now()-this.started);
        this.status.textContent = success ? 'Creación confirmada. Tiempo registrado en las estadísticas.' : 'Intento sin éxito. No se contabiliza como creación exitosa.';
    }
    reset() {
        clearInterval(this.tick); this.attempt = null; this.starting = null; this.submitted = false;
        this.root.querySelector('[name=attempt_id]').value = '';
    }
}
window.CreationTimer = CreationTimer;
document.querySelectorAll('form[data-creation-channel="manual"]').forEach(form => {
    const timer = new CreationTimer(form, 'manual');
    form.addEventListener('submit', async event => {
        if (timer.submitted) return;
        event.preventDefault();
        if (timer.sending) return;
        timer.sending = true;
        try {
            await timer.start(); timer.submitted = true;
            timer.status.textContent = 'Guardando la solicitud…';
            form.querySelectorAll('button[type=submit]').forEach(button => button.disabled = true);
            form.requestSubmit();
        } catch (_) { timer.sending = false; /* Permite reintentar tras el error. */ }
    });
});

(() => {
    const element = document.getElementById('ticket-preview-modal');
    if (!element || !window.bootstrap) return;
    const modal = bootstrap.Modal.getOrCreateInstance(element);
    const body = document.getElementById('ticket-preview-body');
    const title = document.getElementById('ticket-preview-title');
    let pending;

    element.addEventListener('hidden.bs.modal', () => pending?.abort());
    document.addEventListener('click', async (event) => {
        const trigger = event.target.closest('a[data-ticket-preview]');
        if (!trigger) return;
        event.preventDefault();
        pending?.abort();
        const controller = new AbortController();
        pending = controller;
        title.textContent = 'Vista previa del reporte';
        body.textContent = 'Cargando reporte…';
        body.setAttribute('aria-busy', 'true');
        modal.show(trigger);
        try {
            const url = new URL(trigger.href);
            url.searchParams.set('preview', '1');
            const response = await fetch(url, { signal: controller.signal });
            if (!response.ok || response.redirected) throw new Error('access');
            const page = new DOMParser().parseFromString(await response.text(), 'text/html');
            const content = page.querySelector('.report-preview');
            if (!content) throw new Error('content');
            title.textContent = content.dataset.reportTitle || 'Vista previa del reporte';
            body.replaceChildren(content);
        } catch (error) {
            if (error.name !== 'AbortError') {
                body.textContent = 'No se pudo cargar el reporte. Comprueba tu sesión y vuelve a intentarlo.';
            }
        } finally {
            if (pending === controller) body.removeAttribute('aria-busy');
        }
    });
})();

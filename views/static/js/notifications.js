(() => {
    const root = document.getElementById('notification-list');
    if (!root) return;
    const badge = document.getElementById('notification-count');
    const dropdown = document.getElementById('notification-dropdown');
    const desktop = dropdown.parentElement, mobile = document.getElementById('mobile-notification-slot');
    const breakpoint = window.matchMedia('(max-width: 991px)');
    function position() { (breakpoint.matches ? mobile : desktop).prepend(dropdown); }
    position(); breakpoint.addEventListener('change', position);
    let busy = false;
    async function refresh() {
        if (busy || document.hidden) return;
        busy = true;
        try {
            const response = await fetch('/api/notifications', {cache:'no-store'});
            if (!response.ok || response.redirected) return;
            const data = await response.json(); badge.textContent = data.unread; badge.hidden = data.unread===0;
            root.replaceChildren();
            for (const item of data.items) {
                const link = document.createElement('a'); link.href = '/tickets/'+item.ticket_id;
                link.className = 'notification-item'+(item.read ? '' : ' unread');
                const message = document.createElement('span'); message.textContent = item.message;
                const time = document.createElement('small'); time.textContent = new Date(item.created_at).toLocaleString('es-PE');
                link.append(message,time);
                link.addEventListener('click', () => fetch('/api/notifications/'+item.id+'/read', {method:'POST',keepalive:true}));
                root.appendChild(link);
            }
            if (!data.items.length) root.textContent = 'No tienes notificaciones.';
        } catch (_) { root.textContent = 'No se pudieron actualizar las notificaciones. Se reintentará automáticamente.'; }
        finally {busy=false;}
    }
    refresh(); setInterval(refresh,5000);
    document.addEventListener('visibilitychange',refresh); window.addEventListener('ti-data-changed',refresh);
})();

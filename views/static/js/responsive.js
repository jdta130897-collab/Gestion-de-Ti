document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('menu-toggle');
    const sidebar = document.getElementById('sidebar');
    const backdrop = document.getElementById('sidebar-backdrop');
    const close = document.getElementById('menu-close');
    const main = document.getElementById('app-main');
    const mobile = window.matchMedia('(max-width: 991.98px)');
    if (!toggle || !sidebar) return;
    function setOpen(open, restoreFocus = true) {
        open = open && mobile.matches;
        document.body.classList.toggle('menu-open', open);
        toggle.setAttribute('aria-expanded', String(open));
        toggle.setAttribute('aria-label', open ? 'Cerrar menu' : 'Abrir menu');
        backdrop.hidden = !open;
        main.inert = open;
        if (open) close.focus();
        else if (restoreFocus) toggle.focus();
    }
    toggle.addEventListener('click', () => setOpen(!document.body.classList.contains('menu-open')));
    close.addEventListener('click', () => setOpen(false));
    backdrop.addEventListener('click', () => setOpen(false));
    sidebar.querySelectorAll('a').forEach(link => link.addEventListener('click', () => setOpen(false, false)));
    document.addEventListener('keydown', event => {
        if (!document.body.classList.contains('menu-open')) return;
        if (event.key === 'Escape') { event.preventDefault(); setOpen(false); }
        if (event.key === 'Tab') {
            const items = [...sidebar.querySelectorAll('a[href], button:not([disabled])')].filter(el => el.getClientRects().length);
            const first = items[0], last = items[items.length - 1];
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        }
    });
    mobile.addEventListener('change', () => {
        setOpen(false, false);
        if (!mobile.matches && document.activeElement === close) sidebar.querySelector('a')?.focus();
    });
});

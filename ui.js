// ===== Conexão BIO — camada de interface =====
//
// Duas coisas que o navegador não dá de graça:
//   1. LOADER global de carregamento (spinner + bloqueio de tela enquanto a API responde)
//   2. MODAIS de confirmação, exclusão e aviso (no lugar do confirm()/alert() nativo)
//
// Sem framework, sem CDN: só DOM + CSS. Tudo aqui é opcional — se o elemento
// não existir na página, a função simplesmente não faz nada.

const UI = (() => {

    // ---------- Loader global ----------

    const MIN_SHOW_DELAY = 120;   // respostas rápidas não devem piscar o loader
    const MIN_VISIBLE_TIME = 250; // e ele não some em um piscar de olhos

    let pending = 0;
    let showTimer = null;
    let hideTimer = null;
    let visibleSince = 0;

    function loaderNode() {
        return document.getElementById('global-loader');
    }

    function loaderIsVisible() {
        const el = loaderNode();
        return !!el && el.classList.contains('is-visible');
    }

    function setLoaderText(text) {
        const el = loaderNode();
        if (!el || !text) return;
        const label = el.querySelector('.loader-label');
        if (label) label.textContent = text;
    }

    function showLoader(text) {
        const el = loaderNode();
        if (!el) return;
        setLoaderText(text || 'Carregando…');

        // Cancela um "esconder" que estava agendado: o pedido ainda está em voo.
        if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
        if (showTimer || loaderIsVisible()) return;

        showTimer = setTimeout(() => {
            showTimer = null;
            const e = loaderNode();
            if (!e) return;
            e.classList.add('is-visible');
            e.setAttribute('aria-hidden', 'false');
            visibleSince = Date.now();
        }, MIN_SHOW_DELAY);
    }

    function hideLoader() {
        if (showTimer) { clearTimeout(showTimer); showTimer = null; }
        if (!loaderIsVisible()) return;

        const remaining = Math.max(0, MIN_VISIBLE_TIME - (Date.now() - visibleSince));
        hideTimer = setTimeout(() => {
            hideTimer = null;
            const e = loaderNode();
            if (!e) return;
            e.classList.remove('is-visible');
            e.setAttribute('aria-hidden', 'true');
        }, remaining);
    }

    // Toda requisição ao servidor abre e fecha o loader automaticamente.
    // (intercepta o fetch: vale para a API, para o login e para qualquer outra chamada)
    const nativeFetch = typeof window.fetch === 'function' ? window.fetch.bind(window) : null;
    if (nativeFetch) {
        window.fetch = function (...args) {
            pending += 1;
            showLoader();
            let promise;
            try {
                promise = nativeFetch(...args);
            } catch (e) {
                pending -= 1;
                if (pending <= 0) hideLoader();
                throw e;
            }
            return Promise.resolve(promise).finally(() => {
                pending -= 1;
                if (pending <= 0) hideLoader();
            });
        };
    }

    // ---------- Botão em estado de carregamento ----------

    function busy(button, on, label) {
        if (!button) return;
        if (on) {
            if (!button.dataset.busyOriginal) button.dataset.busyOriginal = button.innerHTML;
            button.classList.add('is-busy');
            button.disabled = true;
            button.innerHTML = `<span class="spinner sm" aria-hidden="true"></span>${label ? ` ${label}` : ''}`;
            button.setAttribute('aria-busy', 'true');
        } else {
            button.classList.remove('is-busy');
            button.removeAttribute('aria-busy');
            button.disabled = false;
            if (button.dataset.busyOriginal) {
                button.innerHTML = button.dataset.busyOriginal;
                delete button.dataset.busyOriginal;
            }
        }
    }

    // Executa uma ação com o botão travado e girando; devolve o resultado da ação.
    async function withBusy(button, action, label) {
        busy(button, true, label);
        try {
            return await action();
        } finally {
            busy(button, false);
        }
    }

    // ---------- Modais ----------

    const ICON_BY_VARIANT = {
        danger: 'trash',
        warning: 'warning',
        success: 'check',
        info: 'info'
    };

    function iconSvg(name) {
        if (!name) return '';
        return `<svg class="icon" aria-hidden="true" focusable="false"><use href="#i-${name}"></use></svg>`;
    }

    function modalNodes() {
        return {
            overlay: document.getElementById('modal-overlay'),
            card: document.getElementById('modal-card'),
            icon: document.getElementById('modal-icon'),
            title: document.getElementById('modal-title'),
            message: document.getElementById('modal-message'),
            confirm: document.getElementById('modal-confirm'),
            cancel: document.getElementById('modal-cancel')
        };
    }

    // Fila: um modal por vez, mesmo que vários avisos venham juntos.
    let modalQueue = Promise.resolve();

    function openModal(options = {}) {
        const d = modalNodes();
        if (!d.overlay || !d.confirm) return Promise.resolve(false);

        const {
            title = 'Confirmar',
            message = '',
            confirmText = 'Confirmar',
            cancelText = 'Cancelar',
            variant = 'info',
            icon = null,
            hideCancel = false
        } = options;

        return new Promise((resolve) => {
            d.title.textContent = title;
            d.message.textContent = message;
            d.message.hidden = !message;

            d.card.className = `modal-card ${variant}`;
            const iconName = icon || ICON_BY_VARIANT[variant] || ICON_BY_VARIANT.info;
            d.icon.innerHTML = iconSvg(iconName);
            d.icon.hidden = !iconName;

            d.confirm.textContent = confirmText;
            d.confirm.className = 'btn-table ' + (variant === 'danger' ? 'danger' : variant === 'warning' ? 'warn' : '');
            d.cancel.textContent = cancelText;
            d.cancel.className = 'btn-table neutral';
            d.cancel.style.display = hideCancel ? 'none' : '';

            const previousFocus = document.activeElement;

            const close = (result) => {
                document.removeEventListener('keydown', onKeyDown);
                d.overlay.removeEventListener('mousedown', onBackdrop);
                d.overlay.classList.remove('is-visible');
                d.overlay.setAttribute('aria-hidden', 'true');
                if (previousFocus && previousFocus.focus) previousFocus.focus();
                resolve(result);
            };

            const onKeyDown = (e) => {
                if (e.key === 'Escape') {
                    e.preventDefault();
                    close(false);
                } else if (e.key === 'Enter' && d.cancel.style.display !== 'none' && document.activeElement === d.cancel) {
                    e.preventDefault();
                    close(false);
                }
            };

            // Clicar fora do cartão também cancela.
            const onBackdrop = (e) => { if (e.target === d.overlay) close(false); };

            d.confirm.onclick = () => close(true);
            d.cancel.onclick = () => close(false);
            document.addEventListener('keydown', onKeyDown);
            d.overlay.addEventListener('mousedown', onBackdrop);

            d.overlay.classList.add('is-visible');
            d.overlay.setAttribute('aria-hidden', 'false');
            d.confirm.focus();
        });
    }

    function enqueue(task) {
        const run = modalQueue.then(task, task);
        modalQueue = run.then(() => {}, () => {});
        return run;
    }

    // Confirmação: resolve true (confirmou) ou false (cancelou).
    function confirm(options = {}) {
        return enqueue(() => openModal(Object.assign({ variant: 'info' }, options)));
    }

    // Aviso: resolve quando o usuário fecha.
    function alert(options = {}) {
        const opts = typeof options === 'string' ? { message: options } : (options || {});
        return enqueue(() => openModal(Object.assign({
            title: 'Atenção',
            confirmText: 'Entendi',
            hideCancel: true,
            variant: 'info'
        }, opts)));
    }

    // ---------- Aviso rápido (sem travar a tela) ----------

    function toast(message, variant = 'info', duration = 3800) {
        const box = document.getElementById('toast-container');
        if (!box) return;
        const el = document.createElement('div');
        el.className = `toast ${variant}`;
        el.setAttribute('role', 'status');
        el.textContent = message;
        el.addEventListener('click', () => el.remove());
        box.appendChild(el);
        setTimeout(() => el.remove(), duration);
    }

    // O alert() nativo vira o modal do projeto. O código antigo continua valendo.
    window.alert = function (message) {
        alert({ message: String(message ?? '') });
    };

    return {
        showLoader,
        hideLoader,
        setLoaderText,
        busy,
        withBusy,
        confirm,
        alert,
        toast
    };
})();

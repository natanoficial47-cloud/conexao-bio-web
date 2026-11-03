// ===== Estresse em Foco — front-end =====
//
// SEGURANÇA: o token de sessão NÃO fica no localStorage. Ele mora num cookie
// HttpOnly que o navegador envia sozinho e que o JavaScript não consegue ler.
// O front pergunta ao servidor quem é o usuário (GET /api/me) e pronto.

function resolveApiBase() {
    const meta = document.querySelector('meta[name="api-base"]');
    const raw = meta ? meta.content.trim() : '';

    // Configuracao explicita tem prioridade.
    if (raw && raw !== 'auto') return raw.replace(/\/+$/, '');

    // "auto": em desenvolvimento (Live Server na 5500) a API roda em outra porta;
    // em producao (Vercel) usamos a propria origem, via rewrite /api -> API.
    // Assim o navegador ve uma origem so e o cookie HttpOnly continua Lax.
    const isDev = location.port === '5500' || location.protocol === 'file:';
    return isDev ? 'http://127.0.0.1:8000/api' : '/api';
}

const API = resolveApiBase();

// Guarda a sessão atual em memória (nada de token no navegador).
let session = null;   // { id, name, email, role }
let selectedMood = '';

// ---------- utilitários ----------

// Escapa texto antes de colocar em innerHTML (evita XSS)
function esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
}

function fieldValue(id) {
    const el = document.getElementById(id);
    return el ? el.value.trim() : '';
}

function show(id, visible) {
    const el = document.getElementById(id);
    if (el) el.style.display = visible ? 'block' : 'none';
}

function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function errorMessage(data, fallback) {
    return (data && typeof data.detail === 'string') ? data.detail : fallback;
}

// Ícone SVG embutido (sem CDN, sem Font Awesome)
function icon(name, className = 'icon') {
    return `<svg class="${className}" aria-hidden="true" focusable="false"><use href="#i-${name}"></use></svg>`;
}

// ---------- sessão ----------

// Se a API estava dormindo (plano gratuito), a primeira resposta demora. Avisamos
// depois de 3 segundos para a espera não parecer travamento.
async function withWakeNotice(work) {
    const timer = setTimeout(() => setText(
        'server-status', 'Acordando o servidor... na primeira vez do dia pode levar até 1 minuto.'), 3000);
    try {
        return await work();
    } finally {
        clearTimeout(timer);
        setText('server-status', '');
    }
}

// fetch autenticado: o cookie HttpOnly viaja sozinho (credentials: 'include').
// Se o servidor responder 401, a sessão acabou e voltamos para o login.
async function apiFetch(path, options = {}) {
    const headers = Object.assign({}, options.headers || {});
    const res = await fetch(`${API}${path}`, Object.assign({}, options, {
        headers,
        credentials: 'include'
    }));
    if (res.status === 401) {
        const wasLogged = !!session;
        session = null;
        if (wasLogged) {
            showLoginScreen();
            alert('Sua sessão expirou. Entre novamente.');
        }
        throw new Error('sessao expirada');
    }
    // 403 com "troca de senha" = o PIN provisório ainda não foi trocado.
    if (res.status === 403) {
        const data = await res.clone().json().catch(() => ({}));
        if (typeof data.detail === 'string' && data.detail.toLowerCase().includes('troca de senha')) {
            openPasswordScreen(true);
            throw new Error('troca de senha obrigatoria');
        }
    }
    return res;
}

function showLoginScreen() {
    show('auth-container', true);
    show('view-student', false);
    show('view-teacher', false);
    show('view-admin', false);
    show('view-staffadmin', false);
    show('view-logs', false);
    show('view-missions-admin', false);
    show('staff-nav', false);
    show('password-container', false);
}

// ---------- troca de senha ----------

// A mesma regra do servidor, para dar retorno na hora (o servidor continua
// sendo a autoridade: nunca confiamos só no navegador).
const MIN_PASSWORD_LENGTH = 10;

function normalizePassword(value) {
    return String(value || '').toLowerCase().replace(/[^a-z0-9]/g, '');
}

function isSequential(text) {
    // Qualquer pedaço de 6+ caracteres em ordem (123456, abcdef) conta.
    if (text.length < 6) return false;
    for (let i = 0; i <= text.length - 6; i++) {
        const diffs = new Set();
        for (let k = 1; k < 6; k++) {
            diffs.add(text.charCodeAt(i + k) - text.charCodeAt(i + k - 1));
        }
        const only = [...diffs];
        if (only.length === 1 && (only[0] === 1 || only[0] === -1)) return true;
    }
    return false;
}

function passwordProblem(password) {
    if (!password || password.length < MIN_PASSWORD_LENGTH) {
        return `A senha precisa ter pelo menos ${MIN_PASSWORD_LENGTH} caracteres.`;
    }
    const flat = normalizePassword(password);
    if (!flat) return 'A senha precisa ter letras ou números.';
    if (new Set(flat).size === 1) return 'A senha não pode repetir o mesmo caractere.';
    if (/^\d+$/.test(flat)) return 'A senha precisa combinar letras e números.';
    if (isSequential(flat)) return 'A senha não pode ter uma sequência (ex: 123456).';
    return null;
}

// Barra de força: simples, sem library.
function checkPasswordStrength() {
    const password = document.getElementById('pwd-new').value;
    const bar = document.getElementById('pwd-meter-bar');
    const hint = document.getElementById('pwd-hint');
    const problem = passwordProblem(password);
    let score = 0;
    if (password.length >= MIN_PASSWORD_LENGTH) score++;
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
    if (/\d/.test(password)) score++;
    if (/[^A-Za-z0-9]/.test(password)) score++;
    if (password.length >= 14) score++;

    if (bar) {
        const pct = Math.min(100, (score / 5) * 100);
        bar.style.width = `${pct}%`;
        bar.className = 'pwd-meter-bar ' + (score <= 1 ? 'weak' : score <= 3 ? 'medium' : 'strong');
    }
    if (hint) {
        hint.textContent = problem
            ? problem
            : 'Boa! Essa senha serve.';
        hint.className = 'pwd-hint ' + (problem ? 'is-error' : 'is-ok');
    }
    return !problem;
}

// forced = true  -> troca obrigatória (PIN provisório): não deixa sair sem trocar
// forced = false -> troca voluntária
function openPasswordScreen(forced) {
    show('auth-container', false);
    show('view-student', false);
    show('view-teacher', false);
    show('view-admin', false);
    show('view-staffadmin', false);
    show('view-logs', false);
    show('view-missions-admin', false);
    show('staff-nav', false);
    show('password-container', true);

    setText('password-title', forced ? 'Crie a sua senha' : 'Trocar minha senha');
    setText('password-subtitle', forced
        ? 'O PIN provisório precisa ser trocado por uma senha só sua antes de continuar.'
        : 'Escolha uma senha nova para proteger o seu acesso.');
    setText('pwd-status', '');
    document.getElementById('pwd-logout-row').style.display = forced ? 'block' : 'none';
    ['pwd-current', 'pwd-new', 'pwd-new2'].forEach(id => { document.getElementById(id).value = ''; });
    checkPasswordStrength();
}

async function changePassword(btn) {
    const current = document.getElementById('pwd-current').value;
    const next = document.getElementById('pwd-new').value;
    const confirm = document.getElementById('pwd-new2').value;

    if (!current) {
        setText('pwd-status', 'Informe a senha atual (ou o PIN provisório).');
        return;
    }
    const problem = passwordProblem(next);
    if (problem) {
        setText('pwd-status', problem);
        return;
    }
    if (next !== confirm) {
        setText('pwd-status', 'As senhas não são iguais.');
        return;
    }

    await UI.withBusy(btn, async () => {
        try {
            const res = await fetch(`${API}/password/change`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ current_password: current, new_password: next }),
                credentials: 'include'
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                setText('pwd-status', errorMessage(data, 'Não foi possível trocar a senha.'));
                return;
            }
            setText('pwd-status', 'Senha trocada! Levando você para o seu painel...');
            show('password-container', false);
            startSession({ name: data.name, role: data.role, must_change_password: false });
        } catch (e) {
            console.error(e);
            setText('pwd-status', 'Não foi possível conectar ao servidor.');
        }
    }, 'Salvando…');
}

// Entra na tela correspondente ao perfil que o servidor informou.
function startSession(data) {
    session = data;
    show('auth-container', false);
    show('password-container', false);

    // PIN provisório: a troca de senha vem ANTES de qualquer painel.
    if (data.must_change_password) {
        openPasswordScreen(true);
        return;
    }

    if (data.role === 'student') {
        show('view-student', true);
        const first = (data.name || '').split(' ')[0];
        setText('student-welcome-title', `Olá, ${first}!`);
        setText('current-student-label', data.name || '');
        loadDiary();
    } else if (data.role === 'teacher') {
        show('view-teacher', true);
        loadTeacherData();
    } else if (data.role === 'psychologist' || data.role === 'admin') {
        initStaffNav(data.role); // uma tela de cada vez
    } else {
        session = null;
        showLoginScreen();
    }
}

// ---------- inicialização ----------
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const res = await withWakeNotice(() => fetch(`${API}/me`, { credentials: 'include' }));
        if (!res.ok) {
            showLoginScreen();
            return;
        }
        startSession(await res.json());
    } catch (e) {
        console.error(e);
        showLoginScreen();
    }
});

// Menu da equipe (uma tela de cada vez):
//   admin: Turma | Indicadores | Missões | Equipe | Acessos     psicóloga: Indicadores | Missões
const STAFF_TABS = {
    admin: ['class', 'metrics', 'missions', 'team', 'logs'],
    psychologist: ['metrics', 'missions']
};
const ALL_STAFF_TABS = ['class', 'metrics', 'missions', 'team', 'logs'];

function initStaffNav(role) {
    const allowed = STAFF_TABS[role] || [];
    ALL_STAFF_TABS.forEach(t => {
        const btn = document.getElementById(`snav-btn-${t}`);
        if (btn) btn.style.display = allowed.includes(t) ? '' : 'none';
    });
    show('staff-nav', true);
    switchStaffTab(allowed[0]);
}

function switchStaffTab(tab) {
    show('view-teacher', tab === 'class');
    show('view-admin', tab === 'metrics');
    show('view-missions-admin', tab === 'missions');
    show('view-staffadmin', tab === 'team');
    show('view-logs', tab === 'logs');
    ALL_STAFF_TABS.forEach(t => {
        const btn = document.getElementById(`snav-btn-${t}`);
        if (btn) btn.classList.toggle('active', t === tab);
    });
    if (tab === 'class') loadTeacherData();
    if (tab === 'metrics') loadAdminMetrics();
    if (tab === 'missions') { cancelMissionForm(); loadManageMissions(); }
    if (tab === 'logs') loadAccessLog();
}

// ---------- login / cadastro ----------
function showAuthForm(mode) {
    const isLogin = mode === 'login';
    show('login-form', isLogin);
    show('register-form', !isLogin);
    setText('auth-title', isLogin ? 'Entrar na plataforma' : 'Criar conta de estudante');
    setText('auth-subtitle', isLogin
        ? 'Use seu e-mail ou matrícula e sua senha para acessar.'
        : 'Preencha seus dados e o código de acesso que a escola informou.');
}

async function postLogin(email, password) {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);
    const res = await fetch(`${API}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData,
        credentials: 'include'
    });
    const data = await res.json().catch(() => ({}));
    return { res, data };
}

// Login único: serve para estudantes e equipe. O perfil vem do servidor.
async function loginUser(btn) {
    const email = fieldValue('auth-email');
    const password = document.getElementById('auth-password').value;

    if (!email || !password) {
        alert('Informe seu e-mail ou matrícula e a senha.');
        return;
    }

    await UI.withBusy(btn, async () => {
        try {
            const { res, data } = await withWakeNotice(() => postLogin(email, password));
            if (!res.ok) {
                alert(errorMessage(data, 'E-mail/matrícula ou senha incorretos.'));
                return;
            }
            document.getElementById('auth-password').value = '';
            startSession({
                name: data.name,
                role: data.role,
                must_change_password: !!data.must_change_password
            });
        } catch (e) {
            console.error(e);
            alert('Não foi possível conectar ao servidor. Tente de novo em instantes.');
        }
    }, 'Entrando…');
}

// Aluno: criar a própria conta (nome + e-mail/matrícula + senha + código de acesso)
async function registerStudent(btn) {
    const name = fieldValue('reg-student-name');
    const email = fieldValue('reg-student-email');
    const password = document.getElementById('reg-student-password').value;
    const password2 = document.getElementById('reg-student-password2').value;
    const classCode = fieldValue('reg-class-code');

    if (!name || !email || !password || !classCode) {
        alert('Preencha todos os campos.');
        return;
    }
    const pwdProblem = passwordProblem(password);
    if (pwdProblem) {
        alert(pwdProblem);
        return;
    }
    if (password !== password2) {
        alert('As senhas não são iguais.');
        return;
    }

    await UI.withBusy(btn, async () => {
        try {
            const res = await withWakeNotice(() => fetch(`${API}/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, email, password, class_code: classCode }),
                credentials: 'include'
            }));
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                alert(errorMessage(data, 'Confira os dados informados e tente novamente.'));
                return;
            }
            document.getElementById('reg-student-password').value = '';
            document.getElementById('reg-student-password2').value = '';
            startSession({
                name: data.name,
                role: data.role,
                must_change_password: !!data.must_change_password
            });
        } catch (e) {
            console.error(e);
            alert('Não foi possível conectar ao servidor.');
        }
    }, 'Criando conta…');
}

// Logout de verdade: o servidor revoga o token e apaga o cookie.
async function logoutSession(btn) {
    UI.busy(btn, true);           // trava o botão enquanto a decisão é tomada
    let ok = false;
    try {
        ok = await UI.confirm({
            title: 'Sair da plataforma',
            message: 'Você vai precisar entrar de novo com e-mail ou matrícula e senha.',
            confirmText: 'Sair',
            cancelText: 'Ficar conectado'
        });
    } finally {
        if (!ok) UI.busy(btn, false);
    }
    if (!ok) return;

    try {
        await fetch(`${API}/logout`, { method: 'POST', credentials: 'include' });
    } catch (e) {
        console.error(e);
    }
    UI.busy(btn, false);
    session = null;
    showLoginScreen();
}

// ---------- painel do estudante ----------
function switchStudentTab(tabId) {
    ['home', 'missions', 'dna', 'diary', 'help'].forEach(t => {
        const content = document.getElementById(`stab-${t}`);
        const btn = document.getElementById(`stab-btn-${t}`);
        if (content) content.style.display = (t === tabId) ? 'block' : 'none';
        if (btn) btn.classList.toggle('active', t === tabId);
    });
    if (tabId === 'diary') loadDiary();
    if (tabId === 'missions') loadMissions();
    if (tabId === 'dna') loadDna();
}

function selectMood(mood) {
    selectedMood = mood;
    document.querySelectorAll('#mood-selector .mood-btn').forEach(b => {
        const selected = !!mood && b.dataset.mood === mood;
        b.style.borderColor = selected ? 'var(--lilac-600)' : 'var(--gray-200)';
        b.style.backgroundColor = selected ? 'var(--lilac-50)' : 'white';
    });
}

async function saveDiaryEntry(btn) {
    const textEl = document.getElementById('diary-text');
    const text = textEl ? textEl.value.trim() : '';

    if (!selectedMood && !text) {
        alert('Selecione um humor ou escreva algo em seu diário.');
        return;
    }

    await UI.withBusy(btn, async () => {
        try {
            const response = await apiFetch('/diary', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mood: selectedMood || 'Não informado',
                    text: text || 'Sem notas adicionais'
                })
            });
            if (!response.ok) throw new Error('Erro ao salvar no servidor.');

            setText('diary-status', '✓ Reflexão salva com segurança!');
            setTimeout(() => setText('diary-status', ''), 4000);

            if (textEl) textEl.value = '';
            selectMood('');
            loadDiary();
        } catch (error) {
            console.error(error);
            if (error.message !== 'sessao expirada') {
                alert('Erro ao salvar o diário. Tente novamente.');
            }
        }
    }, 'Salvando…');
}

async function loadDiary() {
    const box = document.getElementById('diary-history');
    if (!box) return;
    try {
        const response = await apiFetch('/diary');
        if (!response.ok) return;
        const entries = await response.json();
        if (!entries.length) {
            box.innerHTML = '<p>Você ainda não escreveu nada por aqui.</p>';
            return;
        }
        box.innerHTML = entries.map(e => {
            const when = e.created_at ? new Date(e.created_at).toLocaleString('pt-BR') : '';
            return `<div class="diary-entry">
                <small>${esc(when)} · ${esc(e.mood)}</small>
                <p>${esc(e.text)}</p>
            </div>`;
        }).join('');
    } catch (e) {
        if (e.message !== 'sessao expirada') console.error(e);
    }
}

// ---------- painel do professor / admin ----------
async function loadTeacherData() {
    const tbody = document.getElementById('teacher-students-table');
    if (!tbody) return;

    try {
        const response = await apiFetch('/students');
        if (!response.ok) {
            tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:2rem; color:#666;">Acesso restrito à equipe.</td></tr>`;
            return;
        }
        renderTeacherTable(await response.json());
    } catch (e) {
        if (e.message !== 'sessao expirada') console.error(e);
    }
}

const RUBRIC_LABELS = ['0 - Não observado', '1 - Raramente', '2 - Algumas vezes', '3 - Frequente', '4 - Consistente'];

function rubricSelect(field, id, value) {
    const options = RUBRIC_LABELS.map((label, i) =>
        `<option value="${i}" ${Number(value) === i ? 'selected' : ''}>${label}</option>`
    ).join('');
    return `<select class="select-control" id="${field}-${id}">${options}</select>`;
}

function renderTeacherTable(students) {
    const tbody = document.getElementById('teacher-students-table');
    if (!tbody) return;

    if (!students || students.length === 0) {
        tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; color: var(--gray-600); padding:2rem;">Nenhum estudante cadastrado ainda.</td></tr>`;
        return;
    }

    const isAdmin = session && session.role === 'admin';

    tbody.innerHTML = students.map(s => {
        const id = Number(s.id);
        return `<tr>
            <td>
                <strong>${esc(s.name)}</strong>
                <small style="display:block; color: var(--gray-600);">${esc(s.email)}</small>
                ${s.must_change_password ? '<span class="tag warn">PIN provisório</span>' : ''}
            </td>
            <td>${rubricSelect('comm', id, s.comm)}</td>
            <td>${rubricSelect('conflict', id, s.conflict)}</td>
            <td>${rubricSelect('coop', id, s.coop)}</td>
            <td>
                <div style="display:flex; gap:0.35rem; flex-wrap:wrap;">
                    <button onclick="saveStudentRubric(${id}, this)" class="btn-table">Salvar</button>
                    <button onclick="resetStudentPin(${id}, this)" class="btn-table neutral">Novo PIN</button>
                    ${isAdmin ? `<button onclick="deleteStudent(${id}, this)" class="btn-table danger">Excluir</button>` : ''}
                </div>
            </td>
        </tr>`;
    }).join('');
}

async function createStudent(btn) {
    const name = fieldValue('new-student-name');
    const email = fieldValue('new-student-email');
    if (!name || !email) {
        alert('Informe o nome e o e-mail/matrícula do aluno.');
        return;
    }
    await UI.withBusy(btn, async () => {
        try {
            const response = await apiFetch('/students', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, email })
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                alert(errorMessage(data, 'Não foi possível cadastrar o aluno.'));
                return;
            }
            setText('new-student-result',
                `Aluno cadastrado! Login: ${data.email} · PIN (senha): ${data.pin} — anote agora, ele não será mostrado de novo.`);
            document.getElementById('new-student-name').value = '';
            document.getElementById('new-student-email').value = '';
            loadTeacherData();
        } catch (e) {
            if (e.message !== 'sessao expirada') console.error(e);
        }
    }, 'Cadastrando…');
}

async function resetStudentPin(id, btn) {
    UI.busy(btn, true);           // trava o botão enquanto a decisão é tomada
    let ok = false;
    try {
        ok = await UI.confirm({
            title: 'Gerar um novo PIN',
            message: 'O acesso atual deste aluno deixa de funcionar. Ele vai precisar entrar com o PIN novo.',
            confirmText: 'Gerar novo PIN',
            variant: 'warning'
        });
    } finally {
        if (!ok) UI.busy(btn, false);
    }
    if (!ok) return;

    await UI.withBusy(btn, async () => {
        try {
            const response = await apiFetch(`/students/${id}/reset-pin`, { method: 'POST' });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                alert(errorMessage(data, 'Não foi possível gerar o PIN.'));
                return;
            }
            alert(`Novo PIN do aluno: ${data.pin}\n\nAnote agora, ele não será mostrado de novo.`);
        } catch (e) {
            if (e.message !== 'sessao expirada') console.error(e);
        }
    }, 'Gerando…');
}

async function saveStudentRubric(id, btn) {
    const comm = parseInt(document.getElementById(`comm-${id}`).value, 10);
    const conflict = parseInt(document.getElementById(`conflict-${id}`).value, 10);
    const coop = parseInt(document.getElementById(`coop-${id}`).value, 10);

    await UI.withBusy(btn, async () => {
        try {
            const response = await apiFetch(`/students/${id}/rubric`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ comm, conflict, coop })
            });
            if (response.ok) {
                UI.toast('Rubrica atualizada com sucesso!', 'success');
                loadTeacherData();
                if (session && session.role === 'admin') loadAdminMetrics();
            } else {
                alert('Erro ao atualizar rubrica.');
            }
        } catch (e) {
            if (e.message !== 'sessao expirada') console.error(e);
        }
    }, 'Salvando…');
}

async function deleteStudent(id, btn) {
    // pega o nome do aluno na tabela para o aviso ficar claro
    const row = btn ? btn.closest('tr') : null;
    const cell = row ? row.querySelector('td strong') : null;
    const name = cell ? cell.textContent.trim() : '';

    UI.busy(btn, true);           // trava o botão enquanto a decisão é tomada
    let ok = false;
    try {
        ok = await UI.confirm({
            title: 'Excluir estudante',
            message: name
                ? `Remover ${name}? O diário e as respostas dele também serão apagados. Essa ação não pode ser desfeita.`
                : 'Remover este estudante? O diário e as respostas dele também serão apagados. Essa ação não pode ser desfeita.',
            confirmText: 'Excluir',
            variant: 'danger'
        });
    } finally {
        if (!ok) UI.busy(btn, false);
    }
    if (!ok) return;

    await UI.withBusy(btn, async () => {
        try {
            const response = await apiFetch(`/students/${id}`, { method: 'DELETE' });
            if (response.ok) {
                UI.toast('Estudante removido com sucesso!', 'success');
                loadTeacherData();
                if (session && session.role === 'admin') loadAdminMetrics();
            } else {
                alert('Apenas administradores podem excluir cadastros.');
            }
        } catch (e) {
            if (e.message !== 'sessao expirada') console.error(e);
        }
    }, 'Excluindo…');
}

// ---------- gestão da equipe (admin) ----------
async function createStaff(btn) {
    const name = fieldValue('staff-name');
    const email = fieldValue('staff-email');
    const password = document.getElementById('staff-password').value;
    const role = document.getElementById('staff-role').value;

    if (!name || !email || !password) {
        alert('Preencha nome, e-mail e senha.');
        return;
    }
    const staffProblem = passwordProblem(password);
    if (staffProblem) {
        alert(staffProblem);
        return;
    }
    await UI.withBusy(btn, async () => {
        try {
            const response = await apiFetch('/staff', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, email, password, role })
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                alert(errorMessage(data, 'Não foi possível criar a conta. Confira os dados (e-mail válido e senha com 10+ caracteres).'));
                return;
            }
            const labels = { teacher: 'Professor(a)', psychologist: 'Psicólogo(a)', admin: 'Administrador(a)' };
            setText('staff-result', `Conta criada: ${data.name} (${labels[data.role] || data.role}).`);
            ['staff-name', 'staff-email', 'staff-password'].forEach(id => { document.getElementById(id).value = ''; });
        } catch (e) {
            if (e.message !== 'sessao expirada') console.error(e);
        }
    }, 'Criando conta…');
}

// ---------- painel da psicologia / coordenação ----------
async function loadAdminMetrics() {
    try {
        const response = await apiFetch('/metrics');
        if (!response.ok) return;
        const data = await response.json();

        setText('admin-evaluated-count', data.total_students);
        setText('admin-total-score', `${data.score} / 1000`);
        setText('admin-meta-percent', `${data.percentage}% da Meta Atingida`);

        let rangeText = 'Evolução Parcial';
        let rangeDesc = 'Intensificar intervenções pedagógicas';
        if (data.percentage >= 90) {
            rangeText = 'Meta Atingida';
            rangeDesc = 'Avaliar sustentabilidade e segurança';
        } else if (data.percentage >= 75) {
            rangeText = 'Evolução Relevante';
            rangeDesc = 'Consolidar habilidades socioemocionais';
        }
        setText('admin-pedagogical-range', rangeText);
        setText('admin-range-desc', rangeDesc);

        [['1', data.dim_comm], ['2', data.dim_conflict], ['3', data.dim_coop]].forEach(([n, value]) => {
            setText(`dim-score-${n}`, `${value} pts`);
            const bar = document.getElementById(`dim-bar-${n}`);
            if (bar) bar.style.width = `${(value / 200) * 100}%`;
        });
    } catch (e) {
        if (e.message !== 'sessao expirada') console.error(e);
    }
}

// ---------- histórico de acessos (admin) ----------
async function loadAccessLog() {
    const tbody = document.getElementById('logs-table');
    if (!tbody) return;
    try {
        const response = await apiFetch('/logs?limit=200');
        if (!response.ok) {
            tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; padding:2rem; color:#666;">Acesso restrito à administração.</td></tr>`;
            return;
        }
        const logs = await response.json();
        if (!logs.length) {
            tbody.innerHTML = `<tr><td colspan="4" style="text-align:center; color: var(--gray-600); padding:2rem;">Nenhum acesso registrado ainda.</td></tr>`;
            return;
        }
        const rotulos = {
            'login': 'Entrou',
            'logout': 'Saiu',
            'senha alterada': 'Trocou a senha',
            'credenciais invalidas': 'Senha errada',
            'senha atual incorreta': 'Senha atual errada'
        };
        tbody.innerHTML = logs.map(l => {
            const quando = l.created_at ? new Date(l.created_at).toLocaleString('pt-BR') : '';
            const ok = l.success;
            const motivo = rotulos[l.reason] || l.reason || '';
            return `<tr>
                <td><small>${esc(quando)}</small></td>
                <td>${esc(l.email || '—')}</td>
                <td><small>${esc(l.ip || '—')}</small></td>
                <td><span class="tag ${ok ? 'ok' : 'bad'}">${ok ? '✓ ' : '✕ '}${esc(motivo)}</span></td>
            </tr>`;
        }).join('');
    } catch (e) {
        if (e.message !== 'sessao expirada') console.error(e);
    }
}

// ---------- missões ----------
let missionsState = null;
let currentMission = null;

const DIM_LABELS = {
    comunicacao: 'Comunicação',
    conflitos: 'Gestão de conflitos',
    cooperacao: 'Cooperação'
};

const LEVEL_STYLE = {
    good: { bg: 'var(--lilac-50)', border: 'var(--lilac-100)', color: 'var(--lilac-800)', icon: 'check', label: 'Ótima escolha' },
    ok:   { bg: '#fffbeb', border: '#fde68a', color: '#92400e', icon: 'half', label: 'Dá para melhorar' },
    poor: { bg: '#fef2f2', border: '#fecaca', color: '#991b1b', icon: 'warning', label: 'Vale repensar' }
};

async function loadMissions() {
    try {
        const response = await apiFetch('/missions');
        if (!response.ok) return;
        missionsState = await response.json();
        renderMissionList();
    } catch (e) {
        console.error(e);
    }
}

function renderMissionList() {
    if (!missionsState) return;
    const s = missionsState;
    setText('missions-progress',
        `${s.completed} de ${s.total_missions} missões feitas · ${s.total_points} de ${s.max_points} pontos`);
    const box = document.getElementById('missions-list');
    if (!box) return;
    box.innerHTML = s.missions.map(m => `
        <button type="button" class="mission-card ${m.done ? 'done' : ''}" onclick="openMission(${Number(m.id)})">
            <span class="tag">${esc(DIM_LABELS[m.dimension] || m.dimension)}</span>
            <strong>${esc(m.title)}</strong>
            <small>${m.done ? `✓ Feita · melhor: ${Number(m.best_points)} pts` : 'Ainda não feita'}</small>
        </button>`).join('');
}

function openMission(id) {
    if (!missionsState) return;
    const m = missionsState.missions.find(x => x.id === id);
    if (!m) return;
    currentMission = m;

    show('missions-list-view', false);
    show('mission-detail-view', true);
    setText('mission-dim', DIM_LABELS[m.dimension] || m.dimension);
    setText('mission-title', m.title);
    setText('mission-scenario', m.scenario);
    show('mission-feedback', false);

    document.getElementById('mission-options').innerHTML = m.options.map(o => `
        <button type="button" class="option-btn" onclick="answerMission('${esc(o.key)}')">
            <strong>${esc(o.key)}.</strong> ${esc(o.text)}
        </button>`).join('');
}

function closeMission() {
    currentMission = null;
    show('mission-detail-view', false);
    show('missions-list-view', true);
    renderMissionList();
}

function setMissionOptionsDisabled(disabled) {
    document.querySelectorAll('#mission-options .option-btn').forEach(b => { b.disabled = disabled; });
}

async function answerMission(key) {
    if (!currentMission) return;
    setMissionOptionsDisabled(true);
    try {
        const response = await apiFetch(`/missions/${encodeURIComponent(currentMission.id)}/answer`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ option: key })
        });
        if (!response.ok) {
            setMissionOptionsDisabled(false);
            alert('Não foi possível registrar sua resposta. Tente novamente.');
            return;
        }
        const r = await response.json();

        // atualiza o progresso local
        const m = missionsState.missions.find(x => x.id === currentMission.id);
        if (m) { m.done = true; m.best_points = r.best_points; }
        missionsState.total_points = r.total_points;
        missionsState.completed = r.completed;

        const st = LEVEL_STYLE[r.level] || LEVEL_STYLE.ok;
        const box = document.getElementById('mission-feedback');
        const title = document.getElementById('feedback-title');
        const text = document.getElementById('feedback-text');
        box.style.display = 'block';
        box.style.backgroundColor = st.bg;
        box.style.borderColor = st.border;
        title.style.color = st.color;
        title.innerHTML = `${icon(st.icon)} ${esc(st.label)}: ${esc(r.title)}`;
        text.style.color = st.color;
        text.textContent = r.feedback;
        setText('feedback-points', `+${r.points} pontos nesta tentativa · melhor resultado da missão: ${r.best_points} pts`);
        box.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    } catch (e) {
        console.error(e);
        setMissionOptionsDisabled(false);
    }
}

function retryMission() {
    show('mission-feedback', false);
    setMissionOptionsDisabled(false);
}

function nextMission() {
    if (!missionsState || !currentMission) return closeMission();
    const list = missionsState.missions;
    const idx = list.findIndex(x => x.id === currentMission.id);
    // prefere a próxima missão ainda não feita; se não houver, volta para a lista
    const ordered = list.slice(idx + 1).concat(list.slice(0, idx));
    const next = ordered.find(x => !x.done);
    if (next) openMission(next.id);
    else closeMission();
}


// ---------- Meu DNA da Personalidade ----------
let dnaState = null;     // { questions, scale, latest }
let dnaAnswers = [];
let dnaIndex = 0;

const DNA_LEVEL = { low: 'Baixo', mid: 'Intermediário', high: 'Alto' };

function showDnaView(name) {
    show('dna-intro-view', name === 'intro');
    show('dna-quiz-view', name === 'quiz');
    show('dna-result-view', name === 'result');
}

async function loadDna() {
    try {
        const response = await apiFetch('/dna');
        if (!response.ok) return;
        dnaState = await response.json();
        if (dnaState.latest) renderDnaResult(dnaState.latest);
        else showDnaView('intro');
    } catch (e) {
        console.error(e);
    }
}

let dnaBusy = false; // evita que dois toques rápidos contem como duas respostas

function startDna() {
    if (!dnaState) return;
    dnaBusy = false;
    dnaAnswers = new Array(dnaState.questions.length).fill(0);
    dnaIndex = 0;
    showDnaView('quiz');
    renderDnaQuestion();
}

async function restartDna() {
    const ok = await UI.confirm({
        title: 'Refazer o teste',
        message: 'O resultado atual continua salvo até você terminar o novo.',
        confirmText: 'Refazer'
    });
    if (ok) startDna();
}

function renderDnaQuestion() {
    const total = dnaState.questions.length;
    const q = dnaState.questions[dnaIndex];
    setText('dna-progress-label', `Afirmação ${dnaIndex + 1} de ${total}`);
    const bar = document.getElementById('dna-progress-bar');
    if (bar) bar.style.width = `${(dnaIndex / total) * 100}%`;
    setText('dna-question', q.text);

    document.getElementById('dna-scale').innerHTML = dnaState.scale.map(s => `
        <button type="button" class="dna-option ${dnaAnswers[dnaIndex] === s.value ? 'selected' : ''}"
                onclick="chooseDna(${Number(s.value)})">
            <span class="dna-num">${Number(s.value)}</span> ${esc(s.label)}
        </button>`).join('');

    const back = document.getElementById('dna-back');
    if (back) back.disabled = dnaIndex === 0;
}

function chooseDna(value) {
    if (dnaBusy) return;
    dnaBusy = true;
    dnaAnswers[dnaIndex] = value;
    renderDnaQuestion();
    const last = dnaIndex === dnaState.questions.length - 1;
    setTimeout(() => {
        if (last) { submitDna(); return; }  // a trava só solta quando o envio termina
        dnaIndex += 1;
        renderDnaQuestion();
        dnaBusy = false;
    }, 180);
}

function dnaBack() {
    if (dnaBusy) return;
    if (dnaIndex > 0) { dnaIndex -= 1; renderDnaQuestion(); }
}

async function submitDna() {
    try {
        const response = await apiFetch('/dna', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ answers: dnaAnswers })
        });
        if (!response.ok) {
            alert('Não foi possível salvar o seu resultado. Tente novamente.');
            return;
        }
        dnaState.latest = await response.json();
        renderDnaResult(dnaState.latest);
    } catch (e) {
        console.error(e);
    } finally {
        dnaBusy = false;
    }
}

function renderDnaResult(r) {
    showDnaView('result');
    const when = r.created_at ? new Date(r.created_at).toLocaleDateString('pt-BR') : '';
    setText('dna-date', when ? `Teste feito em ${when}` : '');

    document.getElementById('dna-result-list').innerHTML = r.dimensions.map(d => {
        const pct = Math.round((d.score / d.max) * 100);
        let body;
        if (d.level === 'high') body = `<p>${esc(d.high)}</p>`;
        else if (d.level === 'low') body = `<p>${esc(d.low)}</p>`;
        else body = `<p>Você ficou na faixa intermediária: pode se identificar com características dos dois lados.</p>
                     <p><em>De um lado:</em> ${esc(d.high)}</p>
                     <p><em>Do outro:</em> ${esc(d.low)}</p>`;
        const care = (d.key === 'sensibilidade' && d.level === 'high')
            ? `<p class="dna-care">Se as preocupações estiverem pesando no seu dia a dia, converse com a psicologia da escola. Pedir ajuda é uma ótima atitude.</p>` : '';
        return `<div class="dna-card">
            <div class="dna-card-head">
                <div><h4>${esc(d.name)}</h4><small>${esc(d.subtitle)}</small></div>
                <span class="dna-level ${esc(d.level)}">${esc(DNA_LEVEL[d.level] || '')}</span>
            </div>
            <div class="dim-head"><span>Sua pontuação</span><span>${Number(d.score)} de ${Number(d.max)}</span></div>
            <div class="bar"><span style="width:${pct}%"></span></div>
            ${body}
            <p><strong>Potencialidades:</strong> ${esc(d.strengths)}</p>
            <p><strong>Aspectos a desenvolver:</strong> ${esc(d.develop)}</p>
            ${care}
            <details><summary>O que significa essa dimensão?</summary><p>${esc(d.concept)}</p></details>
        </div>`;
    }).join('');
}

// ---------- gerenciar missões (psicologia / admin) ----------
let manageMissions = [];
let editingMissionId = null;
let formOptions = [];

const LEVEL_OPTIONS = [
    ['good', 'Melhor escolha (10 pts)'],
    ['ok', 'Intermediária (5 pts)'],
    ['poor', 'A repensar (0 pts)']
];

async function loadManageMissions() {
    try {
        const response = await apiFetch('/missions/manage');
        if (!response.ok) return;
        manageMissions = await response.json();
        renderManageMissions();
    } catch (e) {
        console.error(e);
    }
}

function renderManageMissions() {
    const box = document.getElementById('manage-missions-list');
    if (!box) return;
    if (!manageMissions.length) {
        box.innerHTML = '<p>Nenhuma missão criada ainda. Clique em "+ Nova missão".</p>';
        return;
    }
    box.innerHTML = manageMissions.map(m => {
        const id = Number(m.id);
        return `<div class="manage-row ${m.active ? '' : 'archived'}">
            <div class="manage-info">
                <strong>${esc(m.title)}</strong>
                <div>
                    <span class="tag">${esc(DIM_LABELS[m.dimension] || m.dimension)}</span>
                    <span class="manage-status">${m.active ? 'Ativa' : 'Arquivada'} · ${Number(m.responses)} resposta(s)</span>
                </div>
            </div>
            <div class="manage-actions">
                <button type="button" class="btn-table" onclick="editMission(${id})">Editar</button>
                <button type="button" class="btn-table neutral" onclick="toggleMissionActive(${id}, this)">${m.active ? 'Arquivar' : 'Ativar'}</button>
                <button type="button" class="btn-table danger" onclick="deleteMission(${id}, this)">Excluir</button>
            </div>
        </div>`;
    }).join('');
}

function blankOption() { return { text: '', level: 'ok', title: '', feedback: '' }; }

function newMission() {
    editingMissionId = null;
    fillMissionForm({ title: '', dimension: 'comunicacao', scenario: '', active: true,
        options: [blankOption(), blankOption(), blankOption()] });
}

function editMission(id) {
    const m = manageMissions.find(x => x.id === id);
    if (!m) return;
    editingMissionId = id;
    fillMissionForm({
        title: m.title, dimension: m.dimension, scenario: m.scenario, active: m.active,
        options: m.options.map(o => ({ text: o.text, level: o.level, title: o.title, feedback: o.feedback }))
    });
}

function fillMissionForm(m) {
    show('mission-manage-list-view', false);
    show('mission-form-view', true);
    setText('mission-form-title', editingMissionId ? 'Editar missão' : 'Nova missão');
    document.getElementById('mf-title').value = m.title;
    document.getElementById('mf-dimension').value = m.dimension;
    document.getElementById('mf-scenario').value = m.scenario;
    document.getElementById('mf-active').checked = !!m.active;
    formOptions = m.options;
    renderMissionFormOptions();
}

function renderMissionFormOptions() {
    const box = document.getElementById('mission-form-options');
    const count = formOptions.length;
    box.innerHTML = formOptions.map((o, i) => `
        <div class="opt-block">
            <div class="opt-head">
                <strong>Opção ${String.fromCharCode(65 + i)}</strong>
                <select class="select-control opt-level">
                    ${LEVEL_OPTIONS.map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}
                </select>
                ${count > 2 ? `<button type="button" class="link-btn" onclick="removeMissionOption(${i})">remover</button>` : ''}
            </div>
            <textarea class="mf-input opt-text" rows="2" maxlength="600" placeholder="O que o aluno escolhe fazer"></textarea>
            <input type="text" class="mf-input opt-title" maxlength="160" placeholder="Título do feedback (ex.: Verificação e diálogo)">
            <textarea class="mf-input opt-feedback" rows="3" maxlength="1200" placeholder="Explicação que o aluno lê depois de escolher"></textarea>
        </div>`).join('');

    // valores entram pelas propriedades (não pelo HTML), então nenhum texto é interpretado como código
    box.querySelectorAll('.opt-block').forEach((el, i) => {
        const o = formOptions[i];
        el.querySelector('.opt-level').value = o.level;
        el.querySelector('.opt-text').value = o.text;
        el.querySelector('.opt-title').value = o.title;
        el.querySelector('.opt-feedback').value = o.feedback;
    });
    const add = document.getElementById('mf-add-option');
    if (add) add.style.display = count >= 4 ? 'none' : '';
}

function readFormOptions() {
    return Array.from(document.querySelectorAll('#mission-form-options .opt-block')).map(el => ({
        text: el.querySelector('.opt-text').value.trim(),
        level: el.querySelector('.opt-level').value,
        title: el.querySelector('.opt-title').value.trim(),
        feedback: el.querySelector('.opt-feedback').value.trim()
    }));
}

function addMissionOption() {
    formOptions = readFormOptions();
    if (formOptions.length < 4) formOptions.push(blankOption());
    renderMissionFormOptions();
}

function removeMissionOption(i) {
    formOptions = readFormOptions();
    if (formOptions.length > 2) formOptions.splice(i, 1);
    renderMissionFormOptions();
}

function cancelMissionForm() {
    editingMissionId = null;
    show('mission-form-view', false);
    show('mission-manage-list-view', true);
}

async function saveMission(btn) {
    const body = {
        title: document.getElementById('mf-title').value.trim(),
        dimension: document.getElementById('mf-dimension').value,
        scenario: document.getElementById('mf-scenario').value.trim(),
        active: document.getElementById('mf-active').checked,
        options: readFormOptions()
    };
    if (body.title.length < 3) { alert('Dê um título para a missão.'); return; }
    if (body.scenario.length < 10) { alert('Descreva a situação (pelo menos 10 caracteres).'); return; }
    if (body.options.some(o => !o.text || !o.title || !o.feedback)) {
        alert('Preencha o texto, o título do feedback e a explicação de todas as opções.');
        return;
    }
    if (!body.options.some(o => o.level === 'good')) {
        alert('Marque pelo menos uma opção como "Melhor escolha".');
        return;
    }
    await UI.withBusy(btn, async () => {
        try {
            const response = await apiFetch(editingMissionId ? `/missions/manage/${editingMissionId}` : '/missions/manage', {
                method: editingMissionId ? 'PUT' : 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            if (!response.ok) {
                const data = await response.json().catch(() => ({}));
                alert(errorMessage(data, 'Não foi possível salvar. Confira se todos os campos estão preenchidos.'));
                return;
            }
            UI.toast('Missão salva com sucesso!', 'success');
            cancelMissionForm();
            loadManageMissions();
        } catch (e) {
            console.error(e);
        }
    }, 'Salvando…');
}

async function toggleMissionActive(id, btn) {
    const m = manageMissions.find(x => x.id === id);
    if (!m) return;
    const body = {
        title: m.title, dimension: m.dimension, scenario: m.scenario, active: !m.active,
        options: m.options.map(o => ({ text: o.text, level: o.level, title: o.title, feedback: o.feedback }))
    };
    await UI.withBusy(btn, async () => {
        try {
            const response = await apiFetch(`/missions/manage/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            if (response.ok) {
                UI.toast(body.active ? 'Missão arquivada.' : 'Missão ativada.', 'success');
                loadManageMissions();
            } else {
                alert('Não foi possível alterar a missão.');
            }
        } catch (e) {
            console.error(e);
        }
    }, 'Salvando…');
}

async function deleteMission(id, btn) {
    const m = manageMissions.find(x => x.id === id);
    const title = m ? m.title : 'esta missão';

    UI.busy(btn, true);           // trava o botão enquanto a decisão é tomada
    let ok = false;
    try {
        ok = await UI.confirm({
            title: 'Excluir missão',
            message: `Excluir "${title}"? As respostas dos alunos nela também serão apagadas. Para só escondê-la, use "Arquivar".`,
            confirmText: 'Excluir',
            variant: 'danger'
        });
    } finally {
        if (!ok) UI.busy(btn, false);
    }
    if (!ok) return;

    await UI.withBusy(btn, async () => {
        try {
            const response = await apiFetch(`/missions/manage/${id}`, { method: 'DELETE' });
            if (response.ok) {
                UI.toast('Missão excluída.', 'success');
                loadManageMissions();
            } else {
                alert('Não foi possível excluir a missão.');
            }
        } catch (e) {
            console.error(e);
        }
    }, 'Excluindo…');
}


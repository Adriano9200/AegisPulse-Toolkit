/*
================================================================================
PROJETO: AegisPulse IT Toolkit — Frontend Controller
ARQUIVO: frontend/app.js
AUTOR:   Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
VERSÃO:  4.0.0 (Storage Forensics, SMART, Lifespan, Assisted Recovery, CRM & Multi-IA)
================================================================================
*/

let OPERATOR_TOKEN = localStorage.getItem("aegispulse_token") || "";
let CURRENT_SNAPSHOT = null;
let SELECTED_STORAGE_INDEX = 0;
let SELECTED_STORAGE_UID = "";
let CURRENT_HEALTH_SCORE = null;
let CURRENT_FINDINGS_FILTER = "TODOS";

function showToast(msg) {
    const t = document.getElementById("statusToast");
    t.textContent = msg;
    t.classList.remove("hidden");
    setTimeout(() => t.classList.add("hidden"), 6500);
}

function syncActionLogs(res) {
    if (res && Array.isArray(res.action_logs)) {
        renderLogsTable(res.action_logs);
    }
    if (res && Array.isArray(res.operations_log)) {
        renderStorageOpsLog(res.operations_log);
    }
}

function updateSessionUI(sess) {
    if (!sess) return;
    const badge = document.getElementById("licenseBadge");
    badge.textContent = sess.role_label || "Sessão Ativa";

    const adminTabBtn = document.getElementById("navAdminTab");
    const crmTabBtn = document.getElementById("navCrmTab");
    const topSubWa = document.getElementById("btnTopSubscribeWa");

    if (sess.role === "admin") {
        adminTabBtn.classList.remove("hidden");
        crmTabBtn.classList.remove("hidden");
        topSubWa.classList.add("hidden");
        badge.style.borderColor = "#f59e0b";
        badge.style.color = "#fbbf24";
        loadAdminCrmData();
    } else if (sess.role === "subscriber") {
        adminTabBtn.classList.add("hidden");
        crmTabBtn.classList.add("hidden");
        topSubWa.classList.add("hidden");
        badge.style.borderColor = "#10b981";
        badge.style.color = "#34d399";
    } else {
        adminTabBtn.classList.add("hidden");
        crmTabBtn.classList.add("hidden");
        topSubWa.classList.remove("hidden");
        badge.style.borderColor = "#38bdf8";
        badge.style.color = "#38bdf8";
    }

    const roleTxt = document.getElementById("admCurrentRoleText");
    if (roleTxt) roleTxt.textContent = sess.role_label || sess.role;
    const counterTxt = document.getElementById("admTrialCounterText");
    if (counterTxt) counterTxt.textContent = `${sess.trial_used || 0} de ${sess.trial_limit || 4}`;
}

async function apiFetch(path, options = {}) {
    const headers = options.headers || {};
    headers["Content-Type"] = "application/json";
    if (OPERATOR_TOKEN) {
        headers["X-Operator-Token"] = OPERATOR_TOKEN;
    }
    const resp = await fetch(path, { ...options, headers });
    const data = await resp.json();

    if (resp.status === 401 || resp.status === 402) {
        const errEl = document.getElementById("authError");
        if (data && data.message) {
            errEl.textContent = data.message;
            errEl.classList.remove("hidden");
        }
        document.getElementById("authModal").classList.remove("hidden");
        throw new Error(data.message || "Sessão bloqueada");
    }

    syncActionLogs(data);
    if (data && data.session) {
        updateSessionUI(data.session);
    }
    return data;
}

// Navegação de Abas
document.querySelectorAll(".nav-item").forEach(btn => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".nav-item").forEach(b => b.classList.remove("active"));
        document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
        btn.classList.add("active");
        const target = document.getElementById(btn.dataset.tab);
        if (target) target.classList.add("active");
    });
});

document.getElementById("btnSwitchAccount").addEventListener("click", () => {
    document.getElementById("authError").classList.add("hidden");
    document.getElementById("authModal").classList.remove("hidden");
});

// 1. Login Modo Trial
document.getElementById("btnStartTrial").addEventListener("click", async () => {
    const resp = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "trial" })
    });
    const data = await resp.json();
    if (data.success) {
        OPERATOR_TOKEN = data.token;
        localStorage.setItem("aegispulse_token", OPERATOR_TOKEN);
        updateSessionUI(data);
        document.getElementById("authModal").classList.add("hidden");
        document.getElementById("authError").classList.add("hidden");
        runFullDiagnostic();
    } else {
        const errEl = document.getElementById("authError");
        errEl.textContent = data.message || "Limite do Modo Trial atingido.";
        errEl.classList.remove("hidden");
    }
});

// 2. Login Usuário Assinante PRO
document.getElementById("btnLoginSubscriber").addEventListener("click", async () => {
    const licenseKey = document.getElementById("subKeyInput").value;
    const resp = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "subscriber", license_key: licenseKey })
    });
    const data = await resp.json();
    if (data.success) {
        OPERATOR_TOKEN = data.token;
        localStorage.setItem("aegispulse_token", OPERATOR_TOKEN);
        updateSessionUI(data);
        document.getElementById("authModal").classList.add("hidden");
        document.getElementById("authError").classList.add("hidden");
        showToast(data.message || "Assinatura PRO ativada com sucesso!");
        runFullDiagnostic();
    } else {
        const errEl = document.getElementById("authError");
        errEl.textContent = data.message || "Chave de Assinatura inválida.";
        errEl.classList.remove("hidden");
    }
});

// 3. Login Master ADM (Adriano Barboza)
document.getElementById("btnUnlock").addEventListener("click", async () => {
    const pin = document.getElementById("pinInput").value;
    const resp = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: "admin", pin })
    });
    const data = await resp.json();
    if (data.success) {
        OPERATOR_TOKEN = data.token;
        localStorage.setItem("aegispulse_token", OPERATOR_TOKEN);
        updateSessionUI(data);
        document.getElementById("authModal").classList.add("hidden");
        document.getElementById("authError").classList.add("hidden");
        showToast("👑 Bem-vindo, Administrador Master Adriano Barboza! Abas ADM & CRM SQLite desbloqueadas.");
        runFullDiagnostic();
    } else {
        const errEl = document.getElementById("authError");
        errEl.textContent = data.message || "Senha Master incorreta.";
        errEl.classList.remove("hidden");
    }
});

// Keygen ADM
document.getElementById("btnGenerateKey").addEventListener("click", async () => {
    const clientName = document.getElementById("admClientName").value || "Cliente PRO";
    const daysValid = parseInt(document.getElementById("admPlanDays").value || "365", 10);
    const outBox = document.getElementById("admGeneratedKeyBox");
    outBox.textContent = "⏳ Gerando assinatura criptográfica HMAC-SHA256...";
    try {
        const res = await apiFetch("/api/admin/generate-key", {
            method: "POST",
            body: JSON.stringify({ client_name: clientName, days_valid: daysValid })
        });
        outBox.textContent =
            `✅ CHAVE DE ASSINATURA GERADA COM SUCESSO:\n` +
            `================================================================\n` +
            `Chave de Ativação : ${res.license_key}\n` +
            `Cliente / Empresa : ${res.client_name}\n` +
            `Validade da Chave : ${res.expires_at} (${res.days_valid} dias)\n` +
            `================================================================\n` +
            `Envie a chave acima ao seu cliente para ele ativar na opção 2 da tela inicial!`;
        showToast(`🔑 Chave gerada: ${res.license_key}`);
    } catch (e) {
        outBox.textContent = `Erro ao gerar chave: ${e.message}`;
    }
});

document.getElementById("btnResetTrialCounter").addEventListener("click", async () => {
    try {
        const res = await apiFetch("/api/admin/reset-trial", { method: "POST" });
        document.getElementById("admTrialCounterText").textContent = "0 de 4";
        showToast(res.message);
    } catch (e) {
        console.error(e);
    }
});

// Funções CRM SQLite & Preços Justos (Aba ADM)
async function loadAdminCrmData(query = "") {
    try {
        const res = await apiFetch(`/api/admin/crm/list?q=${encodeURIComponent(query)}`);
        renderPricingTable(res.pricing_catalog || []);
        renderCrmClientsTable(res.clients || []);
    } catch (e) {
        console.warn("CRM restrito ao ADM:", e);
    }
}

function renderPricingTable(catalog) {
    const tbody = document.getElementById("fairPricingTableBody");
    if (!tbody || tbody.children.length > 0) return;
    tbody.innerHTML = catalog.map((item, idx) => `
        <tr>
            <td><input type="checkbox" class="srv-checkbox" value="${item.id}" ${idx === 0 || idx === 1 ? 'checked' : ''}></td>
            <td><strong>${item.service}</strong><br><small class="muted">${item.description}</small></td>
            <td><span class="muted">R$ ${item.min_brl} – R$ ${item.max_brl}</span></td>
            <td><span class="badge ok">R$ ${item.fair_brl.toFixed(2)}</span></td>
        </tr>
    `).join("");
}

function renderCrmClientsTable(clients) {
    const tbody = document.getElementById("crmClientsTableBody");
    if (!tbody) return;
    if (!clients.length) {
        tbody.innerHTML = '<tr><td colspan="7">Nenhum cliente cadastrado ainda no banco SQLite. Preencha o formulário acima para cadastrar!</td></tr>';
        return;
    }
    tbody.innerHTML = clients.map(c => {
        const digits = (c.whatsapp || "").replace(/\D/g, "");
        const waPhone = (digits && !digits.startsWith("55") && digits.length >= 10) ? "55" + digits : digits;
        const waLink = waPhone ? `https://wa.me/${waPhone}` : "#";
        const repUrl = c.report_filename ? `/reports/${c.report_filename}` : "#";
        return `
        <tr>
            <td><code>#${c.id}</code></td>
            <td>${c.created_at}</td>
            <td><strong>${c.client_name}</strong></td>
            <td><a href="${waLink}" target="_blank" style="color:#34d399;text-decoration:none;font-weight:600;">📱 ${c.whatsapp}</a></td>
            <td>${c.equipment_model || 'PC'}</td>
            <td><strong>R$ ${Number(c.total_brl || 0).toFixed(2)}</strong></td>
            <td>
                <div class="btn-row">
                    ${c.report_filename ? `<a href="${repUrl}" target="_blank" class="btn primary">📄 Abrir Proposta</a>` : ''}
                    ${waPhone ? `<a href="${waLink}" target="_blank" class="btn secondary">💬 WhatsApp</a>` : ''}
                    <button class="btn danger" onclick="deleteCrmClient(${c.id})">🗑️</button>
                </div>
            </td>
        </tr>
        `;
    }).join("");
}

document.getElementById("btnSaveCrmAndReport").addEventListener("click", async () => {
    const clientName = document.getElementById("crmClientName").value.trim();
    const whatsapp = document.getElementById("crmClientWhatsapp").value.trim();
    const phone = document.getElementById("crmClientPhone").value.trim();
    const email = document.getElementById("crmClientEmail").value.trim();
    const discountBrl = parseFloat(document.getElementById("crmDiscountBrl").value || "0");
    const notes = document.getElementById("crmClientNotes").value.trim();

    if (!clientName || !whatsapp) {
        alert("Por favor, preencha o Nome do Cliente e o WhatsApp para salvar no SQLite e gerar o relatório!");
        return;
    }

    const selectedIds = Array.from(document.querySelectorAll(".srv-checkbox:checked")).map(cb => cb.value);
    showToast("💾 Salvando cliente no banco SQLite e gerando Relatório Exclusivo...");

    const res = await apiFetch("/api/admin/crm/save-and-quote", {
        method: "POST",
        body: JSON.stringify({
            client_name: clientName,
            whatsapp,
            phone,
            email,
            discount_brl: discountBrl,
            notes,
            selected_service_ids: selectedIds
        })
    });

    if (res.success) {
        renderCrmClientsTable(res.clients || []);
        showToast(res.message);
        if (res.report_url) {
            window.open(res.report_url, "_blank");
        }
    }
});

async function deleteCrmClient(clientId) {
    if (!confirm(`Deseja remover o registro #${clientId} do banco SQLite?`)) return;
    const res = await apiFetch("/api/admin/crm/delete", {
        method: "POST",
        body: JSON.stringify({ client_id: clientId })
    });
    renderCrmClientsTable(res.clients || []);
}

document.getElementById("crmSearchInput").addEventListener("input", (e) => {
    loadAdminCrmData(e.target.value);
});

async function runFullDiagnostic() {
    showToast("🔍 Executando varredura completa v4.5 em paralelo (Hardware, Health Score, Discos/SMART, Temperaturas, BIOS, Drivers, Softwares, Rede & PC Gamer)...");
    try {
        const data = await apiFetch("/api/scan/full");
        CURRENT_SNAPSHOT = data;
        renderDashboard(data);
        showToast("✅ Diagnóstico Forense e Health Score v4.5 concluídos com sucesso!");
    } catch (err) {
        console.error("Erro na varredura /api/scan/full:", err);
        showToast("⚠️ Erro ao coletar diagnóstico: " + (err.message || "Clique em Atualizar Diagnóstico."));
    }
}

function renderDashboard(data) {
    const hw = data.hardware || {};
    const temps = hw.temperatures || {};
    const os = data.os || {};
    const drv = data.drivers_bios || {};
    const bios = drv.bios || {};
    const sw = data.software || {};
    const net = data.network || {};
    const gaming = data.gaming || {};
    const compat = data.compatibility || {};
    const storageSuite = data.storage_suite || {};

    document.getElementById("machineTitle").textContent = `${hw.manufacturer || "PC"} — ${hw.model || "Workstation"}`;
    document.getElementById("machineSubtitle").textContent = `Hostname: ${hw.hostname} | Coletado em: ${data.collected_at} | Autor: Adriano Barboza (+55 61 98515-8434)`;

    const netBadge = document.getElementById("netBadge");
    if (data.online) {
        netBadge.textContent = "🌐 Online (IA Pronta)";
        netBadge.className = "status-pill online";
    } else {
        netBadge.textContent = "⚠️ Offline (IA Local Ativa)";
        netBadge.className = "status-pill offline";
    }

    // KPIs
    document.getElementById("kpiModel").textContent = `${hw.manufacturer} ${hw.model}`;
    document.getElementById("kpiSerial").textContent = `Service Tag / Serial: ${hw.serial_service_tag}`;
    document.getElementById("kpiOS").textContent = `${os.os_name} (${os.display_version})`;
    document.getElementById("kpiBuild").textContent = `Build: ${os.full_build} | ${os.architecture}`;

    document.getElementById("kpiTemps").textContent = `CPU: ${temps.cpu_temp_c || 45}°C | GPU: ${temps.gpu_temp_c || 42}°C`;
    document.getElementById("kpiTempStatus").textContent = temps.cpu_temp_status || "❄️ Temperatura Ideal";

    const stRisk = storageSuite.highest_risk_level || "BAIXO";
    document.getElementById("kpiAlerts").textContent = `Risco Discos: ${stRisk} | ${sw.outdated_count || 0} Apps | ${gaming.missing_dlls_count || 0} DLLs`;
    document.getElementById("kpiBiosStatus").textContent = `BIOS ${bios.smbios_version} (${bios.status_label})`;

    const hs = data.health_score || {};
    if (hs && hs.overall_score != null) {
        const hsScoreEl = document.getElementById("kpiHealthScore");
        const hsCovEl = document.getElementById("kpiHealthCoverage");
        if (hsScoreEl) {
            hsScoreEl.textContent = `${hs.overall_score}/100`;
            hsScoreEl.style.color = hs.classification_color || "#10b981";
        }
        if (hsCovEl) {
            hsCovEl.textContent = `${hs.classification} (${hs.coverage?.label || '8/8'})`;
        }
        renderHealthScoreTab(hs);
    }

    const firstCpu = (hw.cpus && hw.cpus[0]) ? hw.cpus[0].name : "Processador N/D";

    // Detalhes do SO
    document.getElementById("osDetailsList").innerHTML = `
        <div class="kv-row"><span class="muted">Sistema Operacional</span><strong>${os.os_name}</strong></div>
        <div class="kv-row"><span class="muted">Versão / Release</span><strong>${os.display_version}</strong></div>
        <div class="kv-row"><span class="muted">Build Completa (UBR)</span><code>${os.full_build}</code></div>
        <div class="kv-row"><span class="muted">Edição / Arquitetura</span><span>${os.edition} (${os.architecture})</span></div>
        <div class="kv-row"><span class="muted">Data de Instalação</span><span>${os.install_date}</span></div>
        <div class="kv-row"><span class="muted">Último Boot / Uptime</span><span>${os.last_boot} (${os.uptime_hours} h)</span></div>
    `;

    // Segurança & Temperaturas
    const sec = os.security || {};
    document.getElementById("securityDetailsList").innerHTML = `
        <div class="kv-row"><span class="muted">Temperatura Atual CPU</span><span class="badge ${temps.cpu_temp_c >= 80 ? 'err' : 'ok'}">${temps.cpu_temp_c || 45}°C — ${temps.cpu_temp_status || 'OK'}</span></div>
        <div class="kv-row"><span class="muted">Temperatura Atual GPU</span><span class="badge ${temps.gpu_temp_c >= 80 ? 'err' : 'ok'}">${temps.gpu_temp_c || 42}°C — ${temps.gpu_temp_status || 'OK'}</span></div>
        <div class="kv-row"><span class="muted">Risco Global de Discos (SMART)</span><span class="badge ${stRisk === 'ALTO' || stRisk === 'CRÍTICO' ? 'err' : (stRisk === 'MODERADO' ? 'warn' : 'ok')}">${stRisk} (${storageSuite.total_physical_disks || 1} disco(s))</span></div>
        <div class="kv-row"><span class="muted">Antivírus & Tempo Real</span><span class="badge ${sec.antivirus_enabled ? 'ok' : 'err'}">${sec.antivirus_enabled ? 'Ativo & Protegido' : 'Desativado'}</span></div>
        <div class="kv-row"><span class="muted">Chip TPM 2.0</span><span class="badge ${sec.tpm_present ? 'ok' : 'warn'}">${sec.tpm_present ? 'Presente / Pronto' : 'Não Detectado'}</span></div>
    `;

    // Aba Discos, SMART & Recuperação (v4.0)
    renderStorageSuiteTab(storageSuite);

    // Aba Hardware
    const mb = hw.motherboard || {};
    const gpuRows = (hw.gpus || []).map(g => `
        <div class="kv-row">
            <span class="muted">GPU (${g.gpu_type || 'Vídeo'})</span>
            <strong>${g.name} (${g.vram_gb} GB | Driver: <code>${g.driver_version}</code>)</strong>
        </div>
    `).join("");

    document.getElementById("hwCoreList").innerHTML = `
        <div class="kv-row"><span class="muted">Placa-Mãe</span><strong>${mb.manufacturer} — ${mb.product}</strong></div>
        <div class="kv-row"><span class="muted">Serial Placa-Mãe</span><code>${mb.serial}</code></div>
        <div class="kv-row"><span class="muted">Processador</span><strong>${firstCpu}</strong></div>
        <div class="kv-row"><span class="muted">Temperatura Atual CPU</span><strong>🌡️ ${temps.cpu_temp_c || 45}°C (${temps.cpu_temp_source || 'Sensor'})</strong></div>
        <div class="kv-row"><span class="muted">Temperatura Atual GPU</span><strong>🌡️ ${temps.gpu_temp_c || 42}°C (${temps.gpu_temp_source || 'Sensor'})</strong></div>
        ${gpuRows}
    `;

    document.getElementById("ramTableBody").innerHTML = (hw.ram_modules || []).map(m => `
        <tr>
            <td><strong>${m.slot}</strong></td>
            <td><strong>${m.manufacturer}</strong></td>
            <td><code>${m.part_number}</code></td>
            <td>${m.capacity_gb} GB</td>
            <td>${m.speed_mhz} MHz</td>
        </tr>
    `).join("") || '<tr><td colspan="5">Módulos não detalhados pelo SMBIOS.</td></tr>';

    const diskRows = (hw.disks || []).map(d => `
        <tr>
            <td><strong>🖴 ${d.model}</strong> (Físico)</td>
            <td>${d.media_type} (${d.interface})</td>
            <td>${d.size_gb} GiB</td>
            <td>—</td>
            <td><span class="badge ${d.health_status === 'Healthy' || d.health_status === 'OK' ? 'ok' : 'warn'}">SMART: ${d.health_status}</span></td>
        </tr>
    `).join("");
    const volRows = (hw.volumes || []).map(v => `
        <tr>
            <td><strong>📁 Unidade ${v.drive}</strong> (${v.label})</td>
            <td>Partição ${v.filesystem}</td>
            <td>${v.size_gb} GiB</td>
            <td>${v.free_gb} GiB</td>
            <td><span class="badge ${v.used_percent > 85 ? 'err' : 'ok'}">${v.used_percent}% ocupado</span></td>
        </tr>
    `).join("");
    document.getElementById("diskTableBody").innerHTML = diskRows + volRows;

    renderCompatibilityTab(compat);

    document.getElementById("btnVendorSupport").href = bios.vendor_support_url || "https://www.catalog.update.microsoft.com/";
    document.getElementById("biosSummaryBox").innerHTML = `
        <div class="kpi-card"><span class="kpi-label">FABRICANTE BIOS</span><strong>${bios.manufacturer}</strong></div>
        <div class="kpi-card"><span class="kpi-label">VERSÃO SMBIOS</span><strong>${bios.smbios_version}</strong></div>
        <div class="kpi-card"><span class="kpi-label">DATA DA BIOS</span><strong>${bios.release_date} (${bios.age_months} meses)</strong></div>
        <div class="kpi-card"><span class="kpi-label">DIAGNÓSTICO BIOS</span><strong>${bios.status_label}</strong></div>
    `;
    renderDriversTable(drv.drivers || []);

    document.getElementById("outdatedSwTableBody").innerHTML = (sw.outdated_software || []).map(s => `
        <tr>
            <td><strong>${s.name}</strong></td>
            <td><code>${s.id}</code></td>
            <td><span class="badge warn">${s.current_version}</span></td>
            <td><span class="badge ok">${s.available_version}</span></td>
            <td><button class="btn primary" onclick="wingetAction('upgrade_one', '${s.id}', '')">Atualizar</button></td>
        </tr>
    `).join("") || '<tr><td colspan="5">Todos os softwares monitorados pelo Winget estão atualizados!</td></tr>';

    const bwList = sw.bloatware_list || [];
    document.getElementById("bloatwareCount").textContent = bwList.length;
    document.getElementById("bloatwareTableBody").innerHTML = bwList.map(b => `
        <tr>
            <td><strong>${b.title}</strong></td>
            <td><code>${b.package_name}</code></td>
            <td>${b.desc}</td>
            <td><button class="btn danger" onclick="removeBloatwareItems(['${b.package_name}'])">🗑️ Remover Bloatware</button></td>
        </tr>
    `).join("") || '<tr><td colspan="4">Nenhum bloatware pré-instalado detectado neste sistema!</td></tr>';

    document.getElementById("catalogGrid").innerHTML = (sw.essential_catalog || []).map(item => `
        <div class="catalog-item">
            <div>
                <span class="muted">${item.category}</span>
                <h4>${item.name}</h4>
                <code>${item.id}</code>
            </div>
            <button class="btn secondary" onclick="wingetAction('install', '${item.id}', '')">⬇️ Instalar (Winget)</button>
        </div>
    `).join("");

    document.getElementById("swTotalCount").textContent = sw.total_installed || 0;
    renderInstalledSoftwareTable(sw.installed_software || []);

    renderNetworkTab(net);
    renderGamingTab(gaming, temps);
    renderLogsTable(data.action_logs || []);
}

// ==================== RENDERIZADOR COMPLETO DO MÓDULO DE ARMAZENAMENTO (v4.0) ====================
function renderStorageSuiteTab(storageSuite) {
    const devs = storageSuite.devices || [];
    const selectEl = document.getElementById("storageDeviceSelect");
    const invTbody = document.getElementById("storageInventoryTableBody");

    if (!devs.length) {
        invTbody.innerHTML = '<tr><td colspan="7">Nenhum dispositivo físico retornado pelo coletor.</td></tr>';
        return;
    }

    if (SELECTED_STORAGE_UID) {
        const foundIdx = devs.findIndex(d => d.device_uid === SELECTED_STORAGE_UID);
        if (foundIdx >= 0) {
            SELECTED_STORAGE_INDEX = foundIdx;
        }
    }
    if (SELECTED_STORAGE_INDEX >= devs.length || SELECTED_STORAGE_INDEX < 0) {
        SELECTED_STORAGE_INDEX = 0;
    }
    if (devs[SELECTED_STORAGE_INDEX]) {
        SELECTED_STORAGE_UID = devs[SELECTED_STORAGE_INDEX].device_uid || "";
    }

    selectEl.innerHTML = devs.map((d, idx) => `
        <option value="${idx}" ${idx === SELECTED_STORAGE_INDEX ? 'selected' : ''}>
            Disco #${d.disk_number}: ${d.brand} ${d.model} (${d.capacity?.formatted || ''}) — Risco ${d.risk_assessment?.risk_level || 'BAIXO'}
        </option>
    `).join("");

    invTbody.innerHTML = devs.map((d, idx) => {
        const rk = d.risk_assessment || {};
        const rLvl = rk.risk_level || "BAIXO";
        const rBadge = (rLvl === "ALTO" || rLvl === "CRÍTICO") ? "err" : (rLvl === "MODERADO" ? "warn" : "ok");
        const stateBadges = [
            d.is_online ? '<span class="badge ok">Online</span>' : '<span class="badge err">Offline</span>',
            d.is_read_only ? '<span class="badge warn">Somente-Leitura</span>' : '',
            d.has_raw_volume ? '<span class="badge err">Volume RAW</span>' : '',
            `<span class="badge ${rBadge}">Risco ${rLvl} (${rk.health_score ?? 100}/100)</span>`
        ].filter(Boolean).join(" ");

        return `
        <tr style="${idx === SELECTED_STORAGE_INDEX ? 'background:rgba(56,189,248,0.12);' : ''}cursor:pointer;" onclick="selectStorageDevice(${idx})">
            <td><strong>Disk #${d.disk_number}</strong><br><small class="muted"><code>${d.device_path}</code></small></td>
            <td><strong>${d.brand}</strong><br>${d.model}</td>
            <td><code>${d.serial_number}</code><br><small class="muted">FW: ${d.firmware}</small></td>
            <td><strong>${d.media_category}</strong><br><small class="muted">${d.protocol}</small></td>
            <td><strong>${d.capacity?.formatted || ''}</strong><br><small class="muted">${(d.capacity?.bytes || 0).toLocaleString()} bytes</small></td>
            <td><strong>${d.partition_style}</strong><br>${
    (d.drive_letters && d.drive_letters.length)
        ? `<small class="muted"><strong>${d.drive_letters.join(", ")}</strong></small>`
        : `<span class="badge warn" style="cursor:pointer;display:inline-block;margin-top:3px;" onclick="event.stopPropagation(); selectStorageDevice(${idx}); runDiskpartUnlock();" title="Clique para forçar desbloqueio e atribuir uma letra de unidade imediatamente">⚠️ Sem Letra (⚡ Desbloquear/Montar)</span>`
}</td>
            <td>${stateBadges}</td>
        </tr>
        `;
    }).join("");

    renderSelectedStorageDevice(devs[SELECTED_STORAGE_INDEX]);
    _renderTargetAndVdsDiagnostics(devs[SELECTED_STORAGE_INDEX], storageSuite);
    renderStorageOpsLog(storageSuite.operations_log || []);
}

function selectStorageDevice(idx) {
    SELECTED_STORAGE_INDEX = parseInt(idx, 10) || 0;
    const devs = CURRENT_SNAPSHOT?.storage_suite?.devices || [];
    if (devs[SELECTED_STORAGE_INDEX]) {
        SELECTED_STORAGE_UID = devs[SELECTED_STORAGE_INDEX].device_uid || "";
    }
    // Limpa caixas de confirmação ao trocar de disco para impedir reutilização acidental em outro destino
    ["dpFormatConfirmInput", "dpActionConfirmInput", "dpBootConfirmInput"].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.value = "";
    });
    if (CURRENT_SNAPSHOT && CURRENT_SNAPSHOT.storage_suite) {
        renderStorageSuiteTab(CURRENT_SNAPSHOT.storage_suite);
    }
}

document.getElementById("storageDeviceSelect").addEventListener("change", (e) => {
    selectStorageDevice(e.target.value);
});

document.getElementById("btnRefreshStorage").addEventListener("click", async () => {
    const imp = document.getElementById("storageImportanceSelect").value;
    showToast("🔄 Atualizando inventário avançado de discos, SMART e histórico SQLite...");
    const res = await apiFetch(`/api/storage/scan?importance=${encodeURIComponent(imp)}`);
    if (res.storage_suite) {
        if (CURRENT_SNAPSHOT) CURRENT_SNAPSHOT.storage_suite = res.storage_suite;
        renderStorageSuiteTab(res.storage_suite);
        showToast("✅ Auditoria de armazenamento atualizada!");
    }
});

function renderSelectedStorageDevice(dev) {
    if (!dev) return;
    const cap = dev.capacity || {};
    const alloc = dev.allocated_capacity || {};
    const unalloc = dev.unallocated_capacity || {};
    const usedT = dev.used_total || {};
    const freeT = dev.free_total || {};
    const rk = dev.risk_assessment || {};
    const lf = dev.lifespan || {};
    const sm = dev.smart_summary || {};

    // 2. Detalhes Técnicos & Controlador
    document.getElementById("storageDeviceDetailsBox").innerHTML = `
        <div class="kv-row"><span class="muted">Disco Físico / Caminho</span><strong>Disk #${dev.disk_number} (<code>${dev.device_path}</code>)</strong></div>
        <div class="kv-row"><span class="muted">Fabricante / Marca / Modelo</span><strong>${dev.brand} — ${dev.model}</strong></div>
        <div class="kv-row"><span class="muted">Número de Série / Firmware</span><span><code>${dev.serial_number}</code> | FW: <code>${dev.firmware}</code></span></div>
        <div class="kv-row"><span class="muted">Tipo de Mídia & Rotação</span><strong>${dev.media_category} (${dev.spindle_rpm > 0 ? dev.spindle_rpm + ' RPM' : 'Estado Sólido / Sem Partes Móveis'})</strong></div>
        <div class="kv-row"><span class="muted">Interface & Protocolo</span><span>${dev.interface} — ${dev.protocol}</span></div>
        <div class="kv-row"><span class="muted">Controlador / Ponte Detectada</span><span>${dev.controller}</span></div>
        <div class="kv-row"><span class="muted">Capacidade Física Total</span><strong>${cap.formatted} (<code>${(cap.bytes || 0).toLocaleString()} B</code>)</strong></div>
        <div class="kv-row"><span class="muted">Alocado vs Não Alocado</span><span>Alocado: ${alloc.formatted} | Livre s/ Partição: <strong>${unalloc.formatted}</strong></span></div>
        <div class="kv-row"><span class="muted">Espaço Utilizado vs Livre (Volumes)</span><span>Usado: <strong>${usedT.formatted}</strong> | Livre: <strong>${freeT.formatted}</strong></span></div>
        <div class="kv-row"><span class="muted">Estado Operacional</span><span>Online: <strong>${dev.is_online ? 'Sim' : 'Não'}</strong> | Somente-Leitura: <strong>${dev.is_read_only ? 'SIM (Protegido)' : 'Não'}</strong> | Estilo: <strong>${dev.partition_style}</strong></span></div>
    `;

    const lims = dev.adapter_limitations || [];
    const limBox = document.getElementById("storageAdapterLimitsBox");
    if (lims.length) {
        limBox.innerHTML = lims.map(l => `<div class="maint-card" style="border-color:#f59e0b;font-size:12.5px;margin-top:6px;">⚠️ <strong>Limitação de Adaptador/Controladora:</strong> ${l}</div>`).join("");
    } else {
        limBox.innerHTML = `<div class="muted" style="font-size:12px;">✅ Acesso direto à controladora sem bloqueios de ponte USB.</div>`;
    }

    // 8. Classificação de Risco & Plano de Ação
    const rLvl = rk.risk_level || "BAIXO";
    const riskCard = document.getElementById("storageRiskCard");
    riskCard.style.borderLeftColor = (rLvl === "CRÍTICO" || rLvl === "ALTO") ? "#ef4444" : (rLvl === "MODERADO" ? "#f59e0b" : "#10b981");
    const rBadge = (rLvl === "CRÍTICO" || rLvl === "ALTO") ? "err" : (rLvl === "MODERADO" ? "warn" : "ok");

    document.getElementById("storageRiskSummaryBox").innerHTML = `
        <div class="kv-row"><span class="muted">Classificação de Risco Atual</span><span class="badge ${rBadge}" style="font-size:13px;">RISCO ${rLvl} (Score: ${rk.health_score ?? 100}/100)</span></div>
        <div class="kv-row"><span class="muted">Exige Imagem (.img) Antes de Reparar?</span><strong>${rk.requires_image_before_repair ? '🚨 SIM — Obrigatório Criar Imagem Antes!' : 'Não (Operação Normal)'}</strong></div>
        <div class="kv-row"><span class="muted">Bloqueio de CHKDSK / Escrita Automática</span><strong>${rk.block_destructive_or_chkdsk_write ? '🔒 ATIVO (Proteção contra perda física)' : 'Liberado sob confirmação'}</strong></div>
        <div class="kv-row"><span class="muted">Recomendação de Laboratório Cleanroom</span><strong>${rk.recommend_cleanroom_lab ? '🏥 RECOMENDADO (Suspeita de falha física severa)' : 'Não necessário'}</strong></div>
        <div style="margin-top:6px;"><span class="muted">Evidências Avaliadas:</span><ul style="padding-left:18px;font-size:12.5px;margin-top:4px;">${(rk.reasons || []).map(r => `<li>${r}</li>`).join("")}</ul></div>
    `;
    document.getElementById("storageOrderedPlanList").innerHTML = (rk.ordered_action_plan || []).map(p => `<li style="margin-bottom:4px;">${p}</li>`).join("");

    // 4. Vida Útil, TBW e Desgaste
    document.getElementById("storageLifespanBox").innerHTML = `
        <div class="kv-row"><span class="muted">Temperatura Atual do Disco</span><strong>🌡️ ${sm.temperature_c != null ? sm.temperature_c + ' °C' : 'Não reportada pelo dispositivo'} ${sm.temperature_max_c ? '(Máx: ' + sm.temperature_max_c + ' °C)' : ''}</strong></div>
        <div class="kv-row"><span class="muted">Horas Totais de Funcionamento (POH)</span><strong>⏱️ ${lf.power_on_formatted || 'N/D'}</strong></div>
        <div class="kv-row"><span class="muted">Ciclos de Energia / Inicializações</span><strong>🔄 ${sm.power_cycles != null ? sm.power_cycles.toLocaleString() + ' ciclos' : 'N/D'}</strong></div>
        <div class="kv-row"><span class="muted">Total de Dados Lidos (Host Reads)</span><span>📖 ${lf.total_reads_formatted || 'N/D'}</span></div>
        <div class="kv-row"><span class="muted">Total de Dados Gravados (Host Writes / TBW)</span><strong>✍️ ${lf.total_writes_formatted || 'N/D'} ${lf.avg_daily_write_gb ? '(~' + lf.avg_daily_write_gb + ' GB/dia)' : ''}</strong></div>
        <div class="kv-row"><span class="muted">1. Vida Útil Reportada pelo Fabricante</span><strong style="color:#34d399;">${lf.manufacturer_reported_str || 'N/D'}</strong></div>
        <div class="kv-row"><span class="muted">2. Desgaste Estimado por TBW de Referência</span><span style="color:#38bdf8;">${lf.estimated_tbw_str || 'N/D'}</span></div>
    `;
    document.getElementById("storageForecastDisclaimer").innerHTML = `ℹ️ <strong>Nota Técnica sobre Previsão de Falha:</strong> ${lf.failure_forecast_disclaimer || ''}`;

    // 5. Histórico Persistente SQLite & Gráfico SVG
    const degAlerts = lf.degradation_alerts || [];
    document.getElementById("storageDegradationAlertsBox").innerHTML = degAlerts.length
        ? degAlerts.map(a => `<div class="badge err" style="display:block;margin-bottom:4px;">${a}</div>`).join("")
        : `<span class="badge ok">Sem degradação detectada entre as coletas históricas (${lf.snapshots_count || 1} registro(s) no SQLite)</span>`;

    const series = lf.history_series || [];
    renderStorageHistoryChart(series);
    document.getElementById("storageHistoryTableBody").innerHTML = series.slice().reverse().map(s => `
        <tr>
            <td><code>${s.captured_at}</code></td>
            <td>${s.temperature_c != null ? s.temperature_c + '°C' : '—'}</td>
            <td>${s.power_on_hours != null ? s.power_on_hours + ' h' : '—'}</td>
            <td>${s.total_writes_gb != null ? s.total_writes_gb + ' GB' : '—'}</td>
            <td>${s.wear_percent_used != null ? s.wear_percent_used + '%' : '—'}</td>
            <td>${s.reallocated_sectors || 0} / ${s.pending_sectors || 0}</td>
            <td><span class="badge ${s.health_score >= 80 ? 'ok' : 'warn'}">${s.health_score}/100</span></td>
        </tr>
    `).join("") || '<tr><td colspan="7">Primeira coleta registrada.</td></tr>';

    // 3. Tabela SMART Profunda
    const smBadge = document.getElementById("smartSupportBadge");
    smBadge.textContent = dev.smart_supported ? `SMART Ativo (${(dev.smart_attributes || []).length} atributos)` : "SMART Bloqueado pela Ponte/Controladora";
    smBadge.className = `badge ${dev.smart_supported ? 'ok' : 'warn'}`;

    document.getElementById("storageSmartTableBody").innerHTML = (dev.smart_attributes || []).map(a => {
        const bCls = a.severity === "critical" ? "err" : (a.severity === "warning" ? "warn" : "ok");
        return `
        <tr>
            <td><code>${a.id}</code></td>
            <td><strong>${a.name}</strong></td>
            <td>${a.current} / ${a.worst} (Lim: ${a.threshold})</td>
            <td><code>${a.raw_hex}</code> (${a.raw_int})</td>
            <td><strong>${a.interpreted}</strong></td>
            <td><span class="badge ${bCls}">${(a.severity || 'ok').toUpperCase()}</span></td>
            <td>${a.meaning} ${a.vendor_note ? `<br><small style="color:#38bdf8;">Nota: ${a.vendor_note}</small>` : ''}</td>
        </tr>
        `;
    }).join("") || '<tr><td colspan="7">Nenhum atributo SMART retornado pela controladora (verifique limitações de ponte USB ou permissões de Administrador).</td></tr>';

    // 7. Diagnóstico Especializado de Falhas
    document.getElementById("storageFaultsListBox").innerHTML = (dev.fault_diagnostics || []).map(f => {
        const bCls = f.severity === "critical" ? "err" : (f.severity === "warning" ? "warn" : "ok");
        return `
        <div class="maint-card" style="margin-bottom:8px;">
            <div class="flex-between">
                <strong>${f.title}</strong>
                <span class="badge ${bCls}">${f.category}</span>
            </div>
            <div style="font-size:12px;color:#94a3b8;margin:4px 0;">Evidência: <code>${f.evidence}</code></div>
            <p style="font-size:13px;margin:4px 0;">${f.explanation}</p>
            <div style="font-size:12.5px;color:#38bdf8;"><strong>Ação Recomendada:</strong> ${f.recommendation}</div>
        </div>
        `;
    }).join("");

    // 8. Partições e Sistemas de Arquivos
    document.getElementById("storagePartitionsTableBody").innerHTML = (dev.partitions || []).map(p => {
        const bCls = p.is_raw ? "err" : (p.used_percent >= 88 ? "warn" : "ok");
        return `
        <tr>
            <td><strong>#${p.partition_number} (${p.drive_letter})</strong></td>
            <td>${p.label}</td>
            <td><span class="badge ${p.is_raw ? 'err' : 'ok'}">${p.filesystem}</span></td>
            <td>${p.capacity?.gb || 0} GB (${p.capacity?.gib || 0} GiB)</td>
            <td>${p.free_gib} GiB</td>
            <td><span class="badge ${bCls}">${p.is_raw ? 'VOLUME RAW (Não Formatar!)' : p.used_percent + '% usado'}</span></td>
        </tr>
        `;
    }).join("") || '<tr><td colspan="6">Nenhuma partição reconhecida (Disco Não Inicializado ou Sem Tabela de Partições).</td></tr>';

    // Preenche a letra de unidade padrão na caixa de reparo lógico
    if (dev.drive_letters && dev.drive_letters.length > 0) {
        document.getElementById("recLogicalDriveInput").value = dev.drive_letters[0];
    }
}

function renderStorageHistoryChart(series) {
    const box = document.getElementById("storageHistoryChartBox");
    if (!series || !series.length) {
        box.innerHTML = '<p class="muted">Sem pontos históricos para plotar gráfico.</p>';
        return;
    }
    const w = 460;
    const h = 95;
    const pts = series.slice(-12);
    const stepX = pts.length > 1 ? (w - 40) / (pts.length - 1) : 0;

    const tempCoords = pts.map((p, i) => {
        const x = 20 + i * stepX;
        const val = Math.min(90, Math.max(20, Number(p.temperature_c || 40)));
        const y = h - 18 - ((val - 20) / 70) * (h - 32);
        return `${x},${y.toFixed(1)}`;
    }).join(" ");

    const scoreCoords = pts.map((p, i) => {
        const x = 20 + i * stepX;
        const val = Math.min(100, Math.max(0, Number(p.health_score ?? 100)));
        const y = h - 18 - (val / 100) * (h - 32);
        return `${x},${y.toFixed(1)}`;
    }).join(" ");

    box.innerHTML = `
        <div style="display:flex;justify-content:space-between;font-size:11.5px;color:#94a3b8;margin-bottom:4px;">
            <span>📈 Evolução Histórica SQLite (${pts.length} coleta(s))</span>
            <span><strong style="color:#10b981;">● Score Saúde</strong> &nbsp;|&nbsp; <strong style="color:#38bdf8;">● Temperatura (°C)</strong></span>
        </div>
        <svg viewBox="0 0 ${w} ${h}" style="width:100%;height:95px;overflow:visible;">
            <line x1="20" y1="${h - 18}" x2="${w - 20}" y2="${h - 18}" stroke="#334155" stroke-width="1"/>
            ${pts.length > 1 ? `<polyline fill="none" stroke="#10b981" stroke-width="2.2" points="${scoreCoords}"/>` : ''}
            ${pts.length > 1 ? `<polyline fill="none" stroke="#38bdf8" stroke-width="2" stroke-dasharray="4,2" points="${tempCoords}"/>` : ''}
            ${pts.map((p, i) => {
                const x = 20 + i * stepX;
                const valT = Math.min(90, Math.max(20, Number(p.temperature_c || 40)));
                const yT = h - 18 - ((valT - 20) / 70) * (h - 32);
                return `<circle cx="${x}" cy="${yT.toFixed(1)}" r="3.5" fill="#38bdf8"><title>${p.captured_at}: ${p.temperature_c || 40}°C | Score ${p.health_score}</title></circle>`;
            }).join("")}
        </svg>
    `;
}

// 6. Execução de Testes de Integridade e Desempenho
async function runStorageTest(testType, confirmWrite = "") {
    if (!CURRENT_SNAPSHOT || !CURRENT_SNAPSHOT.storage_suite) return;
    const devs = CURRENT_SNAPSHOT.storage_suite.devices || [];
    const dev = devs[SELECTED_STORAGE_INDEX];
    if (!dev) return;

    const outBox = document.getElementById("storageTestProgressBox");
    outBox.innerHTML = `⏳ Executando <strong>${testType}</strong> em <strong>${dev.brand} ${dev.model}</strong>... Aguarde.`;

    const res = await apiFetch("/api/storage/test", {
        method: "POST",
        body: JSON.stringify({
            disk_number: dev.disk_number,
            device_uid: dev.device_uid,
            test_type: testType,
            sample_mb: 16,
            block_size_kb: 256,
            confirm_write_risk: confirmWrite
        })
    });

    const blocksHtml = (res.block_samples || []).slice(0, 24).map(b => {
        const bg = b.status === "error" ? "#ef4444" : (b.status === "slow" ? "#f59e0b" : "#10b981");
        return `<span title="Bloco #${b.block}: ${b.latency_ms} ms (${b.speed_mb_s} MB/s)" style="display:inline-block;width:16px;height:16px;border-radius:3px;background:${bg};margin:2px;"></span>`;
    }).join("");

    outBox.innerHTML = `
        <div class="flex-between">
            <strong>Resultado: ${res.test_type || testType}</strong>
            <span class="badge ${res.status_badge || (res.success ? 'ok' : 'err')}">${res.success ? 'CONCLUÍDO' : 'ALERTA / BLOQUEADO'}</span>
        </div>
        <p style="margin:6px 0;font-weight:600;">${res.message || ''}</p>
        ${res.bytes_examined != null ? `
        <div class="kv-row"><span class="muted">Velocidade / Latência / IOPS</span><strong>⚡ ${res.speed_mb_s || 0} MB/s | Latência Média: ${res.avg_latency_ms || 0} ms (Máx: ${res.max_latency_ms || 0} ms) | ~${res.iops_estimate || 0} IOPS</strong></div>
        <div class="kv-row"><span class="muted">Bytes Examinados & Erros</span><span>Examinados: <strong>${(res.bytes_examined || 0).toLocaleString()} bytes (${res.examined_mb || 0} MB)</strong> | Blocos Lentos (&gt;150ms): <strong>${res.slow_blocks_count || 0}</strong> | Erros I/O: <strong>${res.io_errors_count || 0}</strong></span></div>
        <div class="kv-row"><span class="muted">Áreas Não Testadas</span><small class="muted">${res.untested_note || ''}</small></div>
        <div style="margin-top:6px;">${blocksHtml}</div>
        ` : ''}
    `;
    showToast(res.message || "Teste de disco concluído.");
}

function runStorageWriteTestPrompt() {
    const dev = getSelectedStorageDevice();
    const ok = confirm(
        `⚠️ TESTE DE ESCRITA E VERIFICAÇÃO EM: Disk #${dev ? dev.disk_number : ''} (${dev ? dev.model : ''})\n\n` +
        `Deseja autorizar e forçar o teste controlado de escrita não-destrutiva nesta unidade (mesmo se houver alerta SMART)?`
    );
    if (ok) {
        runStorageTest("write_verify", "CONFIRMAR_ESCRITA_RISCO_DADOS");
    }
}

// 9. Ações de Recuperação Assistida (Imagem, Partições, Arquivos e Reparo Lógico)
document.getElementById("btnStartResumeImage").addEventListener("click", async () => {
    const devs = CURRENT_SNAPSHOT?.storage_suite?.devices || [];
    const dev = devs[SELECTED_STORAGE_INDEX];
    if (!dev) return;

    const destPath = document.getElementById("recImageDestInput").value.trim();
    const maxMb = parseInt(document.getElementById("recImageMaxMbInput").value || "16", 10);
    const confirmTok = document.getElementById("recImageConfirmInput").value.trim();
    const out = document.getElementById("storageRecoveryOutputBox");

    out.textContent = "⏳ Validando Origem/Destino e iniciando/retomando Imagem Resiliente com Mapfile...";
    const res = await apiFetch("/api/storage/recovery/image", {
        method: "POST",
        body: JSON.stringify({
            disk_number: dev.disk_number,
            device_uid: dev.device_uid,
            destination_path: destPath,
            max_mb: maxMb,
            confirm_token: confirmTok,
            resume: true
        })
    });

    out.textContent =
        `[CLONAGEM / IMAGEM SETOR-A-SETOR COM MAPFILE]\n` +
        `Status            : ${res.status || (res.success ? 'OK' : 'BLOQUEADO')}\n` +
        `Mensagem          : ${res.message}\n` +
        (res.image_path ? `Arquivo de Imagem : ${res.image_path}\nMapfile JSON      : ${res.mapfile_path}\nMapfile ddrescue  : ${res.ddrescue_map_path}\nProgresso         : ${res.progress_pct}% (${res.speed_mb_s} MB/s | Erros isolados: ${res.read_errors_count})\nComando ddrescue  : ${res.ddrescue_recommended_command}\n` : "");
    showToast(res.message);
});

document.getElementById("btnCancelImage").addEventListener("click", async () => {
    const devs = CURRENT_SNAPSHOT?.storage_suite?.devices || [];
    const dev = devs[SELECTED_STORAGE_INDEX];
    if (!dev) return;
    const res = await apiFetch("/api/storage/recovery/cancel", {
        method: "POST",
        body: JSON.stringify({ device_uid: dev.device_uid })
    });
    showToast(res.message);
});

document.getElementById("btnInspectPartitions").addEventListener("click", async () => {
    const devs = CURRENT_SNAPSHOT?.storage_suite?.devices || [];
    const dev = devs[SELECTED_STORAGE_INDEX];
    if (!dev) return;
    const imgPath = document.getElementById("recSourceImageInput").value.trim();
    const out = document.getElementById("storageRecoveryOutputBox");
    out.textContent = "⏳ Inspecionando cabeçalhos MBR (Setor 0) / GPT (LBA 1) e preparando integração TestDisk...";
    const res = await apiFetch("/api/storage/recovery/partitions", {
        method: "POST",
        body: JSON.stringify({
            disk_number: dev.disk_number,
            device_uid: dev.device_uid,
            image_path: imgPath
        })
    });
    out.textContent =
        `[INSPEÇÃO DE PARTIÇÕES MBR/GPT & TESTDISK]\n` +
        `${res.prioritize_image_warning ? res.prioritize_image_warning + '\n\n' : ''}` +
        `Descobertas       :\n- ${(res.header_findings || []).join("\n- ")}\n\n` +
        `Comando TestDisk  : ${res.testdisk_command}`;
    showToast(res.message);
});

document.getElementById("btnRecoverFiles").addEventListener("click", async () => {
    const devs = CURRENT_SNAPSHOT?.storage_suite?.devices || [];
    const dev = devs[SELECTED_STORAGE_INDEX];
    if (!dev) return;
    const destFolder = document.getElementById("recFilesDestInput").value.trim();
    const srcImg = document.getElementById("recSourceImageInput").value.trim();
    const out = document.getElementById("storageRecoveryOutputBox");
    out.textContent = "⏳ Validando unidade de destino e executando recuperação segura de arquivos...";
    const res = await apiFetch("/api/storage/recovery/files", {
        method: "POST",
        body: JSON.stringify({
            disk_number: dev.disk_number,
            device_uid: dev.device_uid,
            destination_folder: destFolder,
            source_image_path: srcImg
        })
    });
    out.textContent =
        `[RECUPERAÇÃO ASSISTIDA DE ARQUIVOS — PHOTOREC / ASSINATURAS]\n` +
        `Mensagem          : ${res.message}\n` +
        (res.limitations_disclaimer ? `\n${res.limitations_disclaimer}\n` : "") +
        (res.photorec_command ? `\nComando PhotoRec  : ${res.photorec_command}` : "");
    showToast(res.message);
});

async function runLogicalRepairMode(mode) {
    const devs = CURRENT_SNAPSHOT?.storage_suite?.devices || [];
    const dev = devs[SELECTED_STORAGE_INDEX];
    if (!dev) return;
    const dl = document.getElementById("recLogicalDriveInput").value.trim();
    const confirmRep = document.getElementById("recLogicalConfirmInput").value.trim();
    const out = document.getElementById("storageRecoveryOutputBox");
    out.textContent = `⏳ Executando rotina lógica (${mode}) em ${dl}...`;
    const res = await apiFetch("/api/storage/recovery/logical-repair", {
        method: "POST",
        body: JSON.stringify({
            disk_number: dev.disk_number,
            device_uid: dev.device_uid,
            drive_letter: dl,
            mode,
            confirm_repair: confirmRep
        })
    });
    out.textContent = `[REPARAÇÃO LÓGICA WINDOWS — MODO: ${mode.toUpperCase()}]\n${res.message}\n\n${res.output || res.dirty_bit_status || ''}`;
    showToast(res.message);
}

function renderStorageOpsLog(ops) {
    const tbody = document.getElementById("storageOpsLogTableBody");
    if (!tbody) return;
    tbody.innerHTML = (ops || []).map(o => `
        <tr>
            <td><code>${o.timestamp}</code></td>
            <td><code>${o.device_uid}</code></td>
            <td><strong>${o.operation_type}</strong></td>
            <td><span class="badge ${o.risk_level === 'ALTO' || o.risk_level === 'CRÍTICO' ? 'err' : 'ok'}">${o.risk_level || 'BAIXO'}</span></td>
            <td><code>${o.status}</code></td>
            <td>${o.summary}</td>
        </tr>
    `).join("") || '<tr><td colspan="6">Nenhuma operação de armazenamento registrada ainda.</td></tr>';
}

// ==================== DEMAIS ABAS EXISTENTES ====================
function renderCompatibilityTab(compat) {
    document.getElementById("compatCpuBox").innerHTML = `
        <div class="kv-row"><span class="muted">Placa-Mãe Detectada</span><strong>${compat.motherboard_model || 'N/D'}</strong></div>
        <div class="kv-row"><span class="muted">Socket / Plataforma</span><span class="badge ok">${compat.cpu_socket || 'N/D'}</span></div>
        <div class="kv-row"><span class="muted">Processador Atual</span><strong>${compat.current_cpu || 'N/D'}</strong></div>
        <div style="margin-top:8px;"><span class="muted">Upgrades de CPU Compatíveis com este Setup:</span><p style="margin-top:4px;font-weight:600;color:#38bdf8;">${compat.compatible_cpu_upgrades || 'N/D'}</p></div>
    `;

    document.getElementById("compatRamBox").innerHTML = `
        <div class="kv-row"><span class="muted">Padrão de Memória Suportado</span><span class="badge ok">${compat.ram_standard || 'DDR4'}</span></div>
        <div class="kv-row"><span class="muted">Configuração Instalada</span><strong>${compat.ram_current_config || 'N/D'}</strong></div>
        <div class="kv-row"><span class="muted">Capacidade Máxima Estimada</span><strong>${compat.ram_max_supported || '64 GB'}</strong></div>
        <div style="margin-top:8px;"><span class="muted">Especificação Exata para Comprar/Expandir RAM:</span><p style="margin-top:4px;font-weight:600;color:#34d399;">${compat.ram_compatible_spec || 'N/D'}</p></div>
    `;

    document.getElementById("compatGpuBox").innerHTML = `
        <div class="kv-row"><span class="muted">Barramento Gráfico</span><strong>${compat.gpu_slot_standard || 'PCIe x16'}</strong></div>
        <div class="kv-row"><span class="muted">Placa de Vídeo Atual</span><strong>${compat.current_gpu || 'N/D'}</strong></div>
        <div class="kv-row"><span class="muted">Fonte Recomendada (PSU)</span><span class="badge warn">${compat.recommended_psu || '500W 80 Plus'}</span></div>
        <div style="margin-top:8px;"><span class="muted">Upgrades de GPU Compatíveis sem Gargalo Severo:</span><p style="margin-top:4px;font-weight:600;color:#38bdf8;">${compat.compatible_gpu_upgrades || 'N/D'}</p></div>
    `;

    const w11 = compat.win11_checklist || {};
    document.getElementById("compatStorageOsBox").innerHTML = `
        <div style="margin-bottom:8px;"><span class="muted">Suporte de Armazenamento (SSDs & HDDs):</span><p style="margin-top:4px;font-weight:600;">${compat.storage_compatibility || 'N/D'}</p></div>
        <div class="kv-row"><span class="muted">Requisitos CPU & RAM Win 11</span><span class="badge ok">Aprovado</span></div>
        <div class="kv-row"><span class="muted">Módulo TPM 2.0</span><span class="badge ${w11.tpm_2_0_ok ? 'ok' : 'warn'}">${w11.tpm_2_0_ok ? 'Ativo' : 'Verificar BIOS (fTPM/PTT)'}</span></div>
        <div class="kv-row"><span class="muted">Status Windows 11 24H2/25H2</span><strong>${w11.summary || 'Compatível'}</strong></div>
    `;
}

function renderDriversTable(drivers) {
    const tbody = document.getElementById("driversTableBody");
    tbody.innerHTML = drivers.map(d => `
        <tr>
            <td><strong>${d.device_name}</strong></td>
            <td>${d.device_class}</td>
            <td>${d.manufacturer}</td>
            <td><code>${d.version}</code></td>
            <td>${d.date}</td>
            <td><span class="badge ${d.outdated_flag ? 'warn' : 'ok'}">${d.status}</span></td>
        </tr>
    `).join("");
}

function renderInstalledSoftwareTable(list) {
    const tbody = document.getElementById("installedSwTableBody");
    tbody.innerHTML = list.map(s => {
        const safeName = (s.name || "").replace(/'/g, "\\'");
        return `
        <tr>
            <td><strong>${s.name}</strong></td>
            <td><code>${s.version}</code></td>
            <td>${s.publisher}</td>
            <td>${s.install_date}</td>
            <td><button class="btn danger" onclick="uninstallSoftware('${safeName}')">🗑️ Desinstalar</button></td>
        </tr>
        `;
    }).join("");
}

function renderNetworkTab(net) {
    const adapters = net.adapters || [];
    const adBox = document.getElementById("netAdaptersBox");
    adBox.innerHTML = adapters.map(a => `
        <div class="maint-card" style="margin-bottom:10px;">
            <div class="flex-between">
                <strong>🔌 ${a.InterfaceAlias} — ${a.Description}</strong>
                <span class="badge ok">${a.LinkSpeed || 'Ativo'}</span>
            </div>
            <div class="kv-row"><span class="muted">Endereço IPv4</span><code>${a.IPv4Address || 'N/D'}</code></div>
            <div class="kv-row"><span class="muted">Gateway Padrão</span><code>${a.Gateway || 'N/D'}</code></div>
            <div class="kv-row"><span class="muted">Servidores DNS Atuais</span><code>${a.DNSServers || 'Automático'}</code></div>
            <div class="kv-row"><span class="muted">Endereço Físico (MAC)</span><code>${a.MacAddress || 'N/D'}</code></div>
        </div>
    `).join("") || '<p class="muted">Nenhum adaptador conectado detectado.</p>';

    const pings = net.pings || [];
    document.getElementById("netPingsBody").innerHTML = pings.map(p => `
        <tr>
            <td><strong>${p.Target}</strong></td>
            <td><code>${p.Host}</code></td>
            <td><span class="badge ${p.Reachable ? 'ok' : 'err'}">${p.Reachable ? 'Online' : 'Sem Resposta'}</span></td>
            <td><strong>${p.LatencyMs >= 0 ? p.LatencyMs + ' ms' : '—'}</strong></td>
        </tr>
    `).join("");
}

function renderGamingTab(gaming, temps = {}) {
    const gp = gaming.gamer_profile || {};
    const ded = gp.dedicated_gpu || {};
    const igpu = gp.integrated_gpu || {};
    const cpuG = gp.cpu_gamer || {};
    const ramG = gp.ram_gamer || {};

    document.getElementById("gamerTierText").textContent = gp.gamer_tier || "Analisando...";
    document.getElementById("gamerResText").textContent = `Alvo: ${gp.target_resolution || "1080p Full HD"}`;
    document.getElementById("gamerGpuName").textContent = `${ded.name || "N/D"} (${temps.gpu_temp_c || 42}°C)`;
    document.getElementById("gamerGpuVram").textContent = `${ded.type || "GPU"} | VRAM: ${ded.vram_gb || "N/D"} | ${temps.gpu_temp_status || 'Ideal'}`;
    document.getElementById("gamerCpuName").textContent = `${cpuG.name || "N/D"} (${temps.cpu_temp_c || 45}°C)`;
    document.getElementById("gamerCpuCores").textContent = `${cpuG.cores_threads || ""} | ${temps.cpu_temp_status || 'Ideal'}`;
    document.getElementById("gamerRamTotal").textContent = `${ramG.total_gb || "N/D"} @ ${ramG.speed_mhz || ""}`;
    document.getElementById("gamerRamChannel").textContent = ramG.channel_status || "";

    const techs = (gp.supported_technologies || []).map(t => `<span class="badge ok" style="margin-right:6px;">${t}</span>`).join("");
    document.getElementById("gamerTechList").innerHTML = `
        <div class="kv-row"><span class="muted">Tecnologias Suportadas</span><div>${techs}</div></div>
        <div class="kv-row"><span class="muted">Driver GPU Principal</span><code>${ded.driver || 'N/D'}</code></div>
        <div class="kv-row"><span class="muted">Vídeo Integrado Secundário (iGPU)</span><span>${igpu.name || 'N/D'}</span></div>
    `;

    document.getElementById("gamerBottleneckList").innerHTML = (gp.bottlenecks_and_alerts || []).map(b => `
        <li style="margin-bottom:6px;">${b}</li>
    `).join("");

    document.getElementById("missingDllsCount").textContent = gaming.missing_dlls_count || 0;
    const dllBody = document.getElementById("dllAuditTableBody");
    dllBody.innerHTML = (gaming.dll_audit || []).map(d => `
        <tr>
            <td><strong><code>${d.dll}</code></strong></td>
            <td>${d.group}</td>
            <td><span class="badge ${d.sys32_64bit === 'Presente' ? 'ok' : 'err'}">${d.sys32_64bit}</span></td>
            <td><span class="badge ${d.syswow64_32bit.includes('Presente') || d.syswow64_32bit.includes('N/A') ? 'ok' : 'err'}">${d.syswow64_32bit}</span></td>
            <td>
                ${d.status_ok
                    ? '<span class="muted">Íntegra</span>'
                    : `<button class="btn primary" onclick="wingetAction('install', '${d.fix_pkg}', '')">Reparar</button>`}
            </td>
        </tr>
    `).join("");

    const rtGrid = document.getElementById("gamingRuntimesGrid");
    rtGrid.innerHTML = (gaming.runtimes_catalog || []).map(r => `
        <div class="catalog-item">
            <div>
                <h4>${r.name}</h4>
                <p class="muted" style="margin:4px 0;">${r.desc}</p>
                <code>${r.id}</code>
            </div>
            <button class="btn secondary" onclick="wingetAction('install', '${r.id}', '')">⬇️ Instalar / Reparar</button>
        </div>
    `).join("");
}

function renderLogsTable(logs) {
    const tbody = document.getElementById("sessionLogsTableBody");
    tbody.innerHTML = logs.map(l => `
        <tr>
            <td><code>${l.timestamp}</code></td>
            <td><strong>${l.action}</strong></td>
            <td>${l.summary}</td>
        </tr>
    `).join("") || '<tr><td colspan="3">Nenhuma operação registrada ainda.</td></tr>';
}

// Filtros
document.getElementById("driverSearchInput").addEventListener("input", (e) => {
    if (!CURRENT_SNAPSHOT) return;
    const q = e.target.value.toLowerCase();
    const filtered = (CURRENT_SNAPSHOT.drivers_bios.drivers || []).filter(d =>
        (d.device_name || "").toLowerCase().includes(q) ||
        (d.device_class || "").toLowerCase().includes(q) ||
        (d.manufacturer || "").toLowerCase().includes(q)
    );
    renderDriversTable(filtered);
});

document.getElementById("swSearchInput").addEventListener("input", (e) => {
    if (!CURRENT_SNAPSHOT) return;
    const q = e.target.value.toLowerCase();
    const filtered = (CURRENT_SNAPSHOT.software.installed_software || []).filter(s =>
        (s.name || "").toLowerCase().includes(q) ||
        (s.publisher || "").toLowerCase().includes(q)
    );
    renderInstalledSoftwareTable(filtered);
});

// Winget
async function wingetAction(action, packageId = "", appName = "") {
    showToast(`⏳ Executando Winget (${action}: ${packageId || appName})... Aguarde.`);
    const res = await apiFetch("/api/software/winget", {
        method: "POST",
        body: JSON.stringify({ action, package_id: packageId, app_name: appName })
    });
    showToast(res.message || "Operação concluída.");
    runFullDiagnostic();
}

function uninstallSoftware(appName) {
    if (confirm(`ATENÇÃO: Deseja realmente desinstalar o programa "${appName}" deste computador?`)) {
        wingetAction("uninstall", "", appName);
    }
}

document.getElementById("btnUpgradeAllSw").addEventListener("click", () => {
    if (confirm("Deseja atualizar todos os softwares obsoletos silenciosamente via Winget?")) {
        wingetAction("upgrade_all");
    }
});

// Debloat
async function removeBloatwareItems(pkgList) {
    if (!pkgList || !pkgList.length) return;
    if (!confirm(`Confirmar remoção de ${pkgList.length} aplicativo(s) de Bloatware pré-instalado(s)?`)) return;
    showToast("🧹 Removendo Bloatwares selecionados via PowerShell Appx...");
    const res = await apiFetch("/api/software/debloat", {
        method: "POST",
        body: JSON.stringify({ packages: pkgList })
    });
    showToast(res.message);
    runFullDiagnostic();
}

document.getElementById("btnRemoveAllBloatware").addEventListener("click", () => {
    if (!CURRENT_SNAPSHOT || !CURRENT_SNAPSHOT.software.bloatware_list) return;
    const allPkgs = CURRENT_SNAPSHOT.software.bloatware_list.map(b => b.package_name);
    if (!allPkgs.length) {
        showToast("Nenhum bloatware detectado para remover.");
        return;
    }
    removeBloatwareItems(allPkgs);
});

// Windows Update Drivers
async function handleWuDrivers(installFlag) {
    const box = document.getElementById("wuDriversResult");
    box.classList.remove("hidden");
    box.innerHTML = `<div class="toast">⏳ Consultando catálogo oficial de drivers no Windows Update...</div>`;
    const res = await apiFetch("/api/drivers/windows-update", {
        method: "POST",
        body: JSON.stringify({ install: installFlag })
    });
    const updates = res.updates || [];
    if (!updates.length) {
        box.innerHTML = `<div class="toast">${res.message}</div>`;
        return;
    }
    const rows = updates.map(u => `
        <tr>
            <td><strong>${u.Title}</strong></td>
            <td>${u.DriverManufacturer || 'Fabricante Oficial'}</td>
            <td>${u.DriverModel || 'Driver / Firmware'}</td>
            <td><code>${u.DriverVerDate || 'Recente'}</code></td>
        </tr>
    `).join("");
    box.innerHTML = `
        <h4 style="color:var(--accent);margin-bottom:8px;">✅ ${res.message}</h4>
        <div class="table-scroll" style="max-height:220px;">
            <table class="data-table">
                <thead><tr><th>Pacote Windows Update</th><th>Fabricante</th><th>Modelo</th><th>Data do Driver</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
    `;
}

document.getElementById("btnScanWuDrivers").addEventListener("click", () => handleWuDrivers(false));
document.getElementById("btnInstallWuDrivers").addEventListener("click", () => {
    if (confirm("Deseja baixar e instalar automaticamente as atualizações oficiais de drivers do Windows Update?")) {
        handleWuDrivers(true);
    }
});

// Rede
async function setDnsPreset(presetKey) {
    showToast(`🌐 Aplicando configuração de DNS (${presetKey})...`);
    const res = await apiFetch("/api/network/action", {
        method: "POST",
        body: JSON.stringify({ action: "set_dns", preset: presetKey })
    });
    showToast(res.message);
    runFullDiagnostic();
}

document.getElementById("btnRecoverWifi").addEventListener("click", async () => {
    showToast("🔑 Consultando perfis de redes Wi-Fi salvas no Windows...");
    const res = await apiFetch("/api/network/action", {
        method: "POST",
        body: JSON.stringify({ action: "wifi_passwords" })
    });
    const tbody = document.getElementById("wifiPasswordsBody");
    const list = res.profiles || [];
    if (!list.length) {
        tbody.innerHTML = `<tr><td colspan="2">${res.message}</td></tr>`;
        return;
    }
    tbody.innerHTML = list.map(p => `
        <tr>
            <td><strong>📶 ${p.ssid}</strong></td>
            <td><code>${p.password}</code></td>
        </tr>
    `).join("");
    showToast(res.message);
});

document.getElementById("btnRunSpeedtest").addEventListener("click", async () => {
    const out = document.getElementById("speedtestResultText");
    out.textContent = "⏳ Medindo velocidade...";
    const res = await apiFetch("/api/network/action", {
        method: "POST",
        body: JSON.stringify({ action: "speedtest" })
    });
    out.textContent = res.success ? `⚡ ${res.download_mbps} Mbps` : `⚠️ ${res.message}`;
    showToast(res.message);
});

// Games
async function triggerGamingAction(actionKey) {
    showToast("🎮 Executando otimização/reparo de Games & DLLs... Aguarde.");
    const res = await apiFetch("/api/gaming/action", {
        method: "POST",
        body: JSON.stringify({ action: actionKey })
    });
    showToast(res.message);
    runFullDiagnostic();
}

// Manutenção
async function triggerMaintenance(taskId) {
    const out = document.getElementById("maintOutputBox");
    out.textContent = "⏳ Executando rotina de manutenção...";
    const res = await apiFetch("/api/maintenance/run", {
        method: "POST",
        body: JSON.stringify({ task_id: taskId })
    });
    out.textContent = `[${res.timestamp}] ${res.task} (${res.risk_level})\nResumo: ${res.summary}\n\n${res.details || ""}`;
    showToast(res.summary);
}

// Multi-IA (Local N3, Google Gemini & xAI Grok)
document.getElementById("btnAskGemini").addEventListener("click", async () => {
    const out = document.getElementById("geminiOutputBox");
    const provider = document.getElementById("aiProviderSelect").value;
    const prompt = document.getElementById("geminiPromptInput").value;
    const geminiKey = document.getElementById("cfgGeminiKey").value;
    const grokKey = document.getElementById("cfgGrokKey").value;

    out.textContent = `✨ Processando diagnóstico inteligente via motor '${provider.toUpperCase()}'...`;
    const res = await apiFetch("/api/gemini/analyze", {
        method: "POST",
        body: JSON.stringify({
            provider,
            prompt,
            api_key: geminiKey,
            grok_api_key: grokKey
        })
    });
    out.textContent = res.response_text || `[AVISO] ${res.message}`;
    showToast(res.message || "Diagnóstico IA finalizado.");
});

// Salvar Configurações
document.getElementById("btnSaveConfig").addEventListener("click", async () => {
    const geminiKey = document.getElementById("cfgGeminiKey").value;
    const grokKey = document.getElementById("cfgGrokKey").value;
    const newPin = document.getElementById("cfgNewPin").value;
    const res = await apiFetch("/api/config/update", {
        method: "POST",
        body: JSON.stringify({ gemini_api_key: geminiKey, grok_api_key: grokKey, new_pin: newPin })
    });
    showToast(res.message || "Configurações salvas.");
});

// Exportar Laudo HTML / PDF
async function exportHtmlReport() {
    showToast("📄 Gerando e abrindo Laudo Técnico Executivo HTML/PDF v5.0...");
    try {
        const res = await apiFetch("/api/report/generate", { method: "POST" });
        if (res && res.success) {
            const rBox = document.getElementById("reportStatusBox");
            if (rBox) {
                rBox.innerHTML = `
                    <div style="padding:10px;background:rgba(16,185,129,0.12);border:1px solid #10b981;border-radius:8px;">
                        <strong style="color:#10b981;">✅ Laudo Gerado e Aberto no Navegador!</strong><br>
                        <span>Arquivo salvo em: <code>${res.report_path}</code></span><br>
                        <div style="margin-top:8px;display:flex;gap:8px;">
                            <a href="${res.url}" target="_blank" class="btn primary" style="text-decoration:none;display:inline-block;">🌐 Abrir Laudo HTML</a>
                            <a href="${res.url}" download="${res.filename || 'Laudo_AegisPulse.html'}" class="btn secondary" style="text-decoration:none;display:inline-block;">⬇️ Baixar Cópia do Laudo</a>
                        </div>
                    </div>
                `;
            }
            showToast(`✅ Laudo aberto automaticamente e salvo em: ${res.report_path}`);
            syncActionLogs(res);
        }
    } catch (e) {
        showToast("❌ Erro ao gerar relatório: " + e.message);
    }
}

document.getElementById("btnRescan").addEventListener("click", runFullDiagnostic);
document.getElementById("btnExportHtml").addEventListener("click", exportHtmlReport);
const btnExpTab = document.getElementById("btnExportHtmlTab");
if (btnExpTab) btnExpTab.addEventListener("click", exportHtmlReport);

(async function init() {
    try {
        const st = await fetch("/api/auth/status", {
            headers: OPERATOR_TOKEN ? { "X-Operator-Token": OPERATOR_TOKEN } : {}
        }).then(r => r.json());

        const trialTxt = document.getElementById("trialModalStatusText");
        if (trialTxt) {
            trialTxt.textContent = `Experimente até ${st.trial_limit || 4} diagnósticos gratuitos + IA Local N3 (Usados nesta máquina: ${st.trial_used || 0}/${st.trial_limit || 4}).`;
        }
        const activeKeyEl = document.getElementById("admActiveKeyText");
        if (activeKeyEl && st.activated_license_key) {
            activeKeyEl.textContent = st.activated_license_key;
        }

        if (!st.authorized) {
            document.getElementById("authModal").classList.remove("hidden");
        } else {
            updateSessionUI(st.session);
            runFullDiagnostic();
        }
    } catch (e) {
        console.error(e);
    }
})();

// ==================== CONTROLADOR AEGISPULSE HEALTH SCORE (v4.5) ====================

function renderHealthScoreTab(hs) {
    if (!hs) return;
    CURRENT_HEALTH_SCORE = hs;

    const scoreBig = document.getElementById("hsOverallScoreBig");
    if (scoreBig) {
        scoreBig.textContent = `${hs.overall_score}`;
        scoreBig.style.color = hs.classification_color || "#10b981";
    }

    const classBadge = document.getElementById("hsClassBadge");
    if (classBadge) {
        classBadge.textContent = hs.classification ? hs.classification.toUpperCase() : "DESCONHECIDO";
        classBadge.className = `badge ${hs.classification_badge || 'ok'}`;
    }

    const covCount = document.getElementById("hsCoverageCountText");
    if (covCount) covCount.textContent = hs.coverage?.label || "—";

    const covPct = document.getElementById("hsCoveragePctText");
    if (covPct) covPct.textContent = `${hs.coverage?.percent || 0}% de cobertura analítica`;

    const uuidTxt = document.getElementById("hsMachineUuidText");
    if (uuidTxt) uuidTxt.textContent = hs.machine_uuid || "—";

    const hostTxt = document.getElementById("hsHostText");
    if (hostTxt) hostTxt.textContent = `Host: ${hs.hostname || 'Local'}`;

    const dateTxt = document.getElementById("hsEvaluatedAtText");
    if (dateTxt) dateTxt.textContent = `Avaliado em: ${hs.evaluated_at || '—'}`;

    const capNotice = document.getElementById("hsCriticalCapNotice");
    if (capNotice) {
        if (hs.critical_cap_applied) {
            capNotice.innerHTML = "🚨 <strong>TRAVA CRÍTICA ATIVA:</strong> Nota limitada a 59 (Ruim) devido a falha crítica de hardware/dados.";
            capNotice.style.color = "#ef4444";
        } else if (hs.has_critical_issue) {
            capNotice.innerHTML = "⚠️ <strong>ALERTA:</strong> Há falha grave identificada nos achados técnicos.";
            capNotice.style.color = "#f97316";
        } else {
            capNotice.innerHTML = "✅ <strong>NORMAL:</strong> Nenhuma falha crítica de hardware ou perda de dados detectada.";
            capNotice.style.color = "#34d399";
        }
    }

    // 8 Categorias Ponderadas
    const catsGrid = document.getElementById("hsCategoriesGrid");
    if (catsGrid) {
        catsGrid.innerHTML = Object.entries(hs.categories || {}).map(([ck, cv]) => {
            const bCls = cv.status === "critico" ? "err" : (cv.status === "atencao" ? "warn" : "ok");
            const scDisplay = cv.available ? `${cv.score}/100` : "Indisponível";
            const barFill = cv.available ? cv.score : 0;
            const barColor = cv.status === "critico" ? "#ef4444" : (cv.status === "atencao" ? "#f59e0b" : "#10b981");

            return `
            <div class="maint-card" style="border-top:3px solid ${barColor};">
                <div class="flex-between">
                    <strong>${cv.category_title || ck}</strong>
                    <span class="badge ${bCls}">${(cv.status || 'normal').toUpperCase()}</span>
                </div>
                <div style="display:flex;justify-content:space-between;align-items:center;margin:8px 0 4px;">
                    <span style="font-size:18px;font-weight:700;color:${barColor};">${scDisplay}</span>
                    <small class="muted">Peso: ${cv.effective_weight_pct || 0}%</small>
                </div>
                <div class="bar-bg" style="width:100%;height:8px;margin-bottom:8px;">
                    <div class="bar-fill" style="background-color:${barColor} !important;width:${barFill}%;"></div>
                </div>
                <p class="muted" style="font-size:12px;margin:0;">${cv.summary || 'Sem observações.'}</p>
            </div>
            `;
        }).join("");
    }

    // Achados e Trilha de Auditoria
    renderFindingsTable(hs.prioritized_findings || []);
    renderAuditTrailTable(hs.audit_trail?.deductions_detail || []);
    loadHealthScoreHistory();
}

function renderFindingsTable(findings) {
    const tbody = document.getElementById("hsFindingsTableBody");
    if (!tbody) return;

    // Atualiza contadores dos filtros
    const allCount = findings.length;
    const critCount = findings.filter(f => f.severity === "CRÍTICO").length;
    const highCount = findings.filter(f => f.severity === "ALTO").length;
    const medCount = findings.filter(f => f.severity === "MÉDIO").length;

    const elAll = document.getElementById("countFindingsAll");
    if (elAll) elAll.textContent = allCount;
    const elCrit = document.getElementById("countFindingsCrit");
    if (elCrit) elCrit.textContent = critCount;
    const elHigh = document.getElementById("countFindingsHigh");
    if (elHigh) elHigh.textContent = highCount;
    const elMed = document.getElementById("countFindingsMed");
    if (elMed) elMed.textContent = medCount;

    const filtered = CURRENT_FINDINGS_FILTER === "TODOS"
        ? findings
        : findings.filter(f => f.severity === CURRENT_FINDINGS_FILTER);

    if (!filtered.length) {
        tbody.innerHTML = '<tr><td colspan="7">Nenhum problema encontrado neste nível de severidade.</td></tr>';
        return;
    }

    tbody.innerHTML = filtered.map(f => {
        const bCls = f.severity === "CRÍTICO" ? "err" : (f.severity === "ALTO" ? "warn" : "ok");
        const rCls = (f.action_risk_level || "").includes("ALTO") ? "err" : ((f.action_risk_level || "").includes("MODERADO") ? "warn" : "ok");

        return `
        <tr>
            <td><strong>${f.title}</strong><br><small class="muted">${f.affected_component}</small></td>
            <td><span class="badge ${bCls}">${f.severity}</span></td>
            <td><small>${f.probable_impact}</small></td>
            <td><code>${f.technical_evidence}</code></td>
            <td><small>${f.confidence}</small></td>
            <td><strong>${f.recommendation}</strong></td>
            <td><span class="badge ${rCls}">${f.action_risk_level}</span></td>
        </tr>
        `;
    }).join("");
}

function filterFindings(sev, btn) {
    CURRENT_FINDINGS_FILTER = sev;
    if (btn && btn.parentElement) {
        btn.parentElement.querySelectorAll(".btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
    }
    if (CURRENT_HEALTH_SCORE) {
        renderFindingsTable(CURRENT_HEALTH_SCORE.prioritized_findings || []);
    }
}

function renderAuditTrailTable(deductions) {
    const tbody = document.getElementById("hsAuditTableBody");
    if (!tbody) return;
    if (!deductions || !deductions.length) {
        tbody.innerHTML = '<tr><td colspan="3">Nenhuma penalidade aplicada. A máquina obteve nota máxima nas categorias disponíveis!</td></tr>';
        return;
    }
    tbody.innerHTML = deductions.map(d => `
        <tr>
            <td><strong>${d.category_title}</strong></td>
            <td><span class="badge err">-${d.points} pts</span></td>
            <td>${d.reason}</td>
        </tr>
    `).join("");
}

async function loadHealthScoreHistory() {
    try {
        const res = await apiFetch("/api/health-score/history?limit=15");
        const items = res.items || [];
        const tbody = document.getElementById("hsHistoryTableBody");
        if (tbody) {
            tbody.innerHTML = items.map(it => `
                <tr>
                    <td><code>${it.evaluated_at}</code></td>
                    <td><strong>${it.overall_score}</strong></td>
                    <td><span class="badge ${it.classification_badge || 'ok'}">${it.classification}</span></td>
                    <td>${it.coverage?.label || '8/8'}</td>
                    <td>${it.has_critical_issue ? '<span class="badge err">SIM</span>' : '<span class="badge ok">Não</span>'}</td>
                    <td><button class="btn secondary" onclick="viewHistoricalHealthScore(${it.id})">🔍 Ver</button></td>
                </tr>
            `).join("") || '<tr><td colspan="6">Nenhuma avaliação anterior no banco SQLite.</td></tr>';
        }
        renderHealthScoreChart(res.chart_series || []);
    } catch (e) {
        console.warn("Falha ao carregar histórico de Health Score:", e);
    }
}

function renderHealthScoreChart(series) {
    const box = document.getElementById("hsHistoryChartBox");
    if (!box) return;
    if (!series || series.length < 1) {
        box.innerHTML = '<p class="muted">Sem coletas suficientes no histórico SQLite.</p>';
        return;
    }
    const w = 460;
    const h = 110;
    const pts = series.slice(-12);
    const stepX = pts.length > 1 ? (w - 40) / (pts.length - 1) : 0;

    const coords = pts.map((p, i) => {
        const x = 20 + i * stepX;
        const val = Math.min(100, Math.max(0, Number(p.score || 0)));
        const y = h - 20 - (val / 100) * (h - 36);
        return `${x},${y.toFixed(1)}`;
    }).join(" ");

    box.innerHTML = `
        <div style="display:flex;justify-content:space-between;font-size:11.5px;color:#94a3b8;margin-bottom:6px;">
            <span>📈 Série Temporal Health Score (${pts.length} coletas registradas)</span>
            <span><strong style="color:#10b981;">● Pontuação (0–100)</strong></span>
        </div>
        <svg viewBox="0 0 ${w} ${h}" style="width:100%;height:110px;overflow:visible;">
            <line x1="20" y1="${h - 20}" x2="${w - 20}" y2="${h - 20}" stroke="#334155" stroke-width="1"/>
            <line x1="20" y1="${h - 20 - 0.6 * (h - 36)}" x2="${w - 20}" y2="${h - 20 - 0.6 * (h - 36)}" stroke="#f59e0b" stroke-width="0.7" stroke-dasharray="3,3"/>
            <line x1="20" y1="${h - 20 - 0.9 * (h - 36)}" x2="${w - 20}" y2="${h - 20 - 0.9 * (h - 36)}" stroke="#10b981" stroke-width="0.7" stroke-dasharray="3,3"/>
            ${pts.length > 1 ? `<polyline fill="none" stroke="#10b981" stroke-width="2.5" points="${coords}"/>` : ''}
            ${pts.map((p, i) => {
                const x = 20 + i * stepX;
                const val = Math.min(100, Math.max(0, Number(p.score || 0)));
                const y = h - 20 - (val / 100) * (h - 36);
                const color = val >= 75 ? "#10b981" : (val >= 60 ? "#f59e0b" : "#ef4444");
                return `<circle cx="${x}" cy="${y.toFixed(1)}" r="4" fill="${color}"><title>${p.date}: ${p.score} pts (${p.classification})</title></circle>`;
            }).join("")}
        </svg>
    `;
}

// Event Listeners do Health Score
const btnEvalHs = document.getElementById("btnEvaluateHealthScore");
if (btnEvalHs) {
    btnEvalHs.addEventListener("click", async () => {
        showToast("🩺 Recalculando Índice de Saúde Health Score e avaliando 8 categorias...");
        try {
            const res = await apiFetch("/api/health-score/evaluate", { method: "POST" });
            if (res.health_score) {
                renderHealthScoreTab(res.health_score);
                showToast(`✅ Health Score calculado: ${res.health_score.overall_score}/100 (${res.health_score.classification})!`);
            }
        } catch (e) {
            console.error(e);
        }
    });
}

const btnCompHs = document.getElementById("btnCompareHealthScore");
if (btnCompHs) {
    btnCompHs.addEventListener("click", async () => {
        showToast("📊 Consultando comparação temporal com avaliação anterior...");
        try {
            const res = await apiFetch("/api/health-score/compare");
            if (res.success && res.comparison) {
                renderHealthScoreComparison(res.comparison);
            } else {
                showToast(res.message || "Histórico insuficiente para comparação.");
            }
        } catch (e) {
            showToast("Necessário ao menos 1 avaliação anterior salva no SQLite.");
        }
    });
}

function renderHealthScoreComparison(comp) {
    const panel = document.getElementById("hsComparisonPanel");
    if (!panel) return;
    panel.classList.remove("hidden");

    document.getElementById("hsCompareTrendSummary").innerHTML = `<strong>${comp.trend_label}:</strong> ${comp.trend_summary}`;

    const deltaSign = comp.score_delta > 0 ? `+${comp.score_delta}` : `${comp.score_delta}`;
    const scoreDeltaEl = document.getElementById("hsDiffScoreDelta");
    if (scoreDeltaEl) {
        scoreDeltaEl.textContent = `${deltaSign} pts`;
        scoreDeltaEl.style.color = comp.score_delta >= 0 ? "#10b981" : "#ef4444";
    }

    const diffDatesEl = document.getElementById("hsDiffDates");
    if (diffDatesEl) diffDatesEl.textContent = `${comp.older_date} ➔ ${comp.newer_date}`;

    const covDeltaEl = document.getElementById("hsDiffCoverageDelta");
    if (covDeltaEl) covDeltaEl.textContent = `${comp.coverage_delta > 0 ? '+' : ''}${comp.coverage_delta}%`;

    const newCntEl = document.getElementById("hsDiffNewCount");
    if (newCntEl) newCntEl.textContent = (comp.new_findings || []).length;

    const resCntEl = document.getElementById("hsDiffResolvedCount");
    if (resCntEl) resCntEl.textContent = (comp.resolved_findings || []).length;

    const detailsBox = document.getElementById("hsDiffDetailsList");
    if (detailsBox) {
        let rows = "";
        for (const f of (comp.new_findings || [])) {
            rows += `<div class="kv-row"><span class="badge err">NOVO ALERTA</span><strong>${f.title}</strong> (${f.affected_component})</div>`;
        }
        for (const f of (comp.resolved_findings || [])) {
            rows += `<div class="kv-row"><span class="badge ok">PROBLEMA RESOLVIDO</span><strong>${f.title}</strong> (${f.affected_component})</div>`;
        }
        if (!rows) {
            rows = '<p class="muted" style="margin:4px 0;">Nenhum problema novo ou resolvido. Conjunto de alertas permaneceu idêntico.</p>';
        }
        detailsBox.innerHTML = rows;
    }
}

const btnToggleAudit = document.getElementById("btnToggleAuditTrail");
if (btnToggleAudit) {
    btnToggleAudit.addEventListener("click", () => {
        const p = document.getElementById("hsAuditPanel");
        if (p) p.classList.toggle("hidden");
    });
}


// ============================================================================
// v5.0 — CENTRAL SUPREMA DISKPART, DESBLOQUEIO FORÇADO, FORMATAÇÃO & BOOTÁVEL
// ============================================================================



function _renderTargetAndVdsDiagnostics(dev, storageSuite) {
    const banner = document.getElementById("dpTargetSummaryBanner");
    const vdsBox = document.getElementById("vdsHealthDiagnosticBox");
    const occupied = storageSuite?.occupied_drive_letters || ["C:"];

    // Atualiza seletor de letras marcando e desabilitando letras já ocupadas (ex: C:, D:, E:, F:, P:)
    const letterSel = document.getElementById("dpDesiredLetterSelect");
    if (letterSel) {
        Array.from(letterSel.options).forEach(opt => {
            if (opt.value === "AUTO") return;
            const fmt = `${opt.value}:`.toUpperCase();
            const isUsed = occupied.includes(fmt);
            opt.disabled = isUsed;
            opt.textContent = isUsed ? `Letra ${fmt} (Já Ocupada)` : `Letra ${fmt} (Livre)`;
        });
        if (letterSel.selectedOptions[0]?.disabled) {
            letterSel.value = "AUTO";
        }
    }

    if (banner && dev) {
        const isSys = Boolean(dev.is_system_disk || dev.contains_windows_volume || dev.contains_efi_boot_partition || dev.is_protected_from_destruction);
        const borderCol = isSys ? "#ef4444" : "#10b981";
        const bgCol = isSys ? "rgba(239,68,68,0.10)" : "rgba(16,185,129,0.08)";
        const statusTitle = isSys
            ? `🔒 DISCO PROTEGIDO PELO SISTEMA — OPERAÇÕES DESTRUTIVAS E FORÇADAS BLOQUEADAS`
            : `✅ DESTINO ELEGÍVEL PARA MANUTENÇÃO, DESBLOQUEIO OU FORMATAÇÃO`;
        const reasonsHtml = (dev.protection_reasons && dev.protection_reasons.length)
            ? `<div style="margin-top:4px;color:#fca5a5;font-size:12px;"><strong>Motivo(s) do Bloqueio:</strong> ${dev.protection_reasons.join(" | ")}</div>`
            : "";

        const partsSummary = (dev.partitions || []).map(p =>
            `Partição #${p.partition_number}: <strong>${p.drive_letter}</strong> (${p.filesystem} | ${p.partition_role || p.type} | ${p.capacity?.formatted || ''})`
        ).join(" • ") || "0 Partições Reconhecidas (Não Inicializado / Espaço Bruto)";

        banner.style.borderColor = borderCol;
        banner.style.background = bgCol;
        banner.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
                <div>
                    <strong style="color:${borderCol};font-size:13.5px;">${statusTitle}</strong><br>
                    <span style="font-size:13px;">
                        🎯 <strong>Destino Selecionado:</strong> <code>Disk #${dev.disk_number} (${dev.device_path})</code> —
                        <strong>${dev.brand} ${dev.model}</strong> | Série: <code>${dev.serial_number}</code> |
                        Hash ID: <code>${dev.hardware_identity_hash || 'N/D'}</code> |
                        Capacidade: <strong>${dev.capacity?.formatted || ''}</strong>
                    </span>
                </div>
                <span class="badge ${isSys ? 'err' : 'ok'}">${isSys ? 'PROTEGIDO (WINDOWS / EFI)' : `DISK #${dev.disk_number} SELECIONADO`}</span>
            </div>
            <div style="margin-top:6px;font-size:12px;color:#cbd5e1;">
                <strong>Partições &amp; Volumes no Destino:</strong> ${partsSummary}
            </div>
            ${reasonsHtml}
        `;
    }

    if (vdsBox) {
        const diag = storageSuite?.diskmgmt_diagnostics || {};
        const isDeg = diag.status === "degraded_or_blocked" || diag.vds_timeout_reached;
        const col = isDeg ? "#f59e0b" : "#10b981";
        const evList = (diag.evidence || []).map(e => `<li>${e}</li>`).join("");
        const recList = (diag.recommended_safe_actions || []).map(r => `<li><strong>Ação Segura:</strong> ${r}</li>`).join("");
        vdsBox.style.borderColor = col;
        vdsBox.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <strong style="color:${col};">🩺 Diagnóstico do Subsistema de Disco &amp; Gerenciamento de Disco (diskmgmt.msc / VDS)</strong>
                <small class="muted">WMI: ${diag.wmi_query_ms ?? 0} ms | VDS: ${diag.vds_query_ms ?? 0} ms | Serviço VDS: ${diag.vds_service_status || 'Running'}</small>
            </div>
            <div style="margin-top:4px;color:#e2e8f0;">${diag.summary || 'Subsistema operacional.'}</div>
            ${evList ? `<ul style="margin:6px 0 0 18px;padding:0;color:#cbd5e1;">${evList}${recList}</ul>` : ''}
        `;
    }
}

function getSelectedStorageDevice() {
    const devs = CURRENT_SNAPSHOT?.storage_suite?.devices || [];
    if (SELECTED_STORAGE_INDEX >= 0 && SELECTED_STORAGE_INDEX < devs.length) {
        return devs[SELECTED_STORAGE_INDEX];
    }
    return devs[0] || null;
}

function _updateDiskpartConsole(title, res) {
    const box = document.getElementById("diskpartConsoleOutput");
    if (!box) return;
    const lines = [];
    lines.push(`=== ${title} (Disk #${res.disk_number ?? ''}) ===`);
    if (res.message) lines.push(res.message);
    if (Array.isArray(res.steps_log) && res.steps_log.length) {
        lines.push("--- Etapas Executadas ---");
        res.steps_log.forEach(s => lines.push(s));
    }
    if (res.powershell_output) {
        lines.push("--- Saída Storage API / PowerShell ---");
        lines.push(res.powershell_output);
    }
    if (res.diskpart_script) {
        lines.push("--- Script DiskPart Enviado ---");
        lines.push(res.diskpart_script);
    }
    if (res.diskpart_output) {
        lines.push("--- Saída Nativa diskpart.exe ---");
        lines.push(res.diskpart_output);
    }
    box.textContent = lines.join("\n");
    box.style.borderColor = res.success ? "#10b981" : "#ef4444";
    box.style.color = res.success ? "#34d399" : "#fca5a5";
    box.scrollTop = 0;
    try { box.scrollIntoView({ behavior: "smooth", block: "nearest" }); } catch (e) {}
}

function _applyRefreshedStorageSuite(res) {
    if (res && res.storage_suite && Array.isArray(res.storage_suite.devices)) {
        if (!CURRENT_SNAPSHOT) CURRENT_SNAPSHOT = {};
        CURRENT_SNAPSHOT.storage_suite = res.storage_suite;
        renderStorageSuiteTab(res.storage_suite);
    }
    syncActionLogs(res);
}

async function runDiskpartUnlock() {
    const dev = getSelectedStorageDevice();
    if (!dev) return;
    const initRaw = document.getElementById("dpInitIfRawCheckbox")?.checked ?? true;
    showToast(`⚡ Forçando desbloqueio total, remoção de Read-Only e atribuição de letra em Disk #${dev.disk_number} (${dev.model})...`);
    const box = document.getElementById("diskpartConsoleOutput");
    if (box) box.textContent = `⏳ Executando desbloqueio agressivo via DiskPart + Storage API em Disk #${dev.disk_number} (${dev.model})...`;

    try {
        const res = await apiFetch("/api/storage/diskpart/unlock", {
            method: "POST",
            body: JSON.stringify({
                disk_number: dev.disk_number,
                device_uid: dev.device_uid,
                initialize_if_raw: initRaw
            })
        });
        _updateDiskpartConsole("DESBLOQUEIO FORÇADO & MONTAGEM", res);
        _applyRefreshedStorageSuite(res);
        showToast(res.message || "Disco desbloqueado e montado com sucesso!");
    } catch (e) {
        if (box) box.textContent = `❌ Erro no desbloqueio: ${e.message}`;
    }
}

async function runDiskpartAssignLetter() {
    const dev = getSelectedStorageDevice();
    if (!dev) return;
    const letter = "AUTO";
    showToast(`🔤 Atribuindo letra (${letter}) para Disk #${dev.disk_number} (${dev.model})...`);
    const box = document.getElementById("diskpartConsoleOutput");
    if (box) box.textContent = `⏳ Forçando montagem e atribuição de letra (${letter}) em Disk #${dev.disk_number}...`;

    try {
        const res = await apiFetch("/api/storage/diskpart/assign-letter", {
            method: "POST",
            body: JSON.stringify({
                disk_number: dev.disk_number,
                device_uid: dev.device_uid,
                desired_letter: letter,
                partition_number: 0
            })
        });
        _updateDiskpartConsole(`ATRIBUIÇÃO DE LETRA (${letter})`, res);
        _applyRefreshedStorageSuite(res);
        showToast(res.message || "Letra atribuída com sucesso!");
    } catch (e) {
        if (box) box.textContent = `❌ Erro ao atribuir letra: ${e.message}`;
    }
}

async function runDiskpartFormat() {
    const dev = getSelectedStorageDevice();
    if (!dev) return;
    const fs = document.getElementById("dpFormatFsSelect")?.value || "NTFS";
    const style = document.getElementById("dpFormatStyleSelect")?.value || "GPT";
    const label = document.getElementById("dpFormatLabelInput")?.value || "AEGIS_DISK";
    const quick = document.getElementById("dpFormatQuickCheckbox")?.checked ?? true;
    const fullRep = document.getElementById("dpFormatFullRepartitionCheckbox")?.checked ?? true;
    const letter = "AUTO";
    let confirmTok = document.getElementById("dpFormatConfirmInput")?.value || "";

    if (confirmTok.trim().toUpperCase() !== "FORMATAR") {
        const p = prompt(
            `⚠️ ATENÇÃO: Você está prestes a formatar o Disco #${dev.disk_number} (${dev.brand} ${dev.model} — ${dev.capacity?.formatted || ''}) em ${fs} (${style}).\n\n` +
            `Todos os dados desta unidade serão apagados e ela receberá uma letra de unidade limpa.\n` +
            `Digite exatamente FORMATAR para confirmar:`
        );
        if (!p) return;
        confirmTok = p.trim();
        const inp = document.getElementById("dpFormatConfirmInput");
        if (inp) inp.value = confirmTok;
    }

    showToast(`💿 Formatando Disk #${dev.disk_number} (${dev.model}) em ${fs} e atribuindo letra... aguarde!`);
    const box = document.getElementById("diskpartConsoleOutput");
    if (box) box.textContent = `⏳ Executando DiskPart Format (${fs} / ${style}) em Disk #${dev.disk_number} (${dev.model})...`;

    try {
        const res = await apiFetch("/api/storage/diskpart/format", {
            method: "POST",
            body: JSON.stringify({
                disk_number: dev.disk_number,
                device_uid: dev.device_uid,
                filesystem: fs,
                volume_label: label,
                quick_format: quick,
                partition_style: style,
                full_repartition: fullRep,
                desired_letter: letter,
                confirm_token: confirmTok,
                confirm_device_uid: dev.device_uid
            })
        });
        _updateDiskpartConsole(`FORMATAÇÃO SUPREMA (${fs})`, res);
        _applyRefreshedStorageSuite(res);
        showToast(res.message || "Formatação concluída!");
    } catch (e) {
        if (box) box.textContent = `❌ Erro na formatação: ${e.message}`;
    }
}

async function runDiskpartQuickAction(actionName) {
    const dev = getSelectedStorageDevice();
    if (!dev) return;
    let confirmTok = document.getElementById("dpActionConfirmInput")?.value || "";
    const destructive = ["clean_disk", "clean_all_zero", "convert_gpt", "convert_mbr"];

    if (destructive.includes(actionName) && !["CONFIRMAR", "FORMATAR", "LIMPAR"].includes(confirmTok.trim().toUpperCase())) {
        const p = prompt(
            `⚠️ A operação DiskPart '${actionName.toUpperCase()}' vai limpar/reconverter a tabela de partições do Disco #${dev.disk_number} (${dev.model}).\n\n` +
            `Digite CONFIRMAR para executar:`
        );
        if (!p) return;
        confirmTok = p.trim();
        const inp = document.getElementById("dpActionConfirmInput");
        if (inp) inp.value = confirmTok;
    }

    showToast(`🛠️ Executando DiskPart [${actionName.toUpperCase()}] em Disk #${dev.disk_number}...`);
    const box = document.getElementById("diskpartConsoleOutput");
    if (box) box.textContent = `⏳ Executando comando DiskPart [${actionName}] em Disk #${dev.disk_number}...`;

    try {
        const res = await apiFetch("/api/storage/diskpart/action", {
            method: "POST",
            body: JSON.stringify({
                disk_number: dev.disk_number,
                device_uid: dev.device_uid,
                action: actionName,
                confirm_token: confirmTok,
                confirm_device_uid: dev.device_uid
            })
        });
        _updateDiskpartConsole(`DISKPART: ${actionName.toUpperCase()}`, res);
        _applyRefreshedStorageSuite(res);
        showToast(res.message || `Comando DiskPart ${actionName} concluído!`);
    } catch (e) {
        if (box) box.textContent = `❌ Erro no DiskPart: ${e.message}`;
    }
}

async function runDiskpartCustomScript() {
    const dev = getSelectedStorageDevice();
    if (!dev) return;
    const scr = document.getElementById("dpCustomScriptInput")?.value || "";
    if (!scr.trim()) {
        showToast("Digite os comandos DiskPart na caixa de script antes de executar.");
        return;
    }
    showToast(`💻 Executando script customizado no DiskPart...`);
    const box = document.getElementById("diskpartConsoleOutput");
    if (box) box.textContent = `⏳ Executando script DiskPart...`;

    try {
        const res = await apiFetch("/api/storage/diskpart/action", {
            method: "POST",
            body: JSON.stringify({
                disk_number: dev.disk_number,
                device_uid: dev.device_uid,
                action: "custom_script",
                custom_script: scr,
                confirm_token: "CONFIRMAR"
            })
        });
        _updateDiskpartConsole("SCRIPT DISKPART CUSTOMIZADO", res);
        _applyRefreshedStorageSuite(res);
        showToast(res.message || "Script DiskPart executado!");
    } catch (e) {
        if (box) box.textContent = `❌ Erro no script DiskPart: ${e.message}`;
    }
}

async function runCreateBootableDrive() {
    const dev = getSelectedStorageDevice();
    if (!dev) return;
    const scheme = document.getElementById("dpBootSchemeSelect")?.value || "UEFI_GPT";
    const fs = document.getElementById("dpBootFsSelect")?.value || "NTFS";
    const label = document.getElementById("dpBootLabelInput")?.value || "AEGIS_BOOT";
    const isoPath = document.getElementById("dpBootIsoPathInput")?.value || "";
    let confirmTok = document.getElementById("dpBootConfirmInput")?.value || "";

    if (!["CRIAR_BOOT", "FORMATAR", "CONFIRMAR"].includes(confirmTok.trim().toUpperCase())) {
        const p = prompt(
            `🚀 CRIADOR DE MÍDIA BOOTÁVEL (${scheme} / ${fs}):\n` +
            `Alvo: Disco #${dev.disk_number} (${dev.brand} ${dev.model} — ${dev.capacity?.formatted || ''})\n` +
            (isoPath ? `ISO: ${isoPath}\n` : `Modo: Preparar Partição de Boot Ativa + Setor NT60\n`) +
            `\nDigite CRIAR_BOOT ou FORMATAR para autorizar:`
        );
        if (!p) return;
        confirmTok = p.trim();
        const inp = document.getElementById("dpBootConfirmInput");
        if (inp) inp.value = confirmTok;
    }

    showToast(`🚀 Criando estrutura bootável (${scheme}) em Disk #${dev.disk_number}... aguarde!`);
    const box = document.getElementById("diskpartConsoleOutput");
    if (box) box.textContent = `⏳ Preparando disco bootável (${scheme} / ${fs}) em Disk #${dev.disk_number} (${dev.model})...`;

    try {
        const res = await apiFetch("/api/storage/diskpart/bootable", {
            method: "POST",
            body: JSON.stringify({
                disk_number: dev.disk_number,
                device_uid: dev.device_uid,
                iso_path: isoPath,
                boot_scheme: scheme,
                filesystem: fs,
                volume_label: label,
                confirm_token: confirmTok,
                confirm_device_uid: dev.device_uid
            })
        });
        _updateDiskpartConsole(`CRIADOR DE DISCO BOOTÁVEL (${scheme})`, res);
        _applyRefreshedStorageSuite(res);
        showToast(res.message || "Mídia bootável criada com sucesso!");
    } catch (e) {
        if (box) box.textContent = `❌ Erro ao criar mídia bootável: ${e.message}`;
    }
}

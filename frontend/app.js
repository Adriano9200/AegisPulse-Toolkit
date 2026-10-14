/*
================================================================================
PROJETO: AegisPulse IT Toolkit — Frontend Controller
ARQUIVO: frontend/app.js
AUTOR:   Adriano Barboza (adriano9200@gmail.com)
================================================================================
*/

let OPERATOR_TOKEN = localStorage.getItem("aegispulse_token") || "";
let CURRENT_SNAPSHOT = null;

function showToast(msg) {
    const t = document.getElementById("statusToast");
    t.textContent = msg;
    t.classList.remove("hidden");
    setTimeout(() => t.classList.add("hidden"), 5500);
}

async function apiFetch(path, options = {}) {
    const headers = options.headers || {};
    headers["Content-Type"] = "application/json";
    if (OPERATOR_TOKEN) {
        headers["X-Operator-Token"] = OPERATOR_TOKEN;
    }
    const resp = await fetch(path, { ...options, headers });
    if (resp.status === 401) {
        document.getElementById("authModal").classList.remove("hidden");
        throw new Error("Não autorizado");
    }
    return resp.json();
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

// Login do Operador
document.getElementById("btnUnlock").addEventListener("click", async () => {
    const pin = document.getElementById("pinInput").value;
    const resp = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin })
    });
    const data = await resp.json();
    if (data.success) {
        OPERATOR_TOKEN = data.token;
        localStorage.setItem("aegispulse_token", OPERATOR_TOKEN);
        document.getElementById("authModal").classList.add("hidden");
        document.getElementById("authError").classList.add("hidden");
        runFullDiagnostic();
    } else {
        document.getElementById("authError").classList.remove("hidden");
    }
});

async function runFullDiagnostic() {
    showToast("🔍 Executando varredura completa de Hardware, SO, BIOS, Drivers e Softwares...");
    try {
        const data = await apiFetch("/api/scan/full");
        CURRENT_SNAPSHOT = data;
        renderDashboard(data);
        showToast("✅ Diagnóstico concluído com sucesso!");
    } catch (err) {
        console.warn("Aguardando autenticação ou falha na coleta:", err);
    }
}

function renderDashboard(data) {
    const hw = data.hardware || {};
    const os = data.os || {};
    const drv = data.drivers_bios || {};
    const bios = drv.bios || {};
    const sw = data.software || {};

    document.getElementById("machineTitle").textContent = `${hw.manufacturer || "PC"} — ${hw.model || "Workstation"}`;
    document.getElementById("machineSubtitle").textContent = `Hostname: ${hw.hostname} | Coletado em: ${data.collected_at} | Autor do Toolkit: Adriano Barboza`;

    const netBadge = document.getElementById("netBadge");
    if (data.online) {
        netBadge.textContent = "🌐 Online (Gemini Pronto)";
        netBadge.className = "status-pill online";
    } else {
        netBadge.textContent = "⚠️ Offline (Modo Local)";
        netBadge.className = "status-pill offline";
    }

    // KPIs
    document.getElementById("kpiModel").textContent = `${hw.manufacturer} ${hw.model}`;
    document.getElementById("kpiSerial").textContent = `Service Tag / Serial: ${hw.serial_service_tag}`;
    document.getElementById("kpiOS").textContent = `${os.os_name} (${os.display_version})`;
    document.getElementById("kpiBuild").textContent = `Build: ${os.full_build} | ${os.architecture}`;

    const firstCpu = (hw.cpus && hw.cpus[0]) ? hw.cpus[0].name : "Processador N/D";
    document.getElementById("kpiCpu").textContent = firstCpu;
    document.getElementById("kpiRam").textContent = `RAM Instalada: ${hw.total_ram_gb} GB (${(hw.ram_modules || []).length} pente(s))`;

    document.getElementById("kpiAlerts").textContent = `${sw.outdated_count || 0} Apps Obsoletos | ${drv.outdated_drivers_count || 0} Drivers Antigos`;
    document.getElementById("kpiBiosStatus").textContent = `BIOS ${bios.smbios_version} (${bios.status_label})`;

    // Detalhes do SO
    const osList = document.getElementById("osDetailsList");
    osList.innerHTML = `
        <div class="kv-row"><span class="muted">Sistema Operacional</span><strong>${os.os_name}</strong></div>
        <div class="kv-row"><span class="muted">Versão / Release</span><strong>${os.display_version}</strong></div>
        <div class="kv-row"><span class="muted">Build Completa (UBR)</span><code>${os.full_build}</code></div>
        <div class="kv-row"><span class="muted">Edição / Arquitetura</span><span>${os.edition} (${os.architecture})</span></div>
        <div class="kv-row"><span class="muted">Data de Instalação</span><span>${os.install_date}</span></div>
        <div class="kv-row"><span class="muted">Último Boot / Uptime</span><span>${os.last_boot} (${os.uptime_hours} h)</span></div>
    `;

    // Segurança
    const sec = os.security || {};
    const secList = document.getElementById("securityDetailsList");
    secList.innerHTML = `
        <div class="kv-row"><span class="muted">Antivírus Ativo</span><span class="badge ${sec.antivirus_enabled ? 'ok' : 'err'}">${sec.antivirus_enabled ? 'Ativo' : 'Desativado'}</span></div>
        <div class="kv-row"><span class="muted">Proteção em Tempo Real</span><span class="badge ${sec.realtime_protection ? 'ok' : 'warn'}">${sec.realtime_protection ? 'Protegido' : 'Alerta'}</span></div>
        <div class="kv-row"><span class="muted">Idade das Assinaturas</span><span>${sec.signature_age_days} dia(s)</span></div>
        <div class="kv-row"><span class="muted">Chip TPM 2.0</span><span class="badge ${sec.tpm_present ? 'ok' : 'warn'}">${sec.tpm_present ? 'Presente / Pronto' : 'Não Detectado'}</span></div>
        <div class="kv-row"><span class="muted">Domínio / Grupo de Trabalho</span><span>${hw.domain_workgroup}</span></div>
    `;

    // Aba Hardware
    const mb = hw.motherboard || {};
    const gpu = (hw.gpus && hw.gpus[0]) ? hw.gpus[0] : {};
    document.getElementById("hwCoreList").innerHTML = `
        <div class="kv-row"><span class="muted">Placa-Mãe</span><strong>${mb.manufacturer} — ${mb.product}</strong></div>
        <div class="kv-row"><span class="muted">Serial Placa-Mãe</span><code>${mb.serial}</code></div>
        <div class="kv-row"><span class="muted">Processador</span><strong>${firstCpu}</strong></div>
        <div class="kv-row"><span class="muted">Placa de Vídeo (GPU)</span><strong>${gpu.name || 'N/D'}</strong></div>
        <div class="kv-row"><span class="muted">Driver de Vídeo Atual</span><code>${gpu.driver_version || 'N/D'}</code></div>
    `;

    const ramBody = document.getElementById("ramTableBody");
    ramBody.innerHTML = (hw.ram_modules || []).map(m => `
        <tr>
            <td><strong>${m.slot}</strong></td>
            <td>${m.manufacturer}</td>
            <td><code>${m.part_number}</code></td>
            <td>${m.capacity_gb} GB</td>
            <td>${m.speed_mhz} MHz</td>
        </tr>
    `).join("") || '<tr><td colspan="5">Módulos não detalhados pelo SMBIOS.</td></tr>';

    const diskBody = document.getElementById("diskTableBody");
    const diskRows = (hw.disks || []).map(d => `
        <tr>
            <td><strong>🖴 ${d.model}</strong> (Físico)</td>
            <td>${d.media_type} (${d.interface})</td>
            <td>${d.size_gb} GB</td>
            <td>—</td>
            <td><span class="badge ${d.health_status === 'Healthy' || d.health_status === 'OK' ? 'ok' : 'warn'}">SMART: ${d.health_status}</span></td>
        </tr>
    `).join("");
    const volRows = (hw.volumes || []).map(v => `
        <tr>
            <td><strong>📁 Unidade ${v.drive}</strong> (${v.label})</td>
            <td>Partição ${v.filesystem}</td>
            <td>${v.size_gb} GB</td>
            <td>${v.free_gb} GB</td>
            <td><span class="badge ${v.used_percent > 85 ? 'err' : 'ok'}">${v.used_percent}% ocupado</span></td>
        </tr>
    `).join("");
    diskBody.innerHTML = diskRows + volRows;

    // Aba Drivers & BIOS
    document.getElementById("btnVendorSupport").href = bios.vendor_support_url || "https://www.catalog.update.microsoft.com/";
    document.getElementById("biosSummaryBox").innerHTML = `
        <div class="kpi-card"><span class="kpi-label">FABRICANTE BIOS</span><strong>${bios.manufacturer}</strong></div>
        <div class="kpi-card"><span class="kpi-label">VERSÃO SMBIOS</span><strong>${bios.smbios_version}</strong></div>
        <div class="kpi-card"><span class="kpi-label">DATA DA BIOS</span><strong>${bios.release_date} (${bios.age_months} meses)</strong></div>
        <div class="kpi-card"><span class="kpi-label">DIAGNÓSTICO BIOS</span><strong>${bios.status_label}</strong></div>
    `;
    renderDriversTable(drv.drivers || []);

    // Aba Softwares & Winget
    const outBody = document.getElementById("outdatedSwTableBody");
    outBody.innerHTML = (sw.outdated_software || []).map(s => `
        <tr>
            <td><strong>${s.name}</strong></td>
            <td><code>${s.id}</code></td>
            <td><span class="badge warn">${s.current_version}</span></td>
            <td><span class="badge ok">${s.available_version}</span></td>
            <td><button class="btn primary" onclick="wingetAction('upgrade_one', '${s.id}')">Atualizar</button></td>
        </tr>
    `).join("") || '<tr><td colspan="5">Todos os softwares monitorados pelo Winget estão atualizados!</td></tr>';

    const catGrid = document.getElementById("catalogGrid");
    catGrid.innerHTML = (sw.essential_catalog || []).map(item => `
        <div class="catalog-item">
            <div>
                <span class="muted">${item.category}</span>
                <h4>${item.name}</h4>
                <code>${item.id}</code>
            </div>
            <button class="btn secondary" onclick="wingetAction('install', '${item.id}')">⬇️ Instalar (Winget)</button>
        </div>
    `).join("");

    document.getElementById("swTotalCount").textContent = sw.total_installed || 0;
    renderInstalledSoftwareTable(sw.installed_software || []);

    // Aba Logs
    renderLogsTable(data.action_logs || []);
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
    tbody.innerHTML = list.map(s => `
        <tr>
            <td><strong>${s.name}</strong></td>
            <td><code>${s.version}</code></td>
            <td>${s.publisher}</td>
            <td>${s.install_date}</td>
        </tr>
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

// Filtros de busca em tempo real
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

// Ações Winget
async function wingetAction(action, packageId = "") {
    showToast(`⏳ Executando Winget (${action} ${packageId})... Aguarde.`);
    const res = await apiFetch("/api/software/winget", {
        method: "POST",
        body: JSON.stringify({ action, package_id: packageId })
    });
    showToast(res.message || "Operação concluída.");
    runFullDiagnostic();
}

document.getElementById("btnUpgradeAllSw").addEventListener("click", () => {
    if (confirm("Deseja atualizar todos os softwares obsoletos silenciosamente via Winget?")) {
        wingetAction("upgrade_all");
    }
});

// Ações de Drivers Windows Update
async function handleWuDrivers(installFlag) {
    const box = document.getElementById("wuDriversResult");
    box.classList.remove("hidden");
    box.textContent = "⏳ Consultando catálogo de drivers no Windows Update...";
    const res = await apiFetch("/api/drivers/windows-update", {
        method: "POST",
        body: JSON.stringify({ install: installFlag })
    });
    box.textContent = res.message + (res.updates && res.updates.length
        ? " -> " + res.updates.map(u => u.Title).join(" | ")
        : "");
}

document.getElementById("btnScanWuDrivers").addEventListener("click", () => handleWuDrivers(false));
document.getElementById("btnInstallWuDrivers").addEventListener("click", () => {
    if (confirm("Deseja baixar e instalar automaticamente as atualizações oficiais de drivers do Windows Update?")) {
        handleWuDrivers(true);
    }
});

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

// Gemini AI
document.getElementById("btnAskGemini").addEventListener("click", async () => {
    const out = document.getElementById("geminiOutputBox");
    const prompt = document.getElementById("geminiPromptInput").value;
    const keyInput = document.getElementById("cfgGeminiKey").value;
    out.textContent = "✨ Consultando Google Gemini AI com a telemetria desta máquina...";
    const res = await apiFetch("/api/gemini/analyze", {
        method: "POST",
        body: JSON.stringify({ prompt, api_key: keyInput })
    });
    out.textContent = res.success ? res.response_text : `[AVISO] ${res.message}\n${res.response_text || ""}`;
});

// Salvar Configurações
document.getElementById("btnSaveConfig").addEventListener("click", async () => {
    const geminiKey = document.getElementById("cfgGeminiKey").value;
    const newPin = document.getElementById("cfgNewPin").value;
    const res = await apiFetch("/api/config/update", {
        method: "POST",
        body: JSON.stringify({ gemini_api_key: geminiKey, new_pin: newPin })
    });
    showToast(res.message || "Configurações salvas.");
});

// Exportar Laudo HTML
async function exportHtmlReport() {
    showToast("📄 Gerando Laudo Técnico e Log em HTML...");
    const res = await apiFetch("/api/report/generate", { method: "POST" });
    if (res.success && res.url) {
        window.open(res.url, "_blank");
        showToast(`✅ Relatório salvo em: ${res.report_path}`);
    }
}

document.getElementById("btnRescan").addEventListener("click", runFullDiagnostic);
document.getElementById("btnExportHtml").addEventListener("click", exportHtmlReport);

// Inicialização
(async function init() {
    try {
        const st = await fetch("/api/auth/status", {
            headers: OPERATOR_TOKEN ? { "X-Operator-Token": OPERATOR_TOKEN } : {}
        }).then(r => r.json());
        if (st.require_pin && !st.authorized) {
            document.getElementById("authModal").classList.remove("hidden");
        } else {
            runFullDiagnostic();
        }
    } catch (e) {
        console.error(e);
    }
})();

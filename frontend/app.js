/*
================================================================================
PROJETO: AegisPulse IT Toolkit — Frontend Controller
ARQUIVO: frontend/app.js
AUTOR:   Adriano Barboza (adriano9200@gmail.com)
VERSÃO:  1.1.0
================================================================================
*/

let OPERATOR_TOKEN = localStorage.getItem("aegispulse_token") || "";
let CURRENT_SNAPSHOT = null;

function showToast(msg) {
    const t = document.getElementById("statusToast");
    t.textContent = msg;
    t.classList.remove("hidden");
    setTimeout(() => t.classList.add("hidden"), 6000);
}

function syncActionLogs(res) {
    if (res && Array.isArray(res.action_logs)) {
        renderLogsTable(res.action_logs);
    }
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
    const data = await resp.json();
    syncActionLogs(data);
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
    showToast("🔍 Executando varredura completa v1.1 (Hardware, SO, BIOS, Drivers, Softwares, Bloatware, Rede e DLLs)...");
    try {
        const data = await apiFetch("/api/scan/full");
        CURRENT_SNAPSHOT = data;
        renderDashboard(data);
        showToast("✅ Diagnóstico v1.1 concluído com sucesso!");
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
    const net = data.network || {};
    const gaming = data.gaming || {};

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

    document.getElementById("kpiAlerts").textContent = `${sw.outdated_count || 0} Apps Obsoletos | ${sw.bloatware_count || 0} Bloatwares | ${gaming.missing_dlls_count || 0} DLLs Ausentes`;
    document.getElementById("kpiBiosStatus").textContent = `BIOS ${bios.smbios_version} (${bios.status_label})`;

    // Detalhes do SO
    document.getElementById("osDetailsList").innerHTML = `
        <div class="kv-row"><span class="muted">Sistema Operacional</span><strong>${os.os_name}</strong></div>
        <div class="kv-row"><span class="muted">Versão / Release</span><strong>${os.display_version}</strong></div>
        <div class="kv-row"><span class="muted">Build Completa (UBR)</span><code>${os.full_build}</code></div>
        <div class="kv-row"><span class="muted">Edição / Arquitetura</span><span>${os.edition} (${os.architecture})</span></div>
        <div class="kv-row"><span class="muted">Data de Instalação</span><span>${os.install_date}</span></div>
        <div class="kv-row"><span class="muted">Último Boot / Uptime</span><span>${os.last_boot} (${os.uptime_hours} h)</span></div>
    `;

    // Segurança
    const sec = os.security || {};
    document.getElementById("securityDetailsList").innerHTML = `
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
    document.getElementById("diskTableBody").innerHTML = diskRows + volRows;

    // Aba Drivers & BIOS
    document.getElementById("btnVendorSupport").href = bios.vendor_support_url || "https://www.catalog.update.microsoft.com/";
    document.getElementById("biosSummaryBox").innerHTML = `
        <div class="kpi-card"><span class="kpi-label">FABRICANTE BIOS</span><strong>${bios.manufacturer}</strong></div>
        <div class="kpi-card"><span class="kpi-label">VERSÃO SMBIOS</span><strong>${bios.smbios_version}</strong></div>
        <div class="kpi-card"><span class="kpi-label">DATA DA BIOS</span><strong>${bios.release_date} (${bios.age_months} meses)</strong></div>
        <div class="kpi-card"><span class="kpi-label">DIAGNÓSTICO BIOS</span><strong>${bios.status_label}</strong></div>
    `;
    renderDriversTable(drv.drivers || []);

    // Aba Softwares, Debloat & Uninstaller
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

    // Aba Rede & Internet
    renderNetworkTab(net);

    // Aba Games & DLLs
    renderGamingTab(gaming);

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

function renderGamingTab(gaming) {
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

// Ações Winget (Instalar, Atualizar, Desinstalar)
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

// Remoção de Bloatware
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

// Windows Update Drivers (Exibição em Tabela Organizada!)
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

// Ações de Rede & Internet
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

// Ações de Games & DLLs
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

/*
================================================================================
PROJETO: AegisPulse IT Toolkit — Frontend Controller
ARQUIVO: frontend/app.js
AUTOR:   Adriano Barboza (adriano9200@gmail.com | WhatsApp: +55 61 98515-8434)
VERSÃO:  3.0.0 (Enterprise Commercial, CRM SQLite, Temperaturas & Compatibilidade)
================================================================================
*/

let OPERATOR_TOKEN = localStorage.getItem("aegispulse_token") || "";
let CURRENT_SNAPSHOT = null;

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

// Funções CRM SQLite & Preços Justos (Aba 11 ADM)
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
    showToast("🔍 Executando varredura completa v3.0 (Hardware, Temperaturas CPU/GPU, Compatibilidade, BIOS, Drivers, Softwares, Rede, PC Gamer & DLLs)...");
    try {
        const data = await apiFetch("/api/scan/full");
        CURRENT_SNAPSHOT = data;
        renderDashboard(data);
        showToast("✅ Diagnóstico v3.0 concluído com sucesso!");
    } catch (err) {
        console.warn("Sessão aguardando autenticação ou limite Trial atingido:", err);
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

    document.getElementById("kpiAlerts").textContent = `${sw.outdated_count || 0} Apps Obsoletos | ${sw.bloatware_count || 0} Bloatwares | ${gaming.missing_dlls_count || 0} DLLs Ausentes`;
    document.getElementById("kpiBiosStatus").textContent = `BIOS ${bios.smbios_version} (${bios.status_label})`;

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
        <div class="kv-row"><span class="muted">Antivírus & Tempo Real</span><span class="badge ${sec.antivirus_enabled ? 'ok' : 'err'}">${sec.antivirus_enabled ? 'Ativo & Protegido' : 'Desativado'}</span></div>
        <div class="kv-row"><span class="muted">Chip TPM 2.0</span><span class="badge ${sec.tpm_present ? 'ok' : 'warn'}">${sec.tpm_present ? 'Presente / Pronto' : 'Não Detectado'}</span></div>
        <div class="kv-row"><span class="muted">Domínio / Grupo de Trabalho</span><span>${hw.domain_workgroup}</span></div>
    `;

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

    // Aba Compatibilidade & Setup (Nova!)
    renderCompatibilityTab(compat);

    // Aba Drivers & BIOS
    document.getElementById("btnVendorSupport").href = bios.vendor_support_url || "https://www.catalog.update.microsoft.com/";
    document.getElementById("biosSummaryBox").innerHTML = `
        <div class="kpi-card"><span class="kpi-label">FABRICANTE BIOS</span><strong>${bios.manufacturer}</strong></div>
        <div class="kpi-card"><span class="kpi-label">VERSÃO SMBIOS</span><strong>${bios.smbios_version}</strong></div>
        <div class="kpi-card"><span class="kpi-label">DATA DA BIOS</span><strong>${bios.release_date} (${bios.age_months} meses)</strong></div>
        <div class="kpi-card"><span class="kpi-label">DIAGNÓSTICO BIOS</span><strong>${bios.status_label}</strong></div>
    `;
    renderDriversTable(drv.drivers || []);

    // Aba Softwares & Debloat
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
    showToast("📄 Gerando Laudo Técnico Executivo HTML/PDF v3.0...");
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

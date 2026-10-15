# 🛡️ AegisPulse IT Toolkit — Edição Comercial v3.0.0
### Diagnóstico • Automação • Inteligência
> **Tecnologia sob controle. Suporte com inteligência.**  
> *Desenvolvido por **Adriano Barboza** • WhatsApp Comercial: **[+55 61 98515-8434](https://wa.me/5561985158434?text=Ol%C3%A1%20Adriano%20Barboza!%20Vi%20o%20AegisPulse%20IT%20Toolkit%20no%20GitHub%20e%20quero%20adquirir%20uma%20Assinatura%20PRO!)** • E-mail: `adriano9200@gmail.com`*

## 📲 Experimente Grátis (Modo Trial) ou Adquira sua Assinatura PRO

O **AegisPulse IT Toolkit v3.0.0** é uma plataforma proprietária de diagnóstico avançado de hardware, telemetria térmica (CPU/GPU), engenharia de PC Gamer, matriz de compatibilidade de setup, automação de manutenção (Winget/Debloat/Rede/DLLs), CRM técnico em SQLite e consultoria assistida por **Inteligência Artificial Multi-Motor (IA Local N3, Google Gemini 3.x e xAI Grok)**.

* **⏳ Modo Trial Gratuito (Demonstração):** Permite realizar até **4 análises completas gratuitas** por equipamento utilizando o motor **🧠 IA Local AegisPulse N3** embarcado.
* **⭐ Assinatura PRO (Para Técnicos, Assistências e Usuários Avançados):** Libera diagnósticos e laudos PDF **ilimitados**, além de desbloquear os motores de IA em nuvem (**✨ Google Gemini 3.x** e **🚀 xAI Grok / Groq Cloud**).
* **👉 Como Adquirir sua Chave de Ativação (`AEGIS-PRO-...`):**
  * **WhatsApp Direto:** **[+55 61 98515-8434](https://wa.me/5561985158434?text=Ol%C3%A1%20Adriano%20Barboza!%20Quero%20adquirir%20uma%20Chave%20de%20Assinatura%20PRO%20do%20AegisPulse%20IT%20Toolkit!)** (Adriano Barboza)
  * **E-mail:** `adriano9200@gmail.com`

## 🚀 Funcionalidades da Versão 3.0.0 (12 Módulos Integrados)

| Módulo / Aba | Recursos Técnicos Implementados |
| :--- | :--- |
| **1. 📊 Visão Geral & Temperaturas** | Identifica qualquer marca e modelo de computador (Service Tag/Serial), edição e Build/UBR do Windows, Uptime real, status do Defender/TPM 2.0 e **Temperatura Atual de CPU e GPU em `°C`**. |
| **2. 🖥️ Hardware & Discos (SMART)** | Inspeciona Placa-Mãe, CPU, GPUs (Dedicada Offboard vs Integrada iGPU com leitura de VRAM 64-bit real via Registro), pentes de RAM por slot (com decodificador hexadecimal JEDEC para Samsung, ADATA, Kingston, SK Hynix, Corsair) e saúde SMART de SSDs/HDDs. |
| **3. 🧩 Compatibilidade & Setup** | Analisa todo o setup atual e informa: Socket da CPU e processadores compatíveis para upgrade, geração/frequência da RAM para expansão, suporte M.2 NVMe/SATA, upgrades de GPU sem gargalo, **Fonte Recomendada (PSU em Watts)** e conformidade Windows 11. |
| **4. ⚙️ Drivers & BIOS** | Audita versão e idade da BIOS/UEFI, filtra drivers nativos da Microsoft (`2006`) de drivers antigos reais e busca/instala atualizações de drivers oficiais via API COM do Windows Update. |
| **5. 📦 Softwares, Uninstaller & Debloat** | Detecta programas obsoletos (`winget upgrade`), traz catálogo pós-formatação 1-clique, **Desinstalador Universal** para qualquer programa e **Removedor Seguro de Bloatware UWP**. |
| **6. 🌐 Rede & Internet** | Inventaria placas de rede ativas, mede latência (Ping), executa Speedtest HTTP via Cloudflare CDN, troca DNS em 1 clique (*Cloudflare 1.1.1.1, Google 8.8.8.8, Cloudflare Security*) e recupera senhas de Wi-Fi salvas no Windows. |
| **7. 🎮 PC Gamer & DLLs** | Classifica o **Tier Gamer** da máquina (*Tier S 1440p/4K*, *Tier A 1080p Ultra*, *Tier B Competitivo*, *Tier C Casual*), monitora temperaturas de CPU/GPU para jogos, verifica **Dual-Channel**, aponta gargalos, audita DLLs 32/64-bit (`System32`/`SysWOW64`), limpa Cache de Shaders e ativa energia *Ultimate Performance*. |
| **8. 🧰 Manutenção & Reparo** | Cria Ponto de Restauração do Sistema, limpa arquivos temporários órfãos com cálculo de MB liberados, verifica integridade da imagem do Windows (`DISM`) e repara a pilha de rede (`Winsock`/`TCP-IP`). |
| **9. ✨ IA Local, Gemini & Grok** | Oferece **🧠 IA Local N3** (gratuita para Trial e PRO) e motores em nuvem **✨ Google Gemini 3.x** e **🚀 xAI Grok / Groq** (exclusivos para Assinantes PRO e ADM), gerando Diagnóstico N3 e Parecer para o Cliente. |
| **10. 📄 Relatórios & Logs HTML/PDF** | Exporta Laudos Técnicos Executivos prontos para impressão em PDF com nitidez total, barras de disco coloridas, seção PC Gamer e Matriz de Compatibilidade. |
| **11. 💰 ADM: CRM SQLite & Preços Justos** | *(Exclusivo ADM)* Banco de dados **SQLite** local (`data/aegispulse_admin.db`) para cadastrar clientes com Nome, Telefone e WhatsApp, **Tabela de Preços Médios Justos de Mercado (Sem Abuso)** e **Gerador de Orçamento/Relatório Exclusivo para Enviar ao Cliente**. |
| **12. 👑 ADM: Licenças & Keygen** | *(Exclusivo ADM)* Gerador criptográfico (**Keygen HMAC-SHA256**) para emitir chaves `AEGIS-PRO-...` (Mensal, Trimestral, Semestral, Anual e Vitalícia) e controle do contador Trial. |

## 📂 Arquitetura de Diretórios do Projeto

```text
AegisPulse-Toolkit/
├── main.py                        # Inicializador do Servidor Local + Janela App Mode
├── Iniciar_AegisPulse.bat         # Atalho 1-clique com elevação automática para Administrador
├── Publicar_No_GitHub.bat         # Publicador automatizado para o GitHub
├── build_exe.bat                  # Compilador para executável portátil (.exe) via PyInstaller
├── config.example.json            # Modelo de configuração local
├── requirements.txt               # Dependências opcionais para build .exe
├── .gitignore                     # Protege config.json, banco SQLite de clientes e laudos privados
├── LICENSE                        # Licença de Software Proprietário — Adriano Barboza
├── README.md                      # Documentação principal e vitrine comercial no GitHub
├── MANUAL_DE_INSTRUCOES.md        # Manual completo de uso (Trial, Assinante PRO e ADM Master)
├── backend/
│   ├── auth.py                    # Licenciamento 3 Níveis (Trial 4x, Assinante PRO e ADM) + Keygen HMAC
│   ├── server.py                  # Servidor REST API v3.0
│   ├── collectors/
│   │   ├── hardware.py            # Hardware, Marca/Modelo, JEDEC RAM, VRAM 64-bit e Temperaturas °C
│   │   ├── os_info.py             # Sistema Operacional, Build/UBR, Uptime, Defender e TPM 2.0
│   │   ├── drivers_bios.py        # BIOS/UEFI, Drivers e integração Windows Update
│   │   └── software.py            # Inventário, Winget, Desinstalador Universal e Debloat UWP
│   └── services/
│       ├── compatibility.py       # Matriz de Compatibilidade de Hardware & Upgrades do Setup
│       ├── gaming_dll.py          # Engenharia PC Gamer, Gargalos, Runtimes e Auditoria de DLLs
│       ├── network_tools.py       # Diagnóstico de Rede, Ping, Speedtest, DNS 1-Clique e Senhas Wi-Fi
│       ├── maintenance.py         # Rotinas seguras de limpeza Temp, Rede, DISM e Ponto de Restauração
│       ├── gemini_ai.py           # Motor Multi-IA: IA Local N3 (Trial/PRO) + Gemini 3.x & Grok (PRO)
│       ├── admin_crm.py           # Banco SQLite de Clientes, Tabela de Preços Justos e Proposta Cliente
│       └── html_reporter.py       # Gerador de Laudos Executivos em HTML5 / PDF de alta nitidez
├── frontend/
│   ├── index.html                 # Interface Gráfica SPA (12 Abas + Modal Comercial)
│   ├── styles.css                 # Design System Dark Tech responsivo
│   └── app.js                     # Controlador Frontend v3.0
├── data/                          # Banco SQLite local (aegispulse_admin.db — ignorado no Git)
├── reports/                       # Laudos e Propostas em HTML/PDF gerados localmente
└── logs/                          # Histórico de auditoria das sessões
```

## 🔒 Aviso de Propriedade Intelectual e Restrição de Uso (Software Proprietário)

**Copyright © 2026 Adriano Barboza (`adriano9200@gmail.com` | WhatsApp: `+55 61 98515-8434`). Todos os direitos reservados.**

Este repositório é mantido público no GitHub **exclusivamente para fins de portfólio de engenharia de software e auditoria técnica de código**.  
Nos termos da Lei de Software (Lei nº 9.609/98) e da Lei de Direitos Autorais (Lei nº 9.610/98), **NÃO É PERMITIDO** a terceiros sem licença formal emitida pelo autor:
1. Utilizar comercialmente este software após o limite demonstrativo do Modo Trial sem adquirir uma Chave de Assinatura válida;
2. Copiar, clonar para distribuição, modificar, remover travas de licenciamento (`backend/auth.py`) ou comercializar versões derivadas;
3. Suprimir a identificação de autoria de **Adriano Barboza** em qualquer tela, código ou relatório gerado.

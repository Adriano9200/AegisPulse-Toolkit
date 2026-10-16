# 🛡️ AegisPulse IT Toolkit — v5.0.0 (Storage Forensics, SMART, Lifespan, Recovery, CRM & Multi-IA)

> **Diagnóstico • Automação • Inteligência**  
> *Tecnologia sob controle. Suporte com inteligência.*  
> **Desenvolvido por Adriano Barboza** (`adriano9200@gmail.com` | **WhatsApp Comercial: `+55 61 98515-8434`**)

[![Versão](https://img.shields.io/badge/Vers%C3%A3o-5.0.0_Enterprise-0284c7?style=for-the-badge)](https://github.com/Adriano9200/AegisPulse-Toolkit)
[![Plataforma](https://img.shields.io/badge/Windows-10_%7C_11_(64--bit)-0078D6?style=for-the-badge&logo=windows)](https://github.com/Adriano9200/AegisPulse-Toolkit)
[![Storage Forensics](https://img.shields.io/badge/Storage-SMART_%7C_NVMe_%7C_Recovery-f59e0b?style=for-the-badge)](https://github.com/Adriano9200/AegisPulse-Toolkit)
[![Licença](https://img.shields.io/badge/Licen%C3%A7a-Propriet%C3%A1ria_(Source--Available)-dc2626?style=for-the-badge)](./LICENSE)
[![WhatsApp](https://img.shields.io/badge/WhatsApp-+55_61_98515--8434-10b981?style=for-the-badge&logo=whatsapp)](https://wa.me/5561985158434)

---

## 🔒 Aviso de Propriedade Intelectual e Licenciamento Comercial

Este repositório no GitHub é disponibilizado na modalidade **Source-Available (Código Visível apenas para Portfólio e Auditoria Técnica)**.  
**Todos os direitos autorais e comerciais pertencem exclusivamente a Adriano Barboza.** Não é permitido utilizar comercialmente, redistribuir ou remover as travas de licenciamento sem adquirir uma **Chave de Assinatura Oficial (`AEGIS-PRO-...`)**.

👉 **Para adquirir sua Licença de Assinatura PRO ou contratar suporte especializado:**
- 📱 **WhatsApp Oficial:** [**+55 61 98515-8434** (Clique para conversar com Adriano Barboza)](https://wa.me/5561985158434?text=Ol%C3%A1%20Adriano%20Barboza!%20Vi%20o%20AegisPulse%20IT%20Toolkit%20no%20GitHub%20e%20quero%20adquirir%20uma%20Assinatura%20PRO!)
- 📧 **E-mail:** `adriano9200@gmail.com`

---

## 💿 Novidade v5.0.0: Estúdio Profissional de Diagnóstico, Saúde SMART, Vida Útil e Recuperação de Armazenamento

O **AegisPulse v5.0.0** incorpora uma suíte forense completa para **HDDs Mecânicos, SSDs SATA, SSDs NVMe, Pendrives USB e Unidades Externas**, estruturada em 10 módulos integrados:

1. **Inventário Avançado de Dispositivos (`backend/collectors/storage_advanced.py`):**
   - Identifica fabricante, marca real, modelo, número de série, firmware, interface, protocolo (`NVMe`, `AHCI/SATA`, `USB UASP`, `USB BOT`), tipo de mídia, rotação (`RPM`) e controlador/ponte USB (`JMicron`, `ASMedia`, `Realtek`).
   - Calcula capacidades em **Bytes exatos**, **Decimal (`GB`/`TB` — $10^9/10^{12}$)** e **Binário (`GiB`/`TiB` — $2^{30}/2^{40}$)**, distinguindo capacidade física total, espaço alocado em partições, espaço não alocado, espaço utilizado e livre.
   - Detecta limitações de adaptadores USB e controladoras RAID/VMD sem inventar métricas indisponíveis.
2. **Diagnóstico SMART Profundo (HDD, SATA SSD e NVMe):**
   - Decodifica a tabela binária ATA SMART (`362 bytes VendorSpecific` + `Thresholds`), contadores Windows `StorageReliabilityCounter`, logs de saúde NVMe (`Critical Warning`, `Available Spare`, `Percentage Used`, `Data Units Read/Written`, `Unsafe Shutdowns`, `Media Errors`) e integra com `smartctl` (`smartmontools`) quando disponível.
   - Trata corretamente atributos específicos de fabricantes (como o contador composto de 48 bits da Seagate nos atributos `01` e `07`).
3. **Estimativa de Vida Útil e Monitoramento Histórico Persistente (`data/aegispulse_storage.db`):**
   - Calcula o tempo acumulado ligado em **horas, dias e anos**.
   - Diferencia estritamente: **(a)** Vida útil reportada pelo fabricante, **(b)** Desgaste estimado por TBW de referência e **(c)** Tendência histórica entre coletas no SQLite (com gráficos SVG e alertas de degradação), sem jamais prometer datas exatas de falha.
4. **Testes Reais e Controlados de Integridade e Desempenho (`backend/services/storage_diagnostics.py`):**
   - Verificação Rápida de Saúde, Benchmark de Leitura Sequencial/Blocos (`MB/s`, latência `ms`, `IOPS`), Varredura Controlada de Superfície e disparo/consulta de Autotestes SMART (curto e estendido).
   - **Proteção Não-Destrutiva:** Nenhum teste destrutivo de escrita é executado por padrão.
5. **Diagnóstico Especializado de 12 Categorias de Falhas:**
   - Diferencia **Falhas Físicas**, **Problemas de Cabo/Conexão**, **Corrupção Lógica** e **Limitações do SO**.
   - Explica tecnicamente **Erros de Redundância Cíclica (CRC)** (deixando claro que erro CRC indica falha no cabo SATA/porta USB e não necessariamente setor defeituoso!), **Setores Realocados/Pendentes/Incorrigíveis**, **Volume RAW**, **Partições Perdidas**, **Disco Não Inicializado**, **Unidade Protegida Contra Gravação (`Read-Only`)**, **Desconexões Inesperadas (Eventos 51, 129, 153, 157)** e **Pendrives USB com Capacidade Adulterada/Falsa**.
6. **Recuperação Assistida e Preservação de Dados (`backend/services/storage_recovery.py`):**
   - **Clonagem / Criação de Imagem Setor-a-Setor (`.img`) com Mapfile e Retomada:** Isola blocos com erro de leitura preenchendo com zeros no destino e gravando os endereços defeituosos em `*.mapfile.json` e `.ddrescue.map` (compatível com **GNU `ddrescue`**), permitindo cancelar com segurança e retomar do ponto exato.
   - **Travas de Segurança:** Bloqueia `Origem == Destino`, impede sobrescrita acidental de discos do sistema e exige confirmação explícita (`CONFIRMAR_IMAGEM`).
   - **Recuperação de Partições e Arquivos:** Integração com **TestDisk** (mais inspetor nativo de assinaturas `MBR 0x55AA` / `GPT EFI PART`) e **PhotoRec** (mais extrator nativo de assinaturas para outra unidade física).
   - **Reparação Lógica Controlada (`CHKDSK` / `Repair-Volume`):** Separa Diagnóstico Passivo (`fsutil dirty query`), Verificação Somente-Leitura (`chkdsk /scan`) e Reparação Ativa — **bloqueando automaticamente o `CHKDSK /F` ou `/R` em discos com suspeita de falha física**.

---

## 🎯 Demais Funcionalidades Integradas do AegisPulse

| Módulo | Recursos Principais |
| :--- | :--- |
| **🌡️ Monitoramento Térmico CPU, GPU & Discos** | Medição em tempo real (`°C`) de Processador, Placa de Vídeo e Discos para PCs Gamer e Casuais. |
| **🧩 Matriz de Compatibilidade & Setup** | Analisa todo o setup (Placa-mãe, Socket CPU, geração/velocidade de RAM, NVMe/SATA, upgrades de GPU sem gargalo, fonte recomendada em Watts e checklist Windows 11). |
| **🎮 Análise Completa PC Gamer & DLLs** | Classifica o Tier Gamer, audita Dual-Channel, verifica 11 DLLs críticas em `System32` e `SysWOW64` e repara Visual C++ / DirectX em 1 clique. |
| **📦 Softwares, Winget & Debloat** | Atualiza programas obsoletos, remove Bloatwares nativos e instala o Kit Essencial Pós-Formatação. |
| **🌐 Rede, DNS, Speedtest & Wi-Fi** | Aplica DNS Cloudflare/Google em 1 clique, mede velocidade de download e recupera senhas de Wi-Fi salvas. |
| **✨ Multi-IA (Local N3, Gemini 3.x & Grok)** | **IA Local N3** gratuita para Trial e PRO + motores em nuvem **Google Gemini 3.x** e **xAI Grok** para Assinantes PRO e ADM. |
| **💰 CRM SQLite & Preços Justos (Exclusivo ADM)** | Banco SQLite de clientes (`Nome`, `Telefone`, `WhatsApp`), catálogo de preços médios justos (sem abuso) e gerador de Proposta Exclusiva para enviar no WhatsApp do cliente. |

---

## ⚖️ Conformidade de Licenças de Ferramentas Externas Opcionais

O **AegisPulse IT Toolkit** opera nativamente com coletores e motores próprios em Python/PowerShell. Quando instaladas separadamente pelo técnico no sistema operacional, as ferramentas externas opcionais abaixo são invocadas apenas via interface de linha de comando (CLI) independente, respeitando integralmente suas licenças originais:
- **smartmontools (`smartctl`):** GNU GPLv2+
- **GNU `ddrescue`:** GNU GPLv2+
- **TestDisk & PhotoRec (CGSecurity):** GNU GPLv2+

Nenhum código-fonte GPL dessas ferramentas é embutido ou redistribuído dentro do binário proprietário do AegisPulse.

---

## 🛠️ Como Executar e Testar

1. Dê dois cliques em **`Iniciar_AegisPulse.bat`** (ou execute `python main.py` como Administrador).
2. Para rodar a suíte de testes automatizados (7 cenários completos com mocks não-destrutivos):
   ```powershell
   python -m unittest discover -s tests -p "test_*.py" -v
   ```

---

**Desenvolvido por Adriano Barboza**  
📱 **WhatsApp:** [+55 61 98515-8434](https://wa.me/5561985158434) | 📧 **E-mail:** `adriano9200@gmail.com`  
*AegisPulse IT Toolkit v5.0.0 — Diagnóstico • Automação • Inteligência.*

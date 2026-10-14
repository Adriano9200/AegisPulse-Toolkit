# 📘 Manual Completo de Operação — AegisPulse IT Toolkit v1.0.0

**Autor:** Adriano Barboza (`adriano9200@gmail.com`)  
**Repositório Oficial:** [https://github.com/Adriano9200/AegisPulse-Toolkit](https://github.com/Adriano9200/AegisPulse-Toolkit)

Este manual detalha, tela por tela e botão por botão, o que cada módulo do **AegisPulse IT Toolkit** faz nos bastidores (no Windows via WMI/CIM, PowerShell, Registro, Winget e API Gemini) e como utilizá-lo durante o atendimento a um cliente real.

## 1. Tela Inicial: Bloqueio de Operador (`Operator Lock`)

* **O que é:** Janela modal de segurança exibida assim que o software é aberto pela primeira vez.
* **O que faz no Backend (`backend/auth.py`):** Converte o PIN digitado em um hash criptográfico **SHA-256** e compara com o valor salvo em `config.json`. Se estiver correto, gera um token único de sessão (`X-Operator-Token`).
* **Como usar:** Digite o PIN padrão **`admin123`** (ou o seu novo PIN personalizado) e clique em **Desbloquear Console**.

## 2. Barra Superior (`Topbar`) — Controles Globais

Localizada no topo de todas as abas, traz identificadores imediatos e duas ações principais:

* **Título e Subtítulo da Máquina:** Mostra na hora o **Fabricante e Modelo** do equipamento (ex: *Dell Inc. — Inspiron 15*, *ASUS — TUF Gaming*, etc.), o **Hostname** na rede e o horário exato da coleta.
* **Indicador de Rede (`🌐 Online (Gemini Pronto)` / `⚠️ Offline`):** Testa conexão ativa com servidores DNS globais (`8.8.8.8` e `1.1.1.1`) para informar se o computador do cliente tem saída para internet e se o módulo Gemini AI e o Winget podem operar.
* **Botão `🔄 Atualizar Diagnóstico`:** Refaz a varredura completa em tempo real (útil logo após você atualizar um programa, limpar arquivos temporários ou instalar um driver).
* **Botão `📄 Gerar Laudo HTML`:** Compila instantaneamente todos os dados coletados + o histórico de ações feitas na sessão + o parecer da IA em um arquivo `.html` profissional dentro da pasta `reports\` e já o abre em uma nova guia pronto para imprimir ou salvar como PDF.

## 3. Aba 1 — `📊 Visão Geral & SO`

Funciona como o painel executivo do atendimento assim que você conecta na máquina do cliente:

* **4 Cards de Indicadores Rápidos (KPIs):**
  1. **Fabricante & Modelo + Service Tag/Serial:** Permite copiar o número de série da máquina sem precisar virar o notebook de cabeça para baixo ou entrar na BIOS.
  2. **Sistema Operacional & Build:** Mostra a edição exata (ex: *Windows 11 Pro 24H2*) e a **Build + UBR** (ex: `26100.2033`), essencial para saber se o PC está recebendo patches cumulativos de segurança.
  3. **Processador & Memória RAM:** Exibe o modelo exato da CPU, o total de RAM em GB e quantos pentes físicos estão instalados.
  4. **Saúde de Drivers & Softwares:** Resume quantos aplicativos têm atualização pendente no Winget, quantos drivers têm mais de 3 anos e se a BIOS precisa de revisão.
* **Painel `Detalhes do Sistema Operacional e Build`:** Mostra a data original em que o Windows foi formatado/instalado e o **Último Boot / Uptime** (muito útil quando o cliente diz que "já reiniciou", mas o Fast Startup manteve o PC ligado há 15 dias).
* **Painel `Segurança, Defender & Firmware`:** Verifica se o Windows Defender está ativo, se a proteção em tempo real está ligada, quantos dias têm as assinaturas de vírus e se o chip **TPM 2.0** está presente e pronto.

## 4. Aba 2 — `🖥️ Hardware & Discos`

Feita para diagnóstico físico de componentes e avaliação de upgrades sem precisar abrir o gabinete:

* **Painel `Placa-Mãe, Processador e Placa de Vídeo (GPU)`:** Consulta `Win32_BaseBoard` e `Win32_VideoController` para mostrar fabricante e modelo exato da placa-mãe, serial da placa-mãe, CPU e versão do driver de vídeo atual.
* **Tabela `Módulos de Memória RAM Instalados`:** Lista cada pente individualmente por slot (`DIMM A1`, `DIMM B1`, etc.), fabricante (Kingston, Corsair, Crucial, Samsung), *Part Number*, capacidade em GB e velocidade em MHz (`3200 MHz`, `4800 MHz`). Ajuda você a responder na hora ao cliente se há slot livre ou qual frequência comprar para upgrade.
* **Tabela `Unidades Físicas (SMART) e Partições Lógicas`:**
  * Nas linhas de **Disco Físico (`🖴`)**, consulta `Get-PhysicalDisk` e `Win32_DiskDrive` para informar se é **SSD NVMe, SSD SATA ou HDD**, a capacidade real e o status **SMART (`Healthy` / `OK` / `Warning`)**.
  * Nas linhas de **Partição (`📁`)**, mostra a letra da unidade (`C:`, `D:`), sistema de arquivos (`NTFS`), espaço livre em GB e porcentagem ocupada (ficando vermelha acima de 85%).

## 5. Aba 3 — `⚙️ Drivers & BIOS`

Focada em estabilidade de hardware, correção de telas azuis e atualização segura de controladores:

* **Cards de Diagnóstico da BIOS / UEFI:** Exibe fabricante da BIOS, versão SMBIOS e a data de lançamento convertida com cálculo automático da idade em meses. Se a BIOS tiver mais de 24 meses, exibe um alerta amarelo (`Verificar Atualização (> 2 anos)`).
* **Botão `🌐 Página Oficial do Fabricante (BIOS/Drivers)`:** Detecta a marca do computador (Dell, Lenovo, HP, Asus, Acer, MSI, Gigabyte, Samsung) e abre direto o portal oficial de suporte daquela marca (ou o Microsoft Update Catalog em PCs montados).
* **Botão `🔍 Buscar Drivers no Windows Update`:** Conecta na API COM oficial `Microsoft.Update.Session` do Windows e pesquisa exclusivamente atualizações pendentes da categoria `Driver` que ainda não foram instaladas.
* **Botão `⚡ Instalar Drivers via Windows Update`:** Baixa e instala automaticamente os drivers oficiais encontrados pelo Windows Update, registrando tudo no log da sessão.
* **Tabela `Inventário de Drivers Instalados` + Busca em Tempo Real:** Lista os drivers assinados do sistema com nome do dispositivo, classe (`DISPLAY`, `NET`, `MEDIA`, `USB`, etc.), fabricante, versão e data, destacando em amarelo drivers críticos com mais de 36 meses. Use a caixa de busca para filtrar rapidamente por `video`, `realtek`, `intel`, `nvidia` ou `bluetooth`.

## 6. Aba 4 — `📦 Softwares & Winget`

Automatiza uma das tarefas que mais tomam tempo no suporte técnico: atualizar programas vulneráveis e instalar o pacote básico pós-formatação:

* **Painel `Softwares Obsoletos Detectados (Integração Winget)`:** Executa `winget upgrade` nos bastidores e monta uma tabela comparando a **Versão Atual** instalada no cliente com a **Versão Nova** disponível.
  * Clique em **`Atualizar`** ao lado de um programa para atualizar somente ele em modo silencioso (`--silent`).
  * Clique em **`🚀 Atualizar Todos os Obsoletos`** no topo para atualizar todos os programas da lista de uma só vez.
* **Painel `Instalador Rápido — Kit Essencial Pós-Formatação (1-Clique)`:** Traz 12 ferramentas essenciais divididas por categoria (*Google Chrome, Firefox, 7-Zip, VLC, Adobe Reader, LibreOffice, AnyDesk, RustDesk, CPU-Z, HWMonitor, CrystalDiskInfo e Malwarebytes*). Basta clicar em **`⬇️ Instalar (Winget)`** para baixar e instalar silenciosamente direto do repositório oficial.
* **Tabela `Inventário Completo de Softwares Instalados`:** Lê as chaves `Uninstall` 32-bit, 64-bit e do usuário no Registro do Windows, listando todos os programas instalados com busca instantânea.

## 7. Aba 5 — `🧰 Manutenção & Reparo`

Reúne procedimentos técnicos padronizados e seguros com classificação de risco e saída detalhada no terminal inferior:

* **`Criar Ponto de Restauração` (Baixo Risco):** Executa `Checkpoint-Computer` criando o ponto `AegisPulse_PreManutencao` antes de você mexer em drivers ou configurações.
* **`Limpeza Segura de Temporários` (Baixo Risco):** Limpa arquivos órfãos em `%TEMP%` e `C:\Windows\Temp` ignorando arquivos em uso e calcula exatamente quantos arquivos foram removidos e quantos MB foram liberados, sem tocar na pasta *Downloads* nem em dados do navegador do cliente.
* **`Verificar Integridade (DISM)` (Baixo Risco):** Executa `DISM.exe /Online /Cleanup-Image /CheckHealth` para verificar rapidamente se a imagem do Windows possui corrupção.
* **`Reparo Completo de Rede e DNS` (Risco Moderado):** Executa em sequência `ipconfig /flushdns`, `netsh winsock reset` e `netsh int ip reset`, exibindo o retorno completo no terminal da tela.

## 8. Aba 6 — `✨ IA Gemini & Config`

Conecta seu Toolkit ao modelo **Google Gemini (`gemini-2.5-flash`)** quando há internet disponível:

* **Como configurar sua chave (1 única vez):** No card da direita (`Configurações do Operador & Segurança`), cole sua **Google Gemini API Key** (obtida gratuitamente no Google AI Studio), opcionalmente escolha seu novo **PIN de Operador** e clique em **`💾 Salvar Configurações Locais`**.
* **Como usar a análise inteligente:** No card da esquerda, clique em **`✨ Analisar Computador com Gemini AI`**. O AegisPulse remove números de série privados por segurança, envia o retrato técnico da máquina para o Gemini e devolve:
  1. **Diagnóstico Técnico N3 (para você):** Gargalos, alertas de armazenamento/RAM, drivers antigos e prioridades de manutenção.
  2. **Parecer para o Cliente:** Um texto claro, educado e sem jargões técnicos pronto para você copiar e mandar no WhatsApp do cliente ou anexar automaticamente no Laudo HTML.
* **Perguntas personalizadas:** Você também pode digitar qualquer pergunta na caixa de texto (ex: *"Este computador roda Counter-Strike 2 ou AutoCAD 2026 com essa configuração?"*) e clicar no botão para receber uma resposta baseada no hardware real daquela máquina.

## 9. Aba 7 — `📄 Relatórios & Logs HTML`

Registra a trilha de auditoria do seu atendimento e gera o entregável final para o cliente:

* **Tabela de Logs da Sessão:** Mostra em ordem cronológica tudo o que foi feito desde que você abriu o AegisPulse (varreduras, limpezas, atualizações via Winget, consultas à IA).
* **Botão `📄 Gerar e Abrir Relatório HTML Agora`:** Gera um arquivo HTML5 moderno na pasta `reports\` (e uma cópia de auditoria em `logs\`) com cabeçalho assinado por **Adriano Barboza**, tabelas visuais, barras de ocupação de disco e botão **`Imprimir / Salvar PDF`**.

# 📘 Manual de Instruções Oficial — AegisPulse IT Toolkit v5.1.0

**Identidade Oficial:**
> **AegisPulse IT Toolkit**  
> *Diagnóstico • Automação • Inteligência*  
> *Tecnologia sob controle. Suporte com inteligência.*  
> **Autor e Proprietário:** Adriano Barboza (`adriano9200@gmail.com` | **WhatsApp:** `+55 61 98515-8434`)

---

## 1. Visão Geral dos 3 Perfis de Acesso

1. **⏳ Modo Trial Gratuito (4 Análises + IA Local N3):**
   - Permite realizar até **4 varreduras completas** gratuitamente, incluindo o novo módulo **💿 Discos, SMART & Recuperação** e a **🧠 IA Local AegisPulse N3**.
   - Ao tentar usar **Google Gemini** ou **xAI Grok** (ou na 5ª análise), convida o usuário de forma intuitiva a assinar pelo seu WhatsApp **`+55 61 98515-8434`**.
2. **⭐ Modo Assinante PRO (`AEGIS-PRO-...`):**
   - Desbloqueado com chave gerada por você no Keygen ADM. Libera varreduras ilimitadas e os motores **Google Gemini 3.x** e **xAI Grok / Groq**, mantendo ocultas suas abas particulares de Administrador.
3. **👑 Modo Administrador Master (Exclusivo Adriano Barboza):**
   - **Sua Senha Master:** `Luna@19102023` (validada por hash SHA-256 `1fd12a251366b5ab823d6bc19c780f5dd04ae40b76e1bd07a91a679f2670e196`, nunca exposta em texto puro no GitHub).
   - Desbloqueia as abas **💰 ADM: Clientes & Preços (CRM SQLite)** e **👑 ADM: Licenças & Keygen**.

---

## 2. Como Usar o Novo Módulo: 💿 Discos, SMART & Recuperação (v5.1.0)

Acesse a segunda aba do menu lateral (**💿 Discos, SMART & Recuperação**) para utilizar as 10 seções profissionais:

### 2.1. Inventário Avançado e Detalhes do Dispositivo
- Clique em qualquer disco na tabela superior (ou selecione no menu suspenso) para inspecionar **HDDs, SSDs SATA, SSDs NVMe, Pendrives USB e Discos Externos**.
- O sistema exibe a capacidade exata em **Bytes**, **Decimal (`GB`/`TB` nominal de fábrica)** e **Binário (`GiB`/`TiB` real do Windows)**, além de identificar pontes USB (`JMicron`, `ASMedia`, `Realtek`) e informar quando um adaptador USB bloqueia comandos SMART.

### 2.2. Saúde SMART Profunda, Vida Útil (TBW / POH) e Histórico SQLite
- **Saúde SMART:** Exibe atributos brutos (`Hex` e `Int`), normalizados (`Atual`, `Pior`, `Limiar`), gravidade e significado técnico, decodificando inclusive contadores compostos de 48 bits da Seagate e registradores NVMe (`Critical Warning`, `Available Spare`, `Percentage Used`, `Data Units Read/Written`).
- **Vida Útil e Desgaste:** Mostra as horas acumuladas em funcionamento e o **equivalente em dias e anos**, diferenciando:
  1. *Vida útil reportada pelo fabricante (SMART/Firmware)*,
  2. *Desgaste estimado por TBW de referência*,
  3. *Tendência histórica entre coletas salvas no banco `data/aegispulse_storage.db`*.

### 2.3. Testes Reais de Integridade e Desempenho
- **⚡ Verificação Rápida:** Inspeciona SMART, partições e latência inicial em segundos.
- **🚀 Benchmark de Leitura (Sequencial/Blocos):** Mede velocidade (`MB/s`), latência média/máxima (`ms`) e `IOPS`, destacando blocos lentos (`>150ms`) sem realizar nenhuma escrita.
- **🔍 Varredura de Superfície:** Examina blocos distribuídos em modo somente-leitura, registrando bytes examinados, áreas não testadas e erros de I/O.
- **⚠️ Teste de Escrita:** Bloqueado por padrão! Só executa em arquivo temporário se você digitar explicitamente `CONFIRMAR_ESCRITA_RISCO_DADOS` e se o disco não tiver falha física.

### 2.4. Diagnóstico Especializado de Falhas (CRC vs Setor Defeituoso, RAW e USB)
- **Erro de Redundância Cíclica (CRC — Atributo 199):** O AegisPulse explica claramente que erros CRC ocorrem na comunicação pelo cabo SATA ou porta/ponte USB — **não significam automaticamente setor defeituoso na mídia**.
- **Volume RAW / Partições Perdidas / Disco Não Inicializado:** Orienta a bloquear qualquer formatação ou inicialização do Windows antes de extrair imagem/dados.
- **Pendrives e Unidades Externas USB:** Detecta proteção contra gravação (`Read-Only` lógico vs trava de hardware NAND esgotada), desconexões no Log de Eventos (`IDs 51, 129, 153, 157`) e alerta sobre pendrives genéricos com firmware adulterado (capacidade falsa).

### 2.5. Fluxo Seguro de Recuperação Assistida
1. **Avaliação de Risco (`BAIXO`, `MODERADO`, `ALTO`, `CRÍTICO`):**
   - Sempre que houver setores pendentes/realocados ou risco alto/crítico, o sistema exige **criar uma imagem `.img` antes de tentar reparar** e **bloqueia automaticamente o `CHKDSK /F` ou `/R`**, evitando que o Windows destrua dados recuperáveis tentando realocar a tabela `$MFT` em um disco morrendo.
   - Quando há sinais severos de colapso físico (0 Bytes / No Media / erros incorrigíveis crescentes em dados críticos), recomenda encaminhamento para **Laboratório Especializado (Cleanroom / PC-3000)**.
2. **Clonagem / Imagem Setor-a-Setor Resiliente (`.img` + Mapfile):**
   - Informe o caminho do arquivo `.img` em **outra unidade física** (o sistema bloqueia `Origem == Destino`) e digite `CONFIRMAR_IMAGEM`.
   - O gerador isola blocos com erro de leitura preenchendo zeros no destino e salvando o mapa em `*.mapfile.json` e `.ddrescue.map` (compatível com **GNU `ddrescue`**), permitindo cancelar e retomar exatamente de onde parou.
3. **Recuperação de Partições (`TestDisk`) e Arquivos (`PhotoRec` / Scanner de Assinaturas):**
   - Inspeciona cabeçalhos `MBR (0x55AA)` e `GPT (EFI PART)` e recupera arquivos exigindo que a pasta de destino fique em **outra unidade**, documentando as limitações de *File Carving* (como perda dos nomes e pastas originais quando a `$MFT` foi destruída).

---

## 5. Como Operar o AegisPulse Health Score (v5.1.0)

Acesse a nova aba **🩺 Health Score** no menu lateral para visualizar o diagnóstico de saúde geral:
1. **Pontuação Geral & Cobertura:** Exibe a nota (0–100), faixa de cor, selo de cobertura (ex: `8 de 8 categorias disponíveis`) e o identificador não-volátil do equipamento (`AEGIS-DEV-...`).
2. **Desempenho por Categoria:** Analise individualmente as 8 categorias ponderadas com seus pesos efetivos, barras de progresso e métricas observadas.
3. **Diagnóstico Acionável Priorizado:** Problemas técnicos listados por ordem de gravidade (Crítico > Alto > Médio > Baixo) com evidência técnica, grau de confiança, impacto provável, recomendação e nível de risco da ação.
4. **Comparação Temporal (Diff):** Clique em **📊 Comparar com Avaliação Anterior** para visualizar a variação exata da nota ($\Delta$), se houve melhora real ou degradação e a lista de problemas novos e resolvidos.
5. **Trilha de Auditoria:** Clique em **🔍 Ver Trilha de Deduções** para auditar exatamente quantos pontos foram deduzidos e por quais motivos técnicos.

---

## 3. Como Executar os Testes Automatizados

Para validar todos os cenários do módulo de armazenamento (discos saudáveis, RAW, erros SMART, CRC, desconexões USB, travas de segurança e retomada de imagem):

```powershell
cd "D:\PROJETOS_PESSOAL\AegisPulse-Toolkit"
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## 4. Como Atualizar sua Pasta Local e Subir a v5.1.0 para o GitHub

Abra o **PowerShell** e execute:

```powershell
robocopy "G:\Meu Drive\AegisPulse-Toolkit" "D:\PROJETOS_PESSOAL\AegisPulse-Toolkit" /E /XD .git __pycache__ data reports logs /XF *.gdoc *.gsheet *.old *.v1_1_old *.v2.old *.v3_0_0.old config.json license.json
cd "D:\PROJETOS_PESSOAL\AegisPulse-Toolkit"
python -m unittest discover -s tests -p "test_*.py" -v
git add .
git status
git commit -m "feat(storage): lancamento AegisPulse v5.1.0 com modulo forense de discos, SMART profundo, vida util SQLite, testes de integridade e recuperacao assistida por Adriano Barboza"
git push
```


## 🛡️ Novidades da Versão 5.1.0 — Validação Centralizada de Destino (10 Camadas), Proteção Cruzada de Boot (EFI/Windows) & Diagnóstico do `diskmgmt.msc`

- **Validação Centralizada Obrigatória (`validate_destructive_storage_target` — 10 Camadas)**:
  1. Distinção estrita entre **Disco Físico (`\\.\PhysicalDriveN`)**, **Partição (`Partition #`)**, **Volume (`Volume GUID`)**, **Letra de Unidade (`C:`, `D:`, `E:`)**, **Volume do Windows (`WINDOWS_OS`)** e **Partição de Inicialização (`EFI_BOOT`)**.
  2. **Proteção Cruzada de Boot (Multi-Disco)**: Se o volume do Windows (`C:`) estiver em um disco (ex: `Disk #2`) e a partição de inicialização EFI estiver em outro disco (ex: `Disk #0`), **ambos os discos** são bloqueados contra formatação, `diskpart clean` ou alterações destrutivas.
  3. **Identidade Física Imutável (`hardware_identity_hash` + `device_uid`)**: Não depende exclusivamente do número volátil `Disk #N`, protegendo contra renumeração de discos entre reinicializações ou reconexões USB.
  4. **Bloqueio de Conflito de Letra (ex: `P:` já ocupada)**: Verifica todas as letras montadas no sistema antes de atribuir uma letra e impede atribuição de letra diretamente a discos sem partição ou em estado `RAW`.
  5. **Confirmação Vinculada ao Destino & Revalidação Live Pré-Execução**: Impede reutilizar a confirmação de um disco em outro e revalida imediatamente antes do comando se o disco não foi removido ou trocado.
- **Diagnóstico Não-Destrutivo do `diskmgmt.msc` / Virtual Disk Service (`diagnose_diskmgmt_and_vds_health`)**:
  - Mede o tempo de resposta do kernel WMI (`Win32_DiskDrive`) vs Virtual Disk Service (`Get-Disk` / `Get-Volume`), identifica contenção de I/O causada por unidades USB externas com setores pendentes (`SMART ID 197`) ou autotestes SMART estendidos em andamento, e comprova com evidências quando o SSD NVMe principal está íntegro.
- **Suíte de Testes Automatizados Ampliada (26 Cenários)**:
  - 16 cenários de armazenamento, trava de boot, renumeração, conflito de letra `P:`, timeout VDS e inicializador (`tests/test_storage_module.py`) + 10 cenários determinísticos do Health Score (`tests/test_health_score.py`).


---

## 💥 Guia Operacional v5.5 — Crash Investigator & Laudos HTML/PDF

### 1. Como Gerar e Baixar Laudos HTML e PDF
1. No topo da interface (ou nas abas **Crash Investigator** e **Relatórios & Logs HTML**), clique em **📄 Gerar Laudo HTML / PDF**.
2. O sistema valida os dados coletados, gera o arquivo `.html` e o arquivo `.pdf` na pasta `reports/` e exibe os botões:
   - **🌐 Abrir Laudo HTML** e **📑 Abrir Laudo PDF** (visualização imediata).
   - **⬇️ Baixar HTML** e **⬇️ Baixar PDF** (download direto com `Content-Disposition: attachment`).
3. Caso a IA em nuvem (Gemini/Grok) não tenha sido acionada ou esteja offline, o laudo é gerado normalmente utilizando o **Parecer Técnico Determinístico Local N3**, sinalizando a origem local.

### 2. Como Utilizar o AegisPulse Crash Investigator
1. Acesse a aba lateral **💥 Crash Investigator (BSOD & Logs)**.
2. Selecione os filtros desejados:
   - **Período Analisado:** 24h, 3 dias, 7 dias (padrão), 15 dias, 30 dias ou 60 dias.
   - **Categoria Técnica:** Todas, BSOD/BugCheck, Kernel-Power, Disco/NTFS/I/O, Hardware/WHEA, Drivers/TDR, Apps/Serviços ou Updates.
   - **Severidade, Origem e Event ID:** Filtre ocorrências específicas (ex.: Event ID `41`, `129`, `153`, `1001`, `4101`).
3. Clique em **🔍 Executar Investigação Forense**.
4. **Como Interpretar as Hipóteses Técnicas:**
   - **Plausibilidade e Confiança:** Calculadas com base na convergência de múltiplas fontes (Event Viewer + Minidump + Reliability Monitor + SMART).
   - **Evidências Favoráveis vs Contrárias:** Verifique sempre a coluna de evidências contrárias antes de substituir peças. Exemplo: erros de `Event ID 129` ou `UltraDMA CRC (ID 199)` com `0` setores pendentes/realocados apontam para comunicação/interface/energia (cabo SATA, porta USB ou LPM/APST), e não para morte física das células do SSD.
   - **Módulos em Minidumps:** Módulos nativos como `ntoskrnl.exe`, `win32kfull.sys` e `dxgkrnl.sys` são listados como **Vítimas do SO**, separados de **Drivers de Terceiros (Suspeitos Prováveis)**.
5. **Execução Segura Controlada N3:**
   - Nenhuma ação é executada automaticamente. Para rodar verificações somente-leitura homologadas (`DISM /CheckHealth`, auditoria `CrashControl`, histórico `WHEA-Logger`, esquema de energia `powercfg`), clique em **▶️ Executar c/ Confirmação** e digite `CONFIRMAR`.

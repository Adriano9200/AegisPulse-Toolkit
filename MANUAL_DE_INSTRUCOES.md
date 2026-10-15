# 📘 Manual Oficial de Instruções — AegisPulse IT Toolkit v3.0.0

**Diagnóstico • Automação • Inteligência**  
*Tecnologia sob controle. Suporte com inteligência.*  
**Autor e Proprietário:** Adriano Barboza  
**WhatsApp Comercial (Vendas & Assinaturas PRO):** [+55 61 98515-8434](https://wa.me/5561985158434)  
**E-mail:** `adriano9200@gmail.com`  
**Repositório Oficial:** [https://github.com/Adriano9200/AegisPulse-Toolkit](https://github.com/Adriano9200/AegisPulse-Toolkit)

## Parte 1 — Como Iniciar o AegisPulse IT Toolkit v3.0.0

1. Na pasta do projeto (`D:\PROJETOS_PESSOAL\AegisPulse-Toolkit`), dê dois cliques em **`Iniciar_AegisPulse.bat`** (ele solicitará permissão de Administrador automaticamente para ler sensores térmicos, SMART dos discos e Windows Update) ou execute no PowerShell:
   ```powershell
   cd "D:\PROJETOS_PESSOAL\AegisPulse-Toolkit"
   python main.py
   ```
2. Caso queira gerar um **executável portátil único (`.exe`)** para divulgar em Modo Trial aos seus clientes sem que eles precisem ter Python instalado, dê dois cliques em **`build_exe.bat`**. O arquivo ficará pronto em `dist\AegisPulse_Toolkit.exe`.

## Parte 2 — Como Funcionam os 3 Perfis de Acesso (Trial, Assinante PRO e ADM)

Ao abrir o **AegisPulse v3.0**, a janela inicial apresenta **3 modalidades claras e intuitivas**:

### 1. ⏳ Modo Trial Gratuito (Para Demonstração e Divulgação)
* **Como entrar:** Basta clicar no botão azul **`🚀 Entrar no Modo Trial`** (não exige senha).
* **O que está liberado:**
  * Permite executar até **4 diagnósticos completos gratuitos** na máquina;
  * Libera o uso gratuito da **🧠 IA Local AegisPulse N3** na Aba 9;
  * Exibe um botão verde no topo (**`📲 Assinar PRO (WhatsApp)`**) que leva o usuário direto para o seu WhatsApp (`+55 61 98515-8434`).
* **Como funciona o bloqueio comercial:**
  * Na **5ª tentativa de análise** (ou se o usuário Trial tentar selecionar **Google Gemini** ou **xAI Grok** na Aba 9), o sistema exibe automaticamente o convite comercial com o seu WhatsApp **`+55 61 98515-8434`** para que ele compre uma Chave de Assinatura PRO!

### 2. ⭐ Modo Assinante PRO (Para Clientes e Técnicos que Comprarem sua Assinatura)
* **Como entrar:** O cliente cola a chave que você gerou para ele (ex: `AEGIS-PRO-20271015-CLIENT-XXXXXXXXXX`) no campo da opção 2 e clica em **`Ativar Chave PRO`**.
* **O que está liberado:**
  * Diagnósticos, manutenções, otimizações gamer e geração de laudos PDF **ilimitados** até a data de vencimento da chave;
  * Desbloqueia o uso dos motores de IA em nuvem (**✨ Google Gemini 3.x** e **🚀 xAI Grok / Groq Cloud**) na Aba 9;
  * **Segurança:** As Abas 11 (`💰 ADM: Clientes & Preços`) e 12 (`👑 ADM: Licenças & Keygen`) permanecem **100% invisíveis e bloqueadas** para o assinante comum!

### 3. 👑 Modo Administrador Master (Exclusivo Adriano Barboza)
* **Como entrar:** Na opção 3 da tela inicial, digite a sua nova **Senha Master pessoal** (configurada via hash SHA-256 seguro) e clique em **`Entrar como ADM`**.
* **O que está liberado:**
  * Acesso irrestrito a todas as ferramentas e motores de IA;
  * Desbloqueia as duas abas exclusivas de gestão do seu negócio:
    * **Aba 11 (`💰 ADM: Clientes & Preços`):** Seu banco de dados **SQLite**, Tabela de Preços Médios Justos de Mercado (Sem Abuso) e Gerador de Relatório/Orçamento Exclusivo para enviar ao cliente.
    * **Aba 12 (`👑 ADM: Licenças & Keygen`):** Seu gerador oficial de chaves `AEGIS-PRO-...` para vender assinaturas Mensais (30d), Trimestrais (90d), Semestrais (180d), Anuais (365d) ou Vitalícias!

## Parte 3 — Guia das Novas Abas da Versão 3.0.0

### 🌡️ Medidor de Temperatura Atual de CPU e GPU (PC Gamer e Casual)
* Visível logo no 3º card da **Aba 1 (`📊 Visão Geral & Temps`)**, na **Aba 2 (`🖥️ Hardware & Discos`)**, na **Aba 7 (`🎮 PC Gamer & DLLs`)** e nos **Laudos PDF**:
  * Mede em tempo real a temperatura da **CPU** e da **GPU** em graus Celsius (`°C`);
  * Classifica automaticamente o estado térmico:
    * **`❄️ Fria / Ideal (< 65°C)`**
    * **`🌡️ Normal em Uso (65–79°C)`**
    * **`🔥 Alerta Térmico (≥ 80°C — Revisar Pasta Térmica/Cooler)`** (excelente argumento técnico para você recomendar a higienização interna + troca de pasta térmica!).

### 🧩 Aba 3: Compatibilidade de Hardware & Upgrades (De Acordo com Todo o Setup)
Analisa automaticamente o conjunto da máquina do cliente e responde na tela:
1. **Placa-Mãe & Socket da CPU:** Identifica a plataforma (ex: *Intel LGA 1151 v2*, *LGA 1200*, *LGA 1700*, *AMD AM4*, *AM5*) e lista quais processadores superiores cabem naquela mesma placa-mãe sem precisar trocá-la.
2. **Memória RAM & Expansão:** Mostra o padrão (*DDR3, DDR4 ou DDR5*), a configuração atual e a especificação exata de pente para comprar e expandir com compatibilidade total.
3. **Placa de Vídeo (PCIe x16) & Fonte Recomendada (PSU):** Calcula a potência de fonte recomendada em Watts (ex: `500W a 550W 80 Plus Bronze/Gold`) e indica quais placas de vídeo modernas combinam com o processador atual sem gargalo severo.
4. **Armazenamento & Checklist Windows 11:** Confirma suporte a SSDs M.2 NVMe e SATA III e verifica se CPU, RAM e TPM 2.0 atendem aos requisitos do Windows 11 24H2/25H2.

### 💰 Aba 11 (Exclusiva ADM): CRM SQLite, Tabela de Preços Justos & Relatório Exclusivo do Cliente
Projetada para profissionalizar o seu atendimento comercial:
1. **Tabela de Preços Médios Justos de Mercado (Sem Abuso):**
   * Traz 9 serviços padronizados com a faixa de mercado e o **Preço Justo Sugerido** (entre R$ 80,00 e R$ 180,00).
   * Basta marcar as caixinhas (`☑️`) dos serviços que o computador do cliente precisa.
2. **Cadastro no Banco SQLite (`data/aegispulse_admin.db`):**
   * Preencha o **Nome do Cliente**, o **WhatsApp (com DDD)**, telefone alternativo, desconto (se houver) e observações.
   * Clique no botão verde **`💾 Salvar no SQLite & Gerar Relatório Exclusivo do Cliente`**.
3. **O que acontece ao clicar:**
   * O atendimento fica salvo permanentemente no seu banco de dados local **SQLite** (na tabela inferior você pode pesquisar qualquer cliente atendido por nome ou WhatsApp);
   * Abre imediatamente uma nova guia com o **Laudo & Orçamento Exclusivo do Cliente** (com visual limpo em fundo claro, dados do cliente, dados e temperaturas do PC, tabela transparente dos serviços orçados e dois botões no topo: **`🖨️ Imprimir / Salvar em PDF`** e **`💬 Enviar Orçamento Direto no WhatsApp do Cliente`**!).

## Parte 4 — Como Trancar o Projeto no GitHub como Software Proprietário (Visível para Análise, Bloqueado para Uso)

Para que qualquer recrutador, empresa ou cliente possa **ver e admirar a arquitetura do seu projeto no GitHub**, mas **não consiga usá-lo livremente nem alterar seu código**, aplicamos **4 travas combinadas**:

1. **Trava Legal (`LICENSE` Proprietária — All Rights Reserved):** O arquivo `LICENSE` deixa explícito que o código não é Open Source (não é MIT nem GPL) — pertence exclusivamente a **Adriano Barboza**, sendo proibida a cópia, redistribuição ou uso comercial sem chave de assinatura.
2. **Trava Criptográfica no Código (`backend/auth.py`):** Sua senha Master nunca fica escrita em texto aberto no código (apenas o hash irreversível SHA-256), e o Modo Trial trava na 4ª análise exigindo uma chave `AEGIS-PRO-...` assinada com HMAC-SHA256.
3. **Trava de Privacidade (`.gitignore`):** Seu arquivo `config.json` (com suas chaves de API Gemini/Grok), seu banco de dados SQLite de clientes (`data/aegispulse_admin.db`) e os relatórios gerados (`reports/*.html`) são bloqueados pelo `.gitignore` e nunca sobem para o GitHub.
4. **Trava de Repositório no Site do GitHub (`Rulesets` + Desativar Forks/Issues se desejar):**
   * Em `https://github.com/Adriano9200/AegisPulse-Toolkit/settings/rules`, mantenha a regra ativa na branch `main` com **Restrict deletions** e **Block force pushes** para blindar seu histórico.

# 🛡️ AegisPulse IT Toolkit
### Diagnóstico • Automação • Inteligência
> **Tecnologia sob controle. Suporte com inteligência.**  
> *Desenvolvido por Adriano Barboza (`adriano9200@gmail.com`)*

**Autor e Criador:** Adriano Barboza (`adriano9200@gmail.com`)  
**Versão:** 1.0.0  
**Plataforma Principal:** Windows 10 / Windows 11 (Compatível com execução multiplataforma para homologação)  
**Licença:** Proprietária — Todos os direitos reservados a **Adriano Barboza**

## Visão Geral

O **AegisPulse IT Toolkit** é uma suíte profissional de diagnóstico, inventário, atualização automatizada, manutenção preventiva e consultoria assistida por Inteligência Artificial (Google Gemini), desenvolvida por **Adriano Barboza** para operações técnicas de suporte N1, N2 e N3 em computadores de clientes particulares, gamers e pequenas empresas.

## Principais Funcionalidades

* **Identificação Universal de Hardware (Marca, Modelo e Service Tag):** Reconhece qualquer fabricante e modelo de desktop ou notebook (Dell, Lenovo, HP, Asus, Acer, Samsung, MSI, Gigabyte ou montados), placa-mãe, processador, módulos individuais de memória RAM (slots, velocidades e part numbers), GPU e saúde SMART das unidades de armazenamento.
* **Auditoria de Sistema Operacional e Build:** Identifica edição exata do Windows, versão (`22H2`, `23H2`, `24H2`), número de Build e UBR (`Update Build Revision`), arquitetura, data de instalação, tempo ligado (Uptime), status do Windows Defender e presença de chip TPM 2.0.
* **Diagnóstico de BIOS/UEFI e Drivers:** Levanta versão SMBIOS, data de lançamento e idade da BIOS (alertando quando superior a 24 meses e fornecendo link direto de suporte do fabricante). Inventaria todos os drivers assinados, destaca dispositivos com código de falha no Gerenciador de Dispositivos e busca/instala atualizações de drivers via catálogo oficial do Windows Update.
* **Inventário de Softwares e Integração com Winget:** Lista os programas instalados, detecta automaticamente versões obsoletas (`winget upgrade`) e permite atualizar individualmente, atualizar todos em lote ou instalar um catálogo pós-formatação em 1 clique.
* **Integração Online com Google Gemini AI:** Quando o dispositivo possui conexão ativa com a internet, envia um resumo sanitizado da telemetria para a API do Gemini (`gemini-2.5-flash`), gerando um diagnóstico avançado para o técnico e um resumo em linguagem simples para o cliente.
* **Geração de Logs e Laudos Técnicos em HTML5:** Produz relatórios e logs visuais completos em HTML autocontido, prontos para impressão ou exportação em PDF na pasta `reports/` e `logs/`.
* **Controle de Acesso do Operador (Operator Lock):** Protegido por autenticação SHA-256 (`PIN do Técnico`), garantindo que terceiros que visualizem o código no GitHub não consigam operar a ferramenta sem a credencial local do autor.

## Estrutura de Diretórios do Projeto

```text
AegisPulse-Toolkit/
├── main.py                      # Ponto de entrada (Servidor Local + Abertura da Interface)
├── Iniciar_AegisPulse.bat       # Inicializador 1-clique com elevação automática para Administrador
├── build_exe.bat                # Script para empacotar em executável único (.exe) via PyInstaller
├── config.example.json          # Modelo de configuração local
├── requirements.txt             # Dependências opcionais para compilação
├── .gitignore                   # Proteção de chaves, config.json e relatórios de clientes
├── LICENSE                      # Licença Proprietária Restrita (Adriano Barboza)
├── README.md                    # Documentação principal do repositório GitHub
├── LEIAME.txt                   # Guia rápido de bolso para atendimento em campo
├── GUIA_GITHUB_PASSO_A_PASSO.md # Manual de publicação, proteção e atualização no GitHub
├── backend/
│   ├── __init__.py
│   ├── server.py                # Servidor HTTP/REST API local
│   ├── auth.py                  # Autenticação SHA-256 e bloqueio de operador
│   ├── collectors/
│   │   ├── hardware.py          # Coletor WMI/CIM de Hardware, Marca, Modelo e SMART
│   │   ├── os_info.py           # Coletor de SO, Build, UBR, Defender e TPM
│   │   ├── drivers_bios.py      # Coletor de BIOS, Drivers e integração Windows Update
│   │   └── software.py          # Inventário de Softwares e automação Winget
│   └── services/
│       ├── maintenance.py       # Rotinas de limpeza Temp, reparo de Rede, DISM e Restore Point
│       ├── gemini_ai.py         # Cliente REST para Google Gemini API com sanitização
│       └── html_reporter.py     # Gerador de Laudos e Logs em HTML5
├── frontend/
│   ├── index.html               # Interface Gráfica SPA (Dark Tech UI)
│   ├── styles.css               # Folha de estilos responsiva
│   └── app.js                   # Controlador assíncrono do Frontend
├── reports/                     # Laudos HTML gerados para clientes
└── logs/                        # Logs de auditoria técnica
```

## Como Executar

1. Certifique-se de ter o **Python 3.10+** instalado no equipamento (ou utilize o executável gerado pelo `build_exe.bat`).
2. Dê dois cliques em **`Iniciar_AegisPulse.bat`** (ele solicitará permissão de Administrador automaticamente) ou execute no terminal:
   ```powershell
   python main.py
   ```
3. Na tela de bloqueio, insira o PIN padrão inicial: **`admin123`** (altere-o imediatamente na aba **IA Gemini & Config**).

## Aviso Legal e Restrição de Uso

Este repositório pertence a **Adriano Barboza**. A visualização pública do código não concede licença de uso comercial, cópia, redistribuição ou modificação. Consulte o arquivo `LICENSE` para os termos completos.

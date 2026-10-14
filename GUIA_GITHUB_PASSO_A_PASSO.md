# 🚀 Guia Passo a Passo: Como Subir, Proteger e Atualizar o AegisPulse no GitHub

**Autor:** Adriano Barboza (`adriano9200@gmail.com`)

Este guia explica exatamente cada comando que você vai copiar e colar no terminal para publicar o seu **AegisPulse IT Toolkit** no GitHub, deixá-lo visível como vitrine profissional, mas **bloqueado contra alterações ou uso indevido por terceiros**.

## Parte 1 — Como funciona a Proteção e Restrição no GitHub?

Para que o seu projeto fique visível no GitHub (ótimo para portfólio e autoridade profissional), mas ninguém possa manipular seu código nem sair usando livremente, aplicamos **3 camadas de proteção**:

1. **Proteção Jurídica e de Direitos Autorais (`LICENSE`):** O arquivo `LICENSE` declara **Todos os Direitos Reservados a Adriano Barboza** (Licença Proprietária). Ao contrário de licenças MIT ou GPL, ninguém tem permissão legal para usar, copiar ou distribuir seu software.
2. **Proteção Técnica no Software (`Operator PIN` + `.gitignore`):** O arquivo `config.json` (onde ficam sua senha mestre e sua chave do Gemini) está listado no `.gitignore`. Quem baixar o repositório verá a tela de bloqueio exigindo o seu PIN de Operador.
3. **Proteção do Repositório no GitHub (`Branch Protection` + Desativação de Forks/Issues se desejar):** No GitHub, apenas a sua conta poderá fazer `push` (enviar alterações) na branch `main`.

## Parte 2 — Passo a Passo: Subindo o Projeto pela Primeira Vez

### Passo 1: Instalar e configurar o Git (se ainda não tiver feito)
Abra o **PowerShell** ou **Prompt de Comando** e configure sua identidade de autor:

```powershell
git config --global user.name "Adriano Barboza"
git config --global user.email "adriano9200@gmail.com"
```

### Passo 2: Entrar na pasta do projeto no seu `G:\Meu Drive`
Execute o comando abaixo para entrar na pasta onde o Toolkit está salvo:

```powershell
cd "G:\Meu Drive\AegisPulse-Toolkit"
```

### Passo 3: Inicializar o repositório Git e registrar os arquivos
Copie e cole os comandos abaixo um por um:

```powershell
# 1. Inicializa o controle de versão Git na pasta
git init

# 2. Define a branch principal como 'main'
git branch -M main

# 3. Adiciona todos os arquivos do projeto (respeitando o .gitignore)
git add .

# 4. Verifica o que será enviado (note que config.json e relatórios de clientes ficam de fora!)
git status

# 5. Cria o primeiro marco (commit) oficial assinado por você
git commit -m "feat: lancamento inicial do AegisPulse IT Toolkit v1.0.0 por Adriano Barboza"
```

### Passo 4: Criar o Repositório no site do GitHub e Conectar
1. Acesse [https://github.com/new](https://github.com/new) e faça login na sua conta.
2. Em **Repository name**, digite: `AegisPulse-Toolkit`
3. Em **Description**, coloque: `Suíte Profissional de Diagnóstico, Manutenção, Automação e IA para Suporte em TI — Por Adriano Barboza`
4. Escolha **Public** (visível para todos, mas apenas você pode editar) ou **Private** (visível apenas para você).
5. **NÃO** marque "Add a README file" nem ".gitignore" (pois já criamos todos eles completos!).
6. Clique em **Create repository**.
7. Copie o endereço do seu repositório (ex: `https://github.com/SEU_USUARIO/AegisPulse-Toolkit.git`) e execute no PowerShell:

```powershell
git remote add origin https://github.com/SEU_USUARIO/AegisPulse-Toolkit.git
git push -u origin main
```

## Parte 3 — Ativando as Restrições de Segurança no GitHub

Logo após subir o código:
1. No seu repositório no GitHub, clique em **Settings** (Configurações).
2. No menu lateral esquerdo, clique em **Branches** (ou **Rules** -> **Rulesets**).
3. Clique em **Add branch protection rule**:
   - Em **Branch name pattern**, digite: `main`
   - Marque **Require a pull request before merging** (impede alterações diretas de terceiros).
   - Marque **Lock branch** se quiser deixá-la somente-leitura até para colaboradores externos.
4. Em **Settings -> General -> Features**, você também pode desmarcar **Issues** ou **Discussions** se quiser que o repositório funcione apenas como vitrine oficial fechada.

## Parte 4 — Como Atualizar o GitHub Sempre que Fizermos Melhorias

Sempre que adicionarmos uma nova função ao **AegisPulse**, basta abrir o PowerShell na pasta `G:\Meu Drive\AegisPulse-Toolkit` e rodar estes 3 comandos:

```powershell
# 1. Prepara os arquivos novos ou modificados
git add .

# 2. Registra a atualização explicando o que mudou
git commit -m "feat: descricao da nova funcionalidade adicionada"

# 3. Envia imediatamente para o GitHub
git push
```

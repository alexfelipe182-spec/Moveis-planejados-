# Operação, recuperação e aceite da primeira versão

Este procedimento separa código entregue de operação comprovada. Uma API saudável,
um arquivo de backup ou um teste sintético aprovado, sozinhos, não encerram o projeto.

## 1. Permissões e administração

- Visitantes e contas comuns podem usar somente as funcionalidades autorizadas.
  Clientes, orçamentos, itens de orçamento, projetos e histórico interno são dados da equipe.
- Confirmar na homologação que uma conta comum recebe `403` nas rotas internas e
  não consegue consultar esses dados fornecendo um ID conhecido.
- Confirmar que a conta administrativa consegue executar o fluxo comercial completo.
- Não promover todas as contas a administrador e não compartilhar senhas. A primeira
  conta administrativa deve ser atribuída pelo responsável, por um canal controlado.
- Testar sessão expirada, renovação, logout e tentativa de reutilizar sessão encerrada.

## 2. Banco definitivo e recuperação

### Decisões que ainda exigem o responsável

A auditoria de 27/08/2026 registrou o banco Render `Ideal`/PostgreSQL 18 com expiração em
**20/09/2026 01:24 UTC — 19/09/2026 22:24, horário de Brasília**. Reconfirmar a data no
[painel do banco](https://dashboard.render.com/d/dpg-da3qhjm1egvs73ak78ng-a).

O plano gratuito não possui backups gerenciados e expira. A continuidade exige escolher
e autorizar um plano de banco sem essa expiração ou uma migração antes do prazo.
Nenhuma compra, migração, exportação de dados reais ou alteração do banco de produção
é feita pelos testes deste repositório. [Limitações oficiais do Render](https://render.com/docs/free#free-postgres)

Antes do aceite, definir:

- Responsável pelo banco, pela recuperação e pelos alertas de falha.
- Local de backup durável, privado e criptografado, fora do disco efêmero da API e do Git.
- Frequência, retenção e perda máxima de dados aceitável. Como ponto de partida para
  aprovação: cópia diária, sete cópias diárias e quatro semanais; ajustar à operação real.
- Tempo máximo de recuperação, medido em um ensaio, e procedimento de troca da aplicação
  para um novo banco. Não assumir um tempo que ainda não foi testado.

### Ferramenta entregue e seus limites

`scripts/database_recovery.py` usa clientes PostgreSQL **18**, formato `custom` do
`pg_dump` e manifesto `.dump.json` com SHA-256. A leitura da origem é configurada como
somente leitura, há limites de espera e o processo não coloca senhas/URLs nos argumentos
nem reproduz a saída de erro do PostgreSQL nos logs.

O arquivo e o manifesto nunca são sobrescritos. Se houver falha, os arquivos parciais
podem permanecer reservados e serão recusados por `verify`/`restore`: usar um nome novo
na próxima tentativa. Um hash confere integridade, **não prova autenticidade, criptografia
ou recuperabilidade**. Guardar arquivo e manifesto juntos, com acesso restrito.
Não publicar dumps, senhas, URLs de conexão ou dados de clientes em Git, chat ou artefatos de CI.

Uma cópia local na máquina do administrador não é uma política de backup automático.
O workflow de recuperação usa apenas dados sintéticos e **não protege os dados reais**.

### Exportação manual autorizada

Pré-requisitos: Python 3.12, dependências do backend e `pg_dump`, `pg_restore` e `psql`
da versão principal 18 no `PATH`. Para conectar de fora do Render, usar a URL **externa**
do banco com `sslmode=require` ou mais estrito. O script aceita apenas esse parâmetro de
URL e exige TLS quando o host não é loopback. Credenciais são recebidas exclusivamente
por variáveis de ambiente. [Cliente PostgreSQL no Ubuntu](https://www.postgresql.org/download/linux/ubuntu/)

No Windows, abrir um terminal privado na raiz do repositório. Preparar previamente uma
pasta de backups com ACL restrita e proteção de disco, fora do repositório. O exemplo
abaixo pede a URL sem exibi-la nem gravá-la no histórico do comando:

```powershell
$backupSecret = Read-Host 'URL externa do banco autorizado, com sslmode=require' -AsSecureString
$env:BACKUP_DATABASE_URL = [System.Net.NetworkCredential]::new('', $backupSecret).Password
try {
    & .\backend\.venv\Scripts\python.exe scripts/database_recovery.py backup --output C:\Backups\ideal-2026-08-27.dump
    if ($LASTEXITCODE -ne 0) { throw 'Backup não concluído; não utilize os arquivos parciais.' }
    & .\backend\.venv\Scripts\python.exe scripts/database_recovery.py verify --archive C:\Backups\ideal-2026-08-27.dump
    if ($LASTEXITCODE -ne 0) { throw 'A verificação de integridade falhou.' }
} finally {
    Remove-Item Env:BACKUP_DATABASE_URL -ErrorAction SilentlyContinue
    $backupSecret = $null
}
```

Trocar a data/nome em cada exportação. O diretório precisa existir. Depois de confirmar
sucesso, guardar **os dois arquivos** no armazenamento privado aprovado, mantendo a
cópia anterior até validar a nova. Não automatizar descarte de versões sem a política acordada.

### Ensaio de restauração, nunca por cima da produção

O comando `restore` foi intencionalmente limitado a um PostgreSQL **local e descartável**:

1. Preparar um servidor PostgreSQL 18 separado e um banco vazio, criado de `template0`,
   com nome começando por `restore_`, por exemplo `restore_ideal_20260827`.
2. Manter a aplicação desconectada desse banco durante o ensaio. O script recusa alvos
   com outras sessões, tabelas, funções, tipos, extensões adicionais ou objetos grandes.
3. Conferir host/porta/nome. A URL precisa usar `localhost`, `127.0.0.1` ou `::1`, não um
   host de produção. Não usar um túnel que aponte ao banco real.
4. Carregar `RESTORE_DATABASE_URL` no terminal privado como no exemplo anterior, usando
   a senha **do alvo**, e executar:

```powershell
& .\backend\.venv\Scripts\python.exe scripts/database_recovery.py restore --archive C:\Backups\ideal-2026-08-27.dump --confirm-target restore_ideal_20260827
if ($LASTEXITCODE -ne 0) { throw 'Restauração não confirmada; investigar em ambiente isolado.' }
```

5. Remover `RESTORE_DATABASE_URL` do ambiente ao terminar. Conferir a revisão Alembic,
   contagem e amostras dos cadastros, totais dos orçamentos e relações cliente/projeto.
6. Executar a aplicação de homologação contra esse alvo e validar os fluxos. Registrar
   o horário do backup, a duração do ensaio, o resultado e quem aprovou.

O restore exige confirmação exata do nome, compara a origem pelo manifesto e usa uma
única transação com interrupção em erro, sem `--clean`, `--create` ou remoção de dados.
Só restaurar arquivos produzidos por uma origem confiável: um dump pode conter SQL
executável. Isolamento da rede/banco e conta de menor privilégio continuam necessários.
[pg_restore e transação única](https://www.postgresql.org/docs/18/app-pgrestore.html)

Uma recuperação real exige plano de incidente aprovado: criar novo banco, recuperar e
validar nele, planejar a troca de conexão e preservar a origem para retorno. Este script
não executa troca de URL da API, exclusão da origem nem restauração remota em produção.

### Evidência automatizada

O workflow `Recovery - PostgreSQL 18 backup and restore` cria um PostgreSQL 18 descartável,
aplica as migrações reais, insere dados sintéticos em clientes/orçamentos/itens/projetos,
exporta, confere o hash e restaura em outro banco vazio. Depois compara o conteúdo de
**todas as tabelas públicas** e a revisão Alembic e confirma a recusa de um segundo restore
no destino já preenchido. O job não recebe segredos do Render e não publica dumps.

## 3. Recuperação de senha por e-mail

A API aceita `EMAIL_PROVIDER=smtp`, `resend` ou `disabled`. O padrão compatível é `smtp`.
No plano gratuito do Render, as portas SMTP 25/465/587 estão bloqueadas; o adaptador
HTTPS pode ser configurado com `EMAIL_PROVIDER=resend`, `EMAIL_FROM`,
`RESEND_API_KEY` e `EMAIL_TIMEOUT_SECONDS` (padrão: 10 segundos).
[Restrições de rede no plano gratuito](https://render.com/docs/free#other-limitations)

O responsável precisa escolher o provedor, verificar o remetente/domínio e cadastrar a
chave diretamente no ambiente do backend. Nunca inserir a chave no frontend, no Git ou
no chat. Para SMTP em hospedagem compatível, configurar o conjunto completo `SMTP_HOST`,
`SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` e o modo TLS correto; não ativar STARTTLS e SSL
simultaneamente.

Critério de aceite: solicitar recuperação com uma conta de teste autorizada, receber
o e-mail, abrir o link, trocar a senha, confirmar que a senha antiga falha e que o link
utilizado/expirado não pode ser reutilizado. Um teste simulado do provedor não comprova
entrega na caixa postal. Não marcar essa etapa como concluída sem a mensagem real.

## 4. Atendimento comercial

Confirmar com o responsável o WhatsApp comercial completo (país + DDD + número), nome
da empresa e dados públicos. Não inventar um telefone nem encaminhar visitantes para um
número de teste. Conferir que “Solicitar orçamento” abre a conversa correta no celular
e no computador, com texto adequado, sem dados internos de outros clientes.

Quando o número não estiver configurado, a interface deve informar essa indisponibilidade,
sem apresentar o atendimento como funcional. O aceite comercial depende de um envio de
teste autorizado pelo responsável.

## 5. Listagens e busca

Em homologação, cadastrar dados sintéticos suficientes para ultrapassar uma página e
conferir: avançar/voltar páginas, buscar um registro fora da primeira página, filtros,
lista vazia, ausência de duplicados e atualização depois de salvar/excluir. Verificar
também seletores de clientes/categorias usados nos formulários. A busca deve consultar
o conjunto completo autorizado, sem liberar dados a contas comuns.

## 6. Docker, validação final e entrega

### Instalação Docker nova

`docker-compose.prod.yml` agora inclui PostgreSQL 18 e Redis privados, espera os dois
healthchecks e passa à API os parâmetros de URL do frontend, sessão, prazo de conexão e
e-mail. Somente a API fica ligada a `127.0.0.1:8000`; usar um proxy HTTPS no host para
publicá-la. O pacote não configura automaticamente domínio, certificado nem site estático.
PostgreSQL e Redis não publicam portas na máquina.

Preparar `.env.production` a partir do exemplo e substituir os valores de demonstração
sem versionar segredos. `DATABASE_URL` deve corresponder ao usuário/senha/banco de
`POSTGRES_*`, usando host `postgres`; caracteres especiais da senha precisam de
codificação de URL. `REDIS_URL` do Compose é sempre `redis://redis:6379/0`.
`CORS_ORIGINS` e `FRONTEND_URL` devem corresponder ao endereço público HTTPS real.

```text
docker compose --env-file .env.production -f docker-compose.prod.yml config -q
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

Não usar `config` sem `-q` em logs compartilhados: ele pode expandir segredos do ambiente.
Conferir `/health`, `/ready` e login por HTTPS antes de abrir acesso público.

**Stack existente com PostgreSQL 16:** não aplicar esse Compose sem planejar migração.
O volume agora é `postgres18_data`, montado em `/var/lib/postgresql`, conforme o layout
da imagem 18. O antigo `postgres_data` não é convertido nem apagado: subir a nova stack
sem migração criaria um banco vazio separado. Preservar a stack/volume antigo, exportar
com autorização, ensaiar restauração e só então planejar a troca. Nunca apontar a imagem
18 para o diretório de dados 16 nem executar `down -v` numa stack com dados reais.
[Layout da imagem oficial PostgreSQL](https://hub.docker.com/_/postgres)

### Roteiro de aceite

Executar primeiro em homologação, no computador e em tela de celular. Dados e e-mails
reais só com autorização. Registrar versão/commit, ambiente, responsável e resultado.

| Verificação | Resultado necessário |
| --- | --- |
| Login, renovação e logout | Sessão funcional e revogada corretamente; falhas explicadas |
| Conta comum vs. administrador | Dados internos inacessíveis à conta comum |
| Cliente → orçamento → itens | Relações e valores persistem corretamente |
| Aprovação → proposta → projeto | Decisão, totais e transições coerentes |
| Listagem/busca além da primeira página | Registro encontrado sem duplicação ou perda |
| E-mail de senha | Mensagem real entregue e link de uso único validado |
| WhatsApp | Número do responsável e abertura corretos |
| Rede/API indisponível | Sem travamento interminável, erro compreensível e nova tentativa |
| Backup → banco isolado | Dados e revisão conferidos; tempo medido |
| Saúde após publicação | Frontend acessível; `/ready` retorna banco/cache saudáveis |

Fechar a primeira versão somente após as pendências operacionais serem aprovadas e
registradas: banco definitivo, política de backup com ensaio real, remetente/e-mail,
número comercial e aceite do responsável. Melhorias visuais opcionais e novas integrações
podem ir para uma versão posterior, sem ocultar essas pendências.

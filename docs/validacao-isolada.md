# Validação local de entrega

Requisitos: Git, Python 3.12 e Docker com containers Linux. Execute na raiz:

```powershell
python scripts/validate_isolated.py
```

O comando funciona também em Linux. Não exige Node no host nem `package.json`.
Instala as dependências declaradas pelo projeto em uma imagem temporária Python
e usa Node 22. O build e o pip-audit precisam de internet; os testes não têm
saída para a internet. Não forneça credenciais reais.

Cada chamada cria uma rede Docker `--internal`, PostgreSQL 16 vazio e Redis 7
exclusivos, sem publicar portas. Os nomes incluem um identificador aleatório.
O PostgreSQL usa tmpfs. A execução não usa volumes ou bancos preexistentes.
A cópia temporária contém somente arquivos já rastreados pelo Git e arquivos de
contrato; arquivos locais não rastreados nunca são copiados. `.env` e variantes são excluídos. Apenas `.env.production.example`
é copiado como texto de referência e nunca carregado pela aplicação.
O contexto enviado ao build da imagem contém somente o Dockerfile temporário e
`backend/requirements.txt`, mesmo quando o daemon Docker é remoto.
O processo Python do container começa com `env -i` e configurações de teste
explícitas. Nenhuma variável SMTP, Stripe, bootstrap ou credencial do host
é herdada. Os destinos efetivos de Settings são comparados com os destinos
esperados e impressos sem senha antes das migrations.

Gates executados:

1. Ruff com os mesmos caminhos do CI, compileall e pip check.
2. Redis disponível, um único head Alembic, upgrade até head, alembic check
   e igualdade entre revisão instalada e revisão esperada.
3. Toda a suíte `backend/tests`, strict-config e cobertura mínima de 80%.
   Inclui rotas HTTP via TestClient e os servidores frontend real e de desenvolvimento.
4. Sintaxe de todos os `.js`/`.cjs` e `node --test frontend/*.test.cjs`.
5. pip-audit em container separado com acesso somente ao requirements.txt.

Os testes bloqueiam os transportes HTTP do httpx e SMTP. OpenAI é bloqueado
no construtor por padrão; cada cenário simulado pode instalar seu próprio
mock. `OPENAI_ENABLED=true` permite os cenários positivos com mock, enquanto
`OPENAI_API_DISABLED=true` e chave vazia mantêm o comportamento padrão local.
Não configure `OPENAI_ENABLED=false` globalmente para essa suíte.

Repita o comando para uma nova rodada. Os e-mails fixos dos testes nunca
encontram cadastros de rodadas anteriores porque cada rodada ganha banco novo.
Não rode pytest diretamente contra um banco usado por pessoas. O conftest
rejeita ambiente diferente de test e hosts externos, mas um endereço local
sozinho não comprova que um banco é descartável: use o executor.

Ao terminar, mesmo com falha, o executor tenta remover independentemente todos os
IDs dos containers criados por ele, seus volumes anônimos, sua rede e sua tag de
imagem. Uma falha de limpeza é informada sem impedir as tentativas seguintes.
Imagens-base/cache do Docker podem permanecer. Não use `docker system prune`,
`compose down -v` de outro projeto ou limpeza global. Em encerramento forçado
do processo/sistema, confira os recursos com o identificador impresso antes
de remover exclusivamente os recursos daquela execução.

O parâmetro opcional `--image` permite reutilizar uma imagem de ferramentas
confiável com os requirements, pytest-cov e pip-audit instalados; essa imagem
não será removida pelo executor.

## Stripe e prévia local

Development/test aceitam `sk_test_` ou `rk_test_`; production aceita `sk_live_`
ou `rk_live_`. Chaves incompatíveis retornam 503 sem chamada ao provedor.
Os formatos seguem a [documentação de autenticação do Stripe](https://docs.stripe.com/api/authentication).
Preços e webhook secret continuam específicos de cada ambiente. Nenhuma
chave real é necessária para executar a suíte.

Frontend servido em localhost, 127.0.0.1 ou IPv6 loopback usa API local na porta
8000. `window.API_BASE_URL` tem precedência. Para demonstrações isoladas, confira
o destino na aba de rede antes de qualquer cadastro; use dados explicitamente
fictícios e ambiente descartável.

## Roteiro comercial (homologação)

Use “Marcenaria Demonstração — dados fictícios” e e-mail único `@example.com`.
Não apresente números fictícios como vendas ou clientes reais.

1. Cadastrar empresa, entrar, conferir trial de 30 dias e abrir `/dashboard/`
   diretamente. Renovar sessão e confirmar que logout impede restauração.
2. Criar cliente “Cliente fictício”, produto “Armário demonstrativo” e orçamento;
   salvar, consultar, editar e conferir persistência e valores calculados.
3. Mostrar revisão humana do orçamento, proposta e fluxo comercial.
4. Entrar com uma segunda empresa fictícia e verificar que seus dados são distintos.
5. Mostrar recuperação de senha usando entrega simulada. Não enviar e-mail real.
6. Mostrar cobrança apenas em sandbox Stripe; explicar o trial e não cobrar cartões reais.
7. Conferir teclado, menus, contraste, rolagem e botões em desktop e tela estreita.
   Registrar separadamente Safari/iPhone físico; emulação não substitui esse teste.

Os testes automatizados sustentam parte desse roteiro, mas não equivalem a uma
demonstração visual completa nem comprovam configuração operacional de produção.

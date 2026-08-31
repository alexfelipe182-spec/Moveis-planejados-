# Fundação SaaS Multi-Marcenarias

Este documento descreve o que está implementado no repositório e o que ainda
precisa de uma decisão operacional. Código local não é apresentado como uma
homologação real de produção.

## Limite de cada marcenaria

`organizations` é o tenant raiz. Usuários, clientes, categorias, produtos,
orçamentos, itens, projetos, fornecedores, insumos, custos e atividades carregam
`organization_id` obrigatório. A API deriva esse valor da sessão; o cliente não
pode escolher o tenant no payload. Listas, contagens, buscas, decisões, histórico,
automações e rentabilidade aplicam o mesmo filtro.

As relações obrigatórias também têm chaves compostas `(organization_id, id)` e
FKs compostas. Assim, uma importação SQL não consegue ligar um produto à categoria,
um orçamento ao cliente, um projeto ao cliente ou um custo ao projeto de outra
marcenaria. Relações opcionais (por exemplo, material removido) continuam com a
semântica original de `SET NULL` e são validadas pela API.

O painel `/api/v1/platform/*` é exclusivo de `is_platform_admin` e só expõe
agregados/metadados de organizações, nunca clientes, valores ou conteúdo
operacional. A promoção é explícita via `BOOTSTRAP_PLATFORM_ADMIN_EMAIL` durante a
migração; não existe promoção automática de todas as contas.

## Migrações e compatibilidade dos PRs

As alterações foram reaproveitadas de forma sequencial, sem mesclar os PRs
conflitantes por força:

| Revisão | Responsabilidade |
| --- | --- |
| 010 | bootstrap administrativo do PR #75 |
| 011 | persistência da inteligência de orçamento do PR #77 |
| 012 | organizações e ownership retrocompatível; legado é atribuído ao tenant 1 |
| 013 | planos, trial, assinatura e idempotência de webhooks |
| 014 | bootstrap explícito do superadministrador |
| 015 | FKs compostas para impedir referências cruzadas |
| 016 | catálogo comercial Essencial, Profissional e Empresarial |

O estado esperado é uma única cabeça Alembic (`016_commercial_plan_catalog`).
Antes de migrar o banco definitivo, executar `alembic upgrade head` em uma cópia
isolada e conferir a revisão corrente. A migração 012 preserva os dados legados em
`Multi-Marcenarias Legado`; a divisão posterior de dados é uma decisão de negócio,
não uma inferência automática.

## Planos, trial e pagamento

O catálogo comercial inicial contém:

| Plano | Mensalidade | Usuários | Posicionamento |
| --- | ---: | ---: | --- |
| Essencial | R$ 49 | 3 | clientes, orçamentos, projetos, produção e custos |
| Profissional | R$ 99 | 10 | IA de orçamento, automações e rentabilidade |
| Empresarial | R$ 249 | 50 | relatórios avançados, suporte prioritário e implantação assistida |

O cadastro público cria a organização, o primeiro usuário como administrador e
14 dias de teste no plano escolhido. O onboarding mostra o progresso e o endpoint
de membros aplica `max_users` do plano.

`BILLING_PROVIDER=disabled` é o padrão seguro. `sandbox` permite testar checkout e
webhooks sem cobrança; o evento é gravado por `(provider, event_id)` e repetição é
idempotente. Só configurar `stripe` com uma chave de assinatura de webhook,
provedor, preço/IDs reais e conta de menor privilégio. Checkout em sandbox nunca é
prova de cobrança real.

O frontend administrativo possui a área **Plano e equipe**, que mostra o estado
de acesso calculado no servidor, catálogo, limite de usuários e criação de
membros no tenant atual. A resposta de checkout informa explicitamente quando é
sandbox e nunca apresenta isso como pagamento concluído. A área **Plataforma**
só é exibida para `is_platform_admin` e lista agregados/metadados; alterações de
status pedem confirmação e são registradas em atividade.

Quando a assinatura está `past_due`, `canceled` ou com trial expirado, consultas
continuam disponíveis para o cliente não perder acesso aos próprios dados, mas
criações, edições, exclusões, decisões, produção, custos e recomendações ficam
bloqueadas no servidor com HTTP 402. Billing e onboarding permanecem acessíveis
para recuperação. Instalações legadas sem linha de assinatura conservam a
compatibilidade até a migração criar esse vínculo.

## Critérios de aceite antes do lançamento

1. Aplicar as migrações em um PostgreSQL 18 descartável e executar os testes de
   fluxo completo (`cliente → orçamento → aceite → projeto → produção → custo →
   rentabilidade`) com dois tenants.
2. Repetir login, refresh, logout, reset de senha, suspensão de tenant e tentativa
   de acessar IDs de outra marcenaria em computador e iPhone real/emulador.
3. Validar paginação/busca, referências fora da primeira página, CSRF por cookie e
   Authorization Bearer.
4. Usar `BILLING_PROVIDER=sandbox` para eventos duplicados e inválidos; não enviar
   cartão ou dados reais ao ambiente de teste.
5. Configurar e testar backup/restore em banco separado, remetente de e-mail,
   domínio HTTPS, CORS, WhatsApp e observabilidade.
6. Registrar commit, revisão Alembic, navegador/dispositivo, horário, responsável
   e evidência de cada cenário. Sem isso, a etapa é pendente mesmo que `/health`
   responda 200.

## Proteção da `main`

A regra de pelo menos uma aprovação é uma configuração do repositório GitHub, não
um arquivo da aplicação. O administrador deve configurar a branch `main` para:

- exigir pull request antes do merge;
- exigir pelo menos 1 review aprovado e dispensar aprovação do autor;
- exigir os checks `backend` e `frontend` do workflow `CI - PostgreSQL + Redis +
  Alembic + API + Frontend`;
- resetar aprovações quando novos commits forem enviados;
- bloquear force-push e exclusão da branch.

Como o ambiente desta execução não possui credencial GitHub/`gh`, essa alteração
não foi fingida nem aplicada remotamente. Depois de configurada, abrir um PR de
teste e confirmar que merge sem review é recusado. O workflow `Main review gate`
já falha PRs sem uma aprovação e deve ser marcado como check obrigatório junto
com `backend` e `frontend` na regra remota.

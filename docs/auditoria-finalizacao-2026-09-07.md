# Auditoria de finalização — Multi-Marcenarias

Data: 07/09/2026

## Objetivo

Finalizar a plataforma com foco em confiabilidade de produção, experiência profissional, orçamento inteligente, segurança de sessão, testes e hospedagem.

A sequência usada nesta auditoria é a definida para o projeto:

1. Entender o pedido
2. Modelar os dados
3. Calcular e auditar
4. Desenhar e construir
5. Validar e documentar

## 1. Entender o pedido

Prioridades desta rodada:

- tornar o orçamento inteligente seguro e transparente;
- impedir salvamento de preços zerados ou desatualizados;
- melhorar estados e proteção contra clique duplo dos botões;
- diferenciar sessão inexistente de falha CSRF real;
- manter isolamento por marcenaria e cálculo determinístico de preços;
- preservar o fluxo GitHub → CI → Render.

## 2. Modelar os dados

O contrato da prévia inteligente agora identifica a origem da interpretação:

- `openai`: interpretação estruturada fornecida pelo provedor OpenAI;
- `assisted_local`: fallback local seguro quando o provedor não está configurado ou está indisponível.

A origem é propagada em `QuotePreview.interpretation_source`. O fallback local continua proibido de inventar preços ou quantidades de catálogo.

## 3. Calcular e auditar

Regras comerciais validadas e reforçadas:

- custos e preços continuam calculados deterministicamente pelo backend;
- a IA não altera valores financeiros arbitrariamente;
- orçamento com total sugerido menor ou igual a zero não pode ser salvo pelo assistente;
- qualquer alteração em material, ferragens, mão de obra, acabamento ou margem invalida o cálculo anterior;
- após alterar custos, é obrigatório calcular novamente antes de salvar;
- itens sem correspondência segura no catálogo continuam sem preço e exigem revisão humana.

Auditoria de sessão:

- ausência de refresh token é condição de autenticação (`401`), não falha CSRF;
- sessão existente com CSRF ausente/incorreto continua retornando `403`;
- rotação e revogação do refresh token permanecem protegidas.

## 4. Desenhar e construir

Melhorias de interface desta rodada:

- badge visível indicando `IA OpenAI` ou `Modo assistido`;
- estado `aria-busy` nos botões de ações assíncronas;
- bloqueio de clique duplicado ao adicionar, editar ou excluir itens;
- botão Salvar bloqueado até existir cálculo válido;
- mensagem explícita quando valores forem alterados e exigirem novo cálculo;
- contraste forte dos valores financeiros preservado em modo claro e escuro;
- layout responsivo dos badges e estados do orçamento inteligente.

## 5. Validar e documentar

Validações obrigatórias antes de merge:

- Ruff;
- compilação Python;
- `pip check`;
- imports;
- PostgreSQL;
- Redis;
- uma única head Alembic;
- aplicação e validação das migrations;
- testes backend;
- auditoria de dependências;
- sintaxe e comportamento do frontend;
- contratos dos módulos frontend;
- smoke test do frontend;
- Docker PostgreSQL + Alembic + API;
- Security Gates;
- CodeQL.

Nenhuma mudança desta auditoria deve ir para `main` ou produção sem todos os checks obrigatórios verdes.

## Estado comprovado antes desta rodada

- frontend de produção hospedado no Render;
- API de produção hospedada no Render;
- PostgreSQL e Redis integrados ao CI;
- cadastro, login e trial de 30 dias implementados;
- multi-tenant estrutural implementado no ORM e nas referências;
- orçamento inteligente com cálculo determinístico e fallback assistido;
- Stripe, recuperação de senha e isolamento multiempresa possuem implementação e testes parciais/estruturais.

## Itens que ainda exigem prova de produção após esta rodada

Os itens abaixo não devem ser considerados concluídos apenas por existirem no código:

1. executar o fluxo real Cliente → Orçamento → Projeto em produção;
2. confirmar uma chamada real ao provedor OpenAI com `OPENAI_API_KEY` configurada no ambiente, sem expor a chave;
3. validar Stripe em modo de teste: checkout, webhook, assinatura, portal, cancelamento e renovação;
4. validar recuperação de senha com entrega real de e-mail;
5. executar teste E2E com duas marcenarias independentes para provar isolamento entre tenants;
6. revisar variáveis finais de produção sem exibir segredos;
7. confirmar CI final e os dois serviços Render `live` no mesmo commit de finalização;
8. executar checklist comercial de demonstração, planos e onboarding.

## Critério de pronto

O projeto só será marcado como finalizado para venda quando os fluxos críticos acima estiverem comprovados ponta a ponta em produção ou em ambiente de teste apropriado, sem falhas críticas abertas e com CI, segurança e deploy verdes.

# Frontend Hardening Implementation Plan

> **For agentic workers:** Use the host's available task-by-task implementation workflow. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tornar os fluxos críticos do frontend mais claros, acessíveis e resistentes a ações duplicadas sem alterar a identidade visual ou os dados.

**Architecture:** Manter o frontend atual em HTML, CSS e JavaScript sem framework. Acrescentar pequenos helpers no proprietário existente `frontend/app.js`, com testes comportamentais em VM e verificações estáticas somente quando o contrato pertence ao HTML.

**Tech Stack:** HTML5, CSS, JavaScript, Node.js `node:test` e `vm`.

## Global Constraints

- Preservar todas as alterações existentes e o sistema visual futurista atual.
- Não publicar, não alterar dados reais e não criar integrações externas.
- Não mudar contratos da API nem inventar conteúdo comercial.
- Registrar falha antes de cada correção e executar a suíte completa ao final.

---

### Task 1: Mensagens acessíveis nos formulários de acesso

**Files:**
- Modify: `frontend/app.js`
- Test: `frontend/app.test.cjs`

**Interfaces:**
- Consumes: nós `#register-message`, `#recovery-message` e `#reset-message`.
- Produces: helper que aplica texto, classe, `role` e `aria-live` conforme sucesso ou erro.

- [x] Criar teste que observa erro como `alert/assertive` e sucesso como `status/polite`.
- [x] Executar o teste focado e confirmar falha nos atributos atuais.
- [x] Implementar helper mínimo e usá-lo nos três formulários.
- [x] Repetir o teste focado; o teste focado passou.

### Task 2: Exclusão protegida contra disparo duplicado

**Files:**
- Modify: `frontend/app.js`
- Test: `frontend/robustness.test.cjs`

**Interfaces:**
- Consumes: `deleteItem(resource, id)`, `configs[resource].endpoint`, `api`, `toast` e `loadResource`.
- Produces: no máximo uma requisição por chave `resource:id` enquanto pendente, com estado visual restaurado e nova tentativa liberada após sucesso ou erro.

- [x] Criar teste com requisição pendente e dois disparos para o mesmo registro.
- [x] Confirmar duas requisições no código atual.
- [x] Implementar `Set` de exclusões pendentes com limpeza em `finally`.
- [x] Testar estado pendente visível, falha, restauração e nova tentativa posterior bem-sucedida.

### Task 3: Controle de tema com ação explícita

**Files:**
- Modify: `frontend/app.js`
- Test: `frontend/production.test.cjs`

**Interfaces:**
- Consumes: `applyTheme(dark)` e `#theme-toggle`.
- Produces: `aria-pressed` coerente com um nome acessível estável; `title` e ícone coerentes com a próxima ação disponível.

- [x] Criar teste que alterna tema claro/escuro e observa os atributos e o ícone.
- [x] Confirmar falha dos rótulos no código atual.
- [x] Atualizar `applyTheme` sem alterar persistência ou tokens de cor.
- [x] Repetir o teste focado; o teste focado passou.

## Review Gate

- [x] Executar `node --test frontend/*.test.cjs` e exigir zero falhas: 128/128 passaram.
- [x] Executar `node --check` em todos os arquivos JavaScript do frontend: 8/8 passaram.
- [x] Executar `git diff --check` nos arquivos tocados: zero erros.
- [x] Solicitar revisão independente somente leitura do delta: nenhum finding restante; `Ready to merge: Yes`.
- [x] Não criar commit ou publicar sem autorização específica do usuário.

## Unresolved externally observable decisions

- A confirmação em navegador real e tecnologia assistiva continua limitada enquanto a prévia local não puder ser aberta pelo ambiente autorizado.

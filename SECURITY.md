# Security Policy

## Supported version

O projeto principal é mantido na branch `main`. Correções de segurança devem ser aplicadas nela e validadas pelos workflows de CI e segurança antes do merge.

## Como reportar uma vulnerabilidade

Não publique segredos, tokens, senhas, chaves de API ou detalhes exploráveis em issues públicas.

Para um possível problema de segurança:

1. descreva o componente afetado e o impacto;
2. informe passos mínimos para reproduzir, sem incluir credenciais reais;
3. remova dados pessoais e segredos de logs e screenshots;
4. aguarde a correção antes de divulgar detalhes que facilitem exploração.

## Controles automatizados

O repositório usa CodeQL, Gitleaks, auditoria de dependências, Ruff, testes automatizados, PostgreSQL, Redis, Alembic, validação de frontend e testes de imagem Docker como gates de qualidade e segurança.

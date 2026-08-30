# Homologação de produção — Multi-Marcenarias

## Antes do deploy

- backup lógico do PostgreSQL validado;
- Recovery Drill verde;
- CI, Docker, Security Gates e CodeQL verdes;
- nenhuma migration concorrente com `010_bootstrap_admin`;
- variável de bootstrap do superadmin revisada;
- revisão humana aprovada.

## Fluxo E2E obrigatório

1. criar Marcenaria A pelo onboarding;
2. criar Marcenaria B pelo onboarding;
3. confirmar que A não lista, abre, edita nem referencia IDs de B;
4. cadastrar cliente em A;
5. criar orçamento com custos e margem;
6. confirmar recomendação de preço, risco e confiança persistidos;
7. aprovar orçamento;
8. registrar envio ao cliente;
9. registrar aceite;
10. confirmar criação automática do projeto;
11. avançar measurement → technical_design → purchasing → production → installation → delivered → completed;
12. cadastrar fornecedor e material;
13. lançar custo de produção;
14. conferir rentabilidade do projeto;
15. conferir histórico apenas do tenant correto;
16. conferir dashboard administrativo apenas do tenant correto;
17. conferir painel do superadmin com visão de tenants sem usar endpoints operacionais para cruzar dados.

## Matriz de dispositivos

Executar o mesmo fluxo em:

- iPhone Safari atual, viewport real e teclado/autofill;
- desktop Chrome atual;
- desktop Safari ou Edge;
- rede móvel e Wi-Fi.

Verificar login, refresh, CSRF, formulários, tabelas roláveis, modais, botões com área de toque, mensagens de erro e logout.

## Critério de aceite

Nenhum vazamento entre tenants, nenhum erro 5xx, nenhuma migration pendente, nenhum check vermelho e nenhum bloqueio de navegação no fluxo comercial principal.

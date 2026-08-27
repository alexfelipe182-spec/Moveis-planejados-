# Painel de produção e custos

O painel é interno, exclusivo para administradores. Não envia pedidos aos fornecedores nem realiza pagamentos.

1. Em **Fornecedores**, cadastre nome e, opcionalmente, contato, e-mail e telefone. Não preencha dados fictícios no ambiente real.
2. Em **Insumos**, informe tipo, unidade, custo e perda percentual. O fornecedor é opcional. A busca consulta o servidor, inclusive por fornecedor.
3. Em **Projetos**, abra **Produção e custos**. Confirme o avanço somente quando concluir a etapa exibida. O fluxo normal é planejamento, medição, projeto técnico, compras, produção, instalação, entregue e concluído.
4. Registre custos com categoria, descrição, quantidade e custo unitário. O insumo é opcional. Selecionando um insumo com custo informado igual a zero, será usado o custo cadastrado. A perda do insumo é aplicada pelo servidor mesmo quando o custo é informado manualmente.
5. Confira o total registrado. Exemplo: quantidade 2 × custo 100 × perda de 10% = 220. Esse total não representa lucro nem orçamento previsto.
6. Confira a lista antes de repetir um envio que falhou por conexão. Esta versão permite criar e consultar custos, mas não editar ou excluir lançamentos. Caso a operação exija correção de custos, ainda é necessário implementar um fluxo de ajuste auditado.

As listas têm paginação. Projetos concluídos ou cancelados não oferecem avanço. O ambiente local de demonstração usa dados descartáveis, não comprova persistência nem backup de produção.

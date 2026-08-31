# Multi-Marcenarias — roteiro de apresentação

Versão local preparada em 28/08/2026. Objetivo: apresentar o sistema e sua vitrine
com dados fictícios, sem contratar serviços ou usar dados de clientes reais.
Este roteiro não representa aceite de produção.

## Abrir a demonstração

No computador em que o projeto está rodando:

- Vitrine: [abrir Multi-Marcenarias](http://127.0.0.1:8765/).
- Painel: [abrir login](http://127.0.0.1:8765/#login).
- Conta exclusiva da prévia: `preview@example.com`.
- Senha exclusiva da prévia: `Preview-local-123!`.

Essa conta não é a conta administrativa real. Não use essa senha em produção.
O endereço é local: serve para apresentar neste computador ou compartilhar sua
tela durante uma reunião. Não funciona como link público no computador do cliente
nem no celular. Não abrir portas, túneis ou publicar a prévia com essas credenciais.

## Apresentação em seis passos — aproximadamente 8 minutos

1. **Vitrine e identidade.** Mostre o nome Multi-Marcenarias, o visual futurista
   e os serviços. Explique que os cartões de ambientes são conceitos, não fotos
   de obras realizadas. Os contatos comerciais continuam em preparação.
2. **Acesso e visão geral.** Entre com a conta de demonstração. Mostre o resumo
   do painel e explique que os dados internos são exclusivos da equipe autorizada.
   Google, LinkedIn e Facebook não estão disponíveis nesta versão.
3. **Clientes e busca.** Abra Clientes e pesquise `Aurora`. O cadastro
   “Cliente Aurora — DEMONSTRAÇÃO” está além dos 125 clientes de teste iniciais;
   isso permite mostrar a busca e a paginação. Não preencha telefone real.
4. **Orçamento e proposta.** Em Orçamentos, pesquise `Aurora`. Abra
   **Itens** para conferir os dois móveis. Feche e use **Visualizar** para
   abrir a proposta detalhada. O documento identifica dados fictícios e a ausência
   de aprovação. **Imprimir / Salvar em PDF** usa a impressão do navegador; confira
   a prévia de impressão antes de salvar. Se o navegador bloquear a janela,
   autorize pop-ups somente para esta prévia local.
5. **Fornecedores, insumos e produção.** Em Fornecedores e Insumos, pesquise
   `DEMONSTRAÇÃO` e mostre o fornecedor Aurora e o MDF de 18 mm. Em Projetos,
   pesquise `Aurora` e abra **Produção e custos**. Mostre os três lançamentos
   e o total. O projeto foi cadastrado separadamente do orçamento neste exemplo;
   não apresente esse cadastro como conversão automática.
6. **Histórico e fechamento.** Mostre o histórico dos cadastros e lançamentos.
   Finalize com: “O sistema reúne clientes, orçamentos, projetos e custos.
   Esta é uma demonstração funcional local. Contatos, integrações e ambiente
   definitivo serão configurados antes do uso real.”

O orçamento começa em análise e o projeto em planejamento. Para manter o exemplo
reutilizável, prefira mostrar sem aprovar, avançar ou acrescentar custos. Caso opte
por testar essas ações, use apenas os registros fictícios e explique a simulação.
O roteiro de preparação não desfaz alterações nem exclui lançamentos.

## Números do exemplo “Cozinha Aurora”

| Composição da proposta | Valor ilustrativo |
| --- | ---: |
| Armário inferior, 1 unidade | R$ 2.400,00 |
| Armário aéreo, 1 unidade | R$ 1.800,00 |
| **Total da proposta** | **R$ 4.200,00** |

| Custos registrados | Cálculo | Total ilustrativo |
| --- | --- | ---: |
| MDF com 10% de perda | 2 × R$ 300,00 × 1,10 | R$ 660,00 |
| Mão de obra | 8 × R$ 50,00 | R$ 400,00 |
| Instalação | 1 × R$ 200,00 | R$ 200,00 |
| **Total de custos lançados** | | **R$ 1.260,00** |

Esses valores não são preços de mercado. A diferença entre proposta e custos
lançados **não comprova lucro**: impostos, frete e outros gastos podem estar ausentes.

## Antes da reunião

- Recarregue a página e confirme o aviso “AMBIENTE DE TESTE”.
- Faça o login e percorra o roteiro uma vez, inclusive a proposta.
- Confira no navegador a legibilidade, os botões e a rolagem em tela de computador
  e em largura equivalente a celular. A validação visual ainda está pendente;
  testes de código não a substituem.
- Não demonstre envio por WhatsApp, recuperação por e-mail ou login social como
  funcionalidades já configuradas. Não faça cadastro de dados reais na prévia.
- Mantenha o computador ligado e o servidor aberto durante a reunião.

## Retomar após fechar o servidor ou reiniciar o computador

O código fica salvo, mas os dados dessa prévia são descartáveis e desaparecem ao
encerrar seu processo. Isso é intencional e não é uma solução de banco permanente.

Na pasta `backend`, com as dependências locais já instaladas, execute:

```powershell
$env:IDEAL_LOCAL_PREVIEW = '1'
$env:ENVIRONMENT = 'test'
& .\.venv\Scripts\python.exe -m uvicorn local_preview:app --app-dir tests --host 127.0.0.1 --port 8765
```

Deixe esse terminal aberto. Em outro terminal, também na pasta `backend`:

```powershell
$env:IDEAL_LOCAL_PREVIEW = '1'
& .\.venv\Scripts\python.exe tests/prepare_presentation.py
```

A preparação usa exclusivamente a prévia em `127.0.0.1:8765`, confere seus avisos,
acessa com a conta sintética e cria apenas o exemplo que falta. Repetir sem alterar
os exemplos não duplica cadastros. Se houver alteração ou duplicidade, ela para
para conferência, sem sobrescrever dados. Execute uma instância por vez.

## O que ainda separa a demonstração da entrega definitiva

Permanecem pendentes: aceite visual em computador/celular, acesso da conta real,
contatos e entrega de e-mail, banco durável com backup e recuperação testados,
ambiente público aprovado e validação após publicação. A tela de custos ainda não
edita nem exclui lançamentos; um fluxo auditado de correção precisa ser definido
antes de usá-la como controle financeiro operacional.

Os seis critérios de conclusão originais continuam em
[operação e aceite](operations.md). Login social e portal de clientes ficam
separados da demonstração administrativa, conforme [escopo de acesso](social-login.md).

# Recuperação de senha por e-mail

## Estado da entrega

O código suporta SMTP e o envio HTTPS opcional pela API do Resend. Os testes usam
transportes simulados: nenhum e-mail real é enviado durante a verificação automática.
O recurso só está concluído em produção depois de configurar o provedor e comprovar
o recebimento e a redefinição de senha em uma caixa de e-mail autorizada.

Serviços web gratuitos do Render bloqueiam conexões de saída nas portas SMTP 25,
465 e 587. O adaptador HTTPS evita depender dessas portas, mas não cria conta,
domínio, credenciais ou assinatura de provedor. [Limitações do Render](https://render.com/docs/free#other-limitations)

## Configuração do servidor

As variáveis abaixo pertencem somente à API, nunca ao frontend ou a arquivos
publicados. Nenhuma chave real deve ser colocada no repositório, em capturas de tela,
nos logs ou no chat.

| Variável | Padrão | Uso |
| --- | --- | --- |
| `EMAIL_PROVIDER` | `smtp` | `smtp`, `resend` ou `disabled`; selecionar `resend` exige as duas configurações seguintes. |
| `RESEND_API_KEY` | ausente | Chave privada de envio, inserida diretamente no ambiente do servidor. |
| `EMAIL_FROM` | ausente | Um endereço válido de remetente do domínio verificado no Resend. |
| `EMAIL_TIMEOUT_SECONDS` | `10` | Tempo máximo de inatividade de cada etapa de conexão/leitura/escrita HTTP; maior que zero e no máximo 30 segundos. |
| `FRONTEND_URL` | URL local em desenvolvimento | Em produção, usar `https://ideal-marcenaria.onrender.com`, onde o link é aberto. |
| `PASSWORD_RESET_EXPIRE_MINUTES` | `30` | Validade do token de recuperação, mínimo de 5 minutos. |

Variáveis opcionais vazias de chave/remetente são tratadas como ausentes. O padrão
`smtp` mantém as configurações existentes e permite iniciar a API sem um serviço de
e-mail; nessa situação, o log informa `missing_configuration`. Isso não equivale a
ter recuperação de senha funcional para usuários em produção.

### Ativação do Resend, a ser feita pelo responsável

1. Escolher e autorizar o provedor e verificar seu domínio de envio. O Resend exige
   domínio sob controle da empresa para envio real; pode ser um subdomínio de
   e-mail, sem trocar o endereço público do site. Aplicar somente os registros DNS
   indicados pelo provedor, após autorização do responsável. [Domínios verificados](https://resend.com/docs/dashboard/domains/introduction)
2. Desativar rastreamento de cliques/abertura no domínio usado para recuperação de
   senha, evitando reescrita desnecessária do link sensível. A documentação do
   provedor recomenda separar esse tipo de mensagem transacional. [Domínios e rastreamento](https://resend.com/docs/dashboard/domains/introduction)
3. Criar uma chave limitada a envio para esse domínio, conforme as opções da conta.
   Não compartilhar o valor; adicioná-lo diretamente em `RESEND_API_KEY` no serviço
   `ideal-marcenaria-api`, área **Environment** do Render.
4. Salvar juntos `EMAIL_PROVIDER=resend`, `EMAIL_FROM` com o remetente verificado e
   `RESEND_API_KEY`. Conferir `FRONTEND_URL` e manter o prazo padrão de 10 segundos
   inicialmente. O servidor recusa a inicialização se Resend for selecionado sem
   chave/remetente válidos. Variáveis secretas marcadas `sync: false` em Blueprint
   não são solicitadas novamente ao atualizar um serviço já existente: o valor
   deve ser inserido diretamente no ambiente.
5. Acompanhar a publicação e executar o teste de aceitação abaixo. O endpoint do
   adaptador é fixo: `https://api.resend.com/emails`, com autorização Bearer e corpo
   JSON contendo remetente, destinatário, assunto e texto. [API de envio do Resend](https://resend.com/docs/api-reference/emails/send-email)

### Compatibilidade SMTP

`EMAIL_PROVIDER=smtp` usa as variáveis existentes: `SMTP_HOST`, `SMTP_PORT` (587),
`SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_STARTTLS` (true), `SMTP_USE_SSL`
(false) e `SMTP_TIMEOUT_SECONDS` (10). Host, usuário, senha e remetente devem ser
configurados juntos. STARTTLS e SSL não podem ficar ativos simultaneamente. O
cliente valida o certificado TLS do servidor. Em produção, não desativar ambas as
formas de TLS; escolher hospedagem e serviço compatíveis com as portas necessárias.

## Segurança e diagnóstico

- A resposta pública continua genérica para conta existente, inexistente, provedor
  indisponível ou e-mail aceito. Produção nunca retorna `debug_token`.
- Links usam o fragmento `/#reset_token=...`, sem colocar o token na query string.
- O cliente HTTPS não segue redirecionamentos e não faz tentativas automáticas.
  Uma falha de leitura pode ocorrer após o provedor já ter aceitado o envio; uma
  repetição automática poderia gerar mensagens duplicadas. [Transportes HTTPX](https://www.python-httpx.org/advanced/transports/)
- Os prazos HTTP são aplicados por etapa de rede, não prometem um prazo total de
  entrega do e-mail. [Prazos HTTPX](https://www.python-httpx.org/advanced/timeouts/)
- Os logs contêm somente provedor, motivo fixo, código HTTP ou tipo da exceção.
  Nunca incluem destinatário, nome, credenciais, token, texto da mensagem ou corpo
  de erro devolvido pelo provedor.

Eventos úteis: `email_delivery_skipped` (desativado/sem configuração),
`email_delivery_failed` (falha de transporte, rejeição ou resposta inválida) e
`email_delivery_accepted` (aceite da mensagem pelo provedor; não prova chegada à
caixa de entrada). Não usar o endpoint `/ready` como prova de envio de e-mail.

## Teste de aceitação obrigatório antes de concluir

Com autorização e uma conta de teste controlada pelo responsável:

1. Solicitar recuperação pela tela; conferir a mensagem genérica e ausência de
   token na resposta da API ou nos logs.
2. Confirmar o recebimento na caixa de entrada, incluindo eventual pasta de spam,
   e verificar remetente, domínio e link do site correto.
3. Abrir o link e redefinir a senha. Confirmar login com a nova senha e rejeição da
   senha antiga, sem registrar valores sensíveis na evidência de entrega.
4. Tentar reutilizar o link: deve ser rejeitado. Conferir expiração e revogação de
   sessões renováveis no ambiente de teste; não perturbar contas reais.
5. Registrar data, ambiente, resultado e responsável, sem endereço completo,
   senha ou token. Se houver falha, consultar os eventos seguros acima e o painel
   privado do provedor. A etapa continua pendente até este teste passar.

Verificação automatizada, sem internet, a partir da raiz do repositório:

```powershell
& .\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_email_delivery.py backend/tests/test_config_security.py backend/tests/test_production_contract.py -q
```

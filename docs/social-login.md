# Login por Google, LinkedIn e Facebook

## Implementado

O frontend apresenta as três opções, marcadas como **Em preparação**, sem redirecionamento, coleta de senha do provedor ou concessão de acesso. O login atual por e-mail/senha da equipe é preservado. O formulário pode rolar em telas baixas.

## Ainda não implementado nem configurado

- Aplicativos OAuth/OIDC registrados nos provedores, credenciais no servidor e URLs de retorno autorizadas.
- Rotas de início/retorno, validação de state/nonce e tokens, troca de código no servidor e criação segura da sessão.
- Vínculo de identidade externa por provedor e identificador estável. Não unir contas somente pelo e-mail sem política segura de vinculação.
- Área de cliente com acesso exclusivamente aos próprios dados. O painel atual exige administrador; login social não deve conceder esse papel.
- Fluxos de consentimento negado, conta sem e-mail, sessão expirada, logout e testes completos com contas autorizadas.

Não basta remover `disabled` dos botões. Eles só devem ser habilitados após implementar, configurar e testar o fluxo completo no backend. Não colocar client secrets no frontend, no Git ou no chat.

Referências oficiais: [Google](https://developers.google.com/identity/protocols/oauth2/web-server), [LinkedIn](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2), [Facebook](https://developers.facebook.com/docs/facebook-login/manually-build-a-login-flow/).

# Atendimento comercial

Edite apenas os dados públicos em `frontend/site-config.js`:

- `whatsappNumber`: número da empresa com DDI (Brasil: `+55`), DDD e número.
  Um número brasileiro de 10 ou 11 dígitos com DDD recebe `55` automaticamente.
- `contactEmail`: endereço comercial opcional, usado se não houver WhatsApp válido.
- `locationText` e `businessHours`: localização e horário aprovados pela empresa.

O arquivo é enviado ao navegador: nunca coloque senha, token ou chave de API nele.
Publique a mudança pelo fluxo de Pull Request e confirme o destinatário antes de
enviar uma mensagem de teste. Alterar o arquivo não envia mensagens automaticamente.

Quando nenhum canal está configurado, os botões levam à seção de contato e a
interface informa que nenhum pedido foi enviado. Isso não substitui a ativação do
número comercial: a captação de orçamentos continua pendente até o titular informá-lo.

Teste automatizado: `node frontend/public-contact.test.cjs`.

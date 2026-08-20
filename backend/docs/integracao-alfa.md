# Integração Alfa Transportes

## Situação

A Alfa Transportes confirma que possui integração por API e que a API de cotação depende de liberação dos setores regional e comercial. O contrato técnico de cotação não está publicado no site. A documentação pública encontrada cobre somente rastreamento (`v1.2`).

Por segurança, a transportadora deve permanecer com a integração inativa até que a Alfa forneça:

- chave de API exclusiva da Modial;
- URL base e endpoint de cotação;
- ambiente de homologação, se existir;
- método HTTP e local de envio da chave;
- modelo completo do request e da resposta;
- campos obrigatórios, tipos, unidades e casas decimais;
- identificação do CNPJ pagador/remetente;
- códigos de serviço/modalidade;
- limites de requisição, timeout e política de retentativa;
- catálogo de erros e exemplos de sucesso e falha;
- regras de liberação por IP, caso existam.

## Mensagem para solicitação

Assunto: Liberação e documentação da API de Cotação — Modial

Olá, equipe Alfa Transportes.

Estamos integrando o sistema de gestão de fretes FreteWay à Alfa Transportes para realizar cotações automáticas usando o contrato comercial da Modial (CNPJ 04.917.818/0001-24).

Solicitamos a liberação da API de cotação junto aos setores regional e comercial e o envio da chave exclusiva da empresa. Precisamos também da documentação técnica atualizada contendo URLs de homologação e produção, autenticação, endpoint, modelo de request/response, campos obrigatórios, códigos de serviço, limites de uso e catálogo de erros.

O nosso sistema já possui armazenamento criptografado de credenciais, timeout, retentativas, auditoria e tratamento de indisponibilidade. Assim que recebermos o contrato técnico e a chave, concluiremos a homologação.

Por favor, confirmem também se o CNPJ da Modial está habilitado para cotação e vinculado à tabela/negociação comercial correta, e se há necessidade de liberação de IP.

Obrigado.

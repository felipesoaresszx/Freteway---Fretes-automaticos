# Integração JAMEF

O adapter utiliza as APIs REST oficiais de autenticação e cotação da JAMEF.

## Produção

- Autenticação: `https://api.jamef.com.br/auth/v1/login`
- Cotação: `https://api.jamef.com.br/calculo-frete/v1/cotacao`

Para homologação, substitua o host por `api-qa.jamef.com.br`. As credenciais dos
dois ambientes são independentes.

## Configuração

Na transportadora JAMEF, selecione cálculo por API e preencha:

- autenticação `Login JAMEF + Bearer`;
- usuário e senha fornecidos pela JAMEF;
- CNPJ/CPF do pagador do frete;
- modal rodoviário ou aéreo;
- filial de origem, quando aplicável.

A senha é criptografada no banco e nunca retorna pela API. O JWT da JAMEF é
mantido apenas em memória e renovado antes de expirar. Respostas de erro não
incluem credenciais nem o corpo devolvido pelo provedor.

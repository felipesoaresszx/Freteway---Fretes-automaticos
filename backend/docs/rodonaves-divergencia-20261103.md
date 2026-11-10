# Rodonaves: comparação entre simulação e portal em 03/11/2026

## Evidência em produção

- Cotação salva: `e23cc46a-683e-42f0-90d6-9f6e5a559994`, criada em `2026-11-03 12:24:50.947224` (timestamp do banco).
- Origem: 07042-180, Guarulhos/SP. Destino: 92027-201, Canoas/RS.
- Nota: R$ 1.000,00; um volume de 10 kg, 57 × 57 × 34 cm.
- Resultado persistido: R$ 208,27, três dias, provider `rodonaves`, protocolo `0`, aviso de simulação.
- Transportadora: método `api`, integração ativa, ambiente `producao`; nenhuma entrada em `carrier_integrations` para esse cadastro.
- Backend e worker têm o mesmo SHA-256 do adapter: `a27e4212debff10ac33988e646f69421b226cdb49809f8912dda1fd8243ef1b2`.
- Ambos executam `RodonavesAdapter`, com POST fixo em `https://quotation-apigateway.rte.com.br/api/v1/simula-cotacao`.
- O campo `endpoint_cotacao` no banco ainda contém `/api/v1/gera-cotacao`. Esse campo não é utilizado pelo adapter específico; portanto não representa o endpoint efetivamente chamado.

## Repetição da simulação

Executada diretamente no backend em produção, com a configuração existente e os volumes salvos, sem alterar banco, código ou serviços. A instrumentação temporária em memória observou a requisição e a resposta; credenciais e tokens não foram exibidos.

```json
{
  "OriginZipCode": "07042180",
  "OriginCityId": 9183,
  "DestinationZipCode": "92027201",
  "DestinationCityId": 7533,
  "TotalWeight": 10,
  "EletronicInvoiceValue": 1000,
  "CustomerTaxIdRegistration": "[CNPJ MODIAL configurado]",
  "TotalPackages": 1,
  "Packs": [{"AmountPackages": 1, "Weight": 10, "Length": 57, "Height": 34, "Width": 57}]
}
```

Resposta HTTP 200, campos relevantes:

```json
{"Value":208.27,"DeliveryTime":3,"ProtocolNumber":"0","Message":null,"ActiveDeliveryTime":true,"DeliveryDaysOnError":false,"DeliveryPhysicalPerson":2,"DeliveryLegalPerson":0}
```

O adapter devolveu exatamente R$ 208,27. Não houve cálculo por tabela, mock ou alteração do preço retornado nessa execução.

## Limite do diagnóstico

A imagem do portal mostra R$ 232,67, três dias, protocolo `225360387`: diferença de R$ 24,40. A diferença entre o valor bruto da simulação e o portal está confirmada. A imagem não contém a requisição do portal nem a composição detalhada das taxas; não é possível atribuir a diferença a imposto, tabela comercial, cliente ou cubagem sem essas evidências. Não foi gerada cotação definitiva via `gera-cotacao`.

Para fechar a causa comercial, comparar a requisição completa do portal e a composição do protocolo `225360387` com a simulação acima. Não aplicar fator de correção ao preço sem essa confirmação.

Contrato consultado: https://dev.rodonaves.com.br/v2.0/reference/apiv1simula-cotacaopost-1

## Ajuste autorizado e documentação recebida

Em 03/11/2026, o campo `endpoint_cotacao` do cadastro acima foi alterado em produção de `/api/v1/gera-cotacao` para `/api/v1/simula-cotacao` e relido após commit. A URL base e a API ativa foram confirmadas. A alteração apenas alinha o cadastro ao endpoint já executado; não muda o cálculo nem os resultados históricos.

O OpenAPI fornecido pelo usuário documenta `/api/v1/gera-cotacao`, não `/simula-cotacao`. Além dos campos enviados na simulação, exige `ReceiverCpfcnp`, `ContactName` e `ContactPhoneNumber`. Também declara campos opcionais como `PayerSelected`, `EmissionUser`, `CustomerEmail`, `PickupAddress` e `DestinationAddress`. O contrato fornecido não define os valores possíveis de `PayerSelected`, portanto não permite escolher um tomador com segurança.

Não se deve concluir que esses campos faltam no contrato de simulação, nem que algum deles explica os R$ 24,40, apenas comparando contratos de endpoints diferentes. O parser atual já aceita `FreightValue`/`ProtocolId` do documento e `Value`/`ProtocolNumber` observados em produção. Mantido o endpoint de simulação; nenhuma cotação definitiva foi gerada.

# Carvalima — investigação da composição e do arredondamento

Data: 05/10/2026. Escopo autorizado: destinos documentados em AC, MS, MT, PA e RO. Esta análise não alterou a aplicação nem o cadastro em produção.

## Evidência documental

Foi relida a proposta original, incluindo as observações e generalidades das páginas finais. O documento informa ICMS adicionado ao frete e ICMS/ISS fora dos preços, conforme legislação, mas não especifica percentual, base ou método de arredondamento. Não há PIS/COFINS, percentual de 14%, percentual de 13,984% ou fator de 1,162572233814 registrados na proposta. TDA depende de negociação; coleta/entrega/redespacho depende de localidade. Nenhuma das listas complementares tem correspondência nos quatro casos analisados.

Taxas de agendamento, armazenagem, devolução, reentrega e manuseio difícil dependem de ocorrência/serviço, não comprovados nas cotações. Não foram somadas para aproximar os resultados. O valor de agendamento de R$ 5,00 não explica simultaneamente diferenças de R$ 6,28, R$ 24,27, R$ 56,64 e R$ 64,90.

## Conferência numérica

O script `tmp/carvalima_formula_audit.py` calcula as parcelas originais com Decimal e compara quatro alternativas: precisão integral; frete-base integral com adicionais arredondados (comportamento atual); todas as parcelas arredondadas; todas truncadas. O resultado detalhado fica em `tmp/carvalima-validacao/formula-audit.json`.

Somente a alternativa que conserva o frete-base integral e arredonda os adicionais admite um único fator multiplicativo capaz de produzir todos os totais, arredondando o total uma vez. O intervalo de fatores compatíveis com as quatro referências é de 1,162571874752621314507365588 até 1,162572592875725928757259288. O ponto médio experimental é 1,162572233814173621632312438.

Fórmula exclusivamente experimental:

`total = arredondar_centavos(subtotal_sem_imposto × 1,162572233814173621632312438)`

| Destino | Subtotal de precisão original + adicionais arredondados | Simulação experimental | Portal |
| --- | ---: | ---: | ---: |
| São Miguel do Guaporé/RO | 648,824 | 754,30 | 754,30 |
| Rio Branco/AC, usando volume do portal | 699,56299744 | 813,29 | 813,29 |
| Campo Grande/MS | 71,9616 | 83,66 | 83,66 |
| Juína/MT | 277,914 | 323,10 | 323,10 |

Esse fator equivale matematicamente a gross-up efetivo de aproximadamente 13,9838394%, sem comprovar qualquer imposto legal ou taxa comercial. O percentual foi ajustado aos exemplos; não é uma fórmula documentada pela transportadora.

Ao inferir o fator a partir de três casos e prever o quarto, a aproximação erra R$ 0,01 para RO e MT. Isso mostra a sensibilidade aos centavos e a ausência de validação independente. Usar 13,984% diretamente na regra atual também não é equivalente, pois o motor arredonda o imposto antes do total: retorna 754,30 / 813,29 / 83,66 / 323,09. Não foi proposta mudança global de arredondamento para outras transportadoras.

## Limites e próximos dados necessários

A composição/base usada pelo portal ainda precisa ser confirmada. A tabela permite validar a tarifa-base e os adicionais expressos, mas não fundamenta o fator experimental. No caso de AC, as medidas da imagem somam 0,818436 m³ e o portal informa 0,8379 m³; a simulação que coincide usa necessariamente o dado do portal, superior ao limite de 250 kg cubados. Essa divergência de entrada precisa ser corrigida na comparação, não ocultada em uma fórmula.

Nenhuma taxa, imposto ou fator foi adicionado em produção. PA ainda não possui uma cotação de referência entre os exemplos apresentados. Não é possível declarar homologadas todas as rotas a partir de um ajuste aos quatro totais; os testes existentes da tabela verificam as tarifas documentadas, não a composição desconhecida do portal.

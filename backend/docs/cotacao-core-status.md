# Núcleo de cotação — diagnóstico de 28/08/2026

## Correções aplicadas

- O cálculo por tabela não reutiliza mais a primeira abrangência quando a UF de destino não está coberta.
- Uma tarifa vinculada a outra abrangência não é mais usada como fallback.
- O peso cubado usa `volume_total_m3` da carga completa quando disponível.
- A elegibilidade aceita UF de origem/destino e reconhece coberturas estaduais (`STATE`), além de nacional e faixa de CEP.
- O reprocessamento cria um novo job a partir do payload original, rejeita duplicidade enquanto há job ativo e atualiza os resultados existentes por transportadora.
- Foram expostos endpoints para reprocessar uma cotação e consultar o status de seu job.
- O histórico no frontend oferece a ação **Reprocessar** e atualiza a listagem após o enfileiramento.

## Evidência de validação

- Backend: `192 passed, 3 skipped`.
- Frontend: `16 passed`; build TypeScript/Vite concluído.
- Worker reiniciado e processando normalmente.
- Execuções reais observadas no worker: Jamef com cotação bem-sucedida; Risso/Senior com cotação bem-sucedida; dois domínios SSW respondendo de forma independente, inclusive com retorno comercial negativo sem interromper os demais provedores.

## Estado das integrações

- **Jamef:** adaptador e autenticação funcionais; execução real bem-sucedida.
- **Risso/Senior:** provider funcional; execução real bem-sucedida. Continua dependente de credenciais e disponibilidade da Senior.
- **SSW:** provider funcional; o código comercial devolvido pelo domínio determina sucesso/indisponibilidade da proposta.
- **Braspress e Correios:** adaptadores cobertos por testes com respostas simuladas; a validação real depende das credenciais/configuração de cada conta.
- **Tabela de frete:** cálculo local funcional e agora estrito quanto a cobertura e vínculo da tarifa.
- **Portal, e-mail e manual:** são modalidades descobertas/cadastradas, mas não constituem API automática de cotação.
- **Transportadora sem integração ativa nem tabela vigente:** permanece sem proposta; o sistema não fabrica preço.

## Endpoints operacionais

- `POST /api/v1/cotacoes/{cotacao_id}/reprocessar`
- `GET /api/v1/cotacoes/{cotacao_id}/job`

O reprocessamento é assíncrono. A resposta HTTP confirma o enfileiramento; o resultado final deve ser acompanhado pelo endpoint do job ou pela atualização automática da tela.

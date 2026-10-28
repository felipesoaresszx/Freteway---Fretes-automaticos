# Rispa / Rispar — FreteCalc

A cotação por API usa GET https://api.fretecalc.com/v1/frete e token no
parâmetro `token`. A credencial permanece criptografada no banco e não é
incluída no código, nos retornos da aplicação ou nas mensagens de erro HTTP.

O adapter converte cada grupo de volumes para `prods` da Tray, com dimensões
em metros, cubagem por unidade, quantidade e peso por unidade em kg.
Como o formulário de cotação informa somente o valor total da nota, o valor
unitário é distribuído igualmente entre todos os volumes.

O retorno é XML. Somente resultados cujo serviço é Rispa/Rispar são aceitos.
`valor` é o frete, `prazo_max` é o prazo em dias e `peso` é conservado no
detalhamento. Retornos vazios não viram frete zero.

Na configuração de API, os campos do protocolo são preenchidos e fixados
automaticamente para cadastros cujo nome começa com Rispa ou Rispar.
Salvar a configuração seleciona o método de cálculo API.

Para ativação administrativa no servidor, a partir de backend, forneça
`RISPA_TOKEN` pelo ambiente e execute `python -m scripts.configure_rispa`.
O script exige exatamente um cadastro existente, preserva tabelas e documentos
e ativa o cadastro para cálculo por API. Não cria cadastros duplicados.

Validação em 09/10/2026: chamada real pelo adapter com CEP 07042180 → 24430380,
10 volumes, 225 kg e nota de R$ 4.852,80 retornou R$ 500,24, prazo de 14 dias
e peso calculado de 378,452 kg. Publicação e ativação no banco do servidor
ainda precisam ser executadas; banco local indisponível.


## Publicacao em 28/10/2026

Integracao especifica Rispa publicada diretamente no backend e worker do servidor.
O fluxo de API deixou de selecionar ApiGenericaAdapter para Rispa/Rispar e usa
RispaAdapter (GET com volumes no formato Tray e leitura do XML). O adaptador
generico permanece para as demais transportadoras. A tabela historica nao e
consultada porque o cadastro da Rispa usa metodo_calculo=api.

Validacao real por executar_cotacao com o cadastro de producao: provider=rispa,
status=success, R$ 500,24 e 14 dias, para a carga de referencia acima.
Health publico: HTTP 200, status=ready e database=ok. Backend saudavel e worker
iniciado. Oito testes automatizados da integracao passaram localmente.

Backup de fontes e imagens anteriores: servidor, diretorio
/home/ubuntu/freteway-server-backups/rispa-20261028 e tags Docker
freteway-backend:before-rispa-20261028 / freteway-worker:before-rispa-20261028.
As alteracoes desta publicacao tambem sao incorporadas ao Git, para que
proximos deploys automaticos mantenham a integracao especifica da Rispa.

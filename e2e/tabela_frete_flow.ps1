param(
    [string]$ApiBase = "http://localhost:8000/api/v1"
)

$ErrorActionPreference = "Stop"
$healthBase = $ApiBase -replace "/api/v1$", ""
for ($tentativa = 0; $tentativa -lt 30; $tentativa++) {
    try {
        $health = Invoke-RestMethod -Method Get -Uri "$healthBase/health"
        if ($health.status -eq "ok") { break }
    }
    catch {
        Start-Sleep -Seconds 1
    }
}
if ($health.status -ne "ok") { throw "API nao ficou pronta para o teste E2E" }
$login = Invoke-RestMethod -Method Post -Uri "$ApiBase/auth/login" -ContentType "application/json" -Body '{"email":"admin@fretesystem.com","password":"admin123"}'
$headers = @{ Authorization = "Bearer $($login.access_token)" }
$transportadora = (Invoke-RestMethod -Method Get -Uri "$ApiBase/transportadoras" -Headers $headers) | Select-Object -First 1
$codigo = "E2E-$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"
$tabelaBody = @{
    transportadora_id = $transportadora.id
    nome = "Tabela E2E"
    codigo = $codigo
    versao = "2026.1"
    moeda = "BRL"
    fator_cubagem = 300
    data_inicio = "2026-08-01T00:00:00"
    data_fim = "2027-08-31T23:59:59"
} | ConvertTo-Json
$tabela = Invoke-RestMethod -Method Post -Uri "$ApiBase/tabelas-frete" -Headers $headers -ContentType "application/json" -Body $tabelaBody

try {
    $fixture = (Resolve-Path "$PSScriptRoot/../backend/tests/fixtures/tabela_frete_e2e.csv").Path
    $upload = (curl.exe -sS -X POST "$ApiBase/tabelas-frete/$($tabela.id)/upload" -H "Authorization: Bearer $($login.access_token)" -F "arquivo=@$fixture;type=text/csv") | ConvertFrom-Json
    $analise = Invoke-RestMethod -Method Post -Uri "$ApiBase/tabelas-frete/$($tabela.id)/analisar?documento_id=$($upload.documento_id)" -Headers $headers
    $revisao = Invoke-RestMethod -Method Get -Uri "$ApiBase/tabelas-frete/$($tabela.id)/revisao" -Headers $headers
    Invoke-RestMethod -Method Post -Uri "$ApiBase/tabelas-frete/$($tabela.id)/aprovar" -Headers $headers -ContentType "application/json; charset=utf-8" -Body '{"motivo":"Aprovacao E2E"}' | Out-Null
    $ativa = Invoke-RestMethod -Method Post -Uri "$ApiBase/tabelas-frete/$($tabela.id)/ativar" -Headers $headers

    $cotacaoBody = @{
        origem = @{ cep = ""; cidade = ""; uf = "" }
        destino = @{ cep = ""; cidade = ""; uf = "" }
        valor_nf = 
        peso = 
        volumes = @(@{ quantidade = ; comprimento_cm = ; largura_cm = ; altura_cm = ; peso_kg =  })
        transportadoras_ids = @($transportadora.id)
    } | ConvertTo-Json -Depth 6 -Compress
    $cotacao = Invoke-RestMethod -Method Post -Uri "$ApiBase/cotacoes" -Headers $headers -ContentType "application/json" -Body $cotacaoBody
    for ($i = 0; $i -lt 20; $i++) {
        Start-Sleep -Milliseconds 500
        $resultado = Invoke-RestMethod -Method Get -Uri "$ApiBase/cotacoes/$($cotacao.id)" -Headers $headers
        if ($resultado.status -ne "processing") { break }
    }

    if ($analise.status -ne "review") { throw "Analise nao chegou a review" }
    if ($revisao.dados_extraidos.tarifas.Count -ne 2) { throw "Revisao sem duas tarifas" }
    if ($ativa.status -ne "active") { throw "Tabela nao foi ativada" }
    if ($resultado.status -ne "completed") { throw "Cotacao falhou: $($resultado.status)" }
    if ($resultado.resultados[0].valor_frete -ne 300) { throw "Frete incorreto: $($resultado.resultados[0].valor_frete)" }

    [pscustomobject]@{
        status = "ok"
        tabela_id = $tabela.id
        cotacao_id = $cotacao.id
        tarifas = $revisao.dados_extraidos.tarifas.Count
        valor_frete = $resultado.resultados[0].valor_frete
        prazo_dias = $resultado.resultados[0].prazo_dias
    }
}
finally {
    Invoke-RestMethod -Method Post -Uri "$ApiBase/tabelas-frete/$($tabela.id)/cancelar?motivo=limpeza-e2e" -Headers $headers | Out-Null
}

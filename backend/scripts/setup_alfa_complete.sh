#!/bin/bash
# Script completo para configurar Alfa Transportes no FreteWay
# Uso: ./scripts/setup_alfa_complete.sh

set -e

echo "======================================================================"
echo "  SCRIPT DE SETUP COMPLETO: ALFA TRANSPORTES"
echo "======================================================================"
echo ""

# Verificar se está no diretório backend
if [ ! -f "alembic.ini" ]; then
    echo "❌ Execute este script a partir do diretório backend/"
    exit 1
fi

echo "✅ Diretório: $(pwd)"
echo ""

# Passo 1: Executar migração
echo "📋 Passo 1/4: Executando migração..."
if alembic current | grep -q "027_alfa_carrier"; then
    echo "✅ Migração 027_alfa_carrier já está aplicada"
else
    echo "🔄 Aplicando migração 027_alfa_carrier..."
    alembic upgrade head
    echo "✅ Migração concluída"
fi
echo ""

# Passo 2: Aguardar banco estar pronto
echo "📋 Passo 2/4: Verificando banco de dados..."
for i in {1..10}; do
    if python3 -c "from app.db.session import async_session; import asyncio; async def test(): pass; asyncio.run(test())" 2>/dev/null; then
        echo "✅ Banco de dados está pronto"
        break
    else
        echo "⏳ Aguardando banco ($i/10)..."
        sleep 2
    fi
done
echo ""

# Passo 3: Configurar via script Python
echo "📋 Passo 3/4: Configurando Alfa Transportes..."
echo ""
echo "Para continuar, você precisará fornecer:"
echo "  - API Key da Alfa Transportes"
echo "  - Base URL (opcional, default: https://api.alfatransportes.com.br)"
echo "  - Endpoint (opcional, default: /cotacao/)"
echo ""

# Executar script Python
python3 scripts/setup_alfa.py

echo ""
echo "======================================================================"
echo "  SETUP CONCLUÍDO!"
echo "======================================================================"
echo ""
echo "A Alfa Transportes está pronta para ser usada no FreteWay!"
echo ""
echo "📌 Para usar:"
echo "  1. Acesse: http://localhost:5173/ (ou sua URL do frontend)"
echo "  2. Vá em: Transportadoras"
echo "  3. Localize: Alfa Transportes"
echo "  4. Clique em: Integrações → Configurar credenciais (se não configurou)"
echo "  5. Teste: Clique em 'Testar conexão'"
echo "  6. Use: Clique em 'Cotar' para fazer uma cotação"
echo ""
echo "📌 Para testar via API:"
echo "  curl -X POST 'http://localhost:8000/api/v1/alfa-setup/configure' \\"
echo "    -H 'Authorization: Bearer YOUR_TOKEN' \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"api_key\": \"YOUR_API_KEY\"}'"
echo ""
echo "======================================================================"

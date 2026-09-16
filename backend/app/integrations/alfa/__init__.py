"""Integração com Alfa Transportes.

Esta integração implementa cotação de frete via API da Alfa Transportes.

Arquitetura:
- client.py: Cliente HTTP para a API
- schemas.py: Schemas Pydantic para validação
- exceptions.py: Exceções específicas
- mapper.py: Conversão entre modelos
- provider.py: Implementação do CarrierAdapter

Para cadastrar:
1. Criar transportadora com código 'alfa'
2. Criar integração API com adapter_code='alfa'
3. Configurar credenciais: api_key (obrigatório), base_url, endpoint (opcionais)

Endereço padrão:
- base_url: https://api.alfatransportes.com.br
- endpoint: /cotacao/

NOTA: A Alfa confirma possessão de API, mas acesso depende de liberação regional/comercial.
"""

from app.integrations.alfa.provider import AlfaProvider

__all__ = ["AlfaProvider"]

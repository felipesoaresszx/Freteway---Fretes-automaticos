"""Municipios das regioes imediatas usadas pela proposta CIF.

Fonte: API de Localidades do IBGE, consultada pelos identificadores de regiao
imediata em 22/09/2026. Os nomes sao normalizados pelo parser antes do uso.
"""

REGIOES_IMEDIATAS_IBGE = {
    ("PA", "BELEM"): {
        "id": 150001,
        "cep_start": "66000000",
        "cep_end": "68499999",
        "municipios": (
            "Acará", "Ananindeua", "Barcarena", "Belém", "Benevides", "Bujaru",
            "Colares", "Concórdia do Pará", "Marituba", "Santa Bárbara do Pará",
            "Santa Izabel do Pará", "Santo Antônio do Tauá", "São Caetano de Odivelas",
            "Tomé-Açu", "Vigia",
        ),
    },
    ("PA", "MARABA"): {
        "id": 150009,
        "cep_start": "68500000",
        "cep_end": "68999999",
        "municipios": (
            "Abel Figueiredo", "Bom Jesus do Tocantins", "Brejo Grande do Araguaia",
            "Itupiranga", "Jacundá", "Marabá", "Nova Ipixuna", "Palestina do Pará",
            "Piçarra", "Rondon do Pará", "São Domingos do Araguaia",
            "São Geraldo do Araguaia", "São João do Araguaia",
        ),
    },
    ("MA", "SAO LUIS"): {
        "id": 210001,
        "cep_start": "65000000",
        "cep_end": "65699999",
        "municipios": (
            "Alcântara", "Axixá", "Bacabeira", "Cachoeira Grande", "Icatu", "Morros",
            "Paço do Lumiar", "Presidente Juscelino", "Raposa", "Rosário", "Santa Rita",
            "São José de Ribamar", "São Luís",
        ),
    },
    ("MA", "BACABAL"): {
        "id": 210010,
        "cep_start": "65700000",
        "cep_end": "65799999",
        "municipios": (
            "Altamira do Maranhão", "Alto Alegre do Maranhão", "Bacabal", "Bom Lugar",
            "Brejo de Areia", "Conceição do Lago-Açu", "Lago da Pedra", "Lago Verde",
            "Lagoa Grande do Maranhão", "Marajá do Sena", "Olho d'Água das Cunhãs",
            "Paulo Ramos", "São Luís Gonzaga do Maranhão", "São Mateus do Maranhão",
            "Satubinha", "Vitorino Freire",
        ),
    },
    ("MA", "IMPERATRIZ"): {
        "id": 210019,
        "cep_start": "65900000",
        "cep_end": "65999999",
        "municipios": (
            "Amarante do Maranhão", "Buritirana", "Campestre do Maranhão", "Cidelândia",
            "Davinópolis", "Estreito", "Governador Edison Lobão", "Imperatriz",
            "João Lisboa", "Lajeado Novo", "Montes Altos", "Porto Franco",
            "Ribamar Fiquene", "São João do Paraíso", "São Pedro da Água Branca",
            "Senador La Rocque", "Vila Nova dos Martírios",
        ),
    },
    ("MA", "BALSAS"): {
        "id": 210022,
        "cep_start": "65800000",
        "cep_end": "65899999",
        "municipios": (
            "Alto Parnaíba", "Balsas", "Carolina", "Feira Nova do Maranhão",
            "Fortaleza dos Nogueiras", "Loreto", "Nova Colinas", "Riachão", "Sambaíba",
            "São Félix de Balsas", "São Raimundo das Mangabeiras", "Tasso Fragoso",
        ),
    },
    ("TO", "ARAGUAINA"): {
        "id": 170005,
        "cep_start": "77000000",
        "cep_end": "77999999",
        "municipios": (
            "Ananás", "Angico", "Aragominas", "Araguaína", "Araguanã", "Arapoema",
            "Babaçulândia", "Barra do Ouro", "Campos Lindos", "Carmolândia", "Darcinópolis",
            "Filadélfia", "Goiatins", "Muricilândia", "Nova Olinda", "Pau D'Arco",
            "Piraquê", "Riachinho", "Santa Fé do Araguaia", "Wanderlândia", "Xambioá",
        ),
    },
}

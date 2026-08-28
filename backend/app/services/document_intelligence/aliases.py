"""Vocabulário canônico compartilhado pelos classificadores de documentos."""

FIELD_ALIASES={
    "zip_start": {"cep inicial","cep inicio","cep de","inicio faixa","faixa de cep"},
    "zip_end": {"cep final","cep fim","cep ate","fim faixa"},
    "destination": {"destino","localidade","praca","praça","cidade","uf","regiao","região"},
    "weight": {"peso","kg","faixa de peso","peso taxado","até kg","acima de"},
    "price": {"frete","tarifa","valor","preco","preço","r$","frete peso"},
    "excess_weight": {"kg excedente","peso excedente","excedente ou fracao","excedente ou fração"},
    "minimum_freight": {"frete minimo","frete mínimo","minimo de cobranca","mínimo de cobrança"},
    "gris": {"gris","gerenciamento de risco"},
    "ad_valorem": {"ad valorem","advalorem","seguro","percentual nf"},
    "toll": {"pedagio","pedágio"},
    "pickup": {"coleta","coleta programada"},
    "delivery": {"entrega","entrega programada"},
}

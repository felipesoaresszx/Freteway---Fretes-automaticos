import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from app.services.enrichment.normalization import normalize_cep, normalize_cnpj, states_in_text
from app.services.enrichment.ports import CrawledPage, SearchProvider


class _Content(HTMLParser):
    def __init__(self): super().__init__(); self.text=[]; self.links=[]
    def handle_data(self, data): self.text.append(data)
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href: self.links.append(href)


def page_content(page: CrawledPage) -> tuple[str, list[str]]:
    parser = _Content(); parser.feed(page.content)
    return " ".join(parser.text), [urljoin(page.url, link) for link in parser.links]


@dataclass(frozen=True)
class Detection:
    kind: str
    value: str
    url: str
    text: str
    confidence: float
    metadata: dict


class OfficialWebsiteDiscovery:
    BLOCKED = ("facebook.com", "instagram.com", "linkedin.com", "google.com", "reclameaqui.com.br", "cnpj", "guias")
    def __init__(self, search: SearchProvider): self.search = search
    async def discover(self, *, cnpj=None, legal_name=None, trade_name=None, city=None, state=None):
        query = " ".join(filter(None, [f'"{cnpj}"' if cnpj else None, legal_name or trade_name, city, state, "transportadora site oficial"]))
        results = await self.search.search(query)
        for rank, result in enumerate(results):
            host = urlparse(result.url).netloc.lower()
            if any(blocked in host for blocked in self.BLOCKED): continue
            haystack = f"{result.title} {result.snippet}".lower()
            identity = (legal_name or trade_name or "").split()[0].lower()
            score = min(.95, .65 + (.2 if identity and identity in haystack + host else 0) + (.1 if cnpj and cnpj in re.sub(r'\D','',haystack) else 0) - rank * .03)
            return {"url": result.url, "confidence_score": max(.4, score)}
        return None


class IntegrationDetector:
    def detect(self, pages: list[CrawledPage]) -> list[Detection]:
        found={}
        patterns=[("SSW", r"ssw\.inf\.br|\bssw(?:cotacao|\s*925)?\b", .98, "SSW"),("API_REST", r"swagger(?:\.json)?|openapi(?:\.json)?|\bapi\s+rest\b|\bbearer\b|\boauth\b", .95, None),("API_SOAP", r"\bsoap\b|\bwsdl\b", .95, None),("WEBSERVICE", r"\bweb\s*service\b", .90, None),("EDI", r"\bedi\b", .88, None),("SENIOR", r"\bsenior\b", .90, "SENIOR"),("PORTAL", r"portal.{0,30}(cotacao|cliente)|cotacao.{0,30}login", .82, None)]
        for page in pages:
            text, links=page_content(page); haystack=" ".join([text,*links])
            for kind, pattern, score, provider in patterns:
                match=re.search(pattern, haystack, re.I)
                if match and kind not in found: found[kind]=Detection(kind, kind, page.url, match.group(0)[:500], score, {"provider":provider})
        return list(found.values())


class CoverageDetector:
    CEP_RANGE=re.compile(r"(\d{5}[-.]?\d{3})\s*(?:ate|até|a|-)\s*(\d{5}[-.]?\d{3})", re.I)
    def detect(self, pages):
        result=[]
        for page in pages:
            text,_=page_content(page)
            if not re.search(r"abrang[eê]ncia|cobertura|onde atendemos|estados atendidos|pra[cç]as atendidas|[aá]rea de atua[cç][aã]o", text, re.I): continue
            for uf in states_in_text(text): result.append(Detection("STATE",uf,page.url,uf,.90,{"uf":uf,"pickup":True,"delivery":True}))
            for start,end in self.CEP_RANGE.findall(text): result.append(Detection("CEP",f"{start}-{end}",page.url,f"{start} até {end}",.95,{"cep_start":normalize_cep(start),"cep_end":normalize_cep(end),"pickup":True,"delivery":True}))
        return list({(x.kind,x.value,x.url):x for x in result}.values())


class FreightTableDetector:
    def detect(self,pages):
        result=[]
        for page in pages:
            text,links=page_content(page)
            relevant=bool(re.search(r"tabela (?:de )?(?:frete|tarifas|pre[cç]os)|tarif[aá]rio|pra[cç]as atendidas", text, re.I))
            for link in links:
                if re.search(r"\.(pdf|xlsx?|csv)(?:\?|$)",link,re.I) and (relevant or re.search(r"frete|tarif|preco|pra[cç]a",link,re.I)): result.append(Detection("TABELA",link,page.url,link,.95,{"access":"PUBLIC"}))
            if relevant and re.search(r"solicite|fale com (?:o )?comercial",text,re.I): result.append(Detection("TABELA","PRIVATE",page.url,"Solicite ao comercial",.80,{"access":"PRIVATE"}))
            if relevant and re.search(r"login|entrar|acesso restrito",text,re.I): result.append(Detection("TABELA","AUTHENTICATED",page.url,"Portal autenticado",.85,{"access":"AUTHENTICATED"}))
        return list({(x.value,x.url):x for x in result}.values())


class ContactDetector:
    def detect(self,pages):
        result=[]
        for page in pages:
            text,_=page_content(page)
            for email in set(re.findall(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}",text)): result.append(Detection("EMAIL",email,page.url,email,.90,{}))
            for phone in set(re.findall(r"(?:\+?55\s*)?\(?\d{2}\)?\s*\d{4,5}[-\s]?\d{4}",text)): result.append(Detection("PHONE",phone,page.url,phone,.85,{}))
        return result


class BranchDetector:
    def detect(self,pages):
        result=[]
        for page in pages:
            text,_=page_content(page)
            if not re.search(r"filiais|unidades|nossas unidades",text,re.I): continue
            cnpjs={normalize_cnpj(x) for x in re.findall(r"\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}",text)}-{None}
            ceps={normalize_cep(x) for x in re.findall(r"\d{5}-?\d{3}",text)}-{None}
            for index,cep in enumerate(ceps or {None}): result.append(Detection("BRANCH",f"{page.url}#{index}",page.url,"Unidade/filial",.85,{"cep":cep,"cnpj":next(iter(cnpjs),None)}))
        return result

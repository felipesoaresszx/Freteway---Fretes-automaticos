import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Badge, Card } from "../../components/ui";
import { useTransportadoras } from "../../hooks/useTransportadoras";
import { TabelasFreteManager } from "./TabelasFreteManager";
import { ImportarTransportadoras } from "./ImportarTransportadoras";
import { CarrierManager } from "./CarrierManager";

export function Transportadoras() {
  const { data, isLoading, isError } = useTransportadoras();
  const [searchParams, setSearchParams] = useSearchParams();
  const [selecionada, setSelecionada] = useState<{ id: string; nome: string } | null>(null);
  const [importando, setImportando] = useState(false);
  const [gerenciando, setGerenciando] = useState<string | null>(null);

  useEffect(() => {
    const id = searchParams.get("transportadora");
    const transportadora = data?.find((item) => item.id === id);
    if (transportadora) setSelecionada({ id: transportadora.id, nome: transportadora.nome });
  }, [data, searchParams]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between"><h1 className="text-lg font-medium">Transportadoras</h1><button onClick={()=>setImportando(true)} className="rounded border border-border px-3 py-2 text-sm hover:bg-surface2">Importar transportadoras</button></div>

      {isLoading && <p className="text-sm text-text-secondary">Carregando transportadoras...</p>}
      {isError && <p className="text-sm text-state-error">Não foi possível carregar as transportadoras.</p>}
      {data && data.length === 0 && <p className="text-sm text-text-secondary">Nenhuma transportadora cadastrada.</p>}

      {data && data.length > 0 && (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {data.map((t) => (
            <Card key={t.id}>
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-sm">{t.nome}</span>
                <Badge tone={t.ativa ? "success" : "warning"}>{t.ativa ? "Ativa" : "Inativa"}</Badge>
              </div>
              <div className="text-xs space-y-1 text-text-secondary">
                <p>Integração: {t.tipo_integracao}</p>
                <p>Sucesso: {t.taxa_sucesso}%</p>
                <p>Tempo médio: {t.tempo_medio_ms} ms</p>
              </div>
              <button
                type="button"
                onClick={() => setSelecionada({ id: t.id, nome: t.nome })}
                className="mt-3 h-8 rounded border border-border px-3 text-xs hover:bg-surface2"
              >
                Gerenciar tabelas
              </button>
              <button type="button" onClick={() => setGerenciando(t.id)} className="ml-2 mt-3 h-8 rounded border border-border px-3 text-xs hover:bg-surface2">Configurar</button>
            </Card>
          ))}
        </div>
      )}

      {selecionada && (
        <TabelasFreteManager
          transportadoraId={selecionada.id}
          transportadoraNome={selecionada.nome}
          onClose={() => { setSelecionada(null); setSearchParams({}); }}
        />
      )}
      {importando && (
        <ImportarTransportadoras onClose={() => setImportando(false)} />
      )}
      {gerenciando && data && <CarrierManager carrier={data.find(item=>item.id===gerenciando)!} onClose={()=>setGerenciando(null)} />}
    </div>
  );
}

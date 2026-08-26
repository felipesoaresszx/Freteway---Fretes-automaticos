import { LoaderCircle, Star, Trash2, PlusCircle } from "lucide-react";
import { useMemo, useRef, useState } from "react";

import { Badge, Card, Field, Input } from "../../components/ui";
import { useCotacao } from "../../hooks/useCotacao";
import { useTransportadoras } from "../../hooks/useTransportadoras";
import type { VolumeIn } from "../../types/cotacao";
import { enderecoService } from "../../services/enderecoService";

let nextVolumeId = 1;

type VolumeForm = { id: number } & Record<keyof VolumeIn, string>;

const volumeVazio = (): VolumeForm => ({
  id: nextVolumeId++, quantidade: "", comprimento_cm: "", largura_cm: "", altura_cm: "", peso_kg: "",
});

export function NovaCotacao() {
  const { data: transportadoras } = useTransportadoras();
  const { criar, isCriando, cotacao, isCarregando, selecionar } = useCotacao();

  const [origem, setOrigem] = useState({ cep: "", cidade: "", uf: "" });
  const [destino, setDestino] = useState({ cep: "", cidade: "", uf: "" });
  const [cepStatus, setCepStatus] = useState({ origem: false, destino: false });
  const [cepErros, setCepErros] = useState<{ origem?: string; destino?: string }>({});
  const cepRequests = useRef({ origem: 0, destino: 0 });
  const [valorNf, setValorNf] = useState("");
  const [documentoDestinatario, setDocumentoDestinatario] = useState("");
  const [volumes, setVolumes] = useState<VolumeForm[]>([volumeVazio()]);
  const [selecionadas, setSelecionadas] = useState<string[]>([]);

  const cubagem = useMemo(
    () => volumes.reduce((acc, v) => acc + (Number(v.comprimento_cm) * Number(v.largura_cm) * Number(v.altura_cm) * Number(v.quantidade)) / 1_000_000, 0),
    [volumes]
  );
  const pesoTotal = useMemo(
    () => volumes.reduce((acc, v) => acc + Number(v.peso_kg) * Number(v.quantidade), 0),
    [volumes]
  );
  const possuiDadosVolume = volumes.some((v) => Object.values(v).some((valor) => valor !== "" && typeof valor === "string"));

  function addVolume() {
    setVolumes((v) => [...v, volumeVazio()]);
  }
  function updateVolume(id: number, field: keyof VolumeIn, value: string) {
    setVolumes((v) => v.map((x) => (x.id === id ? { ...x, [field]: value } : x)));
  }
  function toggle(id: string) {
    setSelecionadas((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  }

  function handleCepChange(tipo: "origem" | "destino", rawValue: string) {
    const digits = rawValue.replace(/\D/g, "").slice(0, 8);
    const formatted = digits.length > 5 ? `${digits.slice(0, 5)}-${digits.slice(5)}` : digits;
    const requestId = ++cepRequests.current[tipo];
    const setter = tipo === "origem" ? setOrigem : setDestino;
    setter((current) => ({ ...current, cep: formatted, ...(digits.length < 8 ? { cidade: "", uf: "" } : {}) }));
    setCepErros((current) => ({ ...current, [tipo]: undefined }));
    if (digits.length !== 8) {
      setCepStatus((current) => ({ ...current, [tipo]: false }));
      return;
    }

    setCepStatus((current) => ({ ...current, [tipo]: true }));
    void enderecoService.consultarCep(digits).then((address) => {
      if (cepRequests.current[tipo] !== requestId) return;
      setter({ cep: formatted, cidade: address.cidade, uf: address.uf });
    }).catch((error: Error) => {
      if (cepRequests.current[tipo] !== requestId) return;
      setCepErros((current) => ({ ...current, [tipo]: error.message }));
    }).finally(() => {
      if (cepRequests.current[tipo] === requestId) {
        setCepStatus((current) => ({ ...current, [tipo]: false }));
      }
    });
  }

  async function handleCalcular() {
    await criar({
      origem,
      destino,
      valor_nf: Number(valorNf),
      documento_destinatario: documentoDestinatario || null,
      peso: pesoTotal,
      volumes: volumes.map(({ id: _id, ...rest }) => ({
        quantidade: Number(rest.quantidade), comprimento_cm: Number(rest.comprimento_cm),
        largura_cm: Number(rest.largura_cm), altura_cm: Number(rest.altura_cm), peso_kg: Number(rest.peso_kg),
      })),
      transportadoras_ids: selecionadas.length > 0 ? selecionadas : null,
    });
  }

  const resultados = cotacao?.resultados ?? [];
  const status = cotacao?.status;
  const todosFinalizados = status && status !== "processing";

  return (
    <div className="space-y-5 max-w-3xl">
      <h1 className="text-lg font-medium">Nova cotação</h1>

      <Card>
        <p className="text-sm font-medium mb-3">Origem e destino</p>
        <div className="grid sm:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Field label="CEP origem">
              <div className="relative"><Input inputMode="numeric" maxLength={9} autoComplete="postal-code" value={origem.cep} onChange={(e) => handleCepChange("origem", e.target.value)} />
                {cepStatus.origem && <LoaderCircle aria-label="Consultando CEP de origem" className="absolute right-3 top-2.5 animate-spin text-text-secondary" size={15} />}
              </div>
              {cepErros.origem && <p className="mt-1 text-xs text-state-error">{cepErros.origem}</p>}
            </Field>
            <div className="grid grid-cols-3 gap-2">
              <div className="col-span-2"><Field label="Cidade"><Input autoComplete="off" value={origem.cidade} onChange={(e) => setOrigem({ ...origem, cidade: e.target.value })} /></Field></div>
              <Field label="UF"><Input autoComplete="off" value={origem.uf} onChange={(e) => setOrigem({ ...origem, uf: e.target.value })} /></Field>
            </div>
          </div>
          <div className="space-y-2">
            <Field label="CEP destino">
              <div className="relative"><Input inputMode="numeric" maxLength={9} autoComplete="postal-code" value={destino.cep} onChange={(e) => handleCepChange("destino", e.target.value)} />
                {cepStatus.destino && <LoaderCircle aria-label="Consultando CEP de destino" className="absolute right-3 top-2.5 animate-spin text-text-secondary" size={15} />}
              </div>
              {cepErros.destino && <p className="mt-1 text-xs text-state-error">{cepErros.destino}</p>}
            </Field>
            <div className="grid grid-cols-3 gap-2">
              <div className="col-span-2"><Field label="Cidade"><Input autoComplete="off" value={destino.cidade} onChange={(e) => setDestino({ ...destino, cidade: e.target.value })} /></Field></div>
              <Field label="UF"><Input autoComplete="off" value={destino.uf} onChange={(e) => setDestino({ ...destino, uf: e.target.value })} /></Field>
            </div>
          </div>
        </div>
      </Card>

      <Card>
        <p className="text-sm font-medium mb-3">Dados da NF</p>
        <div className="grid sm:grid-cols-4 gap-3">
          <Field label="Valor NF (R$)"><Input autoComplete="off" type="number" value={valorNf} onChange={(e) => setValorNf(e.target.value)} /></Field>
          <Field label="CPF/CNPJ destinatário"><Input inputMode="numeric" maxLength={14} value={documentoDestinatario} onChange={(e) => setDocumentoDestinatario(e.target.value.replace(/\D/g, "").slice(0, 14))} placeholder="Exigido por integrações como Risso e Braspress" /></Field>
          <Field label="Peso total calculado">
            <div className="h-9 rounded px-3 text-sm flex items-center bg-surface2 border border-border text-text-secondary">
              {possuiDadosVolume ? `${pesoTotal.toFixed(2)} kg` : "—"}
            </div>
          </Field>
          <Field label="Cubagem calculada">
            <div className="h-9 rounded px-3 text-sm flex items-center bg-surface2 border border-border text-text-secondary">
              {possuiDadosVolume ? `${cubagem.toFixed(3)} m³` : "—"}
            </div>
          </Field>
        </div>
      </Card>

      <Card>
        <div className="flex items-center justify-between mb-3">
          <p className="text-sm font-medium">Volumes</p>
          <button onClick={addVolume} className="text-xs flex items-center gap-1 px-2.5 py-1.5 rounded border border-border">
            <PlusCircle size={13} /> Adicionar volume
          </button>
        </div>
        <div className="space-y-2">
          {volumes.map((v) => (
            <div key={v.id} className="grid grid-cols-2 items-end gap-2 sm:grid-cols-[repeat(5,minmax(0,1fr))_2rem]">
              <div className="min-w-0"><Field label="Qtd"><Input min="1" type="number" value={v.quantidade} onChange={(e) => updateVolume(v.id, "quantidade", e.target.value)} /></Field></div>
              <div className="min-w-0"><Field label="C (cm)"><Input min="0" type="number" value={v.comprimento_cm} onChange={(e) => updateVolume(v.id, "comprimento_cm", e.target.value)} /></Field></div>
              <div className="min-w-0"><Field label="L (cm)"><Input min="0" type="number" value={v.largura_cm} onChange={(e) => updateVolume(v.id, "largura_cm", e.target.value)} /></Field></div>
              <div className="min-w-0"><Field label="A (cm)"><Input min="0" type="number" value={v.altura_cm} onChange={(e) => updateVolume(v.id, "altura_cm", e.target.value)} /></Field></div>
              <div className="col-span-2 min-w-0 sm:col-span-1"><Field label="Peso unit. (kg)"><Input min="0" type="number" value={v.peso_kg} onChange={(e) => updateVolume(v.id, "peso_kg", e.target.value)} /></Field></div>
              <button
                onClick={() => setVolumes((all) => all.filter((x) => x.id !== v.id))}
                disabled={volumes.length === 1}
                aria-label="Remover volume"
                className="h-9 w-8 flex items-center justify-center justify-self-end rounded text-state-error disabled:opacity-30"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <p className="text-sm font-medium mb-3">Transportadoras</p>
        <div className="grid sm:grid-cols-2 gap-2 text-sm">
          {(transportadoras ?? []).filter((t) => t.ativa).map((t) => (
            <label key={t.id} className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={selecionadas.includes(t.id)} onChange={() => toggle(t.id)} />
              {t.nome} <span className="text-xs text-text-secondary">({t.tipo_integracao})</span>
            </label>
          ))}
          {!transportadoras?.length && <p className="text-xs text-text-secondary">Carregando lista da API...</p>}
        </div>
        <p className="text-xs text-text-secondary mt-2">Nenhuma selecionada = consulta todas as ativas.</p>
      </Card>

      <button
        onClick={handleCalcular}
        disabled={isCriando}
        className="w-full h-11 rounded font-medium text-sm bg-state-info text-white disabled:opacity-60"
      >
        {isCriando ? "Enviando..." : "Calcular fretes"}
      </button>

      {cotacao && (
        <Card>
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-medium">{todosFinalizados ? "Resultado" : "Consultando transportadoras..."}</p>
            {isCarregando && <span className="text-xs text-text-secondary">atualizando...</span>}
          </div>
          <div className="space-y-2">
            {resultados.length === 0 && <p className="text-xs text-text-secondary">Aguardando primeira resposta do backend...</p>}
            {resultados.map((r) => {
              const isMelhor = cotacao.melhor_opcao_id === r.transportadora_id;
              return (
                <div
                  key={r.transportadora_id}
                  className={`flex items-center justify-between px-3 py-2.5 rounded border ${
                    isMelhor ? "bg-state-success/10 border-state-success/30" : "bg-surface2 border-border"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {isMelhor && <Star size={14} className="text-state-success fill-state-success" />}
                    <span className="text-sm font-medium">{r.transportadora}</span>
                  </div>
                  {r.status === "success" && (
                    <span className="text-sm text-right">
                      R$ {r.valor_frete?.toFixed(2)} <span className="mx-1 text-text-secondary">·</span>
                      <span className="text-text-secondary">{r.prazo_dias} dias</span>
                    </span>
                  )}
                  {(r.status === "error" || r.status === "timeout") && (
                    <div className="max-w-md text-right">
                      <Badge tone={r.status === "timeout" ? "warning" : "error"}>
                        {r.status === "timeout" ? "Timeout" : "Erro"}
                      </Badge>
                      {r.erro?.mensagem && <p className="mt-1 text-xs text-state-error">{r.erro.mensagem}</p>}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          {todosFinalizados && cotacao.melhor_opcao_id && (
            <div className="mt-3">
              {cotacao.recomendacao_motivo && <p className="mb-2 text-xs text-text-secondary">Recomendação: {cotacao.recomendacao_motivo}</p>}
              <button
                onClick={() => selecionar(cotacao.melhor_opcao_id as string)}
                className="w-full h-9 rounded text-sm font-medium bg-state-success text-bg"
              >
                Selecionar melhor opção
              </button>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

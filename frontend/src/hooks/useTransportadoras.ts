import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { transportadoraService } from "../services/transportadoraService";
import type { TransportadoraInput } from "../types/transportadora";
import type { ConfiguracaoApiInput } from "../types/transportadora";

export interface CarrierCardFilters { search?:string;status?:string;integration_type?:string;coverage_uf?:string;enrichment_status?:string;sort?:string;page:number;page_size:number; }

export function useTransportadoras() {
  return useQuery({
    queryKey: ["transportadoras"],
    queryFn: transportadoraService.listar,
  });
}

export function useCarrierSummaries() {
  return useQuery({ queryKey:["transportadoras","enrichment-summary"], queryFn:transportadoraService.listarResumos, refetchInterval:(query)=>query.state.data?.some(item=>item.status==="PROCESSING")?5000:false });
}

export function useCarrierCards(filters:CarrierCardFilters) {
  return useQuery({queryKey:["transportadoras","cards",filters],queryFn:()=>transportadoraService.listarCards({...filters}),placeholderData:previous=>previous});
}

export function useCarrierStats() {
  return useQuery({queryKey:["transportadoras","stats"],queryFn:transportadoraService.obterStats});
}

export function useCriarTransportadora() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: transportadoraService.criar,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["transportadoras"] }),
  });
}

export function useAtualizarTransportadora() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, dados }: { id: string; dados: TransportadoraInput }) => transportadoraService.atualizar(id, dados),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["transportadoras"] }),
  });
}

export function useAlterarStatusTransportadora() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ativa }: { id: string; ativa: boolean }) => transportadoraService.alterarStatus(id, ativa),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["transportadoras"] }),
  });
}

export function useExcluirTransportadora() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: transportadoraService.excluir,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["transportadoras"] }),
        queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
      ]);
    },
  });
}

export function useConsultaCnpj() {
  return useMutation({ mutationFn: transportadoraService.consultarCnpj });
}

export function useConfiguracaoApi(transportadoraId: string | null) {
  return useQuery({
    queryKey: ["transportadoras", transportadoraId, "configuracao-api"],
    queryFn: () => transportadoraService.obterConfiguracaoApi(transportadoraId as string),
    enabled: Boolean(transportadoraId),
  });
}

export function useSalvarConfiguracaoApi(transportadoraId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (dados: ConfiguracaoApiInput) => transportadoraService.salvarConfiguracaoApi(transportadoraId, dados),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["transportadoras", transportadoraId, "configuracao-api"] }),
  });
}

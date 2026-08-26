import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { tabelaFreteService } from "../services/tabelaFreteService";

export function useTabelasFrete(transportadoraId: string) {
  return useQuery({
    queryKey: ["tabelas-frete", transportadoraId],
    queryFn: () => tabelaFreteService.listar(transportadoraId),
    enabled: Boolean(transportadoraId),
  });
}

export function useCriarTabelaFrete(transportadoraId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: tabelaFreteService.criar,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tabelas-frete", transportadoraId] }),
  });
}

export function useUploadTabelaFrete() {
  return useMutation({
    mutationFn: ({ tabelaId, arquivo }: { tabelaId: string; arquivo: File }) =>
      tabelaFreteService.uploadDocumento(tabelaId, arquivo),
  });
}

export function useAnalisarTabelaFrete(transportadoraId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ tabelaId, documentoIds }: { tabelaId: string; documentoIds: string[] }) =>
      tabelaFreteService.analisar(tabelaId, documentoIds),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["tabelas-frete", transportadoraId] }),
  });
}

export function useExcluirTabelaFrete(transportadoraId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: tabelaFreteService.excluir,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tabelas-frete", transportadoraId] }),
  });
}

export function useRevisaoTabelaFrete(tabelaId: string | null) {
  return useQuery({
    queryKey: ["tabelas-frete", tabelaId, "revisao"],
    queryFn: () => tabelaFreteService.obterRevisao(tabelaId as string),
    enabled: Boolean(tabelaId),
  });
}

export function useSalvarRevisaoTabelaFrete(tabelaId: string, transportadoraId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (dados: Record<string, unknown>) => tabelaFreteService.salvarRevisao(tabelaId, dados),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tabelas-frete", tabelaId, "revisao"] }),
  });
}

export function useAprovarTabelaFrete(transportadoraId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ tabelaId, motivo }: { tabelaId: string; motivo: string }) => tabelaFreteService.aprovar(tabelaId, motivo),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tabelas-frete", transportadoraId] }),
  });
}

export function useConfirmarImportacao(transportadoraId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ tabelaId, dados, motivo }: { tabelaId: string; dados: Record<string, unknown>; motivo: string }) =>
      tabelaFreteService.confirmarImportacao(tabelaId, dados, motivo),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tabelas-frete", transportadoraId] }),
  });
}

export function useAtivarTabelaFrete(transportadoraId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: tabelaFreteService.ativar,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["tabelas-frete", transportadoraId] }),
  });
}

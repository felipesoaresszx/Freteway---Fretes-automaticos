import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { cotacaoService } from "../services/cotacaoService";
import type { CotacaoFiltros } from "../types/cotacao";

export function useCotacoes(filtros: CotacaoFiltros) {
  return useQuery({
    queryKey: ["cotacoes", filtros],
    queryFn: () => cotacaoService.listar(filtros),
    placeholderData: keepPreviousData,
    refetchInterval: (query) =>
      query.state.data?.items.some((item) => item.status === "processing") ? 3_000 : false,
  });
}

export function useReprocessarCotacao() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => cotacaoService.reprocessar(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["cotacoes"] }),
  });
}

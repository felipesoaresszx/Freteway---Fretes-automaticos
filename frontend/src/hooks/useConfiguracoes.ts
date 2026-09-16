import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { configuracoesService as service } from "../services/configuracoesService";
import type { CotacaoSettings, EmpresaSankhyaInput, EmpresaSettings, IntegracaoGlobalInput, NotificacaoSettings, SegurancaSettings, UsuarioInput } from "../types/configuracoes";

const invalidar = (queryClient: ReturnType<typeof useQueryClient>, chave: string[]) => queryClient.invalidateQueries({ queryKey: chave });
export const useCurrentUser = () => useQuery({ queryKey: ["auth", "me"], queryFn: service.me });
export const useEmpresaSettings = () => useQuery({ queryKey: ["configuracoes", "empresa"], queryFn: service.empresa });
export function useSalvarEmpresa() { const q = useQueryClient(); return useMutation({ mutationFn: (d: EmpresaSettings) => service.salvarEmpresa(d), onSuccess: () => invalidar(q, ["configuracoes", "empresa"]) }); }
export const useEmpresasSankhya = () => useQuery({ queryKey: ["configuracoes", "empresas-sankhya"], queryFn: service.empresasSankhya });
export function useCriarEmpresaSankhya() { const q=useQueryClient(); return useMutation({ mutationFn: (d: EmpresaSankhyaInput)=>service.criarEmpresaSankhya(d), onSuccess:()=>invalidar(q,["configuracoes","empresas-sankhya"]) }); }
export function useAtualizarEmpresaSankhya() { const q=useQueryClient(); return useMutation({ mutationFn: ({id,dados}:{id:string;dados:EmpresaSankhyaInput})=>service.atualizarEmpresaSankhya(id,dados), onSuccess:()=>invalidar(q,["configuracoes","empresas-sankhya"]) }); }
export function useUploadLogo() { const q = useQueryClient(); return useMutation({ mutationFn: service.uploadLogo, onSuccess: () => invalidar(q, ["configuracoes", "empresa"]) }); }
export const useCotacaoSettings = () => useQuery({ queryKey: ["configuracoes", "cotacao"], queryFn: service.cotacao });
export function useSalvarCotacaoSettings() { const q = useQueryClient(); return useMutation({ mutationFn: (d: CotacaoSettings) => service.salvarCotacao(d), onSuccess: () => invalidar(q, ["configuracoes", "cotacao"]) }); }
export const useNotificacaoSettings = () => useQuery({ queryKey: ["configuracoes", "notificacoes"], queryFn: service.notificacoes });
export function useSalvarNotificacaoSettings() { const q = useQueryClient(); return useMutation({ mutationFn: (d: NotificacaoSettings) => service.salvarNotificacoes(d), onSuccess: () => invalidar(q, ["configuracoes", "notificacoes"]) }); }
export const useSegurancaSettings = () => useQuery({ queryKey: ["configuracoes", "seguranca"], queryFn: service.seguranca });
export function useSalvarSegurancaSettings() { const q = useQueryClient(); return useMutation({ mutationFn: (d: SegurancaSettings) => service.salvarSeguranca(d), onSuccess: () => invalidar(q, ["configuracoes", "seguranca"]) }); }
export const useRoles = () => useQuery({ queryKey: ["configuracoes", "roles"], queryFn: service.roles });
export const useUsuarios = () => useQuery({ queryKey: ["configuracoes", "usuarios"], queryFn: service.usuarios });
export function useCriarUsuario() { const q = useQueryClient(); return useMutation({ mutationFn: (d: UsuarioInput) => service.criarUsuario(d), onSuccess: () => invalidar(q, ["configuracoes", "usuarios"]) }); }
export function useAtualizarUsuario() { const q = useQueryClient(); return useMutation({ mutationFn: ({ id, dados }: { id: string; dados: UsuarioInput }) => service.atualizarUsuario(id, dados), onSuccess: () => invalidar(q, ["configuracoes", "usuarios"]) }); }
export function useStatusUsuario() { const q = useQueryClient(); return useMutation({ mutationFn: ({ id, ativa }: { id: string; ativa: boolean }) => service.alterarStatusUsuario(id, ativa), onSuccess: () => invalidar(q, ["configuracoes", "usuarios"]) }); }
export const useIntegracoesGlobais = () => useQuery({ queryKey: ["configuracoes", "integracoes"], queryFn: service.integracoes });
export function useSalvarIntegracaoGlobal() { const q = useQueryClient(); return useMutation({ mutationFn: ({ id, dados }: { id: string; dados: IntegracaoGlobalInput }) => service.salvarIntegracao(id, dados), onSuccess: () => invalidar(q, ["configuracoes", "integracoes"]) }); }
export function useTestarIntegracaoGlobal() { const q = useQueryClient(); return useMutation({ mutationFn: service.testarIntegracao, onSuccess: () => invalidar(q, ["configuracoes", "integracoes"]) }); }
export const useAuditoria = (page: number, recurso?: string) => useQuery({ queryKey: ["configuracoes", "auditoria", page, recurso], queryFn: () => service.auditoria(page, recurso) });

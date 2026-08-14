import { apiClient } from "../api/client";

export interface EnderecoCep {
  cep: string;
  cidade: string;
  uf: string;
  logradouro: string | null;
  bairro: string | null;
}

export const enderecoService = {
  async consultarCep(cep: string): Promise<EnderecoCep> {
    return (await apiClient.get<EnderecoCep>(`/enderecos/cep/${cep.replace(/\D/g, "")}`)).data;
  },
};

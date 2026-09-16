import { Bell, Building2, Calculator, History, KeyRound, Network, ShieldCheck, Users } from "lucide-react";
import { useMemo, useState } from "react";
import { useCurrentUser } from "../../hooks/useConfiguracoes";
import { AuditoriaSection } from "./AuditoriaSection";
import { EmpresasSankhyaSection } from "./EmpresasSankhyaSection";
import { IntegracoesGlobaisSection } from "./IntegracoesGlobaisSection";
import { NotificacoesSection } from "./NotificacoesSection";
import { ParametrosCotacaoSection } from "./ParametrosCotacaoSection";
import { PerfilEmpresaSection } from "./PerfilEmpresaSection";
import { SegurancaSection } from "./SegurancaSection";
import { UsuariosSection } from "./UsuariosSection";

type Tab = "empresa"|"empresas-sankhya"|"usuarios"|"integracoes"|"cotacao"|"notificacoes"|"seguranca"|"auditoria";
export function Configuracoes(){const me=useCurrentUser();const[t,st]=useState<Tab>('empresa');const permissoes=new Set(me.data?.permissions??[]);const tabs=useMemo(()=>[
  {id:'empresa' as Tab,label:'Empresa',icon:Building2,show:permissoes.has('settings.view')},
  {id:'empresas-sankhya' as Tab,label:'Empresas Sankhya',icon:Network,show:permissoes.has('settings.view')},
  {id:'usuarios' as Tab,label:'Usuários',icon:Users,show:permissoes.has('users.view')},
  {id:'integracoes' as Tab,label:'Integrações globais',icon:KeyRound,show:permissoes.has('integrations.view')},
  {id:'cotacao' as Tab,label:'Cotação',icon:Calculator,show:permissoes.has('settings.view')},
  {id:'notificacoes' as Tab,label:'Notificações',icon:Bell,show:permissoes.has('settings.view')},
  {id:'seguranca' as Tab,label:'Segurança',icon:ShieldCheck,show:permissoes.has('settings.view')},
  {id:'auditoria' as Tab,label:'Auditoria',icon:History,show:permissoes.has('audit.view')},
].filter(x=>x.show),[me.data]);if(me.isLoading)return <p className="text-sm text-text-secondary">Carregando configurações...</p>;if(me.isError)return <p className="text-sm text-state-error">Você não possui acesso às configurações.</p>;return <div className="space-y-5"><div><h1 className="text-lg font-medium">Configurações</h1><p className="mt-1 text-xs text-text-secondary">Empresa, usuários, integrações, parâmetros e segurança do sistema.</p></div><div className="flex gap-1 overflow-x-auto rounded-lg border border-border bg-surface p-1">{tabs.map(tab=><button key={tab.id} onClick={()=>st(tab.id)} className={`inline-flex h-9 shrink-0 items-center gap-2 rounded px-3 text-xs transition ${t===tab.id?'bg-surface2 text-text-primary':'text-text-secondary hover:text-text-primary'}`}><tab.icon size={14}/>{tab.label}</button>)}</div>{t==='empresa'&&<PerfilEmpresaSection/>}{t==='empresas-sankhya'&&<EmpresasSankhyaSection/>}{t==='usuarios'&&<UsuariosSection/>}{t==='integracoes'&&<IntegracoesGlobaisSection/>}{t==='cotacao'&&<ParametrosCotacaoSection/>}{t==='notificacoes'&&<NotificacoesSection/>}{t==='seguranca'&&<SegurancaSection/>}{t==='auditoria'&&<AuditoriaSection/>}</div>}

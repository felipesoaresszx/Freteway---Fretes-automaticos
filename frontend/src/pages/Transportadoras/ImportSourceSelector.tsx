import { FileSpreadsheet, PencilLine, Search, X } from "lucide-react";

export type ImportSource="SOURCE"|"FILE"|"ANTT"|"MANUAL";
export function ImportSourceSelector({onSelect,onClose}:{onSelect:(source:ImportSource)=>void;onClose:()=>void}){
  const options=[
    {key:"FILE" as const,icon:FileSpreadsheet,title:"CSV / Excel",description:"Importe e valide uma lista de transportadoras."},
    {key:"ANTT" as const,icon:Search,title:"ANTT / RNTRC",description:"Busque no cadastro oficial da ANTT."},
    {key:"MANUAL" as const,icon:PencilLine,title:"Cadastro manual",description:"Cadastre uma transportadora individualmente."},
  ];
  return <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/75 p-4 pt-[8vh]" role="dialog" aria-modal="true"><div className="w-full max-w-3xl rounded-lg border border-border bg-surface shadow-2xl"><header className="flex items-start justify-between border-b border-border p-5"><div><h2 className="font-semibold">Importar transportadoras</h2><p className="mt-1 text-xs text-text-secondary">Escolha a origem dos dados</p></div><button onClick={onClose} aria-label="Fechar" className="rounded border border-border p-2"><X size={15}/></button></header><div className="grid gap-3 p-5 sm:grid-cols-3">{options.map(option=><button key={option.key} onClick={()=>onSelect(option.key)} className="group min-h-40 rounded-lg border border-border p-4 text-left hover:border-state-info hover:bg-state-info/5"><option.icon className="text-state-info" size={22}/><h3 className="mt-5 text-sm font-semibold">{option.title}</h3><p className="mt-2 text-xs leading-5 text-text-secondary">{option.description}</p></button>)}</div></div></div>
}

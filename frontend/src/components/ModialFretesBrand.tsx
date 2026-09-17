export function ModialFretesBrand({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-3" aria-label="Modial Fretes — Gestão de fretes">
      <img
        src="/modial-favicon.svg"
        alt=""
        aria-hidden="true"
        className="h-10 w-10 shrink-0"
      />
      {!compact && (
        <div className="border-l border-current/20 pl-3 leading-none">
          <span className="block text-[15px] font-bold tracking-[0.16em] text-text-primary">MODIAL</span>
          <span className="mt-1.5 block text-[10px] font-semibold tracking-[0.22em] text-brand-copper">FRETES</span>
        </div>
      )}
    </div>
  );
}

import type { PropsWithChildren, InputHTMLAttributes } from "react";

export function Card({ children, className = "" }: PropsWithChildren<{ className?: string }>) {
  return <div className={`rounded-xl p-4 bg-surface border border-border shadow-card ${className}`}>{children}</div>;
}

export function Badge({
  tone = "default",
  children,
}: PropsWithChildren<{ tone?: "default" | "success" | "warning" | "error" | "info" }>) {
  const tones: Record<string, string> = {
    default: "bg-surface2 text-text-primary border-border",
    success: "bg-brand-copper/10 text-brand-copper border-brand-copper/40",
    warning: "bg-state-warning/10 text-state-warning border-state-warning/30",
    error: "bg-state-error/10 text-state-error border-state-error/30",
    info: "bg-state-info/10 text-state-info border-state-info/30",
  };
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium border ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function Field({ label, children }: PropsWithChildren<{ label: string }>) {
  return (
    <label className="flex min-w-0 flex-col gap-1.5">
      <span className="text-xs font-medium text-text-secondary">{label}</span>
      {children}
    </label>
  );
}

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...props}
      className={`h-9 w-full min-w-0 rounded-md px-3 text-sm outline-none bg-surface border border-border text-text-primary placeholder:text-text-secondary/70 hover:border-text-secondary/50 focus:border-state-info focus:ring-2 focus:ring-state-info/15 ${props.className || ""}`}
    />
  );
}

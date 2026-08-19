import { CheckCircle2, LoaderCircle } from "lucide-react";
import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { Brand } from "../../components/Brand";
import { FretewayBrand } from "../../components/FretewayBrand";
import { Field, Input } from "../../components/ui";
import { useCompany } from "../../contexts/CompanyContext";
import { useAuth } from "../../hooks/useAuth";

export function Login() {
  const { isAuthenticated, isCheckingAuth, login, isLoggingIn, loginError } = useAuth();
  const { company, isRestoring, isIdentifying, identifyCompany, clearCompany } = useCompany();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");
  const [accessCode, setAccessCode] = useState("");
  const [identifyError, setIdentifyError] = useState<string | null>(null);

  if (isRestoring) return <div className="flex min-h-screen items-center justify-center bg-bg"><div className="space-y-4 text-center"><FretewayBrand /><div className="flex items-center justify-center gap-2 text-xs text-text-secondary"><LoaderCircle className="animate-spin" size={15}/>Carregando ambiente seguro...</div></div></div>;
  if (!isCheckingAuth && isAuthenticated) return <Navigate to="/dashboard" replace />;

  async function identify(event: React.FormEvent) {
    event.preventDefault(); setIdentifyError(null);
    try { await identifyCompany(accessCode); }
    catch (error) { setIdentifyError(error instanceof Error ? error.message : "Código de empresa inválido. Verifique o código informado e tente novamente."); }
  }
  async function identifyOnBlur() {
    if (company || isIdentifying || accessCode.trim().length < 3) return;
    setIdentifyError(null);
    try { await identifyCompany(accessCode); }
    catch (error) { setIdentifyError(error instanceof Error ? error.message : "Código de cliente inválido."); }
  }
  async function submitLogin(event: React.FormEvent) {
    event.preventDefault();
    await login({ codigo_cliente: accessCode.trim().toUpperCase(), email, password, otp: otp || undefined });
    navigate("/dashboard");
  }
  async function switchCompany() {
    await clearCompany(); setEmail(""); setPassword(""); setOtp(""); setIdentifyError(null);
  }

  return <main className="flex min-h-screen items-center justify-center bg-bg bg-[radial-gradient(circle_at_top_right,color-mix(in_srgb,var(--color-primary)_14%,transparent),transparent_34%)] p-4 text-text-primary transition-colors duration-300">
    <section className="w-full max-w-sm rounded-xl border border-border bg-surface p-7 shadow-card transition-colors duration-300">
      <div className="mb-7 border-b border-border pb-5">{company ? <Brand /> : <FretewayBrand />}</div>
      {!company ? <form onSubmit={identify} className="space-y-4" noValidate>
        <div><h1 className="text-lg font-semibold">Acesse sua empresa</h1><p className="mt-1.5 text-xs leading-5 text-text-secondary">Informe o código de acesso fornecido pela FRETEWAY.</p></div>
        <Field label="Código do cliente"><Input autoFocus autoCapitalize="characters" autoComplete="organization" value={accessCode} onBlur={() => void identifyOnBlur()} onChange={(event) => { setAccessCode(event.target.value.toUpperCase()); setIdentifyError(null); }} required maxLength={40} disabled={isIdentifying} aria-invalid={Boolean(identifyError)} aria-describedby={identifyError ? "company-code-error" : undefined} className={identifyError ? "border-state-error" : ""}/></Field>
        <div id="company-code-error" aria-live="polite">{identifyError && <p className="text-xs leading-5 text-state-error">{identifyError}</p>}</div>
        <button type="submit" disabled={isIdentifying || accessCode.trim().length < 3} className="flex h-10 w-full items-center justify-center gap-2 rounded-md bg-[var(--color-button)] text-sm font-medium text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60">{isIdentifying && <LoaderCircle className="animate-spin" size={15}/>} {isIdentifying ? "Identificando empresa..." : "Continuar"}</button>
      </form> : <form onSubmit={submitLogin} className="space-y-4">
        <div className="flex items-start justify-between gap-3"><div><p className="flex items-center gap-1.5 text-xs font-medium text-state-success"><CheckCircle2 size={14}/>Empresa identificada</p><p className="mt-1 text-xs text-text-secondary">Entre com suas credenciais pessoais.</p></div><button type="button" onClick={() => void switchCompany()} className="shrink-0 text-xs font-medium text-[var(--color-primary)] hover:underline">Trocar empresa</button></div>
        <Field label="E-mail"><Input type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} required /></Field>
        <Field label="Senha"><Input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /></Field>
        <Field label="Código 2FA (se habilitado)"><Input inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={otp} onChange={(event) => setOtp(event.target.value.replace(/\D/g, ""))} /></Field>
        <div aria-live="polite">{loginError && <p className="text-xs text-state-error">{loginError.message}</p>}</div>
        <button type="submit" disabled={isLoggingIn} className="flex h-10 w-full items-center justify-center gap-2 rounded-md bg-[var(--color-button)] text-sm font-medium text-white transition hover:brightness-110 disabled:opacity-60">{isLoggingIn && <LoaderCircle className="animate-spin" size={15}/>} {isLoggingIn ? "Entrando..." : "Entrar"}</button>
        <p className="pt-1 text-center text-[10px] uppercase tracking-[0.12em] text-text-secondary">Tecnologia FRETEWAY</p>
      </form>}
    </section>
  </main>;
}

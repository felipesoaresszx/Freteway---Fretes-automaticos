import { LoaderCircle } from "lucide-react";
import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";

import { ModialFretesBrand } from "../../components/ModialFretesBrand";
import { Field, Input } from "../../components/ui";
import { useAuth } from "../../hooks/useAuth";

export function Login() {
  const { isAuthenticated, isCheckingAuth, login, isLoggingIn, loginError } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");

  if (!isCheckingAuth && isAuthenticated) return <Navigate to="/dashboard" replace />;

  async function submitLogin(event: React.FormEvent) {
    event.preventDefault();
    await login({ email, password, otp: otp || undefined });
    navigate("/dashboard");
  }

  return <main className="flex min-h-screen items-center justify-center bg-bg bg-[radial-gradient(circle_at_top_right,color-mix(in_srgb,var(--color-primary)_14%,transparent),transparent_34%)] p-4 text-text-primary">
    <section className="w-full max-w-sm rounded-xl border border-border bg-surface p-7 shadow-card">
      <div className="mb-7 border-b border-border pb-5"><ModialFretesBrand /></div>
      <form onSubmit={submitLogin} className="space-y-4">
        <div><h1 className="text-lg font-semibold">Acesse o Modial Fretes</h1><p className="mt-1.5 text-xs leading-5 text-text-secondary">Entre com suas credenciais pessoais.</p></div>
        <Field label="E-mail"><Input autoFocus type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} required /></Field>
        <Field label="Senha"><Input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /></Field>
        <Field label="Código 2FA (se habilitado)"><Input inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={otp} onChange={(event) => setOtp(event.target.value.replace(/\D/g, ""))} /></Field>
        <div aria-live="polite">{loginError && <p className="text-xs text-state-error">{loginError.message}</p>}</div>
        <button type="submit" disabled={isLoggingIn || isCheckingAuth} className="flex h-10 w-full items-center justify-center gap-2 rounded-md bg-[var(--color-button)] text-sm font-medium text-white transition hover:brightness-110 disabled:opacity-60">{isLoggingIn && <LoaderCircle className="animate-spin" size={15}/>} {isLoggingIn ? "Entrando..." : "Entrar"}</button>
      </form>
    </section>
  </main>;
}

import { describe, expect, it } from "vitest";

import type { User } from "../types/auth";
import { hasPermission } from "./PermissionRoute";

const user: User = {
  id: "u1", nome: "Maria", email: "maria@example.com",
  permissions: ["settings.view", "transportadoras.view"],
};

describe("hasPermission", () => {
  it("autoriza somente permissões atribuídas diretamente", () => {
    expect(hasPermission(user, "settings.view")).toBe(true);
    expect(hasPermission(user, "settings.manage")).toBe(false);
  });

  it("nega acesso sem usuário autenticado", () => {
    expect(hasPermission(null, "settings.view")).toBe(false);
    expect(hasPermission(undefined, "settings.view")).toBe(false);
  });
});

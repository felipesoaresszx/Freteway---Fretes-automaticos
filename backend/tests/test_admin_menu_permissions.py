import pytest
from fastapi import HTTPException

from app.core.deps import require_permission
from app.models.models import Permission, Role, User


def user_with(role_name: str, permission_codes: list[str]) -> User:
    role = Role(nome=role_name, permissions=[Permission(codigo=code, descricao=code) for code in permission_codes])
    return User(email=f"{role_name}@example.com", password_hash="unused", nome=role_name, roles=[role])


@pytest.mark.asyncio
async def test_operador_e_visualizacao_nao_acessam_configuracoes_ou_de_para():
    for role in ("operador", "visualizacao"):
        user = user_with(role, ["cotacoes.view", "transportadoras.view"])
        for permission in ("settings.view", "integrations.view"):
            with pytest.raises(HTTPException) as error:
                await require_permission(permission)(user)
            assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_mantem_acesso():
    admin = user_with("admin", ["settings.view", "integrations.view"])
    assert await require_permission("settings.view")(admin) is admin
    assert await require_permission("integrations.view")(admin) is admin

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# =========================
# Definição das roles
# =========================

ROLES: Dict[str, Dict[str, Any]] = {
    "visualizador": {
        "keywords": ["read", "view", "monitor"],
        "level": 1,
    },
    "controlador": {
        "keywords": ["control", "edit", "operate"],
        "level": 2,
    },
    "gerente": {
        "keywords": ["manage", "admin", "config"],
        "level": 3,
    },
}

# =========================
# Mock da tabela tb_users
# =========================

tb_users: List[Dict[str, Any]] = [
    {
        "id_users": 1,
        "tx_name": "Bruno Guimaraes",
        "tx_password": "123456",
        "tx_role": "gerente",
        "tx_role_keywords": ROLES["gerente"]["keywords"],
        "dt_created_at": datetime(2025, 10, 1, 9, 0),
        "dt_modified_at": datetime(2025, 10, 5, 14, 30),
    },
    {
        "id_users": 2,
        "tx_name": "Ana Souza",
        "tx_password": "ana@123",
        "tx_role": "controlador",
        "tx_role_keywords": ROLES["controlador"]["keywords"],
        "dt_created_at": datetime(2025, 10, 2, 10, 15),
        "dt_modified_at": datetime(2025, 10, 6, 11, 0),
    },
    {
        "id_users": 3,
        "tx_name": "Carlos Pereira",
        "tx_password": "carlos#321",
        "tx_role": "visualizador",
        "tx_role_keywords": ROLES["visualizador"]["keywords"],
        "dt_created_at": datetime(2025, 10, 3, 8, 45),
        "dt_modified_at": datetime(2025, 10, 3, 8, 45),
    },
    {
        "id_users": 4,
        "tx_name": "Mariana Lima",
        "tx_password": "mariana@dev",
        "tx_role": "gerente",
        "tx_role_keywords": ROLES["gerente"]["keywords"],
        "dt_created_at": datetime(2025, 10, 4, 13, 20),
        "dt_modified_at": datetime(2025, 10, 10, 9, 0),
    },
    {
        "id_users": 5,
        "tx_name": "Lucas Andrade",
        "tx_password": "lucas123",
        "tx_role": "visualizador",
        "tx_role_keywords": ROLES["visualizador"]["keywords"],
        "dt_created_at": datetime(2025, 10, 5, 16, 10),
        "dt_modified_at": datetime(2025, 10, 5, 16, 10),
    },
    {
        "id_users": 6,
        "tx_name": "Fernanda Rocha",
        "tx_password": "fernanda!",
        "tx_role": "controlador",
        "tx_role_keywords": ROLES["controlador"]["keywords"],
        "dt_created_at": datetime(2025, 10, 6, 9, 40),
        "dt_modified_at": datetime(2025, 10, 8, 15, 25),
    },
    {
        "id_users": 7,
        "tx_name": "Rafael Martins",
        "tx_password": "rafael@2025",
        "tx_role": "visualizador",
        "tx_role_keywords": ROLES["visualizador"]["keywords"],
        "dt_created_at": datetime(2025, 10, 7, 11, 0),
        "dt_modified_at": datetime(2025, 10, 7, 11, 0),
    },
    {
        "id_users": 8,
        "tx_name": "Juliana Costa",
        "tx_password": "juliana321",
        "tx_role": "controlador",
        "tx_role_keywords": ROLES["controlador"]["keywords"],
        "dt_created_at": datetime(2025, 10, 8, 14, 50),
        "dt_modified_at": datetime(2025, 10, 9, 10, 10),
    },
    {
        "id_users": 9,
        "tx_name": "Pedro Henrique",
        "tx_password": "pedro@teste",
        "tx_role": "gerente",
        "tx_role_keywords": ROLES["gerente"]["keywords"],
        "dt_created_at": datetime(2025, 10, 9, 8, 30),
        "dt_modified_at": datetime(2025, 10, 12, 17, 0),
    },
    {
        "id_users": 10,
        "tx_name": "Camila Nogueira",
        "tx_password": "camila.dev",
        "tx_role": "visualizador",
        "tx_role_keywords": ROLES["visualizador"]["keywords"],
        "dt_created_at": datetime(2025, 10, 10, 15, 45),
        "dt_modified_at": datetime(2025, 10, 10, 15, 45),
    },
]

# =========================
# Helpers de acesso
# =========================

def get_all_users() -> List[Dict[str, Any]]:
    return tb_users

def get_user_by_name(name: str) -> Optional[Dict[str, Any]]:
    n = (name or "").strip().lower()
    return next((u for u in tb_users if u["tx_name"].lower() == n), None)

def get_users_by_role(role: str) -> List[Dict[str, Any]]:
    return [u for u in tb_users if u["tx_role"] == role]

def authenticate_user(username: str, password: str, desired_role: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Autentica usuário + valida permissão por hierarquia:
      gerente (3) >= controlador (2) >= visualizador (1)

    Retorna: (ok, mensagem, user_dict|None)
    """
    username = (username or "").strip()
    password = (password or "").strip()
    desired_role = (desired_role or "").strip().lower()

    if not username or not password:
        return False, "Informe usuário e senha.", None

    if desired_role not in ROLES:
        return False, "Perfil de acesso inválido.", None

    user = get_user_by_name(username)
    if not user:
        return False, "Usuário não encontrado.", None

    # Mock simples (produção: senha hasheada)
    if user.get("tx_password") != password:
        return False, "Senha incorreta.", None

    user_role = user.get("tx_role")
    if user_role not in ROLES:
        return False, "Usuário com perfil inválido no cadastro.", None

    user_level = ROLES[user_role]["level"]
    desired_level = ROLES[desired_role]["level"]

    if user_level < desired_level:
        return False, f"Usuário não possui permissão para o perfil '{desired_role}'.", None

    return True, f"Login bem-sucedido como '{desired_role}'.", user
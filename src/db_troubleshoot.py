"""Diagnostica a ligação a uma base de dados Microsoft SQL Server via ODBC."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pyodbc


PREFERRED_DRIVERS = (
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
    "ODBC Driver 13 for SQL Server",
)


class ConfigurationError(ValueError):
    """Indica que a configuração da ligação é inválida ou está incompleta."""


@dataclass(frozen=True)
class DatabaseConfig:
    server: str
    database: str
    user: str | None = None
    password: str | None = None
    driver: str | None = None
    trusted_connection: bool = False
    encrypt: bool = True
    trust_server_certificate: bool = False


def _read_bool(value: object, name: str, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    raise ConfigurationError(
        f"'{name}' deve ser verdadeiro ou falso (true/false)."
    )


def load_config(
    config_path: Path,
    environ: Mapping[str, str] | None = None,
) -> DatabaseConfig:
    """Carrega o JSON local e aplica variáveis de ambiente como substituições."""
    env = os.environ if environ is None else environ
    values: dict[str, object] = {}

    if config_path.exists():
        try:
            with config_path.open("r", encoding="utf-8") as file:
                loaded = json.load(file)
        except json.JSONDecodeError as error:
            raise ConfigurationError(
                f"JSON inválido em '{config_path}': {error.msg} "
                f"(linha {error.lineno}, coluna {error.colno})."
            ) from error
        except OSError as error:
            raise ConfigurationError(
                f"Não foi possível ler '{config_path}': {error}."
            ) from error

        if not isinstance(loaded, dict):
            raise ConfigurationError(
                f"'{config_path}' deve conter um objeto JSON."
            )
        values.update(loaded)

    environment_names = {
        "server": "DB_SERVER",
        "database": "DB_DATABASE",
        "user": "DB_USER",
        "password": "DB_PASSWORD",
        "driver": "DB_DRIVER",
        "trusted_connection": "DB_TRUSTED_CONNECTION",
        "encrypt": "DB_ENCRYPT",
        "trust_server_certificate": "DB_TRUST_SERVER_CERTIFICATE",
    }
    for key, name in environment_names.items():
        if name in env:
            values[key] = env[name]

    server = values.get("server")
    database = values.get("database")
    if not isinstance(server, str) or not server.strip():
        raise ConfigurationError(
            "Indique 'server' no ficheiro de configuração ou em DB_SERVER."
        )
    if not isinstance(database, str) or not database.strip():
        raise ConfigurationError(
            "Indique 'database' no ficheiro de configuração ou em DB_DATABASE."
        )

    user = values.get("user")
    password = values.get("password")
    if user is not None and not isinstance(user, str):
        raise ConfigurationError("'user' tem de ser texto.")
    if password is not None and not isinstance(password, str):
        raise ConfigurationError("'password' tem de ser texto.")

    trusted_connection = _read_bool(
        values.get("trusted_connection"), "trusted_connection", False
    )
    if not trusted_connection:
        if not isinstance(user, str) or not user:
            raise ConfigurationError(
                "Indique 'user' ou ative 'trusted_connection'."
            )
        if not isinstance(password, str) or not password:
            raise ConfigurationError(
                "Indique 'password' ou ative 'trusted_connection'."
            )

    driver = values.get("driver")
    if driver is not None and (not isinstance(driver, str) or not driver.strip()):
        raise ConfigurationError("'driver' tem de ser texto não vazio.")

    return DatabaseConfig(
        server=server.strip(),
        database=database.strip(),
        user=user,
        password=password,
        driver=driver.strip() if isinstance(driver, str) else None,
        trusted_connection=trusted_connection,
        encrypt=_read_bool(values.get("encrypt"), "encrypt", True),
        trust_server_certificate=_read_bool(
            values.get("trust_server_certificate"),
            "trust_server_certificate",
            False,
        ),
    )


def list_odbc_drivers() -> list[str]:
    """Devolve os nomes dos drivers ODBC instalados."""
    return list(pyodbc.drivers())


def resolve_driver(requested: str | None, installed: list[str]) -> str:
    if requested:
        if requested not in installed:
            raise ConfigurationError(
                f"O driver '{requested}' não está instalado. "
                "Consulte a lista apresentada com --list-drivers."
            )
        return requested

    for candidate in PREFERRED_DRIVERS:
        if candidate in installed:
            return candidate

    sql_server_drivers = [name for name in installed if "sql server" in name.lower()]
    if sql_server_drivers:
        return sql_server_drivers[-1]

    raise ConfigurationError(
        "Não foi encontrado um driver ODBC para SQL Server. "
        "Instale o ODBC Driver 17 ou 18 for SQL Server."
    )


def _odbc_value(value: str) -> str:
    """Envolve valores em chavetas e escapa chavetas finais segundo ODBC."""
    return "{" + value.replace("}", "}}") + "}"


def build_connection_string(config: DatabaseConfig, driver: str) -> str:
    parts = [
        f"DRIVER={_odbc_value(driver)}",
        f"SERVER={_odbc_value(config.server)}",
        f"DATABASE={_odbc_value(config.database)}",
        f"Encrypt={'yes' if config.encrypt else 'no'}",
        "TrustServerCertificate="
        f"{'yes' if config.trust_server_certificate else 'no'}",
    ]
    if config.trusted_connection:
        parts.append("Trusted_Connection=yes")
    else:
        parts.extend(
            [
                f"UID={_odbc_value(config.user or '')}",
                f"PWD={_odbc_value(config.password or '')}",
            ]
        )
    return ";".join(parts) + ";"


def test_db_connection(
    config: DatabaseConfig,
    driver: str,
    timeout: int,
) -> str | None:
    """Testa a ligação; devolve uma mensagem de erro ou None em caso de sucesso."""
    connection_string = build_connection_string(config, driver)
    try:
        connection = pyodbc.connect(connection_string, timeout=timeout)
        connection.close()
    except pyodbc.Error as error:
        message = str(error)
        if config.password:
            for secret in {
                config.password,
                config.password.replace("}", "}}"),
                _odbc_value(config.password),
            }:
                message = message.replace(secret, "***")
        return message
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verifica drivers ODBC e testa uma ligação ao SQL Server."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "db_credentials.json",
        help="Caminho para o JSON local (predefinição: db_credentials.json).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=5,
        help="Tempo limite de ligação em segundos (predefinição: 5).",
    )
    parser.add_argument(
        "--list-drivers",
        action="store_true",
        help="Lista os drivers ODBC instalados e termina.",
    )
    args = parser.parse_args(argv)

    if args.timeout < 1:
        parser.error("--timeout tem de ser pelo menos 1 segundo.")

    print("=== Diagnóstico de ligação ao SQL Server ===")
    print("\n1. Drivers ODBC instalados")
    drivers = list_odbc_drivers()
    if drivers:
        for driver in drivers:
            print(f" - {driver}")
    else:
        print("Nenhum driver ODBC foi encontrado.")
    if args.list_drivers:
        return 0 if drivers else 1

    try:
        config = load_config(args.config)
        driver = resolve_driver(config.driver, drivers)
    except ConfigurationError as error:
        print(f"\nErro de configuração: {error}", file=sys.stderr)
        return 2

    print(f"\n2. Driver selecionado: {driver}")
    print(f"\n3. A testar a ligação a {config.server}/{config.database}...")
    error_message = test_db_connection(config, driver, args.timeout)
    if error_message is not None:
        print(f"Falha na ligação: {error_message}", file=sys.stderr)
        print(
            "\nVerifique o nome e a disponibilidade do servidor, a base de dados, "
            "as credenciais, a firewall e se o driver ODBC está atualizado."
        )
        return 1

    print("Ligação efetuada com sucesso.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

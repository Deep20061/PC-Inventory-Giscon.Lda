import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import db_troubleshoot as app


class LoadConfigTests(unittest.TestCase):
    def test_reads_json_and_applies_environment_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "credentials.json"
            config_path.write_text(
                json.dumps(
                    {
                        "server": "old-server",
                        "database": "sample",
                        "user": "local-user",
                        "password": "local-password",
                    }
                ),
                encoding="utf-8",
            )

            config = app.load_config(
                config_path,
                {"DB_SERVER": "new-server", "DB_PASSWORD": "new-password"},
            )

        self.assertEqual(config.server, "new-server")
        self.assertEqual(config.password, "new-password")
        self.assertEqual(config.database, "sample")
        self.assertTrue(config.encrypt)

    def test_loads_trusted_connection_without_sql_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            config = app.load_config(
                Path(directory) / "missing.json",
                {
                    "DB_SERVER": "localhost",
                    "DB_DATABASE": "sample",
                    "DB_TRUSTED_CONNECTION": "true",
                },
            )

        self.assertTrue(config.trusted_connection)

    def test_requires_password_for_sql_authentication(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(app.ConfigurationError, "password"):
                app.load_config(
                    Path(directory) / "missing.json",
                    {
                        "DB_SERVER": "localhost",
                        "DB_DATABASE": "sample",
                        "DB_USER": "user",
                    },
                )

    def test_rejects_malformed_json(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "credentials.json"
            config_path.write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(app.ConfigurationError, "JSON inválido"):
                app.load_config(config_path, {})


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.config = app.DatabaseConfig(
            server="server;instance",
            database="sample",
            user="alice",
            password="secret",
        )

    def test_connection_string_escapes_odbc_values(self):
        connection_string = app.build_connection_string(
            self.config, "ODBC Driver 18 for SQL Server"
        )
        self.assertIn("SERVER={server;instance}", connection_string)
        self.assertIn("PWD={secret}", connection_string)
        self.assertIn("Encrypt=yes", connection_string)
        self.assertIn("TrustServerCertificate=no", connection_string)

    def test_prefers_newest_supported_driver(self):
        selected = app.resolve_driver(
            None,
            ["ODBC Driver 17 for SQL Server", "ODBC Driver 18 for SQL Server"],
        )
        self.assertEqual(selected, "ODBC Driver 18 for SQL Server")

    @patch.object(app.pyodbc, "connect")
    def test_successful_connection_is_closed(self, connect):
        connection = Mock()
        connect.return_value = connection

        error = app.test_db_connection(
            self.config, "ODBC Driver 18 for SQL Server", 5
        )

        self.assertIsNone(error)
        connection.close.assert_called_once_with()

    @patch.object(app.pyodbc, "connect")
    def test_connection_error_does_not_expose_password(self, connect):
        self.config = app.DatabaseConfig(
            server="server",
            database="sample",
            user="alice",
            password="se}cret",
        )
        connect.side_effect = app.pyodbc.Error("failed using se}}cret")

        error = app.test_db_connection(
            self.config, "ODBC Driver 18 for SQL Server", 5
        )

        self.assertEqual(error, "failed using ***")


if __name__ == "__main__":
    unittest.main()

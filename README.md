# PC Inventory Utilities

Python utilities for Windows computer inventory, SQL Server integration, and
scheduled inventory tasks. Source code is kept separate from PyInstaller
configuration, tests, local credentials, and generated executables.

## Project layout

```text
.
|-- src/          Python application and diagnostic scripts
|-- packaging/    PyInstaller spec files
|-- tests/        Automated tests
|-- db_credentials.example.json
|-- requirements.txt
`-- README.md
```

## Programs

| Source file | Purpose |
|---|---|
| `src/db_troubleshoot.py` | Lists installed ODBC drivers and tests a SQL Server connection. |
| `src/pcinventory_pessoal.py` | Collects local system and hardware information. |
| `src/gEasy_pcinventory-client.py` | Inventory client that emails hardware changes. |
| `src/receber-dados.py` | Receives inventory attachments over POP3/TLS and updates SQL Server. |
| `src/tarefa_geasy.py` | Creates and runs a weekly Windows scheduled task. |

`packaging/` contains PyInstaller specs for the available source files. Build
outputs are written to `build/` and `dist/`; these folders and compiled
executables are excluded from Git. The local
`easy_pcinventory-client-Giscon.spec` refers to a source file that is not
present and is therefore not included.

## Requirements

- Python 3.10 or later
- Microsoft ODBC Driver 17 or 18 for SQL Server for the database utilities
- Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

Install the [Microsoft ODBC Driver for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server).

To build Windows executables, install PyInstaller separately:

```powershell
python -m pip install pyinstaller
```

## Local configuration

Copy `db_credentials.example.json` to `db_credentials.json` and enter your
local SQL Server settings. The real credentials file is ignored by Git.

The database diagnostic also accepts these environment variables, which
override JSON settings:

| Variable | Description |
|---|---|
| `DB_SERVER` | SQL Server host, optionally including an instance |
| `DB_DATABASE` | Database name |
| `DB_USER` | SQL authentication user |
| `DB_PASSWORD` | SQL authentication password |
| `DB_DRIVER` | Optional installed ODBC driver name |

The mail-enabled programs use environment variables rather than hard-coded
credentials:

| Variable | Program | Description |
|---|---|---|
| `SMTP_SENDER` | Inventory client | Sender account |
| `SMTP_RECIPIENT` | Inventory client | Recipient address |
| `SMTP_PASSWORD` | Inventory client | Sender account password |
| `SMTP_SERVER` | Inventory client | SMTP server with STARTTLS |
| `SMTP_PORT` | Inventory client | SMTP port (default: `587`) |
| `POP3_SERVER` | Mail receiver | POP3 server with TLS |
| `POP3_PORT` | Mail receiver | POP3 TLS port (default: `995`) |
| `POP3_USER` | Mail receiver | Mail account |
| `POP3_PASSWORD` | Mail receiver | Mail account password |
| `INVENTORY_SAVE_DIR` | Mail receiver | Directory for received attachments |
| `DB_CREDENTIALS_FILE` | Mail receiver | Optional path to the local SQL JSON file |

Set these variables in the Windows environment before running the relevant
program. The scripts do not automatically load `.env` files. SMTP uses
STARTTLS; POP3 uses TLS.

## Run from the repository root

```powershell
python src\db_troubleshoot.py --list-drivers
python src\db_troubleshoot.py
python src\pcinventory_pessoal.py
python "src\gEasy_pcinventory-client.py"
python "src\receber-dados.py"
python src\tarefa_geasy.py
```

The database diagnostic finds `db_credentials.json` relative to the repository,
even when launched from another working directory. The receiver writes to
`received/` by default; set `INVENTORY_SAVE_DIR` to change this location.

`tarefa_geasy.py` creates a Windows scheduled task. Run it only on a computer
where you are authorized to create scheduled tasks. The mail receiver processes
and deletes messages after handling them; verify its configuration and target
database before running it.

## Build executables

Run PyInstaller from the repository root so that the spec paths resolve:

```powershell
python -m PyInstaller --distpath dist --workpath build packaging\db_troubleshoot.spec
python -m PyInstaller --distpath dist --workpath build packaging\pcinventory_pessoal.spec
python -m PyInstaller --distpath dist --workpath build packaging\gEasy_pcinventory-client.spec
python -m PyInstaller --distpath dist --workpath build packaging\receber-dados.spec
python -m PyInstaller --distpath dist --workpath build packaging\tarefa_geasy.spec
```

## Tests

```powershell
python -m unittest discover -s tests -v
```

The diagnostic tests do not require access to a live database.

## Security and privacy

- Inventory reports can contain computer names, network addresses, and serial
  numbers. Local reports and attachments are excluded from Git.
- Never commit `db_credentials.json`, `.env` files, passwords, or other secrets.
- Rotate any credentials that were previously embedded in source code before
  using the accounts again.

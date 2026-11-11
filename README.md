# Utilitários de inventário e diagnóstico

Repositório com código-fonte de utilitários Python para inventário de
computadores, integração de dados com SQL Server e tarefas agendadas no
Windows. Os executáveis compilados e os dados locais não fazem parte do
repositório.

## Programas

| Ficheiro | Função |
|---|---|
| `db_troubleshoot.py` | Lista drivers ODBC e testa uma ligação ao SQL Server. |
| `pcinventory_pessoal.py` | Recolhe informação de hardware e sistema local. |
| `gEasy_pcinventory-client.py` | Cliente de inventário, com envio de alterações por e-mail. |
| `receber-dados.py` | Recebe anexos por POP3 sobre TLS e atualiza o SQL Server. |
| `tarefa_geasy.py` | Regista e executa uma tarefa semanal do cliente no Windows. |

Os ficheiros `.spec` contêm as configurações PyInstaller disponíveis para
gerar os executáveis com código-fonte presente. Os diretórios `build/` e
`dist/` e os ficheiros `.exe` são ignorados pelo Git. O ficheiro
`easy_pcinventory-client-Giscon.spec` referencia um `.py` que não existe nesta
pasta, por isso não é incluído.

## Requisitos

- Python 3.10 ou superior
- Microsoft ODBC Driver 17 ou 18 for SQL Server para os programas que usam SQL
- Dependências Python:

```powershell
python -m pip install -r requirements.txt
```

Instalação do [Microsoft ODBC Driver for SQL Server](https://learn.microsoft.com/pt-pt/sql/connect/odbc/download-odbc-driver-for-sql-server).

## Configuração local

Copie `db_credentials.example.json` para `db_credentials.json` e preencha as
credenciais locais do SQL Server. `db_credentials.json` está excluído do Git.
O utilitário de diagnóstico aceita também `DB_SERVER`, `DB_DATABASE`,
`DB_USER`, `DB_PASSWORD` e `DB_DRIVER`. O recetor usa o JSON local e aceita
`DB_DRIVER` para selecionar o driver. Nunca adicione credenciais reais ao
repositório ou ao histórico Git.

O cliente de e-mail usa estas variáveis:

| Variável | Programa | Descrição |
|---|---|---|
| `SMTP_SENDER` | `gEasy_pcinventory-client.py` | Conta remetente |
| `SMTP_RECIPIENT` | `gEasy_pcinventory-client.py` | Destinatário |
| `SMTP_PASSWORD` | `gEasy_pcinventory-client.py` | Palavra-passe do remetente |
| `SMTP_SERVER` | `gEasy_pcinventory-client.py` | Servidor SMTP com STARTTLS |
| `SMTP_PORT` | `gEasy_pcinventory-client.py` | Porta SMTP (predefinição: `587`) |
| `POP3_SERVER` | `receber-dados.py` | Servidor POP3 com TLS |
| `POP3_PORT` | `receber-dados.py` | Porta POP3 TLS (predefinição: `995`) |
| `POP3_USER` | `receber-dados.py` | Conta de e-mail |
| `POP3_PASSWORD` | `receber-dados.py` | Palavra-passe da conta |
| `INVENTORY_SAVE_DIR` | `receber-dados.py` | Pasta local para anexos recebidos |
| `DB_CREDENTIALS_FILE` | `receber-dados.py` | Caminho alternativo para o JSON local |

Configure estas variáveis no ambiente Windows antes de executar os programas.
O código não carrega automaticamente ficheiros `.env`. O cliente SMTP exige
STARTTLS; o recetor usa POP3 sobre TLS.

## Executar

Na pasta do repositório:

```powershell
python db_troubleshoot.py --list-drivers
python db_troubleshoot.py
python pcinventory_pessoal.py
python "gEasy_pcinventory-client.py"
python "receber-dados.py"
python tarefa_geasy.py
```

`tarefa_geasy.py` cria uma tarefa agendada no Windows; execute-a apenas num
computador onde tenha autorização para configurar tarefas agendadas. O
recetor processa e remove mensagens após a operação; valide a configuração e
o destino antes de o executar.

## Testes

```powershell
python -m unittest discover -s tests -v
```

Os testes do diagnóstico não necessitam de acesso a uma base de dados real.

## Segurança e privacidade

- O inventário pode conter nomes de computadores, endereços de rede e números
  de série. Os relatórios e anexos locais são ignorados pelo Git.
- Os ficheiros compilados são excluídos; publique apenas código e configuração
  sem segredos.
- Se alguma credencial anteriormente embutida no código já foi utilizada,
  altere-a antes de publicar ou voltar a usar a conta.

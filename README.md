# Sistema Ponto

Automação de registro de ponto com Telegram, relatórios e cálculos trabalhistas.

## Requisitos

- Python 3.10+
- Google Chrome/Chromium e chromedriver
- Conta no Supabase (Postgres)

## Configuração

Crie um arquivo .env com as variáveis obrigatórias:

- SALARIO_BASE
- HORARIO_ENTRADA
- HORARIO_SAIDA
- INTERVALO_MINIMO
- TOLERANCIA_MINUTOS
- URL_SISTEMA
- LOGIN
- SENHA
- TELEGRAM_TOKEN
- TELEGRAM_CHAT_ID
- TELEGRAM_ADMIN_IDS

Para usar Supabase/Postgres, adicione:

- DATABASE_URL (ou SUPABASE_DATABASE_URL)

Se DATABASE_URL não estiver definido, o sistema usa SQLite local (DB_PATH).

## Rodar localmente

1) Instale as dependências:

   ```bash
   pip install -r requirements.txt
   ```

2) Execute:

   ```bash
   python main.py
   ```

## GitHub Actions (cron grátis)

Use o workflow em [.github/workflows/cron.yml](.github/workflows/cron.yml) para rodar 2x por dia.

1) Crie os secrets no repositório (Settings → Secrets and variables → Actions):

- SALARIO_BASE
- URL_SISTEMA
- LOGIN
- SENHA
- HORARIO_ENTRADA
- HORARIO_SAIDA
- INTERVALO_MINIMO
- TOLERANCIA_MINUTOS
- TELEGRAM_TOKEN
- TELEGRAM_CHAT_ID
- TELEGRAM_ADMIN_IDS
- DATABASE_URL
- SUPABASE_DATABASE_URL
- LOG_LEVEL
- BACKUP_RETENTION_DAYS
- PERICULOSIDADE
- ADICIONAL_NOTURNO
- HE_60
- HE_65
- HE_75
- HE_100
- HE_150
- PGHOST_OVERRIDE (opcional)
- PGHOSTADDR (opcional)

1) Ajuste o cron em UTC no workflow. Exemplo (BRT UTC-3):

- 07:30 BRT → 10:30 UTC
- 17:18 BRT → 20:18 UTC

Se o Supabase não tiver IPv4 no host padrão, use o pooler (host alternativo) e defina
`PGHOST_OVERRIDE` com o host do pooler, ou `PGHOSTADDR` com um IPv4 direto.

## Observações

- O container instala o Chromium e o chromedriver para o Selenium.
- Logs e relatórios são gerados no filesystem local do runner do GitHub Actions.

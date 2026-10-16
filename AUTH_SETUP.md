# Authentication setup

Run these commands in PowerShell from the project directory:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app app init-db
.\.venv\Scripts\python.exe -m flask --app app create-user owner --role admin
.\.venv\Scripts\python.exe -m flask --app app create-user cashier --role cashier
.\.venv\Scripts\python.exe -m flask --app app run --debug
```

Account creation prompts for a password and confirmation. Use at least 12 characters.
Usernames are trimmed and stored in lowercase. No default accounts are created.
Visit http://127.0.0.1:5000/ to sign in.

Admins can access the dashboard, POS, and product entry. Cashiers can access POS.
Logout uses a POST form. Sessions expire after eight hours and forms require a CSRF token.
Password recovery and login rate limiting are not implemented yet.

Without `DATABASE_URL`, local development uses `instance/auth.sqlite3`. A generated
persistent secret is stored in `instance/secret_key` when `SECRET_KEY` is unset.
Both files are excluded from Git. The app loads the project `.env` file for both
`python app.py` and `flask` commands; existing shell variables take precedence.

For PostgreSQL, add the database URL to `.env` before initializing the database:

```dotenv
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE
```

Replace the placeholders with your PostgreSQL connection details, then run
`init-db` and `create-user` using the commands above. Accounts in SQLite do not
automatically transfer to PostgreSQL. Restart the app after changing `.env`.
If login or the dashboard reports a missing table (such as `sale` or `product`),
stop the app and run `init-db` again. It creates missing tables without deleting
existing accounts or records.

For deployment, set a stable random `SECRET_KEY` shared by all app workers and
`SESSION_COOKIE_SECURE=1` when serving over HTTPS. Use a production WSGI server.
`init-db` creates missing tables; schema changes will need a migration workflow.

Run the tests with an isolated in-memory SQLite database:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

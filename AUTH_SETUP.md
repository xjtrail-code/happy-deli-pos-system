# Authentication and employee setup

Run these commands in PowerShell from the project directory:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app app init-db
.\.venv\Scripts\python.exe -m flask --app app create-user owner --role admin
.\.venv\Scripts\python.exe -m flask --app app run --debug
```

Set `DATABASE_URL` in `.env` to your PostgreSQL connection URL before initializing.
`init-db` creates missing tables without deleting existing data. Run it once when
upgrading an existing installation to add the `user_permissions` table. Existing
admins retain full access and existing cashiers retain POS access.

Sign in as an administrator and open **Employees** in the sidebar or
**Employee Management** on the dashboard. Create an account with a unique username,
email, first and last name, and a password of at least 12 characters. Usernames
are trimmed and stored in lowercase. Passwords are stored as hashes and cannot
be viewed. The command-line account creator uses a placeholder email ending in
`@accounts.invalid`; update the profile through Employee Management afterward.

Expand an account to edit its username/profile, reset its password, select its
role, activate or deactivate it, and change individual permissions:

- POS / Checkout, including completing sales and product lookup.
- Inventory, including viewing products and receiving stock.
- Product entry, including adding, editing, and deleting products.
- Reports / Analytics.
- Supplier Management.
- Reorder Recommendations: generate low-stock suggestions and track approval,
  ordering, and completion. Generation prefers the preferred supplier, then
  lowest cost, and respects supplier minimum quantities. Products without a
  supplier link are skipped. Actions record status; place orders with the supplier
  separately and record delivered stock before marking the recommendation complete.
- Receipts: view customer sales and supplier purchases, and print sales receipts.
- Record supplier receipts and receive stock: requires Receipts access as well.
  Save a supplier reference and item quantities/costs to record the purchase and
  update inventory together. Do not also receive those same units through Inventory.
  Supplier reference numbers are unique per supplier to prevent duplicate receiving.
  Supplier totals are item costs before tax and fees; attachment upload and OCR
  are not included.

Run `init-db` when upgrading to create the `purchase_receipts` and
`purchase_receipt_items` tables. No existing records are removed. Customer receipts
use existing POS transactions and their saved prices. Supplier receipts are entered
manually in the Supplier purchases section of Receipts.

Administrators always have full access, including employee management. Employees
cannot manage accounts or grant themselves permissions. Changes apply on the next
request, including to existing sessions. Deactivating an account prevents login
and further use of an existing session. Accounts are retained for sales history.
You cannot deactivate or demote your own administrator account. Leave both password
fields blank when editing to keep the existing password.

Employees land on their workspace after login and see only permitted menu links.
Permissions are also checked on the server for direct URLs and form submissions.
Logout uses POST, sessions expire after eight hours, and forms require CSRF tokens.
Password recovery and login rate limiting are not implemented yet.

Use a stable random `SECRET_KEY` shared by all workers and set
`SESSION_COOKIE_SECURE=1` for HTTPS deployment. If no key is configured, local
startup creates a persistent key in `instance/secret_key` (excluded from Git).
Use a production WSGI server for deployment.

Run tests against an isolated in-memory SQLite database:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

# Inventory Loss Detection System

A Flask and MySQL web application for recording inventory activity,
monitoring stock differences, identifying possible shrinkage, and
managing store operations. The application also supports customer sales
and product exchanges.

## 1. Main Features

-   User login with role-based access.
-   Store and product management.
-   Employee management.
-   Inventory movement recording: receipts, sales, transfers,
    adjustments, damage, and returns.
-   Store inventory and cycle-count recording.
-   Shrinkage alerts and investigations.
-   Customer sales with customer and bill details.
-   Product exchange against an original completed customer sale.
-   Owner account management, including owner credential changes and
    ownership transfer.

## 2. Technology Stack

-   Python
-   Flask
-   MySQL
-   MySQL Connector/Python
-   HTML and CSS
-   JavaScript
-   python-dotenv

## 3. Project Structure

``` text
inventory_loss_detection_project/
|
|-- app.py
|-- auth_utils.py
|-- config.py
|-- database.py
|-- create_owner.py
|-- change_owner_details.py
|-- change_owner_password.py
|-- migration_user_accounts.sql
|-- schema.sql
|-- requirements.txt
|-- .env.example
|
|-- routes/
|   |-- auth_routes.py
|   |-- account_routes.py
|   |-- store_routes.py
|   |-- sku_routes.py
|   |-- employee_routes.py
|   |-- inventory_routes.py
|   |-- sales_routes.py
|   |-- returns_routes.py
|   |-- alert_routes.py
|   |-- investigation_routes.py
|
|-- services/
|   |-- inventory_service.py
|   |-- shrinkage_service.py
|
|-- templates/
|   |-- base.html
|   |-- login.html
|   |-- dashboard.html
|   |-- stores.html
|   |-- products.html
|   |-- employees.html
|   |-- movements.html
|   |-- cycle_counts.html
|   |-- sales.html
|   |-- returns.html
|   |-- alerts.html
|   |-- investigations.html
|   |-- accounts.html
|   |-- 403.html
|
|-- static/
|   |-- css/style.css
|   |-- js/script.js
|
|-- data/
    |-- README.txt
```

## 4. Role-Based Permissions

The application uses three login roles:

  Feature                          Owner   Manager                              Employee
  -------------------------------- ------- ------------------------------------ ----------
  Dashboard                        Yes     Yes                                  Yes
  View stores and products         Yes     Yes                                  Yes
  Add/manage stores                Yes     No                                   No
  Add/edit products                Yes     Yes                                  No
  Employee management              Yes     View/manage as permitted by routes   No
  Record inventory movements       Yes     Yes                                  Yes
  Perform cycle counts             Yes     Yes                                  Yes
  View shrinkage alerts            Yes     Yes                                  No
  Manage investigations            Yes     Yes                                  No
  Customer sales                   Yes     Yes                                  Yes
  Process product exchanges        Yes     Yes                                  Yes
  View complete exchange history   Yes     Yes                                  No
  Manage login accounts            Yes     No                                   No
  Transfer ownership               Yes     No                                   No

Access is checked in Flask routes using role decorators. Hiding a
navigation link is not the only permission check.

## 5. Store-Wise Employee Assignment

Each employee profile can be assigned to a store. This helps identify
which store an employee belongs to when reviewing employee records.

### How store assignment works

1. Log in as the Owner.
2. Open the **Employees** page.
3. Add the employee's name and employee code.
4. Select the employee's job role.
5. Select the employee's assigned store from **Assign Store**.
6. Save the employee.
7. Open **Manage Accounts** and create a login account linked to that
   employee profile.
8. Assign the login account the appropriate application role, such as
   `MANAGER` or `EMPLOYEE`.

For example:

| Employee | Application login role | Assigned store |
|---|---|---|
| Madhu | MANAGER | Hyderabad store |
| Sruthi | EMPLOYEE | Hyderabad store |
| Navya | MANAGER | Vijayawada store |
| Anitha | EMPLOYEE | Vijayawada store |

The names above are examples. Assign each real employee to the correct
store in the Employees page.

### How to check which store an employee belongs to

Run this query in MySQL Workbench:

```sql
USE inventory_loss_db1;

SELECT
    e.employee_role_id,
    e.employee_name,
    e.employee_code,
    e.role_name AS employee_job_role,
    s.store_name,
    e.status
FROM EmployeeRole e
LEFT JOIN Store s
    ON e.store_id = s.store_id
ORDER BY s.store_name, e.employee_name;
```

The `EmployeeRole.store_id` column identifies the employee's assigned
store. The `LEFT JOIN` also displays employees who have not yet been
assigned to a store; their `store_name` will be `NULL`.

### Store-wise employee count

To count active employees in each store:

```sql
SELECT
    s.store_name,
    COUNT(e.employee_role_id) AS active_employee_count
FROM Store s
LEFT JOIN EmployeeRole e
    ON e.store_id = s.store_id
   AND e.status = 'ACTIVE'
GROUP BY s.store_id, s.store_name
ORDER BY s.store_name;
```

### Important distinction: employee job role and application login role

The project uses two different role fields:

- `EmployeeRole.role_name` describes the employee's job function, such
  as `MANAGER`, `STORE_OPERATOR`, `WAREHOUSE_OPERATOR`, `ANALYST`, or
  `ADMIN`.
- `UserAccount.account_role` controls the employee's application login
  permissions, such as `OWNER`, `MANAGER`, or `EMPLOYEE`.

The login account is connected to the employee profile through
`UserAccount.employee_role_id`. The employee's assigned store is stored
in `EmployeeRole.store_id`.

### Current store-access limitation

In this project version, the employee profile stores the assigned
`store_id`, and the Employees page displays the corresponding store name.
However, the current Sales page still loads all active stores for every
logged-in user. The current routes do not yet consistently restrict
Managers and Employees to only their assigned store.

Therefore, do not treat the employee's assigned store as an enforced
security boundary in this version.

A future store-level access-control update should enforce these rules
inside the Flask backend, not only hide store options in HTML:

| Login role | Intended store access |
|---|---|
| Owner | All stores |
| Manager | Only the store assigned to their employee profile |
| Employee | Only the store assigned to their employee profile |

That update should apply consistently to Dashboard, Sales, Returns &
Exchanges, Opening Stock, Inventory Movements, Cycle Counts, and other
store-specific operations. Until that backend restriction is added and
tested, users may still be able to see or select stores beyond their
assigned store on some pages.

## 6. Product Exchange Functionality

The Returns & Exchanges page is available from the application
navigation.

### Exchange workflow

1.  Search using the original customer sale ID.
2.  The application displays the products in that completed sale.
3.  Select the product and enter the quantity to exchange.
4.  Select a return reason:
    -   Defective
    -   Customer changed mind
    -   Wrong product
    -   Other
5.  Select the condition of the returned product:
    -   `SELLABLE`
    -   `DAMAGED`
6.  Select an active replacement product.
7.  Complete the exchange.

### Exchange rules in this version

-   The original sale must exist and have `COMPLETED` status.
-   The returned item must belong to the original sale.
-   The return quantity must be positive and cannot exceed the quantity
    still available to return.
-   A replacement product must be active and have enough available
    stock.
-   The replacement product's current `SKU.unit_price` must equal the
    original sale item's `CustomerSaleItem.selling_price`.
-   This version supports equal-price exchanges only. It does not
    process refunds, additional payments, or price differences.
-   The exchange is saved as a new customer sale and sale item.
-   The original sale is retained; the exchange is linked to it through
    the Return record.

### Inventory treatment

-   A sellable returned item creates a `RETURN` inventory movement,
    increasing sellable stock.
-   A damaged returned item creates a `RETURN` movement followed by a
    `DAMAGE` movement. The two movements cancel each other for
    sellable-stock calculation.
-   The replacement item creates a `SALE` movement, reducing its
    available stock.
-   The exchange and inventory records are written in a database
    transaction. If an error occurs, the transaction is rolled back.

### Exchange history visibility

-   Owner and Manager can view the exchange history on the Returns &
    Exchanges page.
-   Employee can process an exchange but does not see the complete
    exchange-history table.

## 7. Database Setup

The configured database name is `inventory_loss_db1`.

### Fresh database

1.  Open MySQL Workbench.
2.  Open and execute `schema.sql`.
3.  The schema creates the project tables, customer sales tables, and
    the Return table extensions used by the exchange feature.

The current `schema.sql` includes the `return_condition`,
`refund_amount`, and `exchange_sale_id` columns. The application uses
`return_condition` and `exchange_sale_id` for exchanges; it does not
implement refunds.

### Existing database

Do not execute the entire `schema.sql` again on a database that already
contains the project tables.

1.  Back up the database.
2.  Run `migration_user_accounts.sql` only if the login-account table
    has not already been created.
3.  Check the Return table:

``` sql
USE inventory_loss_db1;
DESC `Return`;
```

4.  Confirm that `return_condition` and `exchange_sale_id` exist. If
    they are both missing, run:

``` sql
ALTER TABLE `Return`
ADD COLUMN return_condition ENUM(
    'SELLABLE',
    'DAMAGED',
    'INSPECTION'
) NOT NULL DEFAULT 'SELLABLE',
ADD COLUMN refund_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
ADD COLUMN exchange_sale_id VARCHAR(40) NULL;

ALTER TABLE `Return`
ADD CONSTRAINT fk_return_exchange_sale
FOREIGN KEY (exchange_sale_id)
REFERENCES CustomerSale(sale_id);
```

If one or more of these columns already exist, do not run the complete
statement unchanged. Add only the missing column(s), and add the foreign
key only if it is not already present. The `CustomerSale` table must
exist before adding the foreign key.

## 8. Python Environment Setup (Windows CMD)

Open Command Prompt in the project folder.

Create a virtual environment:

``` cmd
python -m venv myenv
```

Activate it:

``` cmd
myenv\Scripts\activate
```

Install dependencies:

``` cmd
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 9. Environment Configuration

1.  Copy `.env.example` to a new file named `.env`.
2.  Open `.env`.
3.  Set your local MySQL username, password, database name, and Flask
    secret key.

Example:

``` env
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=inventory_loss_db1
SECRET_KEY=replace_with_a_long_random_secret_key
```

Use your own MySQL password. Do not commit or share `.env`.

## 10. Create the First Owner Account

After creating the database and configuring `.env`, activate the virtual
environment and run:

``` cmd
python create_owner.py
```

Follow the prompts to create the first Owner login. The script stores a
password hash, not the plain-text password.

## 11. Create Manager and Employee Accounts

1.  Log in as Owner.
2.  Create the employee profile from the Employees page, if required.
3.  Open Manage Accounts.
4.  Create a login account and assign the Manager or Employee role.
5.  Provide the credentials securely to the account holder.

Only the Owner can manage login accounts through the application.


## Opening Stock Management

Owner and Manager accounts can use the **Opening Stock** navigation page
to configure the initial quantity for each product at each store. This is
required before the application can calculate available stock for a sale.

1. Log in as Owner or Manager.
2. Open **Opening Stock**.
3. Select the store and product.
4. Enter the actual initial quantity available at that store.
5. Save the opening stock, then return to Customer Sales.

The page creates a `StoreInventory` row only when one does not already
exist for that store/product pair. It does not overwrite an existing
opening balance. If stock needs to change after transactions have been
recorded, record an appropriate inventory movement/adjustment instead.

## 12. Run the Application

To allow other devices on the same local network (Wi-Fi/LAN) to access
the application, configure the Flask server to listen on all network
interfaces.

At the bottom of `app.py`, use:

``` python
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
```

In the activated virtual environment, start the application:

``` cmd
python app.py
```

Flask displays two URLs:

- `http://127.0.0.1:5000` — use this URL on the same computer that runs
  the Flask application. `127.0.0.1` is the local loopback address.
- `http://192.168.1.25:5000` — example of the host computer's private
  network IP address. Other devices on the same Wi-Fi/LAN can use this
  address to access the application. Your actual IP address may be
  different.

Open the login page using the appropriate address:

``` text
http://127.0.0.1:5000/login
```

On another computer or phone connected to the same Wi-Fi/LAN, open:

``` text
http://192.168.1.25:5000/login
```

Replace `192.168.1.25` with the IPv4 address shown for the computer
running Flask. To find it on Windows, open Command Prompt and run:

``` cmd
ipconfig
```

Look for the **IPv4 Address** under the active Wi-Fi or Ethernet adapter.

### Important network requirements

- Keep the computer running Flask switched on and keep the application
  running while other devices use it.
- The other devices and the host computer must be connected to the same
  local network.
- If another device cannot connect, allow inbound TCP port `5000` through
  Windows Defender Firewall on the host computer.
- `127.0.0.1` works only on the computer where the application is running.
- `192.168.1.25` is an example private IP address. It can change when the
  network reconnects or the router assigns a new address.
- This setup is for a trusted local network. Do not expose Flask's
  development server directly to the public internet. For production,
  use a production WSGI server, HTTPS, and appropriate security settings.

Each user can sign in with their own account from a separate browser or
device. The application and its database remain hosted centrally on the
computer running Flask.

After logging in, use the navigation menu to open Customer Sales and
Returns & Exchanges.

The `/health` endpoint can be used for a basic application status check:

``` text
http://127.0.0.1:5000/health
```

From another device on the same network, use the host computer's IP:

``` text
http://192.168.1.25:5000/health
```

## 13. Suggested Test Sequence

Use test data in a development database, not live inventory.

1.  Create an active store.
2.  Create active products with known prices.
3.  Configure opening stock in `StoreInventory` for the products at that
    store.
4.  Record any required receipt movements.
5.  Create a customer sale for a product.
6.  Copy the generated sale ID from the sales record.
7.  Open Returns & Exchanges and search for that sale ID.
8.  Exchange a quantity that is less than or equal to the remaining
    returnable quantity.
9.  Select a replacement product with the same unit price and sufficient
    stock.
10. Confirm that the exchange succeeds.
11. Verify the `Return`, `CustomerSale`, `CustomerSaleItem`, and
    `InventoryMovement` records in MySQL.
12. Test a damaged return and confirm that both `RETURN` and `DAMAGE`
    movements are recorded.
13. Log in as Employee and confirm that the exchange form is available
    but the complete exchange-history table is not displayed.

## 14. Useful Verification Queries

View exchange records:

``` sql
USE inventory_loss_db1;

SELECT
    return_id,
    original_sale_movement_id,
    store_id,
    sku_id,
    return_quantity,
    return_reason,
    return_condition,
    exchange_sale_id,
    status
FROM `Return`
ORDER BY return_date DESC;
```

View the new exchange sales:

``` sql
SELECT
    sale_id,
    customer_id,
    store_id,
    sale_date,
    total_amount,
    status
FROM CustomerSale
ORDER BY sale_date DESC;
```

View inventory movements created for an exchange:

``` sql
SELECT
    movement_id,
    store_id,
    sku_id,
    movement_type,
    quantity,
    reason,
    reference_id,
    movement_date
FROM InventoryMovement
WHERE reference_id LIKE 'RET-%'
   OR reason LIKE '%exchange%'
ORDER BY movement_date DESC;
```

## 15. Owner Account Management

The project includes scripts and application functionality for Owner
account maintenance.

Change Owner username and password using:

``` cmd
python change_owner_details.py
```

Ownership transfer is available to the current Owner from Manage
Accounts. The current Owner must verify their password. After a
successful transfer, the previous Owner account is deactivated and the
new Owner account becomes active.

Never place actual usernames, passwords, password hashes, or database
credentials in this README.

## 16. Data and Limitations

-   The `data/README.txt` file describes the data folder as a place for
    synthetic test data and sample CSV files.
-   An automatic synthetic data generator is not included in this
    project version.
-   The exchange implementation supports equal-price exchanges only.
-   The exchange feature does not implement refunds, additional customer
    payments, or price adjustments.
-   The application is intended as a learning/project implementation.
    Before production use, add CSRF protection, HTTPS, stronger
    validation, audit logging, database backup procedures, and
    deployment security.

## 17. Troubleshooting

### `ModuleNotFoundError`

Activate the virtual environment and install dependencies:

``` cmd
myenv\Scripts\activate
pip install -r requirements.txt
```

### MySQL connection error

-   Confirm that the MySQL server is running.
-   Check `.env` values.
-   Confirm that `MYSQL_DATABASE` is `inventory_loss_db1`.
-   Confirm that the MySQL user has permission to access the database.

### `Table doesn't exist`

Confirm that the required schema and migrations have been executed in
the correct database. Do not rerun the full schema on an existing
database without a backup.

### Returns & Exchanges page gives a BuildError

Confirm that `app.py` imports and registers the returns blueprint:

``` python
from routes.returns_routes import returns_bp

app.register_blueprint(returns_bp)
```

Also confirm that `base.html` uses the endpoint:

``` html
<a href="{{ url_for('returns_bp.returns') }}">Returns & Exchanges</a>
```

### Exchange fails because of stock

Confirm that the store/product pair has an opening quantity in
`StoreInventory`, and that its inventory movements produce enough
available stock for the replacement product.

------------------------------------------------------------------------

**Project:** Inventory Loss Detection System\
**Database:** MySQL (`inventory_loss_db1`)\
**Application:** Flask

## Access from another computer on the same network

The Flask app is configured to listen on all network interfaces:

```python
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
```

Start the app from the activated virtual environment:

```cmd
python app.py
```

Use the URLs printed by Flask:

- `http://127.0.0.1:5000` is for a browser on the computer running Flask.
- `http://192.168.1.25:5000` is an example of the host computer's private LAN address. Other devices on the same Wi-Fi/LAN can use it. Replace `192.168.1.25` with the actual IPv4 address of the host computer.

To find the host computer's IPv4 address on Windows, run `ipconfig` in Command Prompt and check the active Wi-Fi or Ethernet adapter. Open the login page from another device using `http://<HOST-IP>:5000/login`.

Keep the host computer and Flask process running. If other devices cannot connect, allow inbound TCP port `5000` through Windows Defender Firewall. This setup is intended for a trusted local network only; do not expose Flask's development server directly to the public internet. Use a production WSGI server and HTTPS for production deployment.


## Inventory Movement Quantity Validation

Inventory movement quantities are stored as whole numbers (`INT`) in
the current database schema. Enter positive whole quantities such as
`1`, `2`, or `10` on the Inventory Movements page. Decimal values such
as `0.01` are rejected with a clear validation message before the
database insert. The quantity input uses `min="1"` and `step="1"` to
match the database type.

If the business needs fractional quantities (for example, kilograms or
metres), the database columns and all stock calculations must be
designed and migrated consistently to use decimal values. Do not change
only the HTML input to allow decimals.


## Automatic cycle-count shrinkage alerts

When a physical stock count is saved, the application now runs shrinkage detection automatically. If the physical quantity is lower than the system quantity, the system creates a `ShrinkageAlert`, changes that cycle count to `REVIEW_REQUIRED`, and displays a message directing the user to the Alerts page. The Alerts page also retains the **Run Shrinkage Detection** action for older pending counts.

A count with no shortage (physical quantity equal to or greater than system quantity) does not create a shrinkage alert and is marked `APPROVED`. This uses the statuses defined by the supplied `CycleCount` schema (`PENDING`, `REVIEW_REQUIRED`, `APPROVED`, `REJECTED`).

Example: system quantity 106 and physical quantity 80 gives a shortage of 26 units, so a shrinkage alert is created. System quantity 106 and physical quantity 106 creates no shortage alert.

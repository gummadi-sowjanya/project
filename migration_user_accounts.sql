USE inventory_loss_db1;

CREATE TABLE IF NOT EXISTS UserAccount (
    user_id VARCHAR(40) PRIMARY KEY,
    employee_role_id INT NULL UNIQUE,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    account_role ENUM('OWNER', 'MANAGER', 'EMPLOYEE') NOT NULL,
    status ENUM('ACTIVE', 'INACTIVE') NOT NULL DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_user_employee
        FOREIGN KEY (employee_role_id)
        REFERENCES EmployeeRole(employee_role_id)
        ON DELETE SET NULL
);

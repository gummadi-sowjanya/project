CREATE DATABASE IF NOT EXISTS inventory_loss_db1;

USE inventory_loss_db1;


-- 1. STORE TABLE

CREATE TABLE Store (
    store_id VARCHAR(20) PRIMARY KEY,
    store_name VARCHAR(100) NOT NULL,
    location VARCHAR(150) NOT NULL,
    store_type VARCHAR(30),
    status ENUM('ACTIVE', 'INACTIVE') DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- 2. SKU TABLE

CREATE TABLE SKU (
    sku_id VARCHAR(20) PRIMARY KEY,
    product_name VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    unit_price DECIMAL(10,2) NOT NULL,
    unit_of_measure VARCHAR(20) DEFAULT 'UNIT',
    status ENUM('ACTIVE', 'INACTIVE') DEFAULT 'ACTIVE',

    CHECK (unit_price >= 0)
);


-- 3. EMPLOYEE ROLE TABLE

CREATE TABLE EmployeeRole (
    employee_role_id INT AUTO_INCREMENT PRIMARY KEY,
    employee_name VARCHAR(100) NOT NULL,
    employee_code VARCHAR(30) UNIQUE NOT NULL,

    role_name ENUM(
        'STORE_OPERATOR',
        'WAREHOUSE_OPERATOR',
        'ANALYST',
        'MANAGER',
        'ADMIN'
    ) NOT NULL,

    store_id VARCHAR(20),
    effective_from DATE NOT NULL,
    effective_to DATE,

    status ENUM('ACTIVE', 'INACTIVE') DEFAULT 'ACTIVE',

    FOREIGN KEY (store_id)
        REFERENCES Store(store_id),

    CHECK (
        effective_to IS NULL
        OR effective_to >= effective_from
    )
);


-- 4. SHIFT TABLE

CREATE TABLE Shift (
    shift_id INT AUTO_INCREMENT PRIMARY KEY,
    store_id VARCHAR(20) NOT NULL,
    shift_name VARCHAR(30) NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,

    status ENUM(
        'SCHEDULED',
        'ACTIVE',
        'COMPLETED'
    ) DEFAULT 'SCHEDULED',

    FOREIGN KEY (store_id)
        REFERENCES Store(store_id),

    CHECK (end_time > start_time)
);


-- 5. PROMOTION TABLE

CREATE TABLE Promotion (
    promotion_id INT AUTO_INCREMENT PRIMARY KEY,
    promotion_name VARCHAR(100) NOT NULL,
    discount_percentage DECIMAL(5,2),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,

    status ENUM('ACTIVE', 'INACTIVE') DEFAULT 'ACTIVE',

    CHECK (
        discount_percentage BETWEEN 0 AND 100
    ),

    CHECK (end_date >= start_date)
);


-- 6. INVENTORY MOVEMENT TABLE

CREATE TABLE InventoryMovement (
    movement_id VARCHAR(40) PRIMARY KEY,
    store_id VARCHAR(20) NOT NULL,
    sku_id VARCHAR(20) NOT NULL,

    movement_type ENUM(
        'RECEIPT',
        'SALE',
        'TRANSFER_IN',
        'TRANSFER_OUT',
        'ADJUSTMENT',
        'DAMAGE',
        'RETURN'
    ) NOT NULL,

    quantity INT NOT NULL,
    reason VARCHAR(255),

    from_store_id VARCHAR(20),
    to_store_id VARCHAR(20),

    employee_role_id INT,
    shift_id INT,
    promotion_id INT,

    adjustment_direction ENUM(
        'INCREASE',
        'DECREASE'
    ),

    movement_date DATETIME NOT NULL,
    reference_id VARCHAR(50),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (store_id)
        REFERENCES Store(store_id),

    FOREIGN KEY (sku_id)
        REFERENCES SKU(sku_id),

    FOREIGN KEY (from_store_id)
        REFERENCES Store(store_id),

    FOREIGN KEY (to_store_id)
        REFERENCES Store(store_id),

    FOREIGN KEY (employee_role_id)
        REFERENCES EmployeeRole(employee_role_id),

    FOREIGN KEY (shift_id)
        REFERENCES Shift(shift_id),

    FOREIGN KEY (promotion_id)
        REFERENCES Promotion(promotion_id),

    CHECK (quantity > 0),

    CHECK (
        movement_type <> 'ADJUSTMENT'
        OR adjustment_direction IS NOT NULL
    )
);


-- 7. STORE INVENTORY TABLE

CREATE TABLE StoreInventory (
    inventory_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    store_id VARCHAR(20) NOT NULL,
    sku_id VARCHAR(20) NOT NULL,
    opening_quantity INT NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE (store_id, sku_id),

    FOREIGN KEY (store_id)
        REFERENCES Store(store_id),

    FOREIGN KEY (sku_id)
        REFERENCES SKU(sku_id),

    CHECK (opening_quantity >= 0)
);


-- 8. CYCLE COUNT TABLE

CREATE TABLE CycleCount (
    count_id VARCHAR(40) PRIMARY KEY,
    store_id VARCHAR(20) NOT NULL,
    sku_id VARCHAR(20) NOT NULL,

    system_quantity INT NOT NULL,
    physical_quantity INT NOT NULL,

    variance INT GENERATED ALWAYS AS (
        physical_quantity - system_quantity
    ) STORED,

    counted_by INT,
    shift_id INT,

    count_date DATETIME NOT NULL,

    status ENUM(
        'PENDING',
        'REVIEW_REQUIRED',
        'APPROVED',
        'REJECTED'
    ) DEFAULT 'PENDING',

    FOREIGN KEY (store_id)
        REFERENCES Store(store_id),

    FOREIGN KEY (sku_id)
        REFERENCES SKU(sku_id),

    FOREIGN KEY (counted_by)
        REFERENCES EmployeeRole(employee_role_id),

    FOREIGN KEY (shift_id)
        REFERENCES Shift(shift_id),

    CHECK (system_quantity >= 0),
    CHECK (physical_quantity >= 0)
);


-- 9. RETURN TABLE

CREATE TABLE `Return` (
    return_id VARCHAR(40) PRIMARY KEY,

    original_sale_movement_id VARCHAR(40) NOT NULL,
    return_movement_id VARCHAR(40),

    store_id VARCHAR(20) NOT NULL,
    sku_id VARCHAR(20) NOT NULL,

    return_quantity INT NOT NULL,

    return_reason ENUM(
        'DEFECTIVE',
        'CUSTOMER_CHANGED_MIND',
        'WRONG_PRODUCT',
        'OTHER'
    ) NOT NULL,

    return_date DATETIME NOT NULL,

    status ENUM(
        'REQUESTED',
        'APPROVED',
        'REJECTED',
        'COMPLETED'
    ) DEFAULT 'REQUESTED',

    FOREIGN KEY (original_sale_movement_id)
        REFERENCES InventoryMovement(movement_id),

    FOREIGN KEY (return_movement_id)
        REFERENCES InventoryMovement(movement_id),

    FOREIGN KEY (store_id)
        REFERENCES Store(store_id),

    FOREIGN KEY (sku_id)
        REFERENCES SKU(sku_id),

    CHECK (return_quantity > 0)
);


-- 10. SHRINKAGE ALERT TABLE

CREATE TABLE ShrinkageAlert (
    alert_id VARCHAR(40) PRIMARY KEY,

    store_id VARCHAR(20) NOT NULL,
    sku_id VARCHAR(20) NOT NULL,
    count_id VARCHAR(40),

    expected_quantity INT NOT NULL,
    actual_quantity INT NOT NULL,
    loss_quantity INT NOT NULL,

    risk_score DECIMAL(5,2),

    alert_reason VARCHAR(500),

    issue_type ENUM(
        'UNEXPLAINED_LOSS',
        'REPEATED_ADJUSTMENT',
        'UNAUTHORIZED_MOVEMENT',
        'TRANSFER_MISMATCH',
        'DATA_INTEGRITY_ERROR'
    ) NOT NULL,

    status ENUM(
        'OPEN',
        'UNDER_INVESTIGATION',
        'RESOLVED',
        'FALSE_POSITIVE'
    ) DEFAULT 'OPEN',

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (store_id)
        REFERENCES Store(store_id),

    FOREIGN KEY (sku_id)
        REFERENCES SKU(sku_id),

    FOREIGN KEY (count_id)
        REFERENCES CycleCount(count_id),

    UNIQUE (count_id),

    CHECK (risk_score BETWEEN 0 AND 100)
);


-- 11. INVESTIGATION TABLE

CREATE TABLE Investigation (
    investigation_id VARCHAR(40) PRIMARY KEY,
    alert_id VARCHAR(40) NOT NULL,

    assigned_employee_id INT,

    investigation_notes TEXT,

    finding ENUM(
        'THEFT_SUSPECTED',
        'DATA_ENTRY_ERROR',
        'LEGITIMATE_DAMAGE',
        'RETURN_MISMATCH',
        'TRANSFER_ERROR',
        'UNRESOLVED'
    ),

    resolution TEXT,

    status ENUM(
        'ASSIGNED',
        'IN_PROGRESS',
        'COMPLETED',
        'CLOSED'
    ) DEFAULT 'ASSIGNED',

    started_at DATETIME,
    completed_at DATETIME,

    FOREIGN KEY (alert_id)
        REFERENCES ShrinkageAlert(alert_id),

    FOREIGN KEY (assigned_employee_id)
        REFERENCES EmployeeRole(employee_role_id),

    CHECK (
        completed_at IS NULL
        OR started_at IS NULL
        OR completed_at >= started_at
    )
);


-- 12. EMPLOYEE SHIFT TABLE

CREATE TABLE EmployeeShift (
    employee_role_id INT NOT NULL,
    shift_id INT NOT NULL,

    PRIMARY KEY (employee_role_id, shift_id),

    FOREIGN KEY (employee_role_id)
        REFERENCES EmployeeRole(employee_role_id),

    FOREIGN KEY (shift_id)
        REFERENCES Shift(shift_id)
);


-- PERFORMANCE INDEXES

CREATE INDEX idx_movement_store_sku_date
ON InventoryMovement (
    store_id,
    sku_id,
    movement_date
);

CREATE INDEX idx_cycle_count_store_sku_date
ON CycleCount (
    store_id,
    sku_id,
    count_date
);
-- 14. USER LOGIN ACCOUNTS AND ROLE-BASED ACCESS
-- Run this section on an existing database to add login support.
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

-- customer table
CREATE TABLE Customer (
    customer_id INT AUTO_INCREMENT PRIMARY KEY,
    customer_name VARCHAR(100) NOT NULL,
    phone VARCHAR(15),
    email VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- CustomerSale table
CREATE TABLE CustomerSale (
    sale_id VARCHAR(40) PRIMARY KEY,
    customer_id INT NULL,
    store_id VARCHAR(20) NOT NULL,
    employee_role_id INT NULL,
    sale_date DATETIME NOT NULL,
    total_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
    status ENUM('COMPLETED', 'CANCELLED') DEFAULT 'COMPLETED',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (customer_id)
        REFERENCES Customer(customer_id),

    FOREIGN KEY (store_id)
        REFERENCES Store(store_id),

    FOREIGN KEY (employee_role_id)
        REFERENCES EmployeeRole(employee_role_id),

    CHECK (total_amount >= 0)
);

-- CustomerSaleItem table
CREATE TABLE CustomerSaleItem (
    sale_item_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    sale_id VARCHAR(40) NOT NULL,
    sku_id VARCHAR(20) NOT NULL,
    quantity INT NOT NULL,
    selling_price DECIMAL(10,2) NOT NULL,
    total_amount DECIMAL(12,2)
        GENERATED ALWAYS AS (quantity * selling_price) STORED,
    movement_id VARCHAR(40) NOT NULL UNIQUE,

    FOREIGN KEY (sale_id)
        REFERENCES CustomerSale(sale_id),

    FOREIGN KEY (sku_id)
        REFERENCES SKU(sku_id),

    FOREIGN KEY (movement_id)
        REFERENCES InventoryMovement(movement_id),

    CHECK (quantity > 0),
    CHECK (selling_price >= 0)
);

ALTER TABLE `Return`
ADD COLUMN return_condition ENUM(
    'SELLABLE',
    'DAMAGED',
    'INSPECTION'
) NOT NULL DEFAULT 'SELLABLE',

ADD COLUMN refund_amount DECIMAL(12,2) NOT NULL DEFAULT 0;

ALTER TABLE `Return`
ADD COLUMN exchange_sale_id VARCHAR(40) NULL,
ADD CONSTRAINT fk_return_exchange_sale
FOREIGN KEY (exchange_sale_id)
REFERENCES CustomerSale(sale_id);
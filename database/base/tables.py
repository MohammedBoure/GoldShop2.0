"""
schema/tables.py
----------------
تعريفات جداول SQL (CREATE TABLE / INSERT IGNORE).
كل قائمة مستقلة بحيث يسهل إضافة جداول جديدة أو تعديل الموجودة.
"""

REFERENCE_TABLE_QUERIES = [
    """CREATE USER IF NOT EXISTS 'root'@'%' IDENTIFIED BY 'root';""",
    """GRANT ALL PRIVILEGES ON jewellerydb.* TO 'root'@'%';""",
    """FLUSH PRIVILEGES;""",

    """CREATE TABLE IF NOT EXISTS Users (
        id INT PRIMARY KEY AUTO_INCREMENT,
        username VARCHAR(50) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        full_name VARCHAR(100),
        role ENUM('Admin', 'Manager', 'Sales', 'Artisan') DEFAULT 'Sales',
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        permissions JSON DEFAULT NULL
    );""",

    """CREATE TABLE IF NOT EXISTS MetalTypes (
        id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(50) NOT NULL,
        purity_value DECIMAL(5, 1) NOT NULL,
        metal_category ENUM('GOLD', 'SILVER') NOT NULL DEFAULT 'GOLD',
        description VARCHAR(100),
        invoice_display_name VARCHAR(255)
    );""",

    """INSERT IGNORE INTO MetalTypes (id, name, purity_value, metal_category) VALUES
        (1,  'Imp 750',    750.0, 'GOLD'),
        (2,  'Loc 705',    705.0, 'GOLD'),
        (3,  'Loc 710',    710.0, 'GOLD'),
        (4,  '21k',        875.0, 'GOLD'),
        (5,  '24k',        999.0, 'GOLD'),
        (6,  'Argent 925', 925.0, 'SILVER'),
        (7,  'Argent 800', 800.0, 'SILVER'),
        (8,  'Argent 999', 999.9, 'SILVER'),
        (9,  'Argent 500', 500.0, 'SILVER'),
        (10, 'Loc 730',    730.0, 'GOLD');""",

    """CREATE TABLE IF NOT EXISTS Categories (
        id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(100) NOT NULL,
        invoice_display_name VARCHAR(255)
    );""",

    """CREATE TABLE IF NOT EXISTS ProductNames (
        id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(200) NOT NULL UNIQUE
    );""",

    """INSERT IGNORE INTO ProductNames (name) VALUES
        ('Bague'), ('Alliance'), ('Solitaire'), ('Chevalière'), ('Demi-alliance'),
        ('Bracelet'), ('Gourmette'), ('Jonc'), ('Demi-jonc'), ('Chaîne de cheville'),
        ('Collier'), ('Chaîne'), ('Sautoir'), ('Ras de cou'),
        ('Boucles d''oreilles'), ('Créoles'), ('Puces d''oreilles'), ('Dormeuses'),
        ('Pendentif'), ('Médaillon'), ('Croix'), ('Main de Fatma'),
        ('Parure'), ('Demi-parure'), ('Montre'),
        ('Broche'), ('Boutons de manchette'), ('Pince à cravate'), ('Piercing'), ('Ceinture en or');""",

    """CREATE TABLE IF NOT EXISTS StorageLocations (
        id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(100) NOT NULL
    );""",

    """CREATE TABLE IF NOT EXISTS TreasuryLocations (
        id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(100) NOT NULL,
        type ENUM('SAFE', 'REGISTER') NOT NULL DEFAULT 'REGISTER',
        description TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );""",

    """INSERT IGNORE INTO TreasuryLocations (id, name, type, description) VALUES
        (1, 'Coffre Principal', 'SAFE',     'Coffre-fort central du magasin'),
        (2, 'Caisse 01',        'REGISTER', 'Boîte de vente n°1');""",

    """CREATE TABLE IF NOT EXISTS ExpenseCategories (
        id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(100) NOT NULL UNIQUE
    );""",

    """INSERT IGNORE INTO ExpenseCategories (name) VALUES
        ('Loyer'), ('Électricité'), ('Eau'), ('Internet'),
        ('Transport'), ('Repas'), ('Salaires'), ('Maintenance'),
        ('Fournitures'), ('Impôts'), ('Zakat'),
        ('Perte de Fonte (Argent)'), ('Perte de Fonte (Or)'),
        ('Autre');""",

    """CREATE TABLE IF NOT EXISTS InvoiceNotes (
        id INT PRIMARY KEY AUTO_INCREMENT,
        note_text VARCHAR(255) UNIQUE NOT NULL
    );""",
]

# ============================================================
# 2. جداول العملاء والموردين
# ============================================================
PARTNER_TABLE_QUERIES = [
    """CREATE TABLE IF NOT EXISTS Suppliers (
        id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(150) NOT NULL,
        phone VARCHAR(20),
        address TEXT,
        base_metal_type_id INT NULL,
        supplier_type ENUM('SUPPLIER', 'ARTISAN', 'BOTH') DEFAULT 'SUPPLIER',
        specialization VARCHAR(100),
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (base_metal_type_id) REFERENCES MetalTypes(id)
    );""",

    """CREATE TABLE IF NOT EXISTS Clients (
        id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(150) NOT NULL,
        phone VARCHAR(20),
        address TEXT,
        notes TEXT
    );""",

    """INSERT IGNORE INTO Clients (id, name, notes)
       VALUES (1, 'Client Passager', 'Client par défaut pour vente comptoir');""",

    """CREATE TABLE IF NOT EXISTS PartnerInitialBalances (
        id INT PRIMARY KEY AUTO_INCREMENT,
        partner_type ENUM('SUPPLIER', 'CLIENT') NOT NULL,
        partner_id INT NOT NULL,
        supplier_account_id INT NULL,
        currency_id INT NULL,
        metal_type_id INT NULL,
        initial_amount DECIMAL(15, 3) DEFAULT 0,
        FOREIGN KEY (currency_id) REFERENCES Currencies(id),
        FOREIGN KEY (metal_type_id) REFERENCES MetalTypes(id)
    );""",

    """CREATE TABLE IF NOT EXISTS SupplierAccounts (
        id INT PRIMARY KEY AUTO_INCREMENT,
        supplier_id INT NOT NULL,
        code VARCHAR(30) NOT NULL DEFAULT 'DEFAULT',
        name VARCHAR(100) NOT NULL DEFAULT 'Default',
        account_type ENUM('DEFAULT', 'LOCAL', 'IMPORT', 'LABOR', 'OTHER') NOT NULL DEFAULT 'DEFAULT',
        reference_metal_type_id INT NULL,
        reference_purity DECIMAL(7, 2) NULL,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY uq_supplier_accounts_supplier_code (supplier_id, code),
        FOREIGN KEY (supplier_id) REFERENCES Suppliers(id) ON DELETE CASCADE,
        FOREIGN KEY (reference_metal_type_id) REFERENCES MetalTypes(id)
    );""",

    """CREATE TABLE IF NOT EXISTS OfficialSuppliers (
        id INT PRIMARY KEY AUTO_INCREMENT,
        supplier_id INT NULL,
        official_code VARCHAR(50) NULL,
        name VARCHAR(150) NOT NULL,
        phone VARCHAR(50) NULL,
        tax_identifier VARCHAR(80) NULL,
        register_number VARCHAR(80) NULL,
        address TEXT NULL,
        notes TEXT NULL,
        is_active BOOLEAN DEFAULT TRUE,
        created_by_user_id INT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uq_official_suppliers_code (official_code),
        UNIQUE KEY uq_official_suppliers_supplier (supplier_id),
        KEY idx_official_suppliers_name (name),
        FOREIGN KEY (supplier_id) REFERENCES Suppliers(id) ON DELETE SET NULL,
        FOREIGN KEY (created_by_user_id) REFERENCES Users(id) ON DELETE SET NULL
    );""",

    """CREATE TABLE IF NOT EXISTS OfficialSupplierOperations (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        official_supplier_id INT NULL,
        operation_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        operation_type ENUM('INCOMING', 'OUTGOING') NOT NULL,
        metal_type_id INT NULL,
        weight_g DECIMAL(15, 3) NOT NULL DEFAULT 0,
        amount_da DECIMAL(15, 2) NOT NULL DEFAULT 0,
        unit_price_per_gram DECIMAL(15, 2)
            GENERATED ALWAYS AS (
                CASE
                    WHEN weight_g <> 0 THEN amount_da / weight_g
                    ELSE 0
                END
            ) STORED,
        document_number VARCHAR(80) NULL,
        description VARCHAR(255) NULL,
        notes TEXT NULL,
        source_kind ENUM('MANUAL', 'IMPORT', 'SALE', 'ADJUSTMENT') NOT NULL DEFAULT 'MANUAL',
        created_by_user_id INT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        KEY idx_official_supplier_ops_supplier_date (official_supplier_id, operation_date),
        KEY idx_official_supplier_ops_type_date (operation_type, operation_date),
        KEY idx_official_supplier_ops_month (operation_date, official_supplier_id, operation_type),
        FOREIGN KEY (official_supplier_id) REFERENCES OfficialSuppliers(id) ON DELETE CASCADE,
        FOREIGN KEY (metal_type_id) REFERENCES MetalTypes(id) ON DELETE SET NULL,
        FOREIGN KEY (created_by_user_id) REFERENCES Users(id) ON DELETE SET NULL
    );""",
]

DAILY_JOURNAL_TABLE_QUERIES = [
    """CREATE TABLE IF NOT EXISTS Sales (
        id INT PRIMARY KEY AUTO_INCREMENT,
        receipt_number VARCHAR(50) UNIQUE NOT NULL,      -- رقم الفاتورة (مثال: INV-202601-001)
        journee_id INT NOT NULL,                         -- ارتباط بيومية العمل الحالية
        client_id INT NOT NULL DEFAULT 1,
        user_id INT NULL,
        
        total_amount_da DECIMAL(15, 2) NOT NULL,         -- المجموع الإجمالي
        discount_da DECIMAL(15, 2) DEFAULT 0,            -- قيمة التخفيض
        net_to_pay_da DECIMAL(15, 2) NOT NULL,           -- الصافي للدفع
        
        cash_paid_da DECIMAL(15, 2) DEFAULT 0,           -- المدفوع نقداً
        tpe_paid_da DECIMAL(15, 2) DEFAULT 0,            -- المدفوع بالبطاقة
        old_gold_weight_g DECIMAL(10, 3) DEFAULT 0,      -- الذهب المكسر المستلم

        impos_weight_g DECIMAL(10, 3) DEFAULT 0,
        
        status ENUM('COMPLETED', 'CANCELLED') DEFAULT 'COMPLETED', -- حالة الفاتورة
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        notes TEXT,
        
        FOREIGN KEY (journee_id) REFERENCES DailySessions(id),
        FOREIGN KEY (client_id) REFERENCES Clients(id),
        FOREIGN KEY (user_id) REFERENCES Users(id)
    );""",

    """CREATE TABLE IF NOT EXISTS SaleItems (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        sale_id INT NOT NULL,
        inventory_id INT NULL,                           -- لمعرفة القطعة الأصلية في المخزون
        
        barcode VARCHAR(50),
        name VARCHAR(200),
        item_type ENUM('WEIGHT', 'PIECE') DEFAULT 'WEIGHT',
        
        sold_weight_g DECIMAL(10, 3) DEFAULT 0,          -- الوزن المباع
        sold_quantity INT DEFAULT 1,                     -- الكمية المباعة
        
        unit_price_da DECIMAL(15, 2) NOT NULL,           -- السعر للغرام أو للقطعة
        total_price_da DECIMAL(15, 2) NOT NULL,          -- الإجمالي لهذا السطر
        
        custom_note VARCHAR(255) NULL,                   -- 🟢 الحقل الجديد لحفظ الملاحظة المخصصة
        
        FOREIGN KEY (sale_id) REFERENCES Sales(id) ON DELETE CASCADE,
        FOREIGN KEY (inventory_id) REFERENCES Inventory(id) ON DELETE SET NULL
    );"""
]

INVENTORY_SALES_TABLE_QUERIES = [
    """CREATE TABLE IF NOT EXISTS Inventory (
        id INT PRIMARY KEY AUTO_INCREMENT,
        barcode VARCHAR(50) UNIQUE,
        name VARCHAR(200) NOT NULL,
        category_id INT,
        metal_type_id INT NULL,
        item_type ENUM('WEIGHT', 'PIECE') DEFAULT 'WEIGHT',
        weight DECIMAL(10, 3) NULL,
        remaining_weight DECIMAL(10, 3) NULL,
        quantity INT DEFAULT 1,
        remaining_quantity INT DEFAULT 1,
        metal_cost_per_gram DECIMAL(10, 2) DEFAULT 0,
        labor_cost_per_gram DECIMAL(10, 2) DEFAULT 0,
        total_cost DECIMAL(15, 2) DEFAULT 0,
        initial_cost DECIMAL(15, 2) DEFAULT 0,
        profit_margin DECIMAL(10, 2) DEFAULT 0,
        margin_type ENUM('FIXED', 'PERCENTAGE') DEFAULT 'FIXED',
        selling_price DECIMAL(15, 2) DEFAULT 0,
        status ENUM('Available', 'Sold', 'Partially_Sold', 'Reserved', 'Scrap', 'Repair', 'Lost') DEFAULT 'Available',
        reserved_for_client_id INT NULL,
        location_id INT,
        image_url VARCHAR(255),
        supplier_id INT,
        entry_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        sold_at DATETIME,
        sold_price DECIMAL(15, 2),
        FOREIGN KEY (category_id) REFERENCES Categories(id) ON DELETE SET NULL,
        FOREIGN KEY (metal_type_id) REFERENCES MetalTypes(id),
        FOREIGN KEY (supplier_id) REFERENCES Suppliers(id) ON DELETE SET NULL,
        FOREIGN KEY (location_id) REFERENCES StorageLocations(id) ON DELETE SET NULL,
        FOREIGN KEY (reserved_for_client_id) REFERENCES Clients(id) ON DELETE SET NULL
    );""",

    """CREATE TABLE IF NOT EXISTS InventoryCountDocumentSequence (
        id TINYINT PRIMARY KEY,
        last_value INT NOT NULL DEFAULT 0,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    );""",

    """INSERT IGNORE INTO InventoryCountDocumentSequence (id, last_value)
       VALUES (1, 0);""",

    """CREATE TABLE IF NOT EXISTS InventoryCountSessions (
        id INT PRIMARY KEY AUTO_INCREMENT,
        count_sequence INT NULL,
        count_number VARCHAR(30) NULL,
        scope ENUM('FULL') NOT NULL DEFAULT 'FULL',
        status ENUM('DRAFT', 'COUNTING', 'REVIEW', 'CLOSED', 'CANCELLED')
            NOT NULL DEFAULT 'DRAFT',
        started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        closed_at DATETIME NULL,
        cancelled_at DATETIME NULL,
        created_by_user_id INT NULL,
        closed_by_user_id INT NULL,
        expected_item_count INT NOT NULL DEFAULT 0,
        counted_item_count INT NOT NULL DEFAULT 0,
        matched_item_count INT NOT NULL DEFAULT 0,
        missing_item_count INT NOT NULL DEFAULT 0,
        different_item_count INT NOT NULL DEFAULT 0,
        extra_item_count INT NOT NULL DEFAULT 0,
        expected_weight DECIMAL(15, 3) NOT NULL DEFAULT 0,
        counted_weight DECIMAL(15, 3) NOT NULL DEFAULT 0,
        weight_difference DECIMAL(15, 3)
            GENERATED ALWAYS AS (counted_weight - expected_weight) STORED,
        notes TEXT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uq_inventory_count_sequence (count_sequence),
        UNIQUE KEY uq_inventory_count_number (count_number),
        KEY idx_inventory_count_status_started (status, started_at),
        FOREIGN KEY (created_by_user_id) REFERENCES Users(id) ON DELETE SET NULL,
        FOREIGN KEY (closed_by_user_id) REFERENCES Users(id) ON DELETE SET NULL
    );""",

    """CREATE TABLE IF NOT EXISTS InventoryCountItems (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        count_id INT NOT NULL,
        inventory_id INT NULL,
        snapshot_barcode VARCHAR(50) NULL,
        snapshot_name VARCHAR(200) NOT NULL,
        snapshot_status VARCHAR(40) NULL,
        snapshot_item_type ENUM('WEIGHT', 'PIECE') NOT NULL DEFAULT 'WEIGHT',
        snapshot_category_id INT NULL,
        snapshot_metal_type_id INT NULL,
        snapshot_location_id INT NULL,
        expected_weight DECIMAL(15, 3) NOT NULL DEFAULT 0,
        expected_quantity INT NOT NULL DEFAULT 0,
        expected_remaining_weight DECIMAL(15, 3) NOT NULL DEFAULT 0,
        expected_remaining_quantity INT NOT NULL DEFAULT 0,
        count_status ENUM('NOT_COUNTED', 'FOUND', 'MISSING', 'DIFFERENT', 'IGNORED')
            NOT NULL DEFAULT 'NOT_COUNTED',
        counted_weight DECIMAL(15, 3) NULL,
        counted_quantity INT NULL,
        count_method ENUM('BARCODE', 'MANUAL', 'IMPORT') NULL,
        counted_at DATETIME NULL,
        counted_by_user_id INT NULL,
        difference_weight DECIMAL(15, 3)
            GENERATED ALWAYS AS (COALESCE(counted_weight, 0) - expected_remaining_weight) STORED,
        difference_quantity INT
            GENERATED ALWAYS AS (COALESCE(counted_quantity, 0) - expected_remaining_quantity) STORED,
        notes TEXT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uq_inventory_count_item (count_id, inventory_id),
        KEY idx_inventory_count_items_status (count_id, count_status),
        KEY idx_inventory_count_items_inventory (inventory_id),
        KEY idx_inventory_count_items_barcode (snapshot_barcode),
        FOREIGN KEY (count_id) REFERENCES InventoryCountSessions(id) ON DELETE CASCADE,
        CONSTRAINT fk_inventory_count_items_inventory
            FOREIGN KEY (inventory_id) REFERENCES Inventory(id) ON DELETE SET NULL,
        FOREIGN KEY (snapshot_category_id) REFERENCES Categories(id) ON DELETE SET NULL,
        FOREIGN KEY (snapshot_metal_type_id) REFERENCES MetalTypes(id) ON DELETE SET NULL,
        FOREIGN KEY (snapshot_location_id) REFERENCES StorageLocations(id) ON DELETE SET NULL,
        FOREIGN KEY (counted_by_user_id) REFERENCES Users(id) ON DELETE SET NULL
    );""",

    """CREATE TABLE IF NOT EXISTS InventoryCountExtraItems (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        count_id INT NOT NULL,
        observed_barcode VARCHAR(50) NULL,
        observed_name VARCHAR(200) NULL,
        observed_item_type ENUM('WEIGHT', 'PIECE') NOT NULL DEFAULT 'WEIGHT',
        observed_weight DECIMAL(15, 3) NOT NULL DEFAULT 0,
        observed_quantity INT NOT NULL DEFAULT 1,
        category_id INT NULL,
        metal_type_id INT NULL,
        location_id INT NULL,
        status ENUM('NEW', 'LINKED', 'IGNORED') NOT NULL DEFAULT 'NEW',
        linked_inventory_id INT NULL,
        recorded_by_user_id INT NULL,
        recorded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        notes TEXT NULL,
        UNIQUE KEY uq_inventory_count_extra_barcode (count_id, observed_barcode),
        KEY idx_inventory_count_extra_status (count_id, status),
        KEY idx_inventory_count_extra_inventory (linked_inventory_id),
        FOREIGN KEY (count_id) REFERENCES InventoryCountSessions(id) ON DELETE CASCADE,
        FOREIGN KEY (category_id) REFERENCES Categories(id) ON DELETE SET NULL,
        FOREIGN KEY (metal_type_id) REFERENCES MetalTypes(id) ON DELETE SET NULL,
        FOREIGN KEY (location_id) REFERENCES StorageLocations(id) ON DELETE SET NULL,
        FOREIGN KEY (linked_inventory_id) REFERENCES Inventory(id) ON DELETE SET NULL,
        FOREIGN KEY (recorded_by_user_id) REFERENCES Users(id) ON DELETE SET NULL
    );""",

    """CREATE TABLE IF NOT EXISTS InventoryCountAdjustments (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        count_id INT NOT NULL,
        count_item_id BIGINT NULL,
        extra_item_id BIGINT NULL,
        inventory_id INT NULL,
        action_type ENUM(
            'MARK_LOST',
            'UPDATE_WEIGHT',
            'UPDATE_QUANTITY',
            'UPDATE_LOCATION',
            'CREATE_INVENTORY',
            'IGNORE'
        ) NOT NULL,
        previous_payload_json JSON NULL,
        new_payload_json JSON NULL,
        applied_by_user_id INT NULL,
        applied_at DATETIME NULL,
        notes TEXT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        KEY idx_inventory_count_adjustments_count (count_id, action_type),
        KEY idx_inventory_count_adjustments_inventory (inventory_id),
        FOREIGN KEY (count_id) REFERENCES InventoryCountSessions(id) ON DELETE CASCADE,
        FOREIGN KEY (count_item_id) REFERENCES InventoryCountItems(id) ON DELETE SET NULL,
        FOREIGN KEY (extra_item_id) REFERENCES InventoryCountExtraItems(id) ON DELETE SET NULL,
        FOREIGN KEY (inventory_id) REFERENCES Inventory(id) ON DELETE SET NULL,
        FOREIGN KEY (applied_by_user_id) REFERENCES Users(id) ON DELETE SET NULL
    );""",

    """CREATE TABLE IF NOT EXISTS ClientCommandDocumentSequence (
        id TINYINT PRIMARY KEY,
        last_value INT NOT NULL DEFAULT 0,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    );""",

    """INSERT IGNORE INTO ClientCommandDocumentSequence (id, last_value)
       VALUES (1, 0);""",

    """CREATE TABLE IF NOT EXISTS ClientCommands (
        id INT PRIMARY KEY AUTO_INCREMENT,
        command_sequence INT NULL,
        command_number VARCHAR(30) NULL,
        client_id INT NOT NULL,
        command_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        expected_delivery_date DATE NULL,
        status ENUM('PENDING', 'CONFIRMED', 'IN_PROGRESS', 'READY', 'DELIVERED', 'CANCELLED')
            NOT NULL DEFAULT 'PENDING',
        currency_id INT NOT NULL DEFAULT 1,
        total_amount DECIMAL(15, 2) NOT NULL DEFAULT 0,
        paid_amount DECIMAL(15, 2) NOT NULL DEFAULT 0,
        remaining_amount DECIMAL(15, 2)
            GENERATED ALWAYS AS (GREATEST(total_amount - paid_amount, 0)) STORED,
        payment_status ENUM('UNPAID', 'PARTIAL', 'PAID') NOT NULL DEFAULT 'UNPAID',
        barcode VARCHAR(50) NULL,
        product_name VARCHAR(200) NOT NULL,
        product_name_id INT NULL,
        category_id INT NULL,
        metal_type_id INT NULL,
        item_type ENUM('WEIGHT', 'PIECE') NOT NULL DEFAULT 'WEIGHT',
        weight DECIMAL(10, 3) NULL,
        quantity INT NOT NULL DEFAULT 1,
        metal_cost_per_gram DECIMAL(10, 2) DEFAULT 0,
        labor_cost_per_gram DECIMAL(10, 2) DEFAULT 0,
        total_cost DECIMAL(15, 2) DEFAULT 0,
        initial_cost DECIMAL(15, 2) DEFAULT 0,
        profit_margin DECIMAL(10, 2) DEFAULT 0,
        margin_type ENUM('FIXED', 'PERCENTAGE') DEFAULT 'FIXED',
        selling_price DECIMAL(15, 2) DEFAULT 0,
        supplier_id INT NULL,
        location_id INT NULL,
        image_url VARCHAR(255) NULL,
        product_description TEXT NULL,
        product_payload_json JSON NULL,
        linked_inventory_id INT NULL,
        linked_sale_id INT NULL,
        delivered_at DATETIME NULL,
        cancelled_at DATETIME NULL,
        notes TEXT NULL,
        user_id INT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        UNIQUE KEY uq_client_commands_sequence (command_sequence),
        UNIQUE KEY uq_client_commands_number (command_number),
        KEY idx_client_commands_client_status (client_id, status),
        KEY idx_client_commands_command_date (command_date),
        KEY idx_client_commands_expected_delivery (expected_delivery_date),
        KEY idx_client_commands_payment_status (payment_status),
        KEY idx_client_commands_linked_inventory (linked_inventory_id),
        KEY idx_client_commands_linked_sale (linked_sale_id),
        FOREIGN KEY (client_id) REFERENCES Clients(id) ON DELETE CASCADE,
        FOREIGN KEY (currency_id) REFERENCES Currencies(id),
        FOREIGN KEY (product_name_id) REFERENCES ProductNames(id) ON DELETE SET NULL,
        FOREIGN KEY (category_id) REFERENCES Categories(id) ON DELETE SET NULL,
        FOREIGN KEY (metal_type_id) REFERENCES MetalTypes(id) ON DELETE SET NULL,
        FOREIGN KEY (supplier_id) REFERENCES Suppliers(id) ON DELETE SET NULL,
        FOREIGN KEY (location_id) REFERENCES StorageLocations(id) ON DELETE SET NULL,
        FOREIGN KEY (linked_inventory_id) REFERENCES Inventory(id) ON DELETE SET NULL,
        FOREIGN KEY (linked_sale_id) REFERENCES Sales(id) ON DELETE SET NULL,
        FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE SET NULL
    );""",
]


TREASURY_SESSION_TABLE_QUERIES = [
    """CREATE TABLE IF NOT EXISTS DailySessions (
        id INT PRIMARY KEY AUTO_INCREMENT,
        opened_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        closed_at DATETIME NULL,
        status ENUM('OPEN', 'CLOSED') DEFAULT 'OPEN',
        opened_by_user_id INT NULL,
        closed_by_user_id INT NULL,
        starting_cash_da DECIMAL(15, 2) DEFAULT 0,
        notes TEXT,
        FOREIGN KEY (opened_by_user_id) REFERENCES Users(id) ON DELETE SET NULL,
        FOREIGN KEY (closed_by_user_id) REFERENCES Users(id) ON DELETE SET NULL
    );"""
]

PAYMENT_TABLE_QUERIES = [
    """CREATE TABLE IF NOT EXISTS Versements (
        id INT PRIMARY KEY AUTO_INCREMENT,
        client_id INT NOT NULL,
        type_versement ENUM('A_VIDE', 'PRODUITS') DEFAULT 'PRODUITS',
        status ENUM('EN_COURS', 'CLOTURE', 'ANNULE') DEFAULT 'EN_COURS',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        
        FOREIGN KEY (client_id) REFERENCES Clients(id)
    );""",

    """CREATE TABLE IF NOT EXISTS Versement_Items (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        versement_id INT NOT NULL,
        inventory_id INT NULL,
        designation VARCHAR(200),
        notes TEXT NULL,
        
        -- الحقل الجديد لمعرفة حالة القطعة داخل العربون
        item_status ENUM('EN_COURS', 'RETIRE', 'ANNULE') DEFAULT 'EN_COURS',
        
        FOREIGN KEY (versement_id) REFERENCES Versements(id) ON DELETE CASCADE,
        FOREIGN KEY (inventory_id) REFERENCES Inventory(id) ON DELETE SET NULL
    );""",

    """CREATE TABLE IF NOT EXISTS Versement_Payments (
        id BIGINT PRIMARY KEY AUTO_INCREMENT,
        versement_id INT NOT NULL,
        versement_item_id BIGINT NULL, 
        journee_id INT NOT NULL,
        montant_da DECIMAL(15, 2) DEFAULT 0,
        tpe_da DECIMAL(15, 2) DEFAULT 0,
        montant_euro DECIMAL(15, 2) DEFAULT 0,       
        taux_change_euro DECIMAL(15, 2) DEFAULT 0,   
        montant_dollar DECIMAL(15, 2) DEFAULT 0,     
        taux_change_dollar DECIMAL(15, 2) DEFAULT 0, 
        remise_da DECIMAL(15, 2) DEFAULT 0,          
        or_casse_g DECIMAL(10, 3) DEFAULT 0,         
        poids_deduit_g DECIMAL(10, 3) NOT NULL DEFAULT 0, 
        prix_gramme_jour_da DECIMAL(15, 2) DEFAULT 0,     
        payment_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        notes TEXT,
        
        FOREIGN KEY (versement_id) REFERENCES Versements(id) ON DELETE CASCADE,
        FOREIGN KEY (versement_item_id) REFERENCES Versement_Items(id) ON DELETE SET NULL,
        FOREIGN KEY (journee_id) REFERENCES DailySessions(id)
    );""",

    "ALTER TABLE Versement_Payments ADD COLUMN tpe_da DECIMAL(15, 2) DEFAULT 0;",
    "ALTER TABLE Versement_Payments ADD COLUMN montant_dollar DECIMAL(15, 2) DEFAULT 0;",
    "ALTER TABLE Versement_Payments ADD COLUMN taux_change_dollar DECIMAL(15, 2) DEFAULT 0;",
    "ALTER TABLE Versement_Payments ADD COLUMN remise_da DECIMAL(15, 2) DEFAULT 0;",
    "ALTER TABLE Versement_Items ADD COLUMN notes TEXT;"
]

ACHAT_OC_TABLE_QUERIES = [
    """CREATE TABLE IF NOT EXISTS AchatOC (
        id INT PRIMARY KEY AUTO_INCREMENT,
        date_achat DATE NOT NULL,
        weight_g DECIMAL(10, 3) NOT NULL,
        unit_price_da DECIMAL(15, 2) NOT NULL,
        total_amount_da DECIMAL(15, 2) NOT NULL,
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );"""
]
RH_TABLE_QUERIES = [
    """CREATE TABLE IF NOT EXISTS RH_Personnel (
        id INT PRIMARY KEY AUTO_INCREMENT,
        nom VARCHAR(150) NOT NULL,
        date_debut VARCHAR(50) NOT NULL,
        date_sortie VARCHAR(50) NULL,
        duree_travail VARCHAR(100) NULL,
        observations TEXT NULL
    );""",

    """CREATE TABLE IF NOT EXISTS RH_Avances (
        id INT PRIMARY KEY AUTO_INCREMENT,
        nom_ouvrier VARCHAR(150) NOT NULL,
        date_avance VARCHAR(50) NOT NULL,
        montant_da VARCHAR(50) NOT NULL,
        observations TEXT NULL
    );""",
]

COFFRE_MAGASIN_TABLE_QUERIES = [
    """CREATE TABLE IF NOT EXISTS CoffreMagasin (
        id INT PRIMARY KEY AUTO_INCREMENT,
        date_operation VARCHAR(50) NOT NULL,
        montant_da VARCHAR(50) NOT NULL DEFAULT '0',
        tpe VARCHAR(50) NOT NULL DEFAULT '0',
        ccp VARCHAR(50) NOT NULL DEFAULT '0',
        euro VARCHAR(50) NOT NULL DEFAULT '0',
        dollar VARCHAR(50) NOT NULL DEFAULT '0',
        designation TEXT NULL
    );""",
]
ARTISAN_WORK_TABLE_QUERIES = [
    """CREATE TABLE IF NOT EXISTS Artisans (
        id INT PRIMARY KEY AUTO_INCREMENT,
        name VARCHAR(150) NOT NULL UNIQUE,
        phone VARCHAR(50) NULL,
        notes TEXT NULL
    );""",

    """CREATE TABLE IF NOT EXISTS ArtisanWorkOrders (
        id INT PRIMARY KEY AUTO_INCREMENT,
        artisan_id INT NOT NULL,
        client_id INT NULL,                  -- 🟢 تم إضافة عمود لربط الزبون
        numero VARCHAR(50) NOT NULL DEFAULT 'x',
        date_remis VARCHAR(50),
        obj TEXT,
        poid VARCHAR(50),
        date_recue VARCHAR(50),
        date_sortie VARCHAR(50),
        prix VARCHAR(50),
        vente VARCHAR(50),
        diff VARCHAR(50),
        FOREIGN KEY (artisan_id) REFERENCES Artisans(id) ON DELETE RESTRICT,
        FOREIGN KEY (client_id) REFERENCES Clients(id) ON DELETE SET NULL  -- 🟢 ربط جدول الزبائن
    );""",
]

FINANCIAL_TABLE_QUERIES = [
]

SERVICES_LOG_TABLE_QUERIES = [
]
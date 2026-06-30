"""
schema/views_indexes.py
-----------------------
تعريفات Views و Indexes لقاعدة البيانات.
"""

# ============================================================
# Views (مشاهد SQL)
# ============================================================
VIEW_QUERIES = [
    """CREATE OR REPLACE VIEW SupplierBalanceView AS
    SELECT
        s.id AS supplier_id,
        s.name AS supplier_name,
        (
            COALESCE((
                SELECT SUM(initial_amount)
                FROM PartnerInitialBalances
                WHERE partner_id=s.id AND partner_type='SUPPLIER' AND currency_id = 1
            ), 0)
            +
            COALESCE((
                SELECT SUM(
                    CASE
                        WHEN COALESCE(t.amount_debit, 0) <> 0 OR COALESCE(t.amount_credit, 0) <> 0
                            THEN COALESCE(t.amount_credit, 0) - COALESCE(t.amount_debit, 0)
                        WHEN t.currency_id = 1 AND UPPER(COALESCE(t.type, '')) LIKE 'PURCHASE%'
                            THEN COALESCE(t.amount, 0)
                        WHEN t.currency_id = 1 AND (
                            UPPER(COALESCE(t.type, '')) LIKE 'PAYMENT%'
                            OR UPPER(COALESCE(t.type, '')) LIKE 'RETURN%'
                        )
                            THEN -COALESCE(t.amount, 0)
                        ELSE 0
                    END
                )
                FROM SupplierTransactions t
                WHERE t.supplier_id=s.id
                  AND (
                      t.operation_id IS NULL
                      OR EXISTS (
                          SELECT 1 FROM SupplierOperations so
                          WHERE so.id = t.operation_id AND so.status = 'POSTED'
                      )
                  )
            ), 0)
        ) AS money_balance_dzd,
        (
            COALESCE((
                SELECT SUM(pib.initial_amount)
                FROM PartnerInitialBalances pib
                LEFT JOIN MetalTypes mt ON mt.id = pib.metal_type_id
                WHERE pib.partner_id=s.id
                  AND pib.partner_type='SUPPLIER'
                  AND pib.metal_type_id IS NOT NULL
                  AND (
                      mt.metal_category = 'GOLD'
                      OR (
                          COALESCE(mt.metal_category, '') <> 'SILVER'
                          AND LOWER(COALESCE(mt.name, '')) NOT LIKE '%argent%'
                          AND pib.metal_type_id NOT IN (6,7,8,9)
                      )
                  )
            ), 0)
            +
            COALESCE((
                SELECT SUM(
                    CASE
                        WHEN COALESCE(t.accounted_weight_debit, 0) <> 0 OR COALESCE(t.accounted_weight_credit, 0) <> 0
                            THEN COALESCE(t.accounted_weight_credit, 0) - COALESCE(t.accounted_weight_debit, 0)
                        WHEN t.metal_type_id IS NOT NULL AND UPPER(COALESCE(t.type, '')) LIKE 'PURCHASE%'
                            THEN COALESCE(t.amount, 0)
                        WHEN t.metal_type_id IS NOT NULL AND (
                            UPPER(COALESCE(t.type, '')) LIKE 'PAYMENT%'
                            OR UPPER(COALESCE(t.type, '')) LIKE 'RETURN%'
                        )
                            THEN -COALESCE(t.amount, 0)
                        ELSE 0
                    END
                )
                FROM SupplierTransactions t
                LEFT JOIN MetalTypes mt ON mt.id = COALESCE(t.input_metal_type_id, t.metal_type_id)
                WHERE t.supplier_id=s.id
                  AND (
                      t.operation_id IS NULL
                      OR EXISTS (
                          SELECT 1 FROM SupplierOperations so
                          WHERE so.id = t.operation_id AND so.status = 'POSTED'
                      )
                  )
                  AND (
                      mt.metal_category = 'GOLD'
                      OR (
                          COALESCE(mt.metal_category, '') <> 'SILVER'
                          AND LOWER(COALESCE(mt.name, '')) NOT LIKE '%argent%'
                          AND COALESCE(t.input_metal_type_id, t.metal_type_id, 0) NOT IN (6,7,8,9)
                      )
                  )
            ), 0)
        ) AS gold_balance_grams,
        (
            COALESCE((
                SELECT SUM(pib.initial_amount)
                FROM PartnerInitialBalances pib
                LEFT JOIN MetalTypes mt ON mt.id = pib.metal_type_id
                WHERE pib.partner_id=s.id
                  AND pib.partner_type='SUPPLIER'
                  AND pib.metal_type_id IS NOT NULL
                  AND (
                      mt.metal_category = 'SILVER'
                      OR LOWER(COALESCE(mt.name, '')) LIKE '%argent%'
                      OR pib.metal_type_id IN (6,7,8,9)
                  )
            ), 0)
            +
            COALESCE((
                SELECT SUM(
                    CASE
                        WHEN COALESCE(t.accounted_weight_debit, 0) <> 0 OR COALESCE(t.accounted_weight_credit, 0) <> 0
                            THEN COALESCE(t.accounted_weight_credit, 0) - COALESCE(t.accounted_weight_debit, 0)
                        WHEN t.metal_type_id IS NOT NULL AND UPPER(COALESCE(t.type, '')) LIKE 'PURCHASE%'
                            THEN COALESCE(t.amount, 0)
                        WHEN t.metal_type_id IS NOT NULL AND (
                            UPPER(COALESCE(t.type, '')) LIKE 'PAYMENT%'
                            OR UPPER(COALESCE(t.type, '')) LIKE 'RETURN%'
                        )
                            THEN -COALESCE(t.amount, 0)
                        ELSE 0
                    END
                )
                FROM SupplierTransactions t
                LEFT JOIN MetalTypes mt ON mt.id = COALESCE(t.input_metal_type_id, t.metal_type_id)
                WHERE t.supplier_id=s.id
                  AND (
                      t.operation_id IS NULL
                      OR EXISTS (
                          SELECT 1 FROM SupplierOperations so
                          WHERE so.id = t.operation_id AND so.status = 'POSTED'
                      )
                  )
                  AND (
                      mt.metal_category = 'SILVER'
                      OR LOWER(COALESCE(mt.name, '')) LIKE '%argent%'
                      OR COALESCE(t.input_metal_type_id, t.metal_type_id) IN (6,7,8,9)
                  )
            ), 0)
        ) AS silver_balance_grams
    FROM Suppliers s;""",

    """CREATE OR REPLACE VIEW ClientDocumentsView AS
    SELECT
        CONCAT(
            CASE
                WHEN COALESCE(s.source_type, 'NORMAL') IN ('LEGACY_CLIENT_CREDIT', 'LEGACY_OPENING_BALANCE')
                    THEN 'CREDIT_CLIENT'
                ELSE 'FACTURE'
            END,
            ':',
            s.id
        ) AS document_uid,
        CASE
            WHEN COALESCE(s.source_type, 'NORMAL') IN ('LEGACY_CLIENT_CREDIT', 'LEGACY_OPENING_BALANCE')
                THEN 'CREDIT_CLIENT'
            ELSE 'FACTURE'
        END AS document_type,
        CASE
            WHEN COALESCE(s.source_type, 'NORMAL') IN ('LEGACY_CLIENT_CREDIT', 'LEGACY_OPENING_BALANCE')
                THEN 'CREDIT_CLIENT'
            ELSE NULL
        END AS versement_type,
        s.id AS source_id,
        CASE
            WHEN COALESCE(s.source_type, 'NORMAL') IN ('LEGACY_CLIENT_CREDIT', 'LEGACY_OPENING_BALANCE')
                THEN NULL
            ELSE s.facture_sequence
        END AS document_sequence,
        CASE
            WHEN COALESCE(s.source_type, 'NORMAL') IN ('LEGACY_CLIENT_CREDIT', 'LEGACY_OPENING_BALANCE')
                THEN COALESCE(NULLIF(s.legacy_source_ref, ''), NULLIF(s.facture_number, ''))
            ELSE s.facture_number
        END AS document_number,
        s.client_id,
        c.name AS client_name,
        s.sale_date AS document_date,
        s.final_amount AS total_amount,
        s.paid_amount AS paid_amount,
        s.remaining_amount AS remaining_amount,
        s.payment_status AS document_status,
        s.source_versement_id AS source_versement_id,
        NULL AS linked_sale_id
    FROM Sales s
    LEFT JOIN Clients c ON c.id = s.client_id
    WHERE UPPER(COALESCE(s.payment_status, '')) NOT IN ('CANCELLED', 'CANCELED', 'ABANDONED')

    UNION ALL

    SELECT
        CONCAT('VERSEMENT:', v.id) AS document_uid,
        'VERSEMENT' AS document_type,
        v.versement_type AS versement_type,
        v.id AS source_id,
        v.versement_sequence AS document_sequence,
        v.versement_number AS document_number,
        v.client_id,
        c.name AS client_name,
        COALESCE(cvp_last.last_payment_date, v.opened_at) AS document_date,
        v.total_amount AS total_amount,
        v.paid_amount AS paid_amount,
        v.remaining_amount AS remaining_amount,
        v.status AS document_status,
        v.source_free_versement_id AS source_versement_id,
        v.linked_sale_id AS linked_sale_id
    FROM ClientVersements v
    LEFT JOIN Clients c ON c.id = v.client_id
    LEFT JOIN (
        SELECT
            cvp_latest.versement_id,
            MAX(cvp_latest.payment_date) AS last_payment_date
        FROM ClientVersementPayments cvp_latest
        WHERE (
                GREATEST(COALESCE(cvp_latest.amount_base, 0), COALESCE(cvp_latest.amount, 0)) > 0.05
                OR COALESCE(cvp_latest.paid_weight, 0) > 0.005
            )
          AND COALESCE(cvp_latest.source_type, '') <> 'CORRECTION'
          AND COALESCE(cvp_latest.payment_method, '') <> 'REVERSAL'
          AND NOT EXISTS (
              SELECT 1
              FROM ClientVersementPayments cvp_latest_reversal
              WHERE cvp_latest_reversal.versement_id = cvp_latest.versement_id
                AND cvp_latest_reversal.source_type = 'CORRECTION'
                AND cvp_latest_reversal.payment_method = 'REVERSAL'
                AND cvp_latest_reversal.notes LIKE CONCAT('%REVERSAL_OF_CVP:', cvp_latest.id, '%')
              LIMIT 1
          )
        GROUP BY cvp_latest.versement_id
    ) cvp_last ON cvp_last.versement_id = v.id
    WHERE COALESCE(v.status, 'OPEN') NOT IN ('CANCELLED', 'ABANDONED')
      AND (
        EXISTS (
            SELECT 1
            FROM ClientVersementPayments cvp_visible
            WHERE cvp_visible.versement_id = v.id
              AND (
                  GREATEST(COALESCE(cvp_visible.amount_base, 0), COALESCE(cvp_visible.amount, 0)) > 0.05
                  OR COALESCE(cvp_visible.paid_weight, 0) > 0.005
              )
              AND COALESCE(cvp_visible.source_type, '') <> 'CORRECTION'
              AND COALESCE(cvp_visible.payment_method, '') <> 'REVERSAL'
              AND NOT EXISTS (
                  SELECT 1
                  FROM ClientVersementPayments cvp_reversal
                  WHERE cvp_reversal.versement_id = cvp_visible.versement_id
                    AND cvp_reversal.source_type = 'CORRECTION'
                    AND cvp_reversal.payment_method = 'REVERSAL'
                    AND cvp_reversal.notes LIKE CONCAT('%REVERSAL_OF_CVP:', cvp_visible.id, '%')
                  LIMIT 1
              )
            LIMIT 1
        )
        OR (
            v.versement_type = 'VERSEMENT_PRODUIT'
            AND COALESCE(v.status, 'OPEN') NOT IN ('CANCELLED', 'ABANDONED')
            AND EXISTS (
                SELECT 1
                FROM ClientVersementItems cvi_visible
                WHERE cvi_visible.versement_id = v.id
                  AND COALESCE(cvi_visible.status, 'OPEN') <> 'CANCELLED'
                  AND (
                      COALESCE(cvi_visible.total_amount, 0) > 0.05
                      OR COALESCE(cvi_visible.total_weight, 0) > 0.005
                      OR COALESCE(cvi_visible.remaining_weight, 0) > 0.005
                  )
                LIMIT 1
            )
        )
    );""",

    """CREATE OR REPLACE VIEW ZakatEstimationView AS
    SELECT
        (
            SELECT COALESCE(SUM(
                CASE
                    WHEN item_type = 'WEIGHT' THEN COALESCE(remaining_weight, 0)
                    WHEN item_type = 'PIECE' THEN COALESCE(weight, 0) * COALESCE(remaining_quantity, 0)
                    ELSE 0
                END
            ), 0)
            FROM Inventory
            WHERE status IN ('Available', 'Partially_Sold')
              AND (
                  (item_type = 'WEIGHT' AND COALESCE(remaining_weight, 0) > 0)
                  OR
                  (item_type = 'PIECE' AND COALESCE(remaining_quantity, 0) > 0)
              )
        ) AS total_gold_weight,
        (SELECT COALESCE(SUM(amount), 0) FROM MoneyTransactions WHERE currency_id = 1) AS cash_balance_dzd,
        (SELECT COALESCE(SUM(remaining_amount), 0) FROM Sales WHERE payment_status != 'Paid') AS receivables_clients,
        (SELECT SUM(money_balance_dzd) FROM SupplierBalanceView WHERE money_balance_dzd > 0) AS payables_suppliers_money;""",
]

# ============================================================
# Indexes (فهارس الأداء)
# ============================================================
INDEX_QUERIES = [
    "CREATE INDEX idx_inv_barcode ON Inventory(barcode);",
    "CREATE INDEX idx_inv_status ON Inventory(status);",
    "CREATE INDEX idx_inv_real_stock_weight ON Inventory(status, item_type, remaining_weight, id);",
    "CREATE INDEX idx_inv_real_stock_piece ON Inventory(status, item_type, remaining_quantity, id);",
    "CREATE INDEX idx_inv_category_status ON Inventory(category_id, status, item_type);",
    "CREATE INDEX idx_inv_metal_status ON Inventory(metal_type_id, status, item_type);",
    "CREATE INDEX idx_inv_location_status ON Inventory(location_id, status, item_type);",
    "CREATE INDEX idx_sales_date ON Sales(sale_date);",
    "CREATE INDEX idx_client_versement_payments_versement_date ON ClientVersementPayments(versement_id, payment_date);",
    "CREATE INDEX idx_supplier_trans_date ON SupplierTransactions(transaction_date);",
    "CREATE INDEX idx_supplier_trans_supplier_date ON SupplierTransactions(supplier_id, transaction_date);",
    "CREATE INDEX idx_supplier_trans_account_date ON SupplierTransactions(supplier_account_id, transaction_date);",
    "CREATE INDEX idx_supplier_trans_operation ON SupplierTransactions(operation_id);",
    "CREATE INDEX idx_supplier_trans_currency ON SupplierTransactions(currency_id);",
    "CREATE INDEX idx_supplier_trans_metal ON SupplierTransactions(metal_type_id, input_metal_type_id);",
    "CREATE INDEX idx_supplier_accounts_supplier_type ON SupplierAccounts(supplier_id, account_type, is_active);",
    "CREATE INDEX idx_supplier_operations_supplier_date ON SupplierOperations(supplier_id, operation_date);",
    "CREATE INDEX idx_supplier_operations_account_date ON SupplierOperations(supplier_account_id, operation_date);",
    "CREATE INDEX idx_supplier_operation_lines_operation ON SupplierOperationLines(operation_id);",
    "CREATE INDEX idx_partner_initial_supplier_account ON PartnerInitialBalances(supplier_account_id);",
    "CREATE INDEX idx_treasury_metals_status ON TreasuryMetals(status);",
    "CREATE INDEX idx_money_trans_date ON MoneyTransactions(transaction_date);",
]

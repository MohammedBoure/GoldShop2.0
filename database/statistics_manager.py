# database/statistics_manager.py

import logging
from datetime import datetime, timedelta, date

class StatisticsManager:
    GOLD_REFERENCE_PURITY = 750.0
    SILVER_REFERENCE_PURITY = 925.0

    def __init__(self, db_instance):
        self.db = db_instance

    @staticmethod
    def _calculate_equivalent_weight(items, reference_purity):
        if reference_purity <= 0:
            return 0.0

        total = 0.0
        for item in items:
            weight = float(item.get('weight') or 0.0)
            purity = float(item.get('purity_value') or 0.0)
            if purity > 0:
                total += weight * purity / reference_purity
        return round(total, 3)

    def get_dashboard_metrics(self):
        metrics = {
            'gold_inventory_by_karat': [],    
            'silver_inventory_by_karat': [],  
            'gold_inventory_equivalent_750': 0.0,
            'silver_inventory_equivalent_925': 0.0,
            'coffre_gold_by_location': [],
            'coffre_silver_by_location': [], 
            'total_cash_dzd': 0.0,
            'client_debts': 0.0,
            'supplier_debts': 0.0,
            'supplier_debts_gold': 0.0,      
            'supplier_debts_silver': 0.0     
        }
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)

                # 1. ذهب الواجهة
                query_gold = """
                    SELECT COALESCE(mt.name, 'Or Inconnu') as name,
                           mt.purity_value as purity_value,
                           SUM(CASE WHEN i.item_type = 'WEIGHT' THEN i.remaining_weight ELSE (i.weight * COALESCE(i.remaining_quantity, 1)) END) as weight
                    FROM Inventory i
                    LEFT JOIN MetalTypes mt ON i.metal_type_id = mt.id
                    WHERE i.status IN ('Available', 'Partially_Sold') 
                      AND (
                          (i.item_type = 'WEIGHT' AND COALESCE(i.remaining_weight, 0) > 0)
                          OR
                          (i.item_type = 'PIECE' AND COALESCE(i.remaining_quantity, 0) > 0)
                      )
                      AND (mt.metal_category = 'GOLD' OR mt.metal_category IS NULL)
                      AND LOWER(COALESCE(mt.name, '')) NOT LIKE '%argent%'
                    GROUP BY mt.name, mt.purity_value
                """
                cursor.execute(query_gold)
                metrics['gold_inventory_by_karat'] = cursor.fetchall()
                metrics['gold_inventory_equivalent_750'] = self._calculate_equivalent_weight(
                    metrics['gold_inventory_by_karat'],
                    self.GOLD_REFERENCE_PURITY,
                )

                # 2. فضة الواجهة
                query_silver = """
                    SELECT COALESCE(mt.name, 'Argent Inconnu') as name,
                           mt.purity_value as purity_value,
                           SUM(CASE WHEN i.item_type = 'WEIGHT' THEN i.remaining_weight ELSE (i.weight * COALESCE(i.remaining_quantity, 1)) END) as weight
                    FROM Inventory i
                    LEFT JOIN MetalTypes mt ON i.metal_type_id = mt.id
                    WHERE i.status IN ('Available', 'Partially_Sold') 
                      AND (
                          (i.item_type = 'WEIGHT' AND COALESCE(i.remaining_weight, 0) > 0)
                          OR
                          (i.item_type = 'PIECE' AND COALESCE(i.remaining_quantity, 0) > 0)
                      )
                      AND (mt.metal_category = 'SILVER' OR LOWER(COALESCE(mt.name, '')) LIKE '%argent%')
                    GROUP BY mt.name, mt.purity_value
                """
                cursor.execute(query_silver)
                metrics['silver_inventory_by_karat'] = cursor.fetchall()
                metrics['silver_inventory_equivalent_925'] = self._calculate_equivalent_weight(
                    metrics['silver_inventory_by_karat'],
                    self.SILVER_REFERENCE_PURITY,
                )

                metrics['coffre_gold_by_location'] = []
                metrics['coffre_silver_by_location'] = []

                # 5. السيولة النقدية DZD من المبيعات والخزنة
                query_cash = """
                    SELECT (
                        COALESCE((SELECT SUM(cash_paid_da + tpe_paid_da) FROM Sales WHERE status = 'COMPLETED'), 0) +
                        COALESCE((SELECT SUM(CAST(montant_da AS DECIMAL(15,2))) FROM CoffreMagasin), 0)
                    ) as balance
                """
                cursor.execute(query_cash)
                cash_res = cursor.fetchone()
                metrics['total_cash_dzd'] = float(cash_res['balance'] or 0) if cash_res else 0.0

                # 6. ديون الزبائن (العرابين المتبقية)
                query_client_debts = """
                    SELECT COALESCE(SUM(montant_da), 0) as debts
                    FROM Versement_Payments
                """
                cursor.execute(query_client_debts)
                res_c_debts = cursor.fetchone()
                metrics['client_debts'] = float(res_c_debts['debts'] or 0) if res_c_debts else 0.0

                # 7. ديون وأرصدة الموردين (DZD, GOLD)
                query_supp_money = """
                    SELECT COALESCE(SUM(amount_credit - amount_debit), 0) as total_debt
                    FROM SupplierTransactions
                """
                cursor.execute(query_supp_money)
                res_s_money = cursor.fetchone()
                metrics['supplier_debts'] = float(res_s_money['total_debt'] or 0) if res_s_money else 0.0

                query_supp_gold = """
                    SELECT COALESCE(SUM(accounted_weight_credit - accounted_weight_debit), 0) as total_debt
                    FROM SupplierTransactions
                """
                cursor.execute(query_supp_gold)
                res_s_gold = cursor.fetchone()
                metrics['supplier_debts_gold'] = float(res_s_gold['total_debt'] or 0) if res_s_gold else 0.0

                metrics['supplier_debts_silver'] = 0.0

        except Exception as e:
            logging.error(f"Dashboard Metrics Error: {e}", exc_info=True)
            
        return metrics
    
    def get_sales_trend(self, days=30, start_date=None, end_date=None, granularity="day"):
        data = []
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                where_clauses = ["status = 'COMPLETED'"]
                params = []

                if start_date and end_date:
                    where_clauses.append("DATE(created_at) BETWEEN %s AND %s")
                    params.extend([str(start_date), str(end_date)])
                elif days is not None and days > 0:
                    where_clauses.append("created_at >= DATE_SUB(CURDATE(), INTERVAL %s DAY)")
                    params.append(days)

                where_sql = " AND ".join(where_clauses)
                if where_sql:
                    where_sql = "WHERE " + where_sql

                granularity = (granularity or "day").lower()
                if granularity == "month":
                    query = f"""
                        SELECT 
                            DATE_FORMAT(created_at, '%Y-%m') as period_key,
                            DATE(DATE_FORMAT(created_at, '%Y-%m-01')) as date,
                            SUM(net_to_pay_da) as daily_value,
                            SUM(net_to_pay_da) as total_amount,
                            COUNT(*) as count
                        FROM Sales
                        {where_sql}
                        GROUP BY DATE_FORMAT(created_at, '%Y-%m')
                        ORDER BY date ASC
                    """
                elif granularity == "week":
                    query = f"""
                        SELECT 
                            DATE_FORMAT(DATE_SUB(DATE(created_at), INTERVAL WEEKDAY(created_at) DAY), '%Y-%m-%d') as period_key,
                            DATE_SUB(DATE(created_at), INTERVAL WEEKDAY(created_at) DAY) as date,
                            SUM(net_to_pay_da) as daily_value,
                            SUM(net_to_pay_da) as total_amount,
                            COUNT(*) as count
                        FROM Sales
                        {where_sql}
                        GROUP BY DATE_SUB(DATE(created_at), INTERVAL WEEKDAY(created_at) DAY)
                        ORDER BY date ASC
                    """
                else:
                    query = f"""
                        SELECT 
                            DATE_FORMAT(created_at, '%Y-%m-%d') as period_key,
                            DATE(created_at) as date,
                            SUM(net_to_pay_da) as daily_value,
                            SUM(net_to_pay_da) as total_amount,
                            COUNT(*) as count
                        FROM Sales
                        {where_sql}
                        GROUP BY DATE(created_at)
                        ORDER BY date ASC
                    """

                cursor.execute(query, tuple(params))
                data = cursor.fetchall()
        except Exception as e:
            logging.error(f"Error getting sales trend: {e}")
        return data

    def get_purchases_trend(self, days=30, start_date=None, end_date=None, granularity="day"):
        data = []
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                where_clauses = []
                params = []

                if start_date and end_date:
                    where_clauses.append("DATE(transaction_date) BETWEEN %s AND %s")
                    params.extend([str(start_date), str(end_date)])
                elif days is not None and days > 0:
                    where_clauses.append("transaction_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)")
                    params.append(days)

                where_sql = " AND ".join(where_clauses)
                if where_sql:
                    where_sql = "WHERE " + where_sql

                granularity = (granularity or "day").lower()
                amount_expr = "COALESCE(CASE WHEN amount_debit > 0 THEN amount_debit ELSE ABS(amount) END, 0)"

                if granularity == "month":
                    query = f"""
                        SELECT
                            DATE_FORMAT(transaction_date, '%Y-%m') as period_key,
                            DATE(DATE_FORMAT(transaction_date, '%Y-%m-01')) as date,
                            SUM({amount_expr}) as daily_cost,
                            SUM({amount_expr}) as total_amount,
                            COUNT(*) as count
                        FROM SupplierTransactions
                        {where_sql}
                        GROUP BY DATE_FORMAT(transaction_date, '%Y-%m')
                        ORDER BY date ASC
                    """
                elif granularity == "week":
                    query = f"""
                        SELECT
                            DATE_FORMAT(DATE_SUB(DATE(transaction_date), INTERVAL WEEKDAY(transaction_date) DAY), '%Y-%m-%d') as period_key,
                            DATE_SUB(DATE(transaction_date), INTERVAL WEEKDAY(transaction_date) DAY) as date,
                            SUM({amount_expr}) as daily_cost,
                            SUM({amount_expr}) as total_amount,
                            COUNT(*) as count
                        FROM SupplierTransactions
                        {where_sql}
                        GROUP BY DATE_SUB(DATE(transaction_date), INTERVAL WEEKDAY(transaction_date) DAY)
                        ORDER BY date ASC
                    """
                else:
                    query = f"""
                        SELECT
                            DATE_FORMAT(transaction_date, '%Y-%m-%d') as period_key,
                            DATE(transaction_date) as date,
                            SUM({amount_expr}) as daily_cost,
                            SUM({amount_expr}) as total_amount,
                            COUNT(*) as count
                        FROM SupplierTransactions
                        {where_sql}
                        GROUP BY DATE(transaction_date)
                        ORDER BY date ASC
                    """

                cursor.execute(query, tuple(params))
                data = cursor.fetchall()
        except Exception as e:
            logging.error(f"Error getting purchases trend: {e}")
        return data

    def get_financial_trend(self, days=30, start_date=None, end_date=None, granularity="day"):
        """جلب التدفق المالي المجمع (مبيعات ومشتريات) للفترة المحددة مع حساب الصافي"""
        sales = self.get_sales_trend(days=days, start_date=start_date, end_date=end_date, granularity=granularity)
        purchases = self.get_purchases_trend(days=days, start_date=start_date, end_date=end_date, granularity=granularity)

        combined = {}
        for s in sales:
            k = str(s.get("period_key") or s.get("date") or "")
            if not k:
                continue
            combined[k] = {
                "period_key": k,
                "date": str(s.get("date") or k),
                "inflow": float(s.get("total_amount") or s.get("daily_value") or 0.0),
                "outflow": 0.0,
                "sales_count": int(s.get("count") or 1)
            }

        for p in purchases:
            k = str(p.get("period_key") or p.get("date") or "")
            if not k:
                continue
            if k not in combined:
                combined[k] = {
                    "period_key": k,
                    "date": str(p.get("date") or k),
                    "inflow": 0.0,
                    "outflow": float(p.get("total_amount") or p.get("daily_cost") or 0.0),
                    "sales_count": 0
                }
            else:
                combined[k]["outflow"] = float(p.get("total_amount") or p.get("daily_cost") or 0.0)

        # ترتيب النتائج زمنياً
        sorted_keys = sorted(combined.keys())
        result = []
        for k in sorted_keys:
            entry = combined[k]
            entry["net"] = entry["inflow"] - entry["outflow"]
            result.append(entry)

        return result

    def get_active_alerts(self):
        alerts = []
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query_low = """
                    SELECT i.id, i.name as Product, c.name as Family, COALESCE(i.remaining_weight, 0) as Val, 'Urgente' as Type, 'Stock Épuisé' as Details
                    FROM Inventory i
                    LEFT JOIN Categories c ON i.category_id = c.id
                    WHERE i.status = 'Available' AND COALESCE(i.remaining_weight, 0) <= 0
                    LIMIT 20
                """
                cursor.execute(query_low)
                alerts.extend(cursor.fetchall())

                query_old = """
                    SELECT i.id, i.name as Product, c.name as Family, DATEDIFF(NOW(), i.entry_date) as Val, 'Stock' as Type, 'Invendu' as Details
                    FROM Inventory i
                    LEFT JOIN Categories c ON i.category_id = c.id
                    WHERE i.status = 'Available' AND i.entry_date < DATE_SUB(NOW(), INTERVAL 6 MONTH)
                    LIMIT 20
                """
                cursor.execute(query_old)
                for item in cursor.fetchall():
                    item['Details'] = f"Depuis {item['Val']} jours"
                    item['Val'] = "Dormant"
                    alerts.append(item)
        except Exception as e:
            pass
        return alerts

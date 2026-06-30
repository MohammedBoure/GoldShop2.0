# database/managers/reports_manager.py

import logging
from datetime import datetime, timedelta

class ReportsManager:
    def __init__(self, db_instance):
        self.db = db_instance

    def get_daily_summary(self, day_date):
        """تقرير ملخص ليوم محدد (يعتمد على الأموال التي دخلت الصندوق فعلاً)"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # المبيعات بناءً على الدفعات وليس إجمالي الفاتورة
                cursor.execute("""
                    SELECT COUNT(*) as count, COALESCE(SUM(paid_amount), 0) as total
                    FROM Sales
                    WHERE DATE(sale_date) = %s
                      AND COALESCE(source_type, 'NORMAL') = 'NORMAL'
                """, (day_date,))
                sales = cursor.fetchone()

                # المصاريف بالدينار
                cursor.execute("""
                    SELECT COALESCE(SUM(e.amount * COALESCE(c.exchange_rate, 1)), 0) as total 
                    FROM Expenses e
                    LEFT JOIN Currencies c ON e.currency_id = c.id
                    WHERE DATE(e.expense_date) = %s AND e.expense_type != 'PERSONAL_DRAWING'
                """, (day_date,))
                expenses = cursor.fetchone()

                # الدفعات المستلمة
                cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM ClientPayments WHERE DATE(payment_date) = %s AND currency_id = 1", (day_date,))
                payments = cursor.fetchone()

                return {
                    'sales_count': sales['count'],
                    'sales_total': float(sales['total']),
                    'expenses_total': float(expenses['total']),
                    'payments_received': float(payments['total'])
                }
        except Exception as e:
            logging.error(f"Error daily summary: {e}")
            return {'sales_count': 0, 'sales_total': 0.0, 'expenses_total': 0.0, 'payments_received': 0.0}


    def get_custom_range_summary(self, start_date, end_date):
        """🟢 تقرير شامل ضمن نطاق تاريخي مع تثبيت أسعار العملات والمعادن وقت وقوع العملية"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # 1. المبيعات والتكاليف التناسبية
                cursor.execute("""
                    SELECT final_amount, paid_amount, total_cost
                    FROM Sales 
                    WHERE DATE(sale_date) BETWEEN %s AND %s
                      AND payment_status != 'Cancelled'
                      AND COALESCE(source_type, 'NORMAL') = 'NORMAL'
                """, (start_date, end_date))
                
                sales_list = cursor.fetchall()
                realized_sales = 0.0
                realized_cogs = 0.0
                
                for sale in sales_list:
                    f_amt = float(sale['final_amount'] or 0)
                    p_amt = float(sale['paid_amount'] or 0)
                    t_cost = float(sale['total_cost'] or 0)
                    ratio = min(1.0, p_amt / f_amt) if f_amt > 0 else 1.0
                    realized_sales += f_amt * ratio
                    realized_cogs += t_cost * ratio

                # 2. المصاريف مع حساب السعر "في ذلك الوقت"
                # نستخدم حقل exchange_rate_at_time (إذا وجد) أو السعر الحالي كاحتياطي
                cursor.execute("""
                    SELECT COALESCE(SUM(e.amount * COALESCE(e.exchange_rate_at_time, c.exchange_rate, 1)), 0) as total 
                    FROM Expenses e
                    LEFT JOIN Currencies c ON e.currency_id = c.id
                    WHERE DATE(e.expense_date) BETWEEN %s AND %s 
                    AND e.expense_type != 'PERSONAL_DRAWING'
                """, (start_date, end_date))
                expenses_total = cursor.fetchone()['total']

                # 3. تفصيل المصاريف
                cursor.execute("""
                    SELECT 
                        cat.name as category, 
                        COALESCE(c.code, 'DZD') as currency_code,
                        SUM(e.amount) as original_amount,
                        SUM(e.amount * COALESCE(e.exchange_rate_at_time, c.exchange_rate, 1)) as amount_dzd
                    FROM Expenses e
                    JOIN ExpenseCategories cat ON e.expense_category_id = cat.id
                    LEFT JOIN Currencies c ON e.currency_id = c.id
                    WHERE DATE(e.expense_date) BETWEEN %s AND %s
                    AND e.expense_type != 'PERSONAL_DRAWING'
                    GROUP BY cat.name, c.code
                    ORDER BY amount_dzd DESC
                """, (start_date, end_date))
                expenses_breakdown = cursor.fetchall()

                # 4. مصاريف الحرفيين
                cursor.execute("""
                    SELECT s.name as artisan_name, COUNT(r.id) as items_count, COALESCE(SUM(r.labor_cost), 0) as total_paid
                    FROM Repairs r
                    JOIN Suppliers s ON r.artisan_id = s.id
                    WHERE DATE(r.delivery_date) BETWEEN %s AND %s AND r.status = 'Delivered'
                    GROUP BY s.name
                """, (start_date, end_date))
                artisan_breakdown = cursor.fetchall()

                return {
                    'sales_total': float(realized_sales),
                    'cogs_total': float(realized_cogs),
                    'expenses_total': float(expenses_total),
                    'expenses_breakdown': expenses_breakdown,
                    'artisan_breakdown': artisan_breakdown
                }
        except Exception as e:
            logging.error(f"Error custom range summary: {e}")
            return {}

    def get_monthly_summary(self, year, month):
        """🟢 إحصائيات شهرية دقيقة: تعتمد على الحساب التناسبي للفائدة (نسبة وتناسب)"""
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                cursor.execute("""
                    SELECT final_amount, paid_amount, total_cost
                    FROM Sales 
                    WHERE MONTH(sale_date) = %s
                      AND YEAR(sale_date) = %s
                      AND payment_status != 'Cancelled'
                      AND COALESCE(source_type, 'NORMAL') = 'NORMAL'
                """, (month, year))
                
                sales_list = cursor.fetchall()
                
                realized_sales = 0.0
                realized_cogs = 0.0
                
                for sale in sales_list:
                    f_amt = float(sale['final_amount'] or 0)
                    p_amt = float(sale['paid_amount'] or 0)
                    t_cost = float(sale['total_cost'] or 0)
                    
                    # 🟢 حساب نسبة المدفوع من إجمالي الفاتورة لتوزيع الفائدة
                    if f_amt > 0:
                        ratio = p_amt / f_amt
                    else:
                        ratio = 1.0
                        
                    # حماية برمجية لكي لا تتجاوز النسبة 100%
                    ratio = min(1.0, max(0.0, ratio))
                    
                    # الفائدة يتم استخراجها تناسبياً (أخذ جزء من التكلفة يوازي الجزء المدفوع)
                    realized_sales += f_amt * ratio
                    realized_cogs += t_cost * ratio

                # المصاريف
                cursor.execute("""
                    SELECT COALESCE(SUM(e.amount * COALESCE(c.exchange_rate, 1)), 0) as total 
                    FROM Expenses e
                    LEFT JOIN Currencies c ON e.currency_id = c.id
                    WHERE MONTH(e.expense_date) = %s AND YEAR(e.expense_date) = %s 
                    AND e.expense_type != 'PERSONAL_DRAWING'
                """, (month, year))
                expenses_total = cursor.fetchone()['total']

                # تفصيل المصاريف
                cursor.execute("""
                    SELECT 
                        cat.name as category, 
                        COALESCE(c.code, 'DZD') as currency_code,
                        SUM(e.amount) as original_amount,
                        SUM(e.amount * COALESCE(c.exchange_rate, 1)) as amount_dzd
                    FROM Expenses e
                    JOIN ExpenseCategories cat ON e.expense_category_id = cat.id
                    LEFT JOIN Currencies c ON e.currency_id = c.id
                    WHERE MONTH(e.expense_date) = %s AND YEAR(e.expense_date) = %s
                    AND e.expense_type != 'PERSONAL_DRAWING'
                    GROUP BY cat.name, c.code, c.id
                    ORDER BY amount_dzd DESC
                """, (month, year))
                expenses_breakdown = cursor.fetchall()

                # مصاريف الحرفيين
                cursor.execute("""
                    SELECT s.name as artisan_name, COUNT(r.id) as items_count, COALESCE(SUM(r.labor_cost), 0) as total_paid
                    FROM Repairs r
                    JOIN Suppliers s ON r.artisan_id = s.id
                    WHERE MONTH(r.delivery_date) = %s AND YEAR(r.delivery_date) = %s AND r.status = 'Delivered'
                    GROUP BY s.name
                """, (month, year))
                artisan_breakdown = cursor.fetchall()

                return {
                    'sales_total': float(realized_sales),
                    'cogs_total': float(realized_cogs),
                    'expenses_total': float(expenses_total),
                    'expenses_breakdown': expenses_breakdown,
                    'artisan_breakdown': artisan_breakdown
                }
        except Exception as e:
            logging.error(f"Error monthly summary: {e}")
            return {}

    def get_sales_trend(self, days=30):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)
                query = """
                    SELECT DATE(sale_date) as day, SUM(paid_amount) as total
                    FROM Sales
                    WHERE DATE(sale_date) BETWEEN %s AND %s
                      AND COALESCE(source_type, 'NORMAL') = 'NORMAL'
                    GROUP BY DATE(sale_date)
                    ORDER BY day ASC
                """
                cursor.execute(query, (start_date, end_date))
                return cursor.fetchall()
        except Exception as e: return []

    def get_top_selling_items(self, limit=5):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                query = """
                    SELECT c.name as category_name, COUNT(*) as units_sold, SUM(si.sold_price) as revenue
                    FROM SaleItems si JOIN Inventory i ON si.inventory_id = i.id JOIN Categories c ON i.category_id = c.id
                    GROUP BY c.name ORDER BY revenue DESC LIMIT %s
                """
                cursor.execute(query, (limit,))
                return cursor.fetchall()
        except Exception as e: return []

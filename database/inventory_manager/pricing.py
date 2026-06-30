import logging


class InventoryPricingMixin:
    def update_gold_price_by_metal(self, metal_type_id, new_price_per_gram):
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                query = """
                    UPDATE Inventory
                    SET 
                        metal_cost_per_gram = %s,
                        total_cost = (%s + COALESCE(labor_cost_per_gram, 0)) * COALESCE(remaining_weight, weight),
                        
                        -- 🟢 تحديث السعر النهائي بذكاء (يحترم النسبة أو الثابت)
                        selling_price = CASE 
                            WHEN margin_type = 'PERCENTAGE' THEN 
                                ((%s + COALESCE(labor_cost_per_gram, 0)) * (1 + (COALESCE(profit_margin, 0) / 100))) * COALESCE(remaining_weight, weight)
                            ELSE 
                                (%s + COALESCE(labor_cost_per_gram, 0) + COALESCE(profit_margin, 0)) * COALESCE(remaining_weight, weight)
                        END
                    WHERE metal_type_id = %s 
                    AND status IN ('Available', 'Partially_Sold')
                    AND item_type = 'WEIGHT'
                    AND COALESCE(remaining_weight, 0) > 0
                """
                cursor.execute(query, (new_price_per_gram, new_price_per_gram, new_price_per_gram, new_price_per_gram, metal_type_id))
                rows_affected = cursor.rowcount
                
                conn.commit()
                return rows_affected, "Mise à jour réussie."

        except Exception as e:
            logging.error(f"Erreur update_gold_price: {e}")
            return False, f"Erreur: {e}"

    def bulk_update_prices(self, target_type: str, target_id: int, operation_type: int, value: float) -> int:
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                
                # الشروط الأساسية
                where_clause = (
                    "WHERE status IN ('Available', 'Partially_Sold') "
                    "AND item_type = 'WEIGHT' "
                    "AND COALESCE(remaining_weight, 0) > 0"
                )
                params = []

                # تحديد الهدف (كل المخزون، فئة معينة، أو معدن معين)
                if target_type == "CATEGORY" and target_id is not None:
                    where_clause += " AND category_id = %s"
                    params.append(target_id)
                elif target_type == "METAL" and target_id is not None:
                    where_clause += " AND metal_type_id = %s"
                    params.append(target_id)
                
                # 🟢 تحديد نوع العملية مع العزل التام
                if operation_type == 0:  # PERCENTAGE (%)
                    where_clause += " AND margin_type = 'PERCENTAGE'" # 🛡️ عزل تام: يمس فقط النسب المئوية
                    update_expr = """
                        profit_margin = profit_margin + %s, 
                        -- حساب سعر البيع الخاص بالنسبة المئوية فقط
                        selling_price = (metal_cost_per_gram + COALESCE(labor_cost_per_gram, 0)) * (1 + (profit_margin / 100)) * COALESCE(remaining_weight, weight)
                    """
                    params.extend([value])
                    
                elif operation_type == 1:  # FIXED AMOUNT (DA)
                    where_clause += " AND margin_type = 'FIXED'" # 🛡️ عزل تام: يمس فقط المبالغ الثابتة
                    update_expr = """
                        profit_margin = profit_margin + %s, 
                        -- حساب سعر البيع الخاص بالمبلغ الثابت فقط
                        selling_price = total_cost + (profit_margin * COALESCE(remaining_weight, weight))
                    """
                    params.extend([value])
                else:
                    return -1

                # دمج الاستعلام النهائي
                full_query = f"UPDATE Inventory SET {update_expr} {where_clause}"
                
                cursor.execute(full_query, tuple(params))
                rows_affected = cursor.rowcount
                conn.commit()
                return rows_affected

        except Exception as e:
            import logging
            logging.error(f"Error in bulk_update_prices: {e}")
            return -1

    def update_margin_by_weight_range(self, min_weight: float, max_weight: float, margin_type: str, new_margin: float) -> int:
        """
        تحديث الفائدة لجميع القطع (الذهب) التي يقع وزنها ضمن نطاق محدد.
        """
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                query = """
                    UPDATE Inventory
                    SET 
                        profit_margin = %s,
                        -- إعادة حساب السعر النهائي فوراً بعد تغيير الفائدة
                        selling_price = CASE 
                            WHEN margin_type = 'PERCENTAGE' THEN 
                                (metal_cost_per_gram + COALESCE(labor_cost_per_gram, 0)) * (1 + (%s / 100.0)) * COALESCE(remaining_weight, weight)
                            ELSE 
                                (metal_cost_per_gram + COALESCE(labor_cost_per_gram, 0) + %s) * COALESCE(remaining_weight, weight)
                        END
                    WHERE item_type = 'WEIGHT'
                    AND status IN ('Available', 'Partially_Sold')
                    AND margin_type = %s
                    AND COALESCE(remaining_weight, 0) > 0
                    AND remaining_weight >= %s
                    AND remaining_weight <= %s
                """
                # المعاملات: الفائدة الجديدة (للحفظ)، الفائدة للنسبة المئوية، الفائدة للمبلغ الثابت، نوع الفائدة، الوزن الأدنى، الوزن الأقصى
                cursor.execute(query, (new_margin, new_margin, new_margin, margin_type, min_weight, max_weight))
                rows_affected = cursor.rowcount
                conn.commit()
                return rows_affected

        except Exception as e:
            import logging
            logging.error(f"Error update_margin_by_weight_range: {e}")
            return -1

    def update_market_price_by_reference(
        self,
        reference_purity: float,
        new_price: float,
        target_metal_ids: list,
        currency_code: str = None,
    ) -> int:
        """Reprice remaining weighted stock while preserving each item's margin."""
        if not target_metal_ids or reference_purity <= 0 or new_price <= 0:
            return -1

        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                placeholders = ",".join(["%s"] * len(target_metal_ids))
                query = f"""
                    UPDATE Inventory i
                    JOIN MetalTypes mt ON i.metal_type_id = mt.id
                    SET
                        i.metal_cost_per_gram = (%s / %s) * mt.purity_value,
                        i.total_cost = (
                            ((%s / %s) * mt.purity_value) + COALESCE(i.labor_cost_per_gram, 0)
                        ) * COALESCE(i.remaining_weight, 0),
                        i.selling_price = CASE
                            WHEN i.margin_type = 'PERCENTAGE' THEN
                                (
                                    ((%s / %s) * mt.purity_value) + COALESCE(i.labor_cost_per_gram, 0)
                                ) * (1 + (COALESCE(i.profit_margin, 0) / 100)) * COALESCE(i.remaining_weight, 0)
                            ELSE
                                (
                                    ((%s / %s) * mt.purity_value)
                                    + COALESCE(i.labor_cost_per_gram, 0)
                                    + COALESCE(i.profit_margin, 0)
                                ) * COALESCE(i.remaining_weight, 0)
                        END
                    WHERE i.status IN ('Available', 'Partially_Sold')
                    AND i.item_type = 'WEIGHT'
                    AND COALESCE(i.remaining_weight, 0) > 0
                    AND mt.id IN ({placeholders})
                """
                params = [
                    new_price, reference_purity,
                    new_price, reference_purity,
                    new_price, reference_purity,
                    new_price, reference_purity,
                    *target_metal_ids,
                ]
                cursor.execute(query, tuple(params))
                affected = cursor.rowcount

                if currency_code:
                    cursor.execute(
                        "SELECT id FROM Currencies WHERE code = %s",
                        (currency_code,),
                    )
                    if cursor.fetchone() is None:
                        raise ValueError(f"System currency {currency_code} was not found.")
                    cursor.execute(
                        "UPDATE Currencies SET exchange_rate = %s WHERE code = %s",
                        (new_price, currency_code),
                    )

                conn.commit()
                return affected
        except Exception as e:
            logging.error(f"Error in update_market_price_by_reference: {e}")
            return -1

    def update_prices_by_reference(self, reference_purity: float, new_price: float, target_metal_ids: list, target_margin_type: str = 'PERCENTAGE', margin_adjustment: float = 0.0) -> int:
        """
        يحدث سعر الذهب لجميع القطع المحددة، لكنه يطبق زيادة/نقصان الفائدة 
        فقط على القطع التي تطابق (target_margin_type) لمنع التداخل بين الثابت والمئوي.
        """
        if not target_metal_ids or reference_purity <= 0 or new_price <= 0:
            return 0
            
        try:
            with self.db.get_db_connection() as conn:
                cursor = conn.cursor()
                format_strings = ','.join(['%s'] * len(target_metal_ids))
                
                # المعاملات: (نوع الفائدة المستهدفة، قيمة التعديل، نوع الفائدة المستهدفة، قيمة التعديل، سعر الذهب، نقاوة المرجع، ايديهات المعادن)
                params = [
                    target_margin_type, margin_adjustment, 
                    target_margin_type, margin_adjustment,
                    new_price, reference_purity
                ] + target_metal_ids
                
                query = f"""
                    UPDATE Inventory i
                    JOIN MetalTypes mt ON i.metal_type_id = mt.id
                    SET 
                        -- 1. تعديل الفائدة بأمان تام (يُعدل فقط إذا تطابق نوع الفائدة مع الخيار المحدد في الواجهة)
                        i.profit_margin = CASE 
                            WHEN i.margin_type = 'PERCENTAGE' AND %s = 'PERCENTAGE' THEN COALESCE(i.profit_margin, 0) + %s
                            WHEN i.margin_type = 'FIXED' AND %s = 'FIXED' THEN COALESCE(i.profit_margin, 0) + %s
                            ELSE COALESCE(i.profit_margin, 0)
                        END,
                        
                        -- 2. تحديث تكلفة المعدن للجميع بسعر السوق الجديد
                        i.metal_cost_per_gram = (%s / %s) * mt.purity_value,
                        i.total_cost = (i.metal_cost_per_gram + COALESCE(i.labor_cost_per_gram, 0)) * COALESCE(i.remaining_weight, i.weight, 0),
                        
                        -- 3. إعادة حساب سعر البيع لكل قطعة بناءً على نوع فائدتها الأصلي
                        i.selling_price = CASE 
                            WHEN i.margin_type = 'PERCENTAGE' THEN 
                                (i.metal_cost_per_gram + COALESCE(i.labor_cost_per_gram, 0)) * (1 + (i.profit_margin / 100)) * COALESCE(i.remaining_weight, i.weight, 0)
                            ELSE 
                                (i.metal_cost_per_gram + COALESCE(i.labor_cost_per_gram, 0) + i.profit_margin) * COALESCE(i.remaining_weight, i.weight, 0)
                        END
                        
                    WHERE i.status IN ('Available', 'Partially_Sold') 
                    AND i.item_type = 'WEIGHT'
                    AND COALESCE(i.remaining_weight, 0) > 0
                    AND mt.id IN ({format_strings})
                """
                
                cursor.execute(query, tuple(params))
                affected = cursor.rowcount
                conn.commit()
                return affected
                
        except Exception as e:
            import logging
            logging.error(f"Error in update_prices_by_reference: {e}")
            return -1

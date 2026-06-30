class InventoryBaseMixin:
    @staticmethod
    def _real_stock_condition(alias: str = "i") -> str:
        return f"""(
            ({alias}.item_type = 'WEIGHT' AND COALESCE({alias}.remaining_weight, 0) > 0)
            OR
            ({alias}.item_type = 'PIECE' AND COALESCE({alias}.remaining_quantity, 0) > 0)
        )"""

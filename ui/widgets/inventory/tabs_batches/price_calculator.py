

# ============================================================
# 1. PriceCalculator — منطق الحسابات فقط (لا واجهة)
# ============================================================
class PriceCalculator:
    """
    مسؤول عن حسابات التكلفة وسعر البيع.
    لا يعتمد على أي عنصر واجهة مباشرة؛
    يستقبل القيم ويُعيد النتائج.
    """

    @staticmethod
    def compute(weight: float, metal_cost: float, labor_cost: float,
                margin: float, margin_type: str) -> tuple[float, float]:
        """
        يُعيد (total_cost, selling_price).
        margin_type: 'FIXED' | 'PERCENTAGE'
        """
        total_cost = (metal_cost + labor_cost) * weight
        if margin_type == "PERCENTAGE":
            profit_per_gram = (metal_cost + labor_cost) * (margin / 100.0)
        else:
            profit_per_gram = margin
        selling_price = total_cost + profit_per_gram * weight
        return total_cost, selling_price


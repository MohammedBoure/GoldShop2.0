/**
 * GoldShop 2.0 - Monthly Summary View Controller (monthly.js)
 * Implements the monthly financial synthesis matching monthly_summary_view.py
 */

(function() {
  const monthSelect = document.getElementById("monthlyMonthSelect");
  const yearSelect = document.getElementById("monthlyYearSelect");

  async function fetchMonthlyData() {
    const container = document.getElementById("monthlyContentArea");
    if (!container) return;

    const now = new Date();
    const year = yearSelect ? yearSelect.value : now.getFullYear();
    const month = monthSelect ? monthSelect.value : (now.getMonth() + 1);

    container.innerHTML = `
      <div class="loading-box">
        <div class="spinner"></div>
        <div>Chargement du résumé mensuel... / جاري تحميل الحصيلة...</div>
      </div>
    `;

    try {
      const res = await GoldShopApp.apiFetch(`/api/v1/reports/monthly-summary?year=${year}&month=${month}`);
      if (res && res.data) {
        renderMonthlyKPIs(res.data.totals || {});
        renderDailyBreakdown(res.data.days || [], res.data.totals || {});
      }
    } catch (err) {
      if (err.message !== "AUTH_REQUIRED") {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">⚠️</div>
            <div>Erreur de chargement de la synthèse mensuelle.</div>
            <button class="btn-secondary" onclick="window.refreshCurrentPageData()">Réessayer</button>
          </div>
        `;
      }
    }
  }

  function renderMonthlyKPIs(totals) {
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    };

    setVal("kpiMonthlySales", GoldShopApp.formatMoney(totals.sales_total_da || 0));
    setVal("kpiMonthlyCash", GoldShopApp.formatMoney(totals.cash_da || 0));
    setVal("kpiMonthlyTpe", GoldShopApp.formatMoney(totals.tpe_da || 0));
    setVal("kpiMonthlyOc", `${GoldShopApp.formatWeight(totals.oc_weight_g || 0)} (${GoldShopApp.formatMoney(totals.oc_amount_da || 0)})`);
    setVal("kpiMonthlyVersements", GoldShopApp.formatMoney(totals.versements_da || 0));
    setVal("kpiMonthlyWorkshop", GoldShopApp.formatMoney(totals.workshop_da || 0));
    setVal("kpiMonthlyBenefice", GoldShopApp.formatMoney(totals.total_benefice_da || totals.benefice_da || 0));
  }

  function renderDailyBreakdown(days, totals) {
    const container = document.getElementById("monthlyContentArea");
    if (!container) return;

    if (!days || days.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">📅</div>
          <div>Aucune donnée pour ce mois.</div>
        </div>
      `;
      return;
    }

    let html = `<div class="data-list">`;

    days.forEach((d, idx) => {
      const dateStr = GoldShopApp.formatDate(d.date);
      const sales = Number(d.sales_total_da || 0);
      const cash = Number(d.cash_da || 0);
      const tpe = Number(d.tpe_da || 0);
      const ocWeight = Number(d.oc_weight_g || 0);
      const ocAmount = Number(d.oc_amount_da || 0);
      const vers = Number(d.versements_da || 0);
      const work = Number(d.workshop_da || 0);
      const profit = Number(d.total_benefice_da || d.benefice_da || 0);
      const salesProfit = Number(d.sales_profit_da || 0);
      const workProfit = Number(d.artisan_profit_da || 0);

      const collapseId = `dayCollapse_${idx}`;

      html += `
        <div class="mobile-card">
          <div class="card-top">
            <div class="card-title-group">
              <span class="card-badge badge-gold">📅 ${dateStr}</span>
              ${d.session_count ? `<span class="card-badge badge-info">${d.session_count} session(s)</span>` : ""}
            </div>
            <div style="text-align: right;">
              <div class="card-row-value success" style="font-size: 14px;">${GoldShopApp.formatMoney(sales)}</div>
              <div style="font-size: 11px; color: var(--gold-500); font-weight: 600;">+ ${GoldShopApp.formatMoney(profit)}</div>
            </div>
          </div>

          <div class="card-rows">
            <div class="card-row">
              <span class="card-row-label">Espèces (Cash):</span>
              <span class="card-row-value">${GoldShopApp.formatMoney(cash)}</span>
            </div>
            <div class="card-row">
              <span class="card-row-label">TPE (Carte):</span>
              <span class="card-row-value info">${GoldShopApp.formatMoney(tpe)}</span>
            </div>
          </div>

          <button class="expand-btn" onclick="toggleAccordion('${collapseId}', this)">
            <span>Afficher détails / عرض التفاصيل</span>
            <span class="chevron">▼</span>
          </button>

          <div id="${collapseId}" class="card-collapse">
            <div class="card-rows">
              <div class="card-row">
                <span class="card-row-label">Or Cassé (O.C):</span>
                <span class="card-row-value danger">${GoldShopApp.formatWeight(ocWeight)} (${GoldShopApp.formatMoney(ocAmount)})</span>
              </div>
              <div class="card-row">
                <span class="card-row-label">Versements (Acomptes):</span>
                <span class="card-row-value">${GoldShopApp.formatMoney(vers)}</span>
              </div>
              <div class="card-row">
                <span class="card-row-label">Atelier / Réparations:</span>
                <span class="card-row-value">${GoldShopApp.formatMoney(work)}</span>
              </div>
              <div class="card-row" style="border-top: 1px solid var(--border-subtle); padding-top: 6px;">
                <span class="card-row-label">Marge Vente:</span>
                <span class="card-row-value gold">${GoldShopApp.formatMoney(salesProfit)}</span>
              </div>
              <div class="card-row">
                <span class="card-row-label">Marge Atelier:</span>
                <span class="card-row-value gold">${GoldShopApp.formatMoney(workProfit)}</span>
              </div>
              <div class="card-row">
                <span class="card-row-label"><b>Bénéfice Net (Faaida):</b></span>
                <span class="card-row-value success"><b>${GoldShopApp.formatMoney(profit)}</b></span>
              </div>
            </div>
          </div>
        </div>
      `;
    });

    html += `</div>`;
    container.innerHTML = html;
  }

  window.toggleAccordion = function(id, btn) {
    const el = document.getElementById(id);
    if (!el) return;
    const isOpen = el.classList.contains("open");
    if (isOpen) {
      el.classList.remove("open");
      if (btn) btn.querySelector(".chevron").textContent = "▼";
    } else {
      el.classList.add("open");
      if (btn) btn.querySelector(".chevron").textContent = "▲";
    }
  };

  document.addEventListener("DOMContentLoaded", () => {
    const now = new Date();
    if (monthSelect && !monthSelect.value) {
      monthSelect.value = now.getMonth() + 1;
    }
    if (yearSelect && !yearSelect.value) {
      yearSelect.value = now.getFullYear();
    }

    if (monthSelect) monthSelect.addEventListener("change", fetchMonthlyData);
    if (yearSelect) yearSelect.addEventListener("change", fetchMonthlyData);

    window.refreshCurrentPageData = fetchMonthlyData;
    fetchMonthlyData();
  });
})();

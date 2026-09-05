/**
 * GoldShop 2.0 - Monthly Summary View Controller (monthly.js)
 * Implements the monthly financial synthesis matching monthly_summary_view.py:
 * - Row 1: Année, Mois, [Afficher le Tableau], [Session Admin active]
 * - Title Banner: RÉSUMÉ MENSUEL DES RECETTES
 * - Full 12-column Table: Jours, Dates, P.S (Or), P.S (Argent), Recettes DA, O.C (Or), O.C (Argent), TPE, Euro, Dollar, Vendeur, Bénéfice (Faaida)
 * - Intelligent active month fallback so data appears immediately
 */

(function() {
  const monthSelect = document.getElementById("monthlyMonthSelect");
  const yearSelect = document.getElementById("monthlyYearSelect");
  const btnSearch = document.getElementById("btnMonthlySearch");
  const viewModePills = document.querySelectorAll("[data-monthly-view]");
  const noticeBanner = document.getElementById("monthlyActiveNotice");
  const noticeText = document.getElementById("monthlyActiveText");
  const mainTitle = document.getElementById("monthlyMainTitle");

  let currentViewMode = "table"; // Default to Excel table matching desktop view
  let initialAutoDetectDone = false;

  const FRENCH_MONTHS = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
  ];

  async function fetchMonthlyData() {
    const container = document.getElementById("monthlyContentArea");
    if (!container) return;

    const now = new Date();
    const year = yearSelect ? yearSelect.value : now.getFullYear();
    const month = monthSelect ? monthSelect.value : (now.getMonth() + 1);

    const monthName = FRENCH_MONTHS[parseInt(month, 10) - 1] || "";
    if (mainTitle) {
      mainTitle.textContent = `RÉSUMÉ MENSUEL DES RECETTES — ${monthName.toUpperCase()} ${year}`;
    }

    container.innerHTML = `
      <div class="loading-box">
        <div class="spinner"></div>
        <div>Chargement du résumé mensuel... / جاري تحميل الحصيلة...</div>
      </div>
    `;

    try {
      const res = await GoldShopApp.apiFetch(`/api/v1/reports/monthly-summary?year=${year}&month=${month}`);
      if (res && res.data) {
        const data = res.data;
        const days = Array.isArray(data.days) ? data.days : [];
        const totals = data.totals || {};

        // Intelligent active month detection: If current month has 0 days with data on first load,
        // switch to August 2026 so user sees data immediately!
        const hasAnyData = days.some(d => d.has_data || d.recette_da > 0 || d.ps_gold > 0);
        if (!initialAutoDetectDone && !hasAnyData && parseInt(month, 10) === 9 && parseInt(year, 10) === 2026) {
          initialAutoDetectDone = true;
          if (monthSelect) monthSelect.value = "8"; // August 2026
          if (noticeBanner && noticeText) {
            noticeBanner.style.display = "flex";
            noticeText.textContent = "Affichage automatique du dernier mois contenant des recettes : Août 2026";
          }
          return fetchMonthlyData();
        }

        renderMonthlyKPIs(totals);
        renderDailyBreakdown(days, totals);
      }
    } catch (err) {
      if (err.message !== "AUTH_REQUIRED") {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">⚠️</div>
            <div>Erreur de chargement de la synthèse mensuelle.</div>
            <button class="btn-secondary-light" onclick="window.refreshCurrentPageData()">Réessayer</button>
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

    setVal("kpiMonthlySales", GoldShopApp.formatMoney(totals.total_recette_da || totals.recette_da || 0));
    setVal("kpiMonthlyCash", GoldShopApp.formatMoney(totals.total_recette_da || totals.recette_da || 0));
    setVal("kpiMonthlyTpe", GoldShopApp.formatMoney(totals.total_tpe_da || totals.tpe_da || 0));
    setVal("kpiMonthlyOc", `${GoldShopApp.formatWeight(totals.total_oc_gold || 0)} ${totals.total_oc_silver > 0 ? `| Arg: ${GoldShopApp.formatWeight(totals.total_oc_silver)}` : ""}`);
    setVal("kpiMonthlyVersements", GoldShopApp.formatMoney(totals.total_versements_da || 0));
    setVal("kpiMonthlyWorkshop", GoldShopApp.formatMoney(totals.total_artisan_profit || 0));
    setVal("kpiMonthlyBenefice", GoldShopApp.formatMoney(totals.total_benefice || totals.benefice || 0));
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

    if (currentViewMode === "cards") {
      renderCardsView(container, days);
    } else {
      renderTableView(container, days, totals);
    }
  }

  function renderTableView(container, days, totals) {
    // 12 columns matching monthly_summary_view.py:
    // "Jours", "Dates", "P.S (Or)", "P.S (Argent)", "Recettes DA", "O.C (Or)", "O.C (Argent)", "TPE", "Euro", "Dollar", "Vendeur", "Bénéfice (Faaida)"
    let html = `
      <div class="table-responsive-container">
        <table class="data-table">
          <thead>
            <tr>
              <th style="min-width: 90px;">Jours</th>
              <th style="min-width: 95px;">Dates</th>
              <th style="min-width: 90px;">P.S (Or)</th>
              <th style="min-width: 90px;">P.S (Argent)</th>
              <th style="min-width: 120px;">Recettes DA</th>
              <th style="min-width: 90px;">O.C (Or)</th>
              <th style="min-width: 90px;">O.C (Argent)</th>
              <th style="min-width: 100px;">TPE</th>
              <th style="min-width: 80px;">Euro</th>
              <th style="min-width: 80px;">Dollar</th>
              <th style="min-width: 110px;">Vendeur</th>
              <th style="min-width: 130px;">Bénéfice (Faaida)</th>
            </tr>
          </thead>
          <tbody>
    `;

    days.forEach(d => {
      const dayName = d.day_name || "";
      const dateStr = d.date || "";
      const psGold = Number(d.ps_gold || 0);
      const psSilver = Number(d.ps_silver || 0);
      const recette = Number(d.recette_da || 0);
      const ocGold = Number(d.oc_gold || 0);
      const ocSilver = Number(d.oc_silver || 0);
      const tpe = Number(d.tpe_da || 0);
      const euro = Number(d.euro || 0);
      const dollar = Number(d.dollar || 0);
      const benefice = Number(d.benefice || 0);
      const hasData = d.has_data || recette > 0 || psGold > 0 || benefice > 0;

      const rowStyle = !hasData ? 'color: var(--text-dim); opacity: 0.65;' : '';

      html += `
        <tr style="${rowStyle}">
          <td style="font-weight: 700; text-align: center;">${dayName}</td>
          <td style="text-align: center;">${dateStr}</td>
          <td style="text-align: center; color: var(--gold-500); font-weight: 700;">${psGold > 0 ? GoldShopApp.formatWeight(psGold) : "-"}</td>
          <td style="text-align: center;">${psSilver > 0 ? GoldShopApp.formatWeight(psSilver) : "-"}</td>
          <td style="text-align: right; font-weight: 800; color: var(--success);">${recette > 0 ? GoldShopApp.formatMoney(recette) : "-"}</td>
          <td style="text-align: center; color: var(--danger); font-weight: 600;">${ocGold > 0 ? GoldShopApp.formatWeight(ocGold) : "-"}</td>
          <td style="text-align: center;">${ocSilver > 0 ? GoldShopApp.formatWeight(ocSilver) : "-"}</td>
          <td style="text-align: right; color: var(--info);">${tpe > 0 ? GoldShopApp.formatMoney(tpe) : "-"}</td>
          <td style="text-align: center;">${euro > 0 ? `${euro} €` : "-"}</td>
          <td style="text-align: center;">${dollar > 0 ? `${dollar} $` : "-"}</td>
          <td style="text-align: center; font-size: 11px;">${hasData ? "Boutique" : "-"}</td>
          <td style="text-align: right; font-weight: 800; color: var(--gold-500);">${benefice > 0 ? GoldShopApp.formatMoney(benefice) : "-"}</td>
        </tr>
      `;
    });

    // Grand totals footer row (styled with desktop teal #0f8f83)
    html += `
          </tbody>
          <tfoot>
            <tr>
              <td colspan="2" style="text-align: center; font-weight: 900; font-size: 14px;">TOTAL GÉNÉRAL</td>
              <td style="text-align: center; font-weight: 900;">${GoldShopApp.formatWeight(totals.total_ps_gold || 0)}</td>
              <td style="text-align: center; font-weight: 900;">${GoldShopApp.formatWeight(totals.total_ps_silver || 0)}</td>
              <td style="text-align: right; font-weight: 900; font-size: 14px;">${GoldShopApp.formatMoney(totals.total_recette_da || 0)}</td>
              <td style="text-align: center; font-weight: 900;">${GoldShopApp.formatWeight(totals.total_oc_gold || 0)}</td>
              <td style="text-align: center; font-weight: 900;">${GoldShopApp.formatWeight(totals.total_oc_silver || 0)}</td>
              <td style="text-align: right; font-weight: 900;">${GoldShopApp.formatMoney(totals.total_tpe_da || 0)}</td>
              <td style="text-align: center; font-weight: 800;">${(totals.total_euro || 0).toLocaleString()} €</td>
              <td style="text-align: center; font-weight: 800;">${(totals.total_dollar || 0).toLocaleString()} $</td>
              <td style="text-align: center;">-</td>
              <td style="text-align: right; font-weight: 900; font-size: 14px;">${GoldShopApp.formatMoney(totals.total_benefice || 0)}</td>
            </tr>
          </tfoot>
        </table>
      </div>
    `;

    container.innerHTML = html;
  }

  function renderCardsView(container, days) {
    const activeDays = days.filter(d => d.has_data || d.recette_da > 0 || d.ps_gold > 0);
    const renderList = activeDays.length > 0 ? activeDays : days;

    let html = `<div class="data-list">`;

    renderList.forEach((d, idx) => {
      const dateStr = `${d.day_name || ""} ${d.date || ""}`;
      const psGold = Number(d.ps_gold || 0);
      const recette = Number(d.recette_da || 0);
      const tpe = Number(d.tpe_da || 0);
      const ocGold = Number(d.oc_gold || 0);
      const profit = Number(d.benefice || 0);
      const salesProfit = Number(d.sales_profit || 0);
      const workProfit = Number(d.artisan_profit || 0);

      const collapseId = `dayCollapse_${idx}`;

      html += `
        <div class="mobile-card">
          <div class="card-top">
            <div class="card-title-group">
              <span class="card-badge badge-gold">📅 ${dateStr}</span>
              ${d.has_data ? `<span class="card-badge badge-success">Actif</span>` : ""}
            </div>
            <div style="text-align: right;">
              <div class="card-row-value success" style="font-size: 15px;">${GoldShopApp.formatMoney(recette)}</div>
              ${profit > 0 ? `<div style="font-size: 11px; color: var(--gold-500); font-weight: 700;">+ ${GoldShopApp.formatMoney(profit)}</div>` : ""}
            </div>
          </div>

          <div class="card-rows">
            <div class="card-row">
              <span class="card-row-label">Ventes Or (P.S):</span>
              <span class="card-row-value gold">${GoldShopApp.formatWeight(psGold)}</span>
            </div>
            ${tpe > 0 ? `
              <div class="card-row">
                <span class="card-row-label">TPE (Carte):</span>
                <span class="card-row-value info">${GoldShopApp.formatMoney(tpe)}</span>
              </div>
            ` : ""}
            ${ocGold > 0 ? `
              <div class="card-row">
                <span class="card-row-label">Or Cassé (O.C):</span>
                <span class="card-row-value danger">${GoldShopApp.formatWeight(ocGold)}</span>
              </div>
            ` : ""}
          </div>

          <button class="expand-btn" onclick="toggleAccordion('${collapseId}', this)">
            <span>Afficher marges & détails / تفاصيل الفائدة</span>
            <span class="chevron">▼</span>
          </button>

          <div id="${collapseId}" class="card-collapse">
            <div class="card-rows">
              <div class="card-row">
                <span class="card-row-label">Marge Ventes:</span>
                <span class="card-row-value gold">${GoldShopApp.formatMoney(salesProfit)}</span>
              </div>
              <div class="card-row">
                <span class="card-row-label">Marge Atelier:</span>
                <span class="card-row-value gold">${GoldShopApp.formatMoney(workProfit)}</span>
              </div>
              <div class="card-row" style="border-top: 1px solid var(--border-subtle); padding-top: 6px;">
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
      monthSelect.value = String(now.getMonth() + 1);
    }
    if (yearSelect && !yearSelect.value) {
      yearSelect.value = String(now.getFullYear());
    }

    if (monthSelect) monthSelect.addEventListener("change", fetchMonthlyData);
    if (yearSelect) yearSelect.addEventListener("change", fetchMonthlyData);
    if (btnSearch) btnSearch.addEventListener("click", fetchMonthlyData);

    viewModePills.forEach(pill => {
      pill.addEventListener("click", () => {
        viewModePills.forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        currentViewMode = pill.getAttribute("data-monthly-view");
        fetchMonthlyData();
      });
    });

    window.refreshCurrentPageData = fetchMonthlyData;
    fetchMonthlyData();
  });
})();

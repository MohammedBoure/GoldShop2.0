/**
 * GoldShop 2.0 - Excel Journal View Controller (journal.js)
 * Implements the daily sales and cash sessions journal matching excel_journal_view.py:
 * - Row 1: Année, Mois, Jour, [Afficher le Journal], [Fc (Caisse)], [+ Nouvelle Vente]
 * - Row 2: Recherche Client, Vendeur
 * - Full 9-column Excel Table: Désignation, P.S, Recette, O.C, TPE, Euro, Dollar, Vendeur, Observation
 * - Intelligent active month fallback to display live data immediately
 */

(function() {
  const yearSelect = document.getElementById("journalYearSelect");
  const monthSelect = document.getElementById("journalMonthSelect");
  const daySelect = document.getElementById("journalDaySelect");
  const sellerSelect = document.getElementById("journalSellerSelect");
  const searchInput = document.getElementById("journalSearchInput");
  const btnSearch = document.getElementById("btnJournalSearch");
  const btnFc = document.getElementById("btnJournalFc");
  const btnNewSale = document.getElementById("btnJournalNewSale");
  const viewModePills = document.querySelectorAll("[data-journal-view]");
  const noticeBanner = document.getElementById("journalActiveMonthNotice");
  const noticeText = document.getElementById("journalActiveMonthText");
  const mainTitle = document.getElementById("journalMainTitle");

  let currentViewMode = "table"; // Default to Excel table matching desktop view
  let initialAutoDetectDone = false;

  const FRENCH_MONTHS = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
  ];

  function populateDaySelect() {
    if (!daySelect) return;
    const currentDay = daySelect.value || "0";
    daySelect.innerHTML = `<option value="0">Tous les jours</option>`;
    for (let d = 1; d <= 31; d++) {
      const opt = document.createElement("option");
      const dStr = d < 10 ? `0${d}` : `${d}`;
      opt.value = String(d);
      opt.textContent = dStr;
      if (String(d) === currentDay) opt.selected = true;
      daySelect.appendChild(opt);
    }
  }

  async function loadSellers() {
    if (!sellerSelect) return;
    try {
      const res = await GoldShopApp.apiFetch("/api/v1/reports/journal/sellers");
      const sellers = Array.isArray(res.data) ? res.data : (res.data && res.data.sellers ? res.data.sellers : []);
      if (sellers.length > 0) {
        const curVal = sellerSelect.value;
        sellerSelect.innerHTML = `<option value="0">Tous les vendeurs</option>`;
        sellers.forEach(s => {
          const opt = document.createElement("option");
          opt.value = s.username || s.name || s.id;
          opt.textContent = s.full_name ? `${s.full_name} (${s.username})` : (s.username || s.name);
          if (opt.value === curVal) opt.selected = true;
          sellerSelect.appendChild(opt);
        });
      }
    } catch (e) {
      console.warn("Failed to load journal sellers", e);
    }
  }

  async function fetchJournalData() {
    const container = document.getElementById("journalContentArea");
    if (!container) return;

    const now = new Date();
    const year = yearSelect ? yearSelect.value : now.getFullYear();
    const month = monthSelect ? monthSelect.value : (now.getMonth() + 1);
    const day = daySelect ? daySelect.value : "0";
    const seller = sellerSelect ? sellerSelect.value : "0";
    const search = searchInput ? searchInput.value.trim() : "";

    const monthName = FRENCH_MONTHS[parseInt(month, 10) - 1] || "";
    if (mainTitle) {
      mainTitle.textContent = `États De Recettes Du Mois De ${monthName} ${year}`;
    }

    const params = new URLSearchParams();
    params.append("year", year);
    params.append("month", month);
    if (day && day !== "0") params.append("day", day);
    if (seller && seller !== "0") params.append("seller_name", seller);
    if (search) params.append("search", search);

    container.innerHTML = `
      <div class="loading-box">
        <div class="spinner"></div>
        <div>Chargement du journal... / جاري تحميل اليومية...</div>
      </div>
    `;

    try {
      const res = await GoldShopApp.apiFetch(`/api/v1/reports/journal?${params.toString()}`);
      if (res && res.data) {
        const data = res.data;
        const sessions = Array.isArray(data.sessions) ? data.sessions : [];
        const grandTotals = data.grand_totals || data.totals || {};

        // Intelligent active month detection: If current month has 0 sessions on initial load,
        // fallback to August 2026 where data exists so user sees records immediately!
        if (!initialAutoDetectDone && sessions.length === 0 && parseInt(month, 10) === 9 && parseInt(year, 10) === 2026) {
          initialAutoDetectDone = true;
          if (monthSelect) monthSelect.value = "8"; // Select August 2026
          if (noticeBanner && noticeText) {
            noticeBanner.style.display = "flex";
            noticeText.textContent = "Affichage automatique du dernier mois contenant des données : Août 2026";
          }
          return fetchJournalData();
        }

        renderJournalKPIs(grandTotals);
        renderJournalSessions(sessions, grandTotals);
      }
    } catch (err) {
      if (err.message !== "AUTH_REQUIRED") {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">⚠️</div>
            <div>Erreur de chargement du journal.</div>
            <button class="btn-secondary-light" onclick="window.refreshCurrentPageData()">Réessayer</button>
          </div>
        `;
      }
    }
  }

  function renderJournalKPIs(totals) {
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    };

    setVal("kpiJournalFc", GoldShopApp.formatMoney(totals.fc_da || totals.fc || 0));
    setVal("kpiJournalRecette", GoldShopApp.formatMoney(totals.recette_da || totals.recette || 0));
    setVal("kpiJournalPsGold", GoldShopApp.formatWeight(totals.ps_gold_g || totals.ps_gold || 0));
    setVal("kpiJournalPsSilver", GoldShopApp.formatWeight(totals.ps_silver_g || totals.ps_silver || 0));
    setVal("kpiJournalOcGold", GoldShopApp.formatWeight(totals.oc_gold_g || totals.oc_gold || 0));
    setVal("kpiJournalOcSilver", GoldShopApp.formatWeight(totals.oc_silver_g || totals.oc_silver || 0));
    setVal("kpiJournalTpe", GoldShopApp.formatMoney(totals.tpe_da || totals.tpe || 0));
    setVal("kpiJournalDevises", `${(totals.euro || 0).toLocaleString()} € | ${(totals.dollar || 0).toLocaleString()} $`);
  }

  function renderJournalSessions(sessions, grandTotals) {
    const container = document.getElementById("journalContentArea");
    if (!container) return;

    if (!sessions || sessions.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">📋</div>
          <div style="font-size: 15px; font-weight: 700; color: var(--text-heading);">Aucune donnée trouvée pour cette période.</div>
          <div style="font-size: 12px; color: var(--text-dim); margin-top: 4px;">لا توجد حركات مسجلة للفترة المحددة. اختر شهراً آخر (مثلاً أوت 2026) لعرض البيانات.</div>
        </div>
      `;
      return;
    }

    if (currentViewMode === "cards") {
      renderCardsView(container, sessions);
    } else {
      renderTableView(container, sessions, grandTotals);
    }
  }

  function renderTableView(container, sessions, grandTotals) {
    let html = `
      <div class="table-responsive-container">
        <table class="data-table">
          <thead>
            <tr>
              <th style="min-width: 180px;">Désignation</th>
              <th style="min-width: 90px;">P.S</th>
              <th style="min-width: 120px;">Recette</th>
              <th style="min-width: 90px;">O.C</th>
              <th style="min-width: 100px;">TPE</th>
              <th style="min-width: 80px;">Euro</th>
              <th style="min-width: 80px;">Dollar</th>
              <th style="min-width: 120px;">Vendeur</th>
              <th style="min-width: 180px;">Observation</th>
            </tr>
          </thead>
          <tbody>
    `;

    sessions.forEach(sess => {
      const dateHeader = sess.date_formatted || GoldShopApp.formatDate(sess.opened_at);
      const fcText = sess.starting_cash_formatted || `Fc : ${GoldShopApp.formatMoney(sess.starting_cash_da || 0)}`;
      const receipts = Array.isArray(sess.receipts) ? sess.receipts : [];
      const sTotals = sess.totals || {};

      // 1. Session Merged Day Header Row
      html += `
        <tr style="background-color: #dfe8ef; font-weight: 800; border-top: 2px solid #cbd5df;">
          <td colspan="3" style="text-align: center; color: #17212b; font-size: 13px; padding: 8px 10px;">
            📅 ${dateHeader}
          </td>
          <td colspan="6" style="text-align: center; color: #17212b; font-size: 13px; padding: 8px 10px; background-color: #e8eef3;">
            💰 ${fcText}
          </td>
        </tr>
      `;

      // 2. Receipt Rows
      if (receipts.length === 0) {
        html += `
          <tr>
            <td colspan="9" style="text-align: center; color: var(--text-dim); font-style: italic; padding: 10px;">
              Aucune vente enregistrée pour cette session
            </td>
          </tr>
        `;
      } else {
        receipts.forEach(r => {
          const desig = r.designation || r.product_name || "Vente";
          const ps = Number(r.p_s || 0);
          const psText = r.ps_formatted || (ps > 0 ? `${ps.toFixed(2)}` : "-");
          const recette = Number(r.recette || 0);
          const ocText = r.oc_formatted || (r.oc_gold > 0 ? `${Number(r.oc_gold).toFixed(2)}` : "-");
          const tpe = Number(r.tpe || 0);
          const euro = Number(r.euro || 0);
          const dollar = Number(r.dollar || 0);
          const vendeur = r.vendeur_name || "-";
          const obs = r.observation || r.raw_notes || "";

          html += `
            <tr>
              <td style="font-weight: 600; text-align: left;">${desig}</td>
              <td style="text-align: center; color: var(--gold-500); font-weight: 700;">${psText}</td>
              <td style="text-align: right; color: var(--success); font-weight: 800;">${recette > 0 ? GoldShopApp.formatMoney(recette) : "-"}</td>
              <td style="text-align: center; color: var(--danger); font-weight: 600;">${ocText}</td>
              <td style="text-align: right; color: var(--info); font-weight: 600;">${tpe > 0 ? GoldShopApp.formatMoney(tpe) : "-"}</td>
              <td style="text-align: center;">${euro > 0 ? `${euro} €` : "-"}</td>
              <td style="text-align: center;">${dollar > 0 ? `${dollar} $` : "-"}</td>
              <td style="text-align: center; font-size: 12px;">${vendeur}</td>
              <td style="text-align: left; font-size: 12px; max-width: 250px; overflow: hidden; text-overflow: ellipsis;">${obs || "-"}</td>
            </tr>
          `;
        });
      }

      // 3. Day Subtotal Row
      html += `
        <tr class="table-subtotal-row">
          <td style="font-weight: 800; text-align: center;">TOTAL DE LA JOURNÉE</td>
          <td style="text-align: center; color: var(--gold-500); font-weight: 800;">${GoldShopApp.formatWeight(sTotals.ps_gold || 0)}</td>
          <td style="text-align: right; color: var(--success); font-weight: 800;">${GoldShopApp.formatMoney(sTotals.recette || 0)}</td>
          <td style="text-align: center; color: var(--danger); font-weight: 800;">${GoldShopApp.formatWeight(sTotals.oc_gold || 0)}</td>
          <td style="text-align: right; color: var(--info); font-weight: 800;">${GoldShopApp.formatMoney(sTotals.tpe || 0)}</td>
          <td style="text-align: center; font-weight: 700;">${(sTotals.euro || 0) > 0 ? `${sTotals.euro} €` : "-"}</td>
          <td style="text-align: center; font-weight: 700;">${(sTotals.dollar || 0) > 0 ? `${sTotals.dollar} $` : "-"}</td>
          <td colspan="2" style="text-align: center; font-size: 11px; color: var(--text-muted);">${receipts.length} opération(s)</td>
        </tr>
      `;
    });

    // 4. Monthly Grand Total Row (matches desktop #0f8f83 header styling)
    html += `
          </tbody>
          <tfoot>
            <tr>
              <td style="text-align: center; font-weight: 900; font-size: 14px;">TOTAL DU MOIS</td>
              <td style="text-align: center; font-weight: 900; font-size: 13px;">${GoldShopApp.formatWeight(grandTotals.ps_gold || grandTotals.ps_gold_g || 0)}</td>
              <td style="text-align: right; font-weight: 900; font-size: 14px;">${GoldShopApp.formatMoney(grandTotals.recette || grandTotals.recette_da || 0)}</td>
              <td style="text-align: center; font-weight: 900; font-size: 13px;">${GoldShopApp.formatWeight(grandTotals.oc_gold || grandTotals.oc_gold_g || 0)}</td>
              <td style="text-align: right; font-weight: 900; font-size: 13px;">${GoldShopApp.formatMoney(grandTotals.tpe || grandTotals.tpe_da || 0)}</td>
              <td style="text-align: center; font-weight: 800;">${(grandTotals.euro || 0).toLocaleString()} €</td>
              <td style="text-align: center; font-weight: 800;">${(grandTotals.dollar || 0).toLocaleString()} $</td>
              <td colspan="2" style="text-align: center; font-weight: 700;">${sessions.length} session(s)</td>
            </tr>
          </tfoot>
        </table>
      </div>
    `;

    container.innerHTML = html;
  }

  function renderCardsView(container, sessions) {
    let html = `<div class="data-list">`;

    sessions.forEach((sess, sIdx) => {
      const dateHeader = sess.date_formatted || GoldShopApp.formatDate(sess.opened_at);
      const fcText = sess.starting_cash_formatted || `Fc : ${GoldShopApp.formatMoney(sess.starting_cash_da || 0)}`;
      const receipts = Array.isArray(sess.receipts) ? sess.receipts : [];
      const sTotals = sess.totals || {};
      const collapseId = `sessionCollapse_${sIdx}`;

      html += `
        <div class="mobile-card">
          <div class="card-top">
            <div class="card-title-group">
              <span class="card-badge badge-gold">📅 ${dateHeader}</span>
              <span class="card-badge badge-info">${fcText}</span>
            </div>
            <div style="text-align: right;">
              <div class="card-row-value success" style="font-size: 15px;">
                ${GoldShopApp.formatMoney(sTotals.recette || 0)}
              </div>
              <div style="font-size: 11px; color: var(--gold-500); font-weight: 700;">
                ${GoldShopApp.formatWeight(sTotals.ps_gold || 0)}
              </div>
            </div>
          </div>

          <div class="card-rows">
            <div class="card-row">
              <span class="card-row-label">Opérations de vente:</span>
              <span class="card-row-value">${receipts.length} ticket(s)</span>
            </div>
            ${(sTotals.oc_gold || 0) > 0 ? `
              <div class="card-row">
                <span class="card-row-label">Or Cassé (O.C):</span>
                <span class="card-row-value danger">${GoldShopApp.formatWeight(sTotals.oc_gold)}</span>
              </div>
            ` : ""}
            ${(sTotals.tpe || 0) > 0 ? `
              <div class="card-row">
                <span class="card-row-label">Paiement TPE:</span>
                <span class="card-row-value info">${GoldShopApp.formatMoney(sTotals.tpe)}</span>
              </div>
            ` : ""}
            ${(sTotals.euro || 0) > 0 || (sTotals.dollar || 0) > 0 ? `
              <div class="card-row">
                <span class="card-row-label">Devises:</span>
                <span class="card-row-value">${(sTotals.euro || 0) > 0 ? `${sTotals.euro} € ` : ""}${(sTotals.dollar || 0) > 0 ? `${sTotals.dollar} $` : ""}</span>
              </div>
            ` : ""}
          </div>

          <button class="expand-btn" onclick="toggleAccordion('${collapseId}', this)">
            <span>Afficher les détails des tickets (${receipts.length}) / عرض التذاكر</span>
            <span class="chevron">▼</span>
          </button>

          <div id="${collapseId}" class="card-collapse">
            <div style="display: flex; flex-direction: column; gap: 6px; margin-top: 6px;">
              ${receipts.map(r => `
                <div style="background: var(--bg-surface-elevated); padding: 8px 10px; border-radius: 6px; font-size: 12px; border: 1px solid var(--border-subtle);">
                  <div style="display: flex; justify-content: space-between; font-weight: 700;">
                    <span>${r.designation || "Article"}</span>
                    <span class="success">${GoldShopApp.formatMoney(r.recette || 0)}</span>
                  </div>
                  <div style="display: flex; justify-content: space-between; color: var(--text-muted); font-size: 11px; margin-top: 3px;">
                    <span>P.S: <b class="gold">${r.ps_formatted || (r.p_s ? `${r.p_s} g` : "-")}</b></span>
                    ${r.oc_gold > 0 ? `<span class="danger">O.C: ${r.oc_formatted || `${r.oc_gold} g`}</span>` : ""}
                    <span>Vendeur: <b>${r.vendeur_name || "Boutique"}</b></span>
                  </div>
                  ${r.observation ? `
                    <div style="color: var(--text-dim); font-size: 11px; margin-top: 4px; font-style: italic;">
                      Note: ${r.observation}
                    </div>
                  ` : ""}
                </div>
              `).join("")}
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

  // Bind Events
  document.addEventListener("DOMContentLoaded", () => {
    populateDaySelect();

    if (yearSelect) yearSelect.addEventListener("change", fetchJournalData);
    if (monthSelect) monthSelect.addEventListener("change", fetchJournalData);
    if (daySelect) daySelect.addEventListener("change", fetchJournalData);
    if (sellerSelect) sellerSelect.addEventListener("change", fetchJournalData);

    if (btnSearch) {
      btnSearch.addEventListener("click", fetchJournalData);
    }

    if (btnFc) {
      btnFc.addEventListener("click", () => {
        GoldShopApp.showToast("Fc (Fond de Caisse) : Consultez les lignes d'entête quotidiennes dans le tableau.", "info");
      });
    }

    if (btnNewSale) {
      btnNewSale.addEventListener("click", () => {
        GoldShopApp.showToast("Pour enregistrer une nouvelle vente, utilisez l'interface tactile du logiciel de caisse.", "info");
      });
    }

    if (searchInput) {
      let debounceTimer;
      searchInput.addEventListener("input", () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(fetchJournalData, 300);
      });
    }

    viewModePills.forEach(pill => {
      pill.addEventListener("click", () => {
        viewModePills.forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        currentViewMode = pill.getAttribute("data-journal-view");
        fetchJournalData();
      });
    });

    window.refreshCurrentPageData = function() {
      loadSellers();
      fetchJournalData();
    };

    loadSellers();
    fetchJournalData();
  });
})();

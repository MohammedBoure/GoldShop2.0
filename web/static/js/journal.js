/**
 * GoldShop 2.0 - Excel Journal View Controller (journal.js)
 * Implements the daily sales and cash sessions journal matching excel_journal_view.py
 */

(function() {
  const dateInput = document.getElementById("journalDateInput");
  const sellerSelect = document.getElementById("journalSellerSelect");
  const searchInput = document.getElementById("journalSearchInput");
  const viewModePills = document.querySelectorAll("[data-journal-view]");

  let currentViewMode = "cards"; // 'cards' or 'table'

  async function loadSellers() {
    if (!sellerSelect) return;
    try {
      const res = await GoldShopApp.apiFetch("/api/v1/reports/journal/sellers");
      if (res && res.data && Array.isArray(res.data.sellers)) {
        const current = sellerSelect.value;
        sellerSelect.innerHTML = `<option value="">-- Tous les vendeurs / الكل --</option>`;
        res.data.sellers.forEach(s => {
          const opt = document.createElement("option");
          opt.value = s.name;
          opt.textContent = `${s.name} (${s.count})`;
          if (s.name === current) opt.selected = true;
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

    const dateVal = dateInput ? dateInput.value : "";
    let year = "", month = "", day = "";
    if (dateVal) {
      const parts = dateVal.split("-");
      year = parts[0];
      month = parts[1];
      day = parts[2];
    }

    const seller = sellerSelect ? sellerSelect.value : "";
    const search = searchInput ? searchInput.value.trim() : "";

    const params = new URLSearchParams();
    if (year) params.append("year", year);
    if (month) params.append("month", month);
    if (day) params.append("day", day);
    if (seller) params.append("seller_name", seller);
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
        renderJournalKPIs(res.data.totals || {});
        renderJournalSessions(res.data.sessions || [], res.data.totals || {});
      }
    } catch (err) {
      if (err.message !== "AUTH_REQUIRED") {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">⚠️</div>
            <div>Erreur de chargement du journal.</div>
            <button class="btn-secondary" onclick="window.refreshCurrentPageData()">Réessayer</button>
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

    setVal("kpiJournalFc", GoldShopApp.formatMoney(totals.fc_da || 0));
    setVal("kpiJournalRecette", GoldShopApp.formatMoney(totals.recette_da || 0));
    setVal("kpiJournalPsGold", GoldShopApp.formatWeight(totals.ps_gold_g || 0));
    setVal("kpiJournalPsSilver", GoldShopApp.formatWeight(totals.ps_silver_g || 0));
    setVal("kpiJournalOcGold", GoldShopApp.formatWeight(totals.oc_gold_g || 0));
    setVal("kpiJournalOcSilver", GoldShopApp.formatWeight(totals.oc_silver_g || 0));
    setVal("kpiJournalTpe", GoldShopApp.formatMoney(totals.tpe_da || 0));
    setVal("kpiJournalDevises", `${(totals.euro || 0).toLocaleString()} € | ${(totals.dollar || 0).toLocaleString()} $`);
  }

  function renderJournalSessions(sessions, totals) {
    const container = document.getElementById("journalContentArea");
    if (!container) return;

    if (!sessions || sessions.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">📋</div>
          <div>Aucune opération enregistrée pour cette sélection.</div>
          <div style="font-size: 11px; color: var(--text-dim);">لا توجد حركات مسجلة لهذا اليوم.</div>
        </div>
      `;
      return;
    }

    if (currentViewMode === "cards") {
      renderCardsView(container, sessions);
    } else {
      renderTableView(container, sessions, totals);
    }
  }

  function renderCardsView(container, sessions) {
    let html = `<div class="data-list">`;

    sessions.forEach(sess => {
      const timeStr = sess.time || (sess.created_at ? sess.created_at.substring(11, 16) : "--:--");
      const sellerStr = sess.seller || sess.seller_name || "Boutique";
      const fc = Number(sess.fc_da || sess.fc || 0);
      const recette = Number(sess.recette_da || sess.recette || 0);
      const psGold = Number(sess.ps_gold_g || 0);
      const psSilver = Number(sess.ps_silver_g || 0);
      const ocGold = Number(sess.oc_gold_g || 0);
      const ocSilver = Number(sess.oc_silver_g || 0);
      const tpe = Number(sess.tpe_da || 0);
      const euro = Number(sess.euro || 0);
      const dollar = Number(sess.dollar || 0);
      const note = sess.notes || sess.note || "";

      html += `
        <div class="mobile-card">
          <div class="card-top">
            <div class="card-title-group">
              <span class="card-badge badge-gold">⏱️ ${timeStr}</span>
              <span class="card-badge badge-info">👤 ${sellerStr}</span>
            </div>
            <div class="card-row-value success" style="font-size: 15px;">
              ${GoldShopApp.formatMoney(recette)}
            </div>
          </div>

          <div class="card-rows">
            ${fc > 0 ? `
              <div class="card-row">
                <span class="card-row-label">Fond de Caisse (Fc):</span>
                <span class="card-row-value">${GoldShopApp.formatMoney(fc)}</span>
              </div>
            ` : ""}
            <div class="card-row">
              <span class="card-row-label">Ventes Or / P_S Or:</span>
              <span class="card-row-value gold">${GoldShopApp.formatWeight(psGold)}</span>
            </div>
            ${psSilver > 0 ? `
              <div class="card-row">
                <span class="card-row-label">Ventes Argent:</span>
                <span class="card-row-value">${GoldShopApp.formatWeight(psSilver)}</span>
              </div>
            ` : ""}
            ${ocGold > 0 || ocSilver > 0 ? `
              <div class="card-row">
                <span class="card-row-label">Or Cassé (O.C):</span>
                <span class="card-row-value danger">${GoldShopApp.formatWeight(ocGold)} ${ocSilver > 0 ? `| Arg: ${GoldShopApp.formatWeight(ocSilver)}` : ""}</span>
              </div>
            ` : ""}
            ${tpe > 0 ? `
              <div class="card-row">
                <span class="card-row-label">Paiement TPE:</span>
                <span class="card-row-value info">${GoldShopApp.formatMoney(tpe)}</span>
              </div>
            ` : ""}
            ${euro > 0 || dollar > 0 ? `
              <div class="card-row">
                <span class="card-row-label">Devises:</span>
                <span class="card-row-value">${euro > 0 ? `${euro} € ` : ""}${dollar > 0 ? `${dollar} $` : ""}</span>
              </div>
            ` : ""}
            ${note ? `
              <div class="card-row" style="background: var(--bg-surface-elevated); padding: 6px 8px; border-radius: 6px; margin-top: 4px;">
                <span class="card-row-label">📝 Note:</span>
                <span class="card-row-value" style="font-size: 12px; font-weight: normal;">${note}</span>
              </div>
            ` : ""}
          </div>
        </div>
      `;
    });

    html += `</div>`;
    container.innerHTML = html;
  }

  function renderTableView(container, sessions, totals) {
    let html = `
      <div class="table-responsive-container">
        <table class="data-table">
          <thead>
            <tr>
              <th>N°</th>
              <th>Heure</th>
              <th>Vendeur</th>
              <th>Fc (DA)</th>
              <th>P_S Or (g)</th>
              <th>P_S Arg (g)</th>
              <th>Recette (DA)</th>
              <th>O.C Or (g)</th>
              <th>O.C Arg (g)</th>
              <th>TPE (DA)</th>
              <th>Euro (€)</th>
              <th>Dollar ($)</th>
              <th>Notes</th>
            </tr>
          </thead>
          <tbody>
    `;

    sessions.forEach((sess, idx) => {
      html += `
        <tr>
          <td>${idx + 1}</td>
          <td><b>${sess.time || "--:--"}</b></td>
          <td>${sess.seller || "Boutique"}</td>
          <td>${sess.fc_da ? GoldShopApp.formatMoney(sess.fc_da) : "-"}</td>
          <td style="color: var(--gold-500); font-weight: 600;">${GoldShopApp.formatWeight(sess.ps_gold_g || 0)}</td>
          <td>${GoldShopApp.formatWeight(sess.ps_silver_g || 0)}</td>
          <td style="color: var(--success); font-weight: 700;">${GoldShopApp.formatMoney(sess.recette_da || 0)}</td>
          <td style="color: var(--danger);">${GoldShopApp.formatWeight(sess.oc_gold_g || 0)}</td>
          <td>${GoldShopApp.formatWeight(sess.oc_silver_g || 0)}</td>
          <td>${sess.tpe_da ? GoldShopApp.formatMoney(sess.tpe_da) : "-"}</td>
          <td>${sess.euro ? `${sess.euro} €` : "-"}</td>
          <td>${sess.dollar ? `${sess.dollar} $` : "-"}</td>
          <td style="max-width: 150px; overflow: hidden; text-overflow: ellipsis;">${sess.notes || "-"}</td>
        </tr>
      `;
    });

    html += `
          </tbody>
          <tfoot>
            <tr>
              <td colspan="3">TOTAL GÉNÉRAL</td>
              <td>${GoldShopApp.formatMoney(totals.fc_da || 0)}</td>
              <td style="color: var(--gold-500);">${GoldShopApp.formatWeight(totals.ps_gold_g || 0)}</td>
              <td>${GoldShopApp.formatWeight(totals.ps_silver_g || 0)}</td>
              <td style="color: var(--success); font-size: 14px;">${GoldShopApp.formatMoney(totals.recette_da || 0)}</td>
              <td style="color: var(--danger);">${GoldShopApp.formatWeight(totals.oc_gold_g || 0)}</td>
              <td>${GoldShopApp.formatWeight(totals.oc_silver_g || 0)}</td>
              <td>${GoldShopApp.formatMoney(totals.tpe_da || 0)}</td>
              <td>${(totals.euro || 0).toLocaleString()} €</td>
              <td>${(totals.dollar || 0).toLocaleString()} $</td>
              <td>-</td>
            </tr>
          </tfoot>
        </table>
      </div>
    `;

    container.innerHTML = html;
  }

  // Bind UI Events
  document.addEventListener("DOMContentLoaded", () => {
    if (dateInput) {
      if (!dateInput.value) {
        dateInput.value = new Date().toISOString().split("T")[0];
      }
      dateInput.addEventListener("change", fetchJournalData);
    }

    if (sellerSelect) {
      sellerSelect.addEventListener("change", fetchJournalData);
    }

    if (searchInput) {
      let debounceTimer;
      searchInput.addEventListener("input", () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(fetchJournalData, 350);
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

    // Hook to global refresh
    window.refreshCurrentPageData = function() {
      loadSellers();
      fetchJournalData();
    };

    loadSellers();
    fetchJournalData();
  });
})();

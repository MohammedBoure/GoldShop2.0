/**
 * GoldShop 2.0 - Versements / Layaways View Controller (versements.js)
 * Implements dossiers, reserved item weights, payments, and 9-column table matching versements_view.py:
 * - Search input + Status dropdown combo + [➕ Nouveau Versement]
 * - Context toolbar: [ℹ️ Détails Articles], [📄 Bon PDF], [💵 Paiement Global], [✅ Clôturer]
 * - 9-column table: Date/Opération, Cash (DA), TPE (DA), Montant (€/$), Taux, Or Cassé (g), Poids Déduit, Statut, Observation
 */

(function() {
  const searchInput = document.getElementById("versementsSearchInput");
  const statusSelect = document.getElementById("versementsStatusSelect");
  const btnNewVersement = document.getElementById("btnNewVersement");
  const btnDetails = document.getElementById("btnVersementDetails");
  const btnPdf = document.getElementById("btnVersementPdf");
  const btnGlobalPay = document.getElementById("btnVersementGlobalPay");
  const btnClose = document.getElementById("btnVersementClose");
  const viewModePills = document.querySelectorAll("[data-versement-view]");

  let currentViewMode = "table"; // Default to table matching desktop
  let currentStatus = "ALL";
  let cachedVersements = [];
  let selectedVersementId = null;

  async function fetchVersementsStats() {
    try {
      const res = await GoldShopApp.apiFetch("/api/v1/versements/stats");
      if (res && res.data) {
        const stats = res.data;
        const setVal = (id, val) => {
          const el = document.getElementById(id);
          if (el) el.textContent = val;
        };
        setVal("kpiVersementActiveCount", stats.total_active_dossiers || 0);
        setVal("kpiVersementReservedWeight", GoldShopApp.formatWeight(stats.total_reserved_weight_g || 0));
        setVal("kpiVersementTotalDue", GoldShopApp.formatMoney(stats.total_remaining_due_da || 0));
      }
    } catch (e) {
      console.warn("Stats fetch failed", e);
    }
  }

  async function fetchVersementsList() {
    const container = document.getElementById("versementsContentArea");
    if (!container) return;

    const query = searchInput ? searchInput.value.trim() : "";
    const status = statusSelect ? statusSelect.value : "ALL";
    const params = new URLSearchParams();
    if (status && status !== "ALL") {
      params.append("status", status);
    }
    if (query) {
      params.append("search", query);
    }

    container.innerHTML = `
      <div class="loading-box">
        <div class="spinner"></div>
        <div>Chargement des versements... / جاري تحميل ملفات العربون...</div>
      </div>
    `;

    try {
      const res = await GoldShopApp.apiFetch(`/api/v1/versements?${params.toString()}`);
      if (res && res.data) {
        // Robust handling: res.data can be an Array directly, or an object containing items
        cachedVersements = Array.isArray(res.data) ? res.data : (res.data.items || []);
        renderVersements(cachedVersements);
      }
    } catch (err) {
      if (err.message !== "AUTH_REQUIRED") {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">⚠️</div>
            <div>Erreur de chargement des dossiers de versement.</div>
            <button class="btn-secondary-light" onclick="window.refreshCurrentPageData()">Réessayer</button>
          </div>
        `;
      }
    }
  }

  function renderVersements(items) {
    const container = document.getElementById("versementsContentArea");
    if (!container) return;

    if (!items || items.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">📦</div>
          <div style="font-size: 15px; font-weight: 700;">Aucun dossier de versement trouvé.</div>
          <div style="font-size: 12px; color: var(--text-dim); margin-top: 4px;">لا توجد ملفات حجز مطابقة للبحث أو الفلتر المحدد.</div>
        </div>
      `;
      return;
    }

    if (currentViewMode === "cards") {
      renderCardsView(container, items);
    } else {
      renderTableView(container, items);
    }
  }

  function renderTableView(container, items) {
    // 9 Columns matching desktop versements_view.py:
    // "Date / Opération", "Cash (DA)", "TPE (DA)", "Montant (€/$)", "Taux (DA/€/$)", "Or Cassé (g)", "Poids Déduit", "Statut", "Observation"
    let html = `
      <div class="table-responsive-container">
        <table class="data-table">
          <thead>
            <tr>
              <th style="min-width: 220px; text-align: left;">Date / Opération</th>
              <th style="min-width: 120px;">Cash (DA)</th>
              <th style="min-width: 100px;">TPE (DA)</th>
              <th style="min-width: 110px;">Montant (€/$)</th>
              <th style="min-width: 100px;">Taux</th>
              <th style="min-width: 100px;">Or Cassé (g)</th>
              <th style="min-width: 110px;">Poids Déduit</th>
              <th style="min-width: 100px;">Statut</th>
              <th style="min-width: 180px;">Observation</th>
            </tr>
          </thead>
          <tbody>
    `;

    items.forEach(item => {
      const vId = item.id || item.versement_id;
      const clientName = item.client_name || item.client || "Client Inconnu";
      const phone = item.client_phone || item.phone || "";
      const dateCreated = GoldShopApp.formatDate(item.created_at || item.date);
      const totalDue = Number(item.total_amount_da || item.total_price_da || item.total_price || 0);
      const totalPaid = Number(item.total_paid_money_da || item.paid_amount_da || item.paid_amount || 0);
      const resteMoney = Math.max(0, totalDue - totalPaid);
      const status = item.status || "EN_COURS";
      const payments = Array.isArray(item.payments) ? item.payments : [];
      const reservedItems = Array.isArray(item.items) ? item.items : (item.reserved_items || []);

      let badgeClass = "badge-success";
      let statusLabel = "🟢 En cours";
      if (status === "CLOTURE" || status === "LIVRE") {
        badgeClass = "badge-info";
        statusLabel = "🔵 Clôturé";
      } else if (status === "ANNULE") {
        badgeClass = "badge-danger";
        statusLabel = "🔴 Annulé";
      }

      // Main Dossier Header Row (spanning across columns)
      html += `
        <tr style="background-color: #dfe8ef; font-weight: 800; border-top: 2px solid #cbd5df; cursor: pointer;" onclick="selectVersementRow(${vId}, this)">
          <td colspan="4" style="padding: 8px 10px; font-size: 13px; color: #17212b;">
            📦 <b>VRS-${String(vId).padStart(5, '0')}</b> — <b>${clientName}</b> ${phone ? `(📞 ${phone})` : ""} — ${dateCreated}
          </td>
          <td colspan="3" style="text-align: right; padding: 8px 10px; font-size: 12px; color: #17212b;">
            Total: <b>${GoldShopApp.formatMoney(totalDue)}</b> | Reste: <b style="color: var(--danger);">${GoldShopApp.formatMoney(resteMoney)}</b>
          </td>
          <td style="text-align: center;">
            <span class="card-badge ${badgeClass}">${statusLabel}</span>
          </td>
          <td style="font-size: 11px; color: var(--text-dim);">${reservedItems.length} article(s)</td>
        </tr>
      `;

      // Reserved Items Rows
      reservedItems.forEach(ritem => {
        const desig = ritem.designation || ritem.product_name || "Article réservé";
        const w = Number(ritem.display_weight || ritem.weight || 0);
        const ded = Number(ritem.deducted_g || 0);
        const rem = Number(ritem.remaining_g || Math.max(0, w - ded));

        html += `
          <tr style="background-color: #fafbfc; font-size: 12px;">
            <td style="padding-left: 24px; color: #2c3e50;">
              💍 ${desig} (${GoldShopApp.formatWeight(w)})
            </td>
            <td style="text-align: right; color: var(--text-muted);">-</td>
            <td style="text-align: right; color: var(--text-muted);">-</td>
            <td style="text-align: center; color: var(--text-muted);">-</td>
            <td style="text-align: center; color: var(--text-muted);">-</td>
            <td style="text-align: center; color: var(--text-muted);">-</td>
            <td style="text-align: center; color: var(--gold-500); font-weight: 700;">
              ${ded > 0 ? `-${GoldShopApp.formatWeight(ded)}` : "-"} (Reste: ${GoldShopApp.formatWeight(rem)})
            </td>
            <td style="text-align: center; font-size: 11px;">${ritem.item_status || "RESERVE"}</td>
            <td style="font-size: 11px; color: var(--text-dim);">${ritem.observation || ritem.custom_note || "-"}</td>
          </tr>
        `;
      });

      // Payments Sub-Rows
      payments.forEach(p => {
        const pDate = GoldShopApp.formatDate(p.payment_date || p.date);
        const pCash = Number(p.montant_da || p.amount_da || 0);
        const pTpe = Number(p.tpe_da || 0);
        const pEuro = Number(p.montant_euro || 0);
        const pDollar = Number(p.montant_dollar || 0);
        const pTaux = Number(p.taux_change_euro || p.taux_change_dollar || 0);
        const pOc = Number(p.or_casse_g || 0);
        const pDed = Number(p.poids_deduit_g || 0);

        html += `
          <tr style="background-color: #ffffff; font-size: 12px;">
            <td style="padding-left: 24px; color: var(--text-muted);">
              💵 Versement le ${pDate}
            </td>
            <td style="text-align: right; color: var(--success); font-weight: 700;">
              ${pCash > 0 ? GoldShopApp.formatMoney(pCash) : "-"}
            </td>
            <td style="text-align: right; color: var(--info); font-weight: 600;">
              ${pTpe > 0 ? GoldShopApp.formatMoney(pTpe) : "-"}
            </td>
            <td style="text-align: center;">
              ${pEuro > 0 ? `${pEuro} € ` : ""}${pDollar > 0 ? `${pDollar} $` : (pEuro === 0 ? "-" : "")}
            </td>
            <td style="text-align: center;">${pTaux > 0 ? pTaux : "-"}</td>
            <td style="text-align: center; color: var(--danger); font-weight: 600;">
              ${pOc > 0 ? GoldShopApp.formatWeight(pOc) : "-"}
            </td>
            <td style="text-align: center; color: var(--gold-500); font-weight: 700;">
              ${pDed > 0 ? `${GoldShopApp.formatWeight(pDed)}` : "-"}
            </td>
            <td style="text-align: center; font-size: 11px; color: var(--success);">Payé</td>
            <td style="font-size: 11px; color: var(--text-dim);">${p.notes || "-"}</td>
          </tr>
        `;
      });
    });

    html += `
          </tbody>
          <tfoot>
            <tr>
              <td colspan="9" style="text-align: center; font-weight: 800; font-size: 13px; color: white;">
                Total: ${items.length} dossier(s) de versement client
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    `;

    container.innerHTML = html;
  }

  function renderCardsView(container, items) {
    let html = `<div class="data-list">`;

    items.forEach((item, idx) => {
      const dossierId = item.id || item.versement_id;
      const clientName = item.client_name || item.client || "Client Inconnu";
      const phone = item.client_phone || item.phone || "";
      const status = item.status || "EN_COURS";
      const createdAt = GoldShopApp.formatDate(item.created_at || item.date);

      const totalPrice = Number(item.total_amount_da || item.total_price_da || item.total_price || 0);
      const paidMoney = Number(item.total_paid_money_da || item.paid_amount_da || item.paid_amount || 0);
      const remainingMoney = Math.max(0, totalPrice - paidMoney);
      const progressPercent = totalPrice > 0 ? Math.min(100, Math.round((paidMoney / totalPrice) * 100)) : 0;

      let badgeClass = "badge-success";
      let statusLabel = "🟢 En Cours";
      if (status === "CLOTURE" || status === "LIVRE") {
        badgeClass = "badge-info";
        statusLabel = "🔵 Clôturé";
      } else if (status === "ANNULE") {
        badgeClass = "badge-danger";
        statusLabel = "🔴 Annulé";
      }

      const collapseId = `versCollapse_${dossierId}_${idx}`;
      const reservedItems = Array.isArray(item.items) ? item.items : (item.reserved_items || []);
      const payments = Array.isArray(item.payments) ? item.payments : [];

      html += `
        <div class="mobile-card" onclick="selectVersementRow(${dossierId}, this)">
          <div class="card-top">
            <div class="card-title-group">
              <span class="card-badge ${badgeClass}">${statusLabel}</span>
              <span style="font-weight: 800; font-size: 14px;">VRS-${String(dossierId).padStart(5, '0')}</span>
            </div>
            <span style="font-size: 11px; color: var(--text-dim);">${createdAt}</span>
          </div>

          <div class="card-rows">
            <div class="card-row">
              <span class="card-row-label">Client:</span>
              <span class="card-row-value" style="font-weight: 700;">${clientName}</span>
            </div>
            ${phone ? `
              <div class="card-row">
                <span class="card-row-label">Téléphone:</span>
                <a href="tel:${phone}" style="color: var(--primary); text-decoration: none; font-weight: 700;">
                  📞 ${phone}
                </a>
              </div>
            ` : ""}
            <div class="card-row">
              <span class="card-row-label">Montant Total:</span>
              <span class="card-row-value">${GoldShopApp.formatMoney(totalPrice)}</span>
            </div>
            <div class="card-row">
              <span class="card-row-label">Payé / Restant:</span>
              <span class="card-row-value success">
                ${GoldShopApp.formatMoney(paidMoney)}
                <span style="color: var(--danger); font-weight: 800; margin-left: 6px;">(Reste: ${GoldShopApp.formatMoney(remainingMoney)})</span>
              </span>
            </div>
          </div>

          <div class="progress-bar-wrap">
            <div class="progress-bar-fill" style="width: ${progressPercent}%;"></div>
          </div>

          <button class="expand-btn" onclick="toggleAccordion('${collapseId}', this)">
            <span>Articles réservés & Détails (${reservedItems.length}) / القطع المحجوزة</span>
            <span class="chevron">▼</span>
          </button>

          <div id="${collapseId}" class="card-collapse">
            <div style="font-size: 12px; font-weight: 700; margin-bottom: 6px; color: var(--text-heading);">
              Articles réservés (${reservedItems.length})
            </div>
            ${reservedItems.length > 0 ? `
              <div style="display: flex; flex-direction: column; gap: 6px; margin-bottom: 8px;">
                ${reservedItems.map(ritem => `
                  <div style="background: var(--bg-surface-elevated); padding: 8px 10px; border-radius: 6px; font-size: 12px; border: 1px solid var(--border-subtle);">
                    <div style="display: flex; justify-content: space-between; font-weight: 700;">
                      <span>💍 ${ritem.designation || ritem.product_name || "Article"}</span>
                      <span class="gold">${GoldShopApp.formatWeight(ritem.display_weight || ritem.weight || 0)}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; color: var(--text-muted); font-size: 11px; margin-top: 3px;">
                      <span>Déduit: <b>${GoldShopApp.formatWeight(ritem.deducted_g || 0)}</b></span>
                      <span>Reste: <b style="color: var(--text-main);">${GoldShopApp.formatWeight(ritem.remaining_g || 0)}</b></span>
                    </div>
                  </div>
                `).join("")}
              </div>
            ` : `<div style="font-size: 11px; color: var(--text-dim); margin-bottom: 8px;">Aucun article détaillé.</div>`}

            ${payments.length > 0 ? `
              <div style="font-size: 12px; font-weight: 700; margin-bottom: 4px; color: var(--text-heading);">
                Historique des versements (${payments.length})
              </div>
              <div style="display: flex; flex-direction: column; gap: 4px; margin-bottom: 8px;">
                ${payments.map(p => `
                  <div style="display: flex; justify-content: space-between; font-size: 11px; border-bottom: 1px dotted var(--border-color); padding: 3px 0;">
                    <span>${GoldShopApp.formatDate(p.payment_date || p.date)}</span>
                    <span style="color: var(--success); font-weight: 700;">${GoldShopApp.formatMoney(p.montant_da || p.amount_da || 0)}</span>
                  </div>
                `).join("")}
              </div>
            ` : ""}
          </div>
        </div>
      `;
    });

    html += `</div>`;
    container.innerHTML = html;
  }

  window.selectVersementRow = function(vId, el) {
    selectedVersementId = vId;
    document.querySelectorAll(".data-table tr").forEach(r => r.style.outline = "");
    if (el) el.style.outline = "2px solid var(--primary)";
  };

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
    if (searchInput) {
      let debounce;
      searchInput.addEventListener("input", () => {
        clearTimeout(debounce);
        debounce = setTimeout(fetchVersementsList, 300);
      });
    }

    if (statusSelect) {
      statusSelect.addEventListener("change", fetchVersementsList);
    }

    if (btnNewVersement) {
      btnNewVersement.addEventListener("click", () => {
        GoldShopApp.showToast("Pour créer un nouveau versement, utilisez l'interface de caisse principale.", "info");
      });
    }

    if (btnDetails) {
      btnDetails.addEventListener("click", () => {
        if (!selectedVersementId && cachedVersements.length > 0) {
          selectedVersementId = cachedVersements[0].id;
        }
        if (selectedVersementId) {
          GoldShopApp.showToast(`Dossier sélectionné: VRS-${String(selectedVersementId).padStart(5, '0')}`, "info");
        } else {
          GoldShopApp.showToast("Veuillez sélectionner un dossier dans le tableau.", "error");
        }
      });
    }

    if (btnPdf) {
      btnPdf.addEventListener("click", () => {
        GoldShopApp.showToast("Aperçu du Bon PDF disponible via l'application de caisse.", "info");
      });
    }

    if (btnGlobalPay) {
      btnGlobalPay.addEventListener("click", () => {
        GoldShopApp.showToast("Pour enregistrer un paiement global, utilisez le terminal de caisse.", "info");
      });
    }

    if (btnClose) {
      btnClose.addEventListener("click", () => {
        GoldShopApp.showToast("La clôture d'un dossier s'effectue après acquittement total du solde.", "info");
      });
    }

    viewModePills.forEach(pill => {
      pill.addEventListener("click", () => {
        viewModePills.forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        currentViewMode = pill.getAttribute("data-versement-view");
        renderVersements(cachedVersements);
      });
    });

    window.refreshCurrentPageData = function() {
      fetchVersementsStats();
      fetchVersementsList();
    };

    fetchVersementsStats();
    fetchVersementsList();
  });
})();

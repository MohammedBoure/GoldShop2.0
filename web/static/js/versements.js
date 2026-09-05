/**
 * GoldShop 2.0 - Versements / Layaways View Controller (versements.js)
 * Implements dossiers, reserved item weights, notes, and payments matching versements_view.py
 */

(function() {
  const searchInput = document.getElementById("versementsSearchInput");
  const statusPills = document.querySelectorAll("[data-versement-status]");

  let currentStatus = "EN_COURS";

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
    const params = new URLSearchParams();
    if (currentStatus && currentStatus !== "ALL") {
      params.append("status", currentStatus);
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
        renderVersementsCards(res.data.items || []);
      }
    } catch (err) {
      if (err.message !== "AUTH_REQUIRED") {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">⚠️</div>
            <div>Erreur de chargement des dossiers de versement.</div>
            <button class="btn-secondary" onclick="window.refreshCurrentPageData()">Réessayer</button>
          </div>
        `;
      }
    }
  }

  function renderVersementsCards(items) {
    const container = document.getElementById("versementsContentArea");
    if (!container) return;

    if (!items || items.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">📦</div>
          <div>Aucun dossier de versement trouvé.</div>
          <div style="font-size: 11px; color: var(--text-dim);">لا توجد ملفات حجز مطابقة.</div>
        </div>
      `;
      return;
    }

    let html = `<div class="data-list">`;

    items.forEach((item, idx) => {
      const dossierId = item.id || item.versement_id;
      const clientName = item.client_name || item.client || "Client Inconnu";
      const phone = item.client_phone || item.phone || "";
      const status = item.status || "EN_COURS";
      const createdAt = GoldShopApp.formatDate(item.created_at || item.date);

      const totalPrice = Number(item.total_price_da || item.total_amount_da || item.total_price || 0);
      const paidMoney = Number(item.total_paid_money_da || item.paid_amount_da || item.paid_amount || 0);
      const remainingMoney = Number(item.remaining_money_da || item.remaining_amount || (totalPrice - paidMoney));
      const progressPercent = totalPrice > 0 ? Math.min(100, Math.round((paidMoney / totalPrice) * 100)) : 0;

      let badgeClass = "badge-gold";
      let statusLabel = status;
      if (status === "EN_COURS") {
        badgeClass = "badge-success";
        statusLabel = "🟢 En Cours";
      } else if (status === "LIVRE") {
        badgeClass = "badge-info";
        statusLabel = "🔵 Livré";
      } else if (status === "ANNULE") {
        badgeClass = "badge-danger";
        statusLabel = "🔴 Annulé";
      }

      const collapseId = `versCollapse_${dossierId}_${idx}`;

      html += `
        <div class="mobile-card">
          <div class="card-top">
            <div class="card-title-group">
              <span class="card-badge ${badgeClass}">${statusLabel}</span>
              <span style="font-weight: 700; font-size: 14px;">Dossier N° ${dossierId}</span>
            </div>
            <span style="font-size: 11px; color: var(--text-dim);">${createdAt}</span>
          </div>

          <div class="card-rows">
            <div class="card-row">
              <span class="card-row-label">Client:</span>
              <span class="card-row-value">${clientName}</span>
            </div>
            ${phone ? `
              <div class="card-row">
                <span class="card-row-label">Téléphone:</span>
                <a href="tel:${phone}" style="color: var(--gold-500); text-decoration: none; font-weight: 600;">
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
                <span style="color: var(--danger); font-weight: 700; margin-left: 6px;">(Reste: ${GoldShopApp.formatMoney(remainingMoney)})</span>
              </span>
            </div>
          </div>

          <div class="progress-bar-wrap">
            <div class="progress-bar-fill" style="width: ${progressPercent}%;"></div>
          </div>

          <button class="expand-btn" onclick="toggleAccordion('${collapseId}', this)">
            <span>Articles réservés & Détails / القطع المحجوزة</span>
            <span class="chevron">▼</span>
          </button>

          <div id="${collapseId}" class="card-collapse">
            <div style="font-size: 12px; font-weight: 700; margin-bottom: 6px; color: var(--gold-500);">
              Articles réservés (${(item.reserved_items || []).length})
            </div>
            ${(item.reserved_items && item.reserved_items.length > 0) ? `
              <div style="display: flex; flex-direction: column; gap: 6px; margin-bottom: 8px;">
                ${item.reserved_items.map(ritem => `
                  <div style="background: var(--bg-surface-elevated); padding: 8px; border-radius: 6px; font-size: 12px;">
                    <div style="display: flex; justify-content: space-between; font-weight: 600;">
                      <span>💍 ${ritem.product_name || ritem.article_name || ritem.name || "Article"}</span>
                      <span class="gold">${GoldShopApp.formatWeight(ritem.total_weight || ritem.weight || 0)}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; color: var(--text-muted); font-size: 11px; margin-top: 3px;">
                      <span>Type: ${ritem.item_type || "WEIGHT"}</span>
                      <span>Déduit: ${GoldShopApp.formatWeight(ritem.deducted_g || 0)} | Reste: <b style="color: var(--text-main);">${GoldShopApp.formatWeight(ritem.remaining_g || 0)}</b></span>
                    </div>
                  </div>
                `).join("")}
              </div>
            ` : `<div style="font-size: 11px; color: var(--text-dim); margin-bottom: 8px;">Aucun article détaillé.</div>`}

            ${(item.payments && item.payments.length > 0) ? `
              <div style="font-size: 12px; font-weight: 700; margin-bottom: 4px; color: var(--gold-500);">
                Historique des versements
              </div>
              <div style="display: flex; flex-direction: column; gap: 4px; margin-bottom: 8px;">
                ${item.payments.map(p => `
                  <div style="display: flex; justify-content: space-between; font-size: 11px; border-bottom: 1px dotted var(--border-color); padding: 3px 0;">
                    <span>${GoldShopApp.formatDate(p.payment_date || p.date)} (${p.payment_method || "Espèces"})</span>
                    <span style="color: var(--success); font-weight: 600;">${GoldShopApp.formatMoney(p.amount_da || p.amount)}</span>
                  </div>
                `).join("")}
              </div>
            ` : ""}

            ${item.custom_note ? `
              <div style="background: rgba(245, 158, 11, 0.08); border-left: 3px solid var(--gold-500); padding: 6px 8px; font-size: 11px; margin-bottom: 4px;">
                <b>Note personnalisée:</b> ${item.custom_note}
              </div>
            ` : ""}

            ${item.observation ? `
              <div style="background: var(--bg-surface-elevated); padding: 6px 8px; font-size: 11px; border-radius: 4px;">
                <b>Observation interne:</b> ${item.observation}
              </div>
            ` : ""}

            ${item.sum_text_1 || item.sum_text_2 ? `
              <div style="font-size: 11px; color: var(--text-dim); margin-top: 6px;">
                <div>${item.sum_text_1 || ""}</div>
                <div>${item.sum_text_2 || ""}</div>
              </div>
            ` : ""}
          </div>
        </div>
      `;
    });

    html += `</div>`;
    container.innerHTML = html;
  }

  document.addEventListener("DOMContentLoaded", () => {
    if (searchInput) {
      let debounce;
      searchInput.addEventListener("input", () => {
        clearTimeout(debounce);
        debounce = setTimeout(fetchVersementsList, 350);
      });
    }

    statusPills.forEach(pill => {
      pill.addEventListener("click", () => {
        statusPills.forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        currentStatus = pill.getAttribute("data-versement-status");
        fetchVersementsList();
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

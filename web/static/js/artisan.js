/**
 * GoldShop 2.0 - Workshop & Repairs View Controller (artisan.js)
 * Implements Tableau de Production and Artisans Accounts matching artisan_work_view.py
 */

(function() {
  const subNavPills = document.querySelectorAll("[data-artisan-subnav]");
  const searchInput = document.getElementById("artisanSearchInput");
  const statusPills = document.querySelectorAll("[data-order-status]");
  const daysSelect = document.getElementById("artisanDaysSelect");

  let activeSubNav = "orders"; // 'orders' or 'artisans'
  let currentStatus = "ALL";

  async function fetchProductionOrders() {
    const container = document.getElementById("artisanContentArea");
    if (!container) return;

    const search = searchInput ? searchInput.value.trim() : "";
    const days = daysSelect ? daysSelect.value : "30";

    const params = new URLSearchParams();
    if (currentStatus && currentStatus !== "ALL") params.append("status", currentStatus);
    if (days) params.append("days", days);
    if (search) params.append("search", search);

    container.innerHTML = `
      <div class="loading-box">
        <div class="spinner"></div>
        <div>Chargement du tableau de production... / جاري تحميل أوامر الورشة...</div>
      </div>
    `;

    try {
      const res = await GoldShopApp.apiFetch(`/api/v1/artisan-work/orders?${params.toString()}`);
      if (res && res.data) {
        renderOrdersCards(res.data.orders || [], res.data.totals || {});
      }
    } catch (err) {
      if (err.message !== "AUTH_REQUIRED") {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">⚠️</div>
            <div>Erreur lors du chargement des ordres d'atelier.</div>
            <button class="btn-secondary" onclick="window.refreshCurrentPageData()">Réessayer</button>
          </div>
        `;
      }
    }
  }

  function renderOrdersCards(orders, totals) {
    const container = document.getElementById("artisanContentArea");
    if (!container) return;

    if (!orders || orders.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">⚒️</div>
          <div>Aucun ordre de fabrication ou réparation trouvé.</div>
          <div style="font-size: 11px; color: var(--text-dim);">لا توجد طلبيات تطابق الفلتر الحالي.</div>
        </div>
      `;
      return;
    }

    let html = `<div class="data-list">`;

    orders.forEach((ord, idx) => {
      const orderId = ord.id || ord.numero;
      const clientName = ord.client_name || ord.Nom || "Client Inconnu";
      const phone = ord.client_phone || ord.Tel || "";
      const artisanName = ord.artisan_name || ord.Artisan || "Atelier Interne";
      const status = ord.status || ord.Statut || "EN_COURS";
      const objDesc = ord.object_description || ord.Obj || "Bijou / Pièce";
      const weight = Number(ord.weight_g || ord.Poid || 0);

      const dateRemis = GoldShopApp.formatDate(ord.date_remis);
      const dateRecue = GoldShopApp.formatDate(ord.date_recue);
      const dateSortie = GoldShopApp.formatDate(ord.date_sortie);

      const prixFacon = Number(ord.prix_facon_da || ord["Prix Façon"] || 0);
      const prixClient = Number(ord.prix_client_da || ord["Prix Client"] || 0);
      const diffProfit = Number(ord.diff_da || ord.Diff || (prixClient - prixFacon));

      let badgeClass = "badge-info";
      if (status === "EN_ATTENTE") badgeClass = "badge-purple";
      else if (status === "EN_COURS") badgeClass = "badge-gold";
      else if (status === "TERMINE") badgeClass = "badge-success";
      else if (status === "LIVRE") badgeClass = "badge-info";
      else if (status === "ANNULE") badgeClass = "badge-danger";

      const collapseId = `orderCollapse_${orderId}_${idx}`;

      html += `
        <div class="mobile-card">
          <div class="card-top">
            <div class="card-title-group">
              <span class="card-badge ${badgeClass}">${status}</span>
              <span style="font-weight: 700; font-size: 14px;">Ordre N° ${orderId}</span>
            </div>
            <span class="card-badge badge-gold">⚒️ ${artisanName}</span>
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
              <span class="card-row-label">Objet / Poids:</span>
              <span class="card-row-value">${objDesc} (<b class="gold">${GoldShopApp.formatWeight(weight)}</b>)</span>
            </div>
            <div class="card-row">
              <span class="card-row-label">Prix Client / Marge:</span>
              <span class="card-row-value">
                <b>${GoldShopApp.formatMoney(prixClient)}</b>
                <span style="color: var(--success); font-size: 12px; margin-left: 6px;">(Diff: +${GoldShopApp.formatMoney(diffProfit)})</span>
              </span>
            </div>
          </div>

          <button class="expand-btn" onclick="toggleAccordion('${collapseId}', this)">
            <span>Dates, Façon & Règlements / تواريخ وأجور الصياغة</span>
            <span class="chevron">▼</span>
          </button>

          <div id="${collapseId}" class="card-collapse">
            <div class="card-rows">
              <div class="card-row">
                <span class="card-row-label">Date remis:</span>
                <span class="card-row-value">${dateRemis}</span>
              </div>
              <div class="card-row">
                <span class="card-row-label">Date prévue (Reçue):</span>
                <span class="card-row-value">${dateRecue}</span>
              </div>
              ${dateSortie !== "-" ? `
                <div class="card-row">
                  <span class="card-row-label">Date sortie:</span>
                  <span class="card-row-value">${dateSortie}</span>
                </div>
              ` : ""}
              <div class="card-row" style="border-top: 1px solid var(--border-subtle); padding-top: 6px;">
                <span class="card-row-label">Prix Façon Artisan:</span>
                <span class="card-row-value danger">${GoldShopApp.formatMoney(prixFacon)}</span>
              </div>
              <div class="card-row">
                <span class="card-row-label">Paiement Espèces (Cash):</span>
                <span class="card-row-value">${GoldShopApp.formatMoney(ord.pay_cash_da || 0)}</span>
              </div>
              ${Number(ord.pay_tpe_da || 0) > 0 ? `
                <div class="card-row">
                  <span class="card-row-label">Paiement TPE:</span>
                  <span class="card-row-value info">${GoldShopApp.formatMoney(ord.pay_tpe_da)}</span>
                </div>
              ` : ""}
              ${Number(ord.pay_oc_g || 0) > 0 ? `
                <div class="card-row">
                  <span class="card-row-label">Paiement Or Cassé:</span>
                  <span class="card-row-value gold">${GoldShopApp.formatWeight(ord.pay_oc_g)}</span>
                </div>
              ` : ""}
            </div>
          </div>
        </div>
      `;
    });

    html += `</div>`;
    container.innerHTML = html;
  }

  async function fetchArtisansList() {
    const container = document.getElementById("artisanContentArea");
    if (!container) return;

    container.innerHTML = `
      <div class="loading-box">
        <div class="spinner"></div>
        <div>Chargement des artisans... / جاري تحميل حسابات الحرفيين...</div>
      </div>
    `;

    try {
      const res = await GoldShopApp.apiFetch("/api/v1/artisan-work/artisans");
      if (res && res.data) {
        renderArtisansCards(res.data.artisans || []);
      }
    } catch (err) {
      if (err.message !== "AUTH_REQUIRED") {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">⚠️</div>
            <div>Erreur lors du chargement des artisans.</div>
          </div>
        `;
      }
    }
  }

  function renderArtisansCards(artisans) {
    const container = document.getElementById("artisanContentArea");
    if (!container) return;

    if (!artisans || artisans.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">👥</div>
          <div>Aucun artisan répertorié.</div>
        </div>
      `;
      return;
    }

    let html = `<div class="data-list">`;

    artisans.forEach(art => {
      const artId = art.id;
      const name = art.name || "Artisan";
      const phone = art.phone || "";
      const specialty = art.specialty || "Fabrication & Réparation";
      const goldBalance = Number(art.pure_gold_balance_g || art.gold_balance_g || 0);
      const moneyBalance = Number(art.labor_money_balance_da || art.money_balance_da || 0);

      html += `
        <div class="mobile-card">
          <div class="card-top">
            <div class="card-title-group">
              <span class="card-badge badge-gold">⚒️ Artisan</span>
              <span style="font-weight: 700; font-size: 15px;">${name}</span>
            </div>
            ${phone ? `<a href="tel:${phone}" style="font-size: 12px; color: var(--gold-500); text-decoration: none;">📞 ${phone}</a>` : ""}
          </div>

          <div style="font-size: 11px; color: var(--text-dim);">${specialty}</div>

          <div class="card-rows" style="margin-top: 6px;">
            <div class="card-row">
              <span class="card-row-label">Solde Or Pur (24K):</span>
              <span class="card-row-value ${goldBalance >= 0 ? "gold" : "danger"}">${GoldShopApp.formatWeight(goldBalance)}</span>
            </div>
            <div class="card-row">
              <span class="card-row-label">Solde Façon (DA):</span>
              <span class="card-row-value ${moneyBalance >= 0 ? "success" : "danger"}">${GoldShopApp.formatMoney(moneyBalance)}</span>
            </div>
          </div>

          <button class="btn-secondary" style="margin-top: 8px; width: 100%;" onclick="openArtisanLedgerModal(${artId}, '${name}')">
            📖 Voir Grand Livre / كشف الحساب
          </button>
        </div>
      `;
    });

    html += `</div>`;
    container.innerHTML = html;
  }

  window.openArtisanLedgerModal = async function(artisanId, artisanName) {
    const modal = document.getElementById("artisanLedgerModal");
    const title = document.getElementById("artisanLedgerTitle");
    const body = document.getElementById("artisanLedgerBody");
    if (!modal || !body) return;

    if (title) title.textContent = `Grand Livre: ${artisanName}`;
    body.innerHTML = `
      <div class="loading-box">
        <div class="spinner"></div>
        <div>Chargement des mouvements...</div>
      </div>
    `;
    modal.classList.add("show");

    try {
      const res = await GoldShopApp.apiFetch(`/api/v1/artisan-work/artisans/${artisanId}/ledger`);
      if (res && res.data) {
        const moves = res.data.movements || [];
        if (moves.length === 0) {
          body.innerHTML = `<div class="empty-state">Aucun mouvement pour cet artisan.</div>`;
          return;
        }
        let mHtml = `<div class="data-list">`;
        moves.forEach(m => {
          mHtml += `
            <div style="background: var(--bg-surface-elevated); border: 1px solid var(--border-color); border-radius: 8px; padding: 10px; font-size: 12px;">
              <div style="display: flex; justify-content: space-between; font-weight: 600; margin-bottom: 4px;">
                <span>${GoldShopApp.formatDate(m.date || m.created_at)}</span>
                <span class="card-badge badge-gold">${m.type || "Mouvement"}</span>
              </div>
              <div style="display: flex; justify-content: space-between; color: var(--text-muted);">
                <span>Poids: <b style="color: var(--text-main);">${GoldShopApp.formatWeight(m.gold_weight_g || 0)}</b></span>
                <span>Façon: <b style="color: var(--text-main);">${GoldShopApp.formatMoney(m.labor_cost_da || 0)}</b></span>
              </div>
              ${m.notes ? `<div style="margin-top: 4px; font-size: 11px; color: var(--text-dim);">${m.notes}</div>` : ""}
            </div>
          `;
        });
        mHtml += `</div>`;
        body.innerHTML = mHtml;
      }
    } catch (e) {
      body.innerHTML = `<div class="empty-state">Erreur de chargement.</div>`;
    }
  };

  window.closeArtisanLedgerModal = function() {
    const modal = document.getElementById("artisanLedgerModal");
    if (modal) modal.classList.remove("show");
  };

  document.addEventListener("DOMContentLoaded", () => {
    subNavPills.forEach(pill => {
      pill.addEventListener("click", () => {
        subNavPills.forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        activeSubNav = pill.getAttribute("data-artisan-subnav");

        const orderFilters = document.getElementById("artisanOrderFilters");
        if (orderFilters) {
          orderFilters.style.display = activeSubNav === "orders" ? "flex" : "none";
        }

        if (activeSubNav === "orders") {
          fetchProductionOrders();
        } else {
          fetchArtisansList();
        }
      });
    });

    if (searchInput) {
      let debounce;
      searchInput.addEventListener("input", () => {
        clearTimeout(debounce);
        debounce = setTimeout(() => {
          if (activeSubNav === "orders") fetchProductionOrders();
        }, 350);
      });
    }

    statusPills.forEach(pill => {
      pill.addEventListener("click", () => {
        statusPills.forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        currentStatus = pill.getAttribute("data-order-status");
        fetchProductionOrders();
      });
    });

    if (daysSelect) {
      daysSelect.addEventListener("change", fetchProductionOrders);
    }

    window.refreshCurrentPageData = function() {
      if (activeSubNav === "orders") fetchProductionOrders();
      else fetchArtisansList();
    };

    fetchProductionOrders();
  });
})();

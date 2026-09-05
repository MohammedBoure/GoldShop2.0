/**
 * GoldShop 2.0 - Workshop & Repairs View Controller (artisan.js)
 * Implements Tableau de Production (14 columns) and Artisans Directory matching artisan_work_view.py:
 * - Tab 1: Tableau de Production (14 colonnes: numero, Nom, Tel, date remis, Obj, Poids, Poids R., Date Reçue, Date Sortie, Prix Façon, Prix Client, Diff, Statut, Artisan)
 * - Tab 2: Répertoire Artisans & Soldes
 */

(function() {
  const subNavPills = document.querySelectorAll("[data-artisan-subnav]");
  const searchInput = document.getElementById("artisanSearchInput");
  const dateFilter = document.getElementById("artisanDateFilter");
  const statusFilter = document.getElementById("artisanStatusFilter");
  const btnNewOrder = document.getElementById("btnNewAtelierOrder");
  const viewModePills = document.querySelectorAll("[data-artisan-view]");
  const filterCard = document.getElementById("artisanOrderFilters");

  let activeSubNav = "orders"; // 'orders' or 'artisans'
  let currentViewMode = "table"; // Default to 14-column Excel table
  let cachedOrders = [];
  let cachedTotals = {};

  async function fetchProductionOrders() {
    const container = document.getElementById("artisanContentArea");
    if (!container) return;

    const search = searchInput ? searchInput.value.trim() : "";
    const days = dateFilter ? dateFilter.value : "ALL";
    const status = statusFilter ? statusFilter.value : "ALL";

    const params = new URLSearchParams();
    if (status && status !== "ALL") params.append("status", status);
    if (days && days !== "ALL") params.append("days", days);
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
        cachedOrders = Array.isArray(res.data) ? res.data : (res.data.orders || []);
        cachedTotals = res.totals || (res.data && res.data.totals) || {};
        renderOrders(cachedOrders, cachedTotals);
      }
    } catch (err) {
      if (err.message !== "AUTH_REQUIRED") {
        container.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">⚠️</div>
            <div>Erreur lors du chargement des ordres d'atelier.</div>
            <button class="btn-secondary-light" onclick="window.refreshCurrentPageData()">Réessayer</button>
          </div>
        `;
      }
    }
  }

  function renderOrders(orders, totals) {
    const container = document.getElementById("artisanContentArea");
    if (!container) return;

    if (!orders || orders.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">⚒️</div>
          <div style="font-size: 15px; font-weight: 700;">Aucun ordre de fabrication ou réparation trouvé.</div>
          <div style="font-size: 12px; color: var(--text-dim); margin-top: 4px;">لا توجد طلبيات تطابق الفلتر الحالي.</div>
        </div>
      `;
      return;
    }

    if (currentViewMode === "cards") {
      renderOrdersCards(container, orders, totals);
    } else {
      renderOrdersTable(container, orders, totals);
    }
  }

  function renderOrdersTable(container, orders, totals) {
    // 14 Columns matching desktop setup_atelier_tab in artisan_work_view.py:
    // "numero", "Nom", "Tel :", "date remis", "Obj", "Poids", "Poids R.",
    // "Date Reçue", "Date Sortie", "Prix (Façon)", "Prix (Client)", "Diff", "Statut", "Artisan"
    let html = `
      <div class="table-responsive-container">
        <table class="data-table">
          <thead>
            <tr>
              <th style="min-width: 60px;">N°</th>
              <th style="min-width: 140px;">Nom</th>
              <th style="min-width: 110px;">Tel :</th>
              <th style="min-width: 95px;">Date Remis</th>
              <th style="min-width: 140px;">Obj</th>
              <th style="min-width: 85px;">Poids</th>
              <th style="min-width: 85px;">Poids R.</th>
              <th style="min-width: 95px;">Date Reçue</th>
              <th style="min-width: 95px;">Date Sortie</th>
              <th style="min-width: 110px;">Prix (Façon)</th>
              <th style="min-width: 110px;">Prix (Client)</th>
              <th style="min-width: 100px;">Diff</th>
              <th style="min-width: 140px;">Statut</th>
              <th style="min-width: 120px;">Artisan</th>
            </tr>
          </thead>
          <tbody>
    `;

    orders.forEach(ord => {
      const num = ord.numero || ord.id || "";
      const clientName = ord.client_name || "Passager";
      const phone = ord.client_phone || "";
      const dateRemis = GoldShopApp.formatDate(ord.date_remis);
      const obj = ord.obj || ord.object_description || "Bijou";
      const pEntre = Number(ord.poids_entre_g || ord.poid || ord.weight_g || 0);
      const pRetour = Number(ord.poids_retour_g || 0);
      const dateRecue = ord.date_recue ? GoldShopApp.formatDate(ord.date_recue) : "-";
      const dateSortie = ord.date_sortie ? GoldShopApp.formatDate(ord.date_sortie) : "-";
      const coutArtisan = Number(ord.cout_artisan_da || ord.prix || 0);
      const prixClient = Number(ord.prix_vente_da || ord.vente || 0);
      const diff = Number(ord.diff || (prixClient - coutArtisan));
      const statusLabel = ord.status_label || ord.status || "RECEPTION";
      const statusColor = ord.status_color || "#27ae60";
      const statusBg = ord.status_bg || "#d5f5e3";
      const artisanName = ord.artisan_name || "Non assigné";

      html += `
        <tr>
          <td style="font-weight: 800; text-align: center;">${num}</td>
          <td style="font-weight: 700; text-align: left;">${clientName}</td>
          <td style="text-align: center; font-size: 11px;">${phone ? `<a href="tel:${phone}" style="text-decoration:none; color:inherit;">${phone}</a>` : "-"}</td>
          <td style="text-align: center;">${dateRemis}</td>
          <td style="text-align: left;">${obj}</td>
          <td style="text-align: center; color: var(--gold-500); font-weight: 700;">${pEntre > 0 ? GoldShopApp.formatWeight(pEntre) : "-"}</td>
          <td style="text-align: center;">${pRetour > 0 ? GoldShopApp.formatWeight(pRetour) : "-"}</td>
          <td style="text-align: center;">${dateRecue}</td>
          <td style="text-align: center;">${dateSortie}</td>
          <td style="text-align: right;">${coutArtisan > 0 ? GoldShopApp.formatMoney(coutArtisan) : "-"}</td>
          <td style="text-align: right; font-weight: 700; color: var(--success);">${prixClient > 0 ? GoldShopApp.formatMoney(prixClient) : "-"}</td>
          <td style="text-align: right; font-weight: 800; color: ${diff >= 0 ? "var(--gold-500)" : "var(--danger)"};">${GoldShopApp.formatMoney(diff)}</td>
          <td style="text-align: center;">
            <span style="display: inline-block; padding: 3px 8px; border-radius: 4px; font-weight: 700; font-size: 11px; background: ${statusBg}; color: ${statusColor}; border: 1px solid ${statusColor};">
              ${statusLabel}
            </span>
          </td>
          <td style="text-align: center; font-weight: 600;">${artisanName}</td>
        </tr>
      `;
    });

    html += `
          </tbody>
          <tfoot>
            <tr>
              <td colspan="9" style="text-align: center; font-weight: 800; font-size: 13px;">
                TOTAL (${orders.length} ordres)
              </td>
              <td style="text-align: right; font-weight: 900;">${GoldShopApp.formatMoney(totals.total_cout_artisan_da || 0)}</td>
              <td style="text-align: right; font-weight: 900;">${GoldShopApp.formatMoney(totals.total_prix_client_da || 0)}</td>
              <td style="text-align: right; font-weight: 900; font-size: 14px;">${GoldShopApp.formatMoney(totals.total_diff_da || 0)}</td>
              <td colspan="2">-</td>
            </tr>
          </tfoot>
        </table>
      </div>
    `;

    container.innerHTML = html;
  }

  function renderOrdersCards(container, orders, totals) {
    let html = `<div class="data-list">`;

    orders.forEach((ord, idx) => {
      const num = ord.numero || ord.id || "";
      const clientName = ord.client_name || "Client Inconnu";
      const phone = ord.client_phone || "";
      const artisanName = ord.artisan_name || "Non assigné";
      const objDesc = ord.obj || ord.object_description || "Bijou / Pièce";
      const weight = Number(ord.poids_entre_g || ord.poid || 0);

      const dateRemis = GoldShopApp.formatDate(ord.date_remis);
      const dateRecue = ord.date_recue ? GoldShopApp.formatDate(ord.date_recue) : "-";
      const dateSortie = ord.date_sortie ? GoldShopApp.formatDate(ord.date_sortie) : "-";

      const coutArtisan = Number(ord.cout_artisan_da || ord.prix || 0);
      const prixClient = Number(ord.prix_vente_da || ord.vente || 0);
      const diffProfit = Number(ord.diff || (prixClient - coutArtisan));

      const statusLabel = ord.status_label || ord.status || "RECEPTION";
      const statusColor = ord.status_color || "#27ae60";
      const statusBg = ord.status_bg || "#d5f5e3";

      const collapseId = `orderCollapse_${idx}`;

      html += `
        <div class="mobile-card">
          <div class="card-top">
            <div class="card-title-group">
              <span style="display: inline-block; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 11px; background: ${statusBg}; color: ${statusColor}; border: 1px solid ${statusColor};">
                ${statusLabel}
              </span>
              <span style="font-weight: 800; font-size: 14px;">N° ${num}</span>
            </div>
            <span style="font-size: 11px; color: var(--text-dim);">${dateRemis}</span>
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
              <span class="card-row-label">Travail / Pièce:</span>
              <span class="card-row-value">${objDesc}</span>
            </div>
            <div class="card-row">
              <span class="card-row-label">Poids Entrée:</span>
              <span class="card-row-value gold">${GoldShopApp.formatWeight(weight)}</span>
            </div>
            <div class="card-row">
              <span class="card-row-label">Prix Client / Marge:</span>
              <span class="card-row-value success">
                ${GoldShopApp.formatMoney(prixClient)}
                <span style="color: var(--gold-500); font-weight: 700; margin-left: 6px;">(Diff: +${GoldShopApp.formatMoney(diffProfit)})</span>
              </span>
            </div>
          </div>

          <button class="expand-btn" onclick="toggleAccordion('${collapseId}', this)">
            <span>Dates de sortie & Détails Façon / تفاصيل الورشة</span>
            <span class="chevron">▼</span>
          </button>

          <div id="${collapseId}" class="card-collapse">
            <div class="card-rows">
              <div class="card-row">
                <span class="card-row-label">Artisan Assigné:</span>
                <span class="card-row-value" style="font-weight: 700;">👨‍🔧 ${artisanName}</span>
              </div>
              <div class="card-row">
                <span class="card-row-label">Date Reçue de l'Artisan:</span>
                <span class="card-row-value">${dateRecue}</span>
              </div>
              <div class="card-row">
                <span class="card-row-label">Date Sortie au Client:</span>
                <span class="card-row-value">${dateSortie}</span>
              </div>
              <div class="card-row">
                <span class="card-row-label">Coût Façon Artisan:</span>
                <span class="card-row-value">${GoldShopApp.formatMoney(coutArtisan)}</span>
              </div>
              <div class="card-row" style="border-top: 1px solid var(--border-subtle); padding-top: 6px;">
                <span class="card-row-label"><b>Bénéfice Net Magasin:</b></span>
                <span class="card-row-value gold"><b>${GoldShopApp.formatMoney(diffProfit)}</b></span>
              </div>
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
        <div>Chargement du répertoire des artisans... / جاري تحميل الحرفيين...</div>
      </div>
    `;

    try {
      const res = await GoldShopApp.apiFetch("/api/v1/artisan-work/artisans");
      const list = Array.isArray(res.data) ? res.data : [];
      renderArtisansDirectory(container, list);
    } catch (err) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">⚠️</div>
          <div>Erreur de chargement des artisans.</div>
        </div>
      `;
    }
  }

  function renderArtisansDirectory(container, artisans) {
    if (!artisans || artisans.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">👨‍🔧</div>
          <div>Aucun artisan enregistré.</div>
        </div>
      `;
      return;
    }

    let html = `<div class="data-list">`;

    artisans.forEach(art => {
      const goldBal = Number(art.gold_balance_g || 0);
      const faconBal = Number(art.facon_balance_da || 0);

      html += `
        <div class="mobile-card" onclick="openArtisanLedger(${art.id}, '${art.name.replace(/'/g, "\\'")}')" style="cursor: pointer;">
          <div class="card-top">
            <div class="card-title-group">
              <span class="card-badge badge-purple">👨‍🔧 Artisan</span>
              <span style="font-weight: 800; font-size: 15px;">${art.name}</span>
            </div>
            <span class="chevron" style="color: var(--primary); font-size: 16px;">➔</span>
          </div>

          <div class="card-rows">
            <div class="card-row">
              <span class="card-row-label">Solde Or Pur 24K:</span>
              <span class="card-row-value gold" style="font-weight: 800;">${GoldShopApp.formatWeight(goldBal)}</span>
            </div>
            <div class="card-row">
              <span class="card-row-label">Solde Façon (DA):</span>
              <span class="card-row-value ${faconBal > 0 ? "danger" : "success"}">${GoldShopApp.formatMoney(faconBal)}</span>
            </div>
            ${art.phone ? `
              <div class="card-row">
                <span class="card-row-label">Téléphone:</span>
                <span style="color: var(--primary); font-weight: 700;">📞 ${art.phone}</span>
              </div>
            ` : ""}
            <div class="card-row">
              <span class="card-row-label">Ordres attribués:</span>
              <span class="card-row-value">${art.orders_count || 0}</span>
            </div>
          </div>
        </div>
      `;
    });

    html += `</div>`;
    container.innerHTML = html;
  }

  window.openArtisanLedger = async function(artisanId, artisanName) {
    const modal = document.getElementById("artisanLedgerModal");
    const title = document.getElementById("artisanLedgerTitle");
    const body = document.getElementById("artisanLedgerBody");
    if (!modal || !body) return;

    if (title) title.textContent = `Grand Livre Artisan — ${artisanName}`;
    body.innerHTML = `
      <div class="loading-box">
        <div class="spinner"></div>
        <div>Chargement du relevé des mouvements...</div>
      </div>
    `;
    modal.classList.add("show");

    try {
      const res = await GoldShopApp.apiFetch(`/api/v1/artisan-work/artisans/${artisanId}/ledger`);
      if (res && res.data) {
        const movements = res.data.ledger || [];
        const bal = res.data.balance || {};

        let ledgerHtml = `
          <div style="display: flex; gap: 8px; margin-bottom: 12px;">
            <div class="kpi-card" style="flex: 1;">
              <div class="kpi-label">Solde Or Fin</div>
              <div class="kpi-value gold">${GoldShopApp.formatWeight(bal.solde_or_fin_g || 0)}</div>
            </div>
            <div class="kpi-card" style="flex: 1;">
              <div class="kpi-label">Solde Façon</div>
              <div class="kpi-value">${GoldShopApp.formatMoney(bal.solde_facon_da || 0)}</div>
            </div>
          </div>
        `;

        if (movements.length === 0) {
          ledgerHtml += `<div class="empty-state"><div>Aucun mouvement enregistré.</div></div>`;
        } else {
          ledgerHtml += `
            <div class="table-responsive-container">
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Type</th>
                    <th>Poids Or Fin</th>
                    <th>Façon (DA)</th>
                    <th>Libellé</th>
                  </tr>
                </thead>
                <tbody>
          `;
          movements.forEach(m => {
            ledgerHtml += `
              <tr>
                <td>${GoldShopApp.formatDate(m.date || m.created_at)}</td>
                <td><span class="card-badge ${m.type === 'DON_OR' ? 'badge-gold' : 'badge-info'}">${m.type || "-"}</span></td>
                <td style="text-align: center; color: var(--gold-500); font-weight: 700;">${m.or_fin_g ? GoldShopApp.formatWeight(m.or_fin_g) : "-"}</td>
                <td style="text-align: right;">${m.facon_da ? GoldShopApp.formatMoney(m.facon_da) : "-"}</td>
                <td>${m.libelle || m.notes || "-"}</td>
              </tr>
            `;
          });
          ledgerHtml += `</tbody></table></div>`;
        }

        body.innerHTML = ledgerHtml;
      }
    } catch (e) {
      body.innerHTML = `<div class="empty-state">Erreur de chargement.</div>`;
    }
  };

  window.closeArtisanLedgerModal = function() {
    const modal = document.getElementById("artisanLedgerModal");
    if (modal) modal.classList.remove("show");
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
    subNavPills.forEach(pill => {
      pill.addEventListener("click", () => {
        subNavPills.forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        activeSubNav = pill.getAttribute("data-artisan-subnav");

        if (activeSubNav === "orders") {
          if (filterCard) filterCard.style.display = "block";
          fetchProductionOrders();
        } else {
          if (filterCard) filterCard.style.display = "none";
          fetchArtisansList();
        }
      });
    });

    if (dateFilter) dateFilter.addEventListener("change", fetchProductionOrders);
    if (statusFilter) statusFilter.addEventListener("change", fetchProductionOrders);

    if (searchInput) {
      let debounce;
      searchInput.addEventListener("input", () => {
        clearTimeout(debounce);
        debounce = setTimeout(fetchProductionOrders, 300);
      });
    }

    if (btnNewOrder) {
      btnNewOrder.addEventListener("click", () => {
        GoldShopApp.showToast("Pour créer un nouveau dépôt d'atelier, utilisez le module atelier de l'application de caisse.", "info");
      });
    }

    viewModePills.forEach(pill => {
      pill.addEventListener("click", () => {
        viewModePills.forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        currentViewMode = pill.getAttribute("data-artisan-view");
        renderOrders(cachedOrders, cachedTotals);
      });
    });

    window.refreshCurrentPageData = function() {
      if (activeSubNav === "orders") {
        fetchProductionOrders();
      } else {
        fetchArtisansList();
      }
    };

    fetchProductionOrders();
  });
})();

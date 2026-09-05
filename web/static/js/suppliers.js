/**
 * GoldShop 2.0 - French Supplier Ledger View Controller (suppliers.js)
 * Implements the French Excel Ledger spreadsheet format matching suppliers_view.py
 */

(function() {
  const searchInput = document.getElementById("suppliersSearchInput");
  const suppliersListView = document.getElementById("suppliersListView");
  const supplierLedgerView = document.getElementById("supplierLedgerView");
  const btnBackToSuppliers = document.getElementById("btnBackToSuppliers");

  let allSuppliers = [];
  let currentSupplierId = null;

  async function fetchSuppliersList() {
    if (!suppliersListView) return;

    suppliersListView.innerHTML = `
      <div class="loading-box">
        <div class="spinner"></div>
        <div>Chargement des fournisseurs... / جاري تحميل الموردين...</div>
      </div>
    `;

    try {
      const res = await GoldShopApp.apiFetch("/api/v1/suppliers");
      if (res && res.data) {
        allSuppliers = res.data.suppliers || [];
        renderSuppliersCards(allSuppliers);
      }
    } catch (err) {
      if (err.message !== "AUTH_REQUIRED") {
        suppliersListView.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">⚠️</div>
            <div>Erreur de chargement des fournisseurs.</div>
            <button class="btn-secondary" onclick="window.refreshCurrentPageData()">Réessayer</button>
          </div>
        `;
      }
    }
  }

  function renderSuppliersCards(suppliers) {
    if (!suppliersListView) return;

    const query = searchInput ? searchInput.value.trim().toLowerCase() : "";
    const filtered = suppliers.filter(s => {
      const name = (s.name || "").toLowerCase();
      const phone = (s.phone || "").toLowerCase();
      return !query || name.includes(query) || phone.includes(query);
    });

    if (filtered.length === 0) {
      suppliersListView.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">👥</div>
          <div>Aucun fournisseur trouvé.</div>
          <div style="font-size: 11px; color: var(--text-dim);">لا توجد نتائج مطابقة.</div>
        </div>
      `;
      return;
    }

    let html = `<div class="data-list">`;

    filtered.forEach(sup => {
      const supId = sup.id;
      const name = sup.name || "Fournisseur";
      const phone = sup.phone || "";
      const company = sup.company_name || sup.address || "";
      const poidsNet = Number(sup.poids_net || sup.weight_balance_g || 0);
      const soldeDa = Number(sup.solde_da || sup.money_balance_da || 0);

      html += `
        <div class="mobile-card" onclick="openSupplierLedger(${supId}, '${name.replace(/'/g, "\\'")}')" style="cursor: pointer;">
          <div class="card-top">
            <div class="card-title-group">
              <span class="card-badge badge-gold">🏢 Fournisseur</span>
              <span style="font-weight: 700; font-size: 15px;">${name}</span>
            </div>
            <span class="chevron" style="color: var(--gold-500); font-size: 16px;">➔</span>
          </div>

          ${company ? `<div style="font-size: 11px; color: var(--text-dim);">${company}</div>` : ""}

          <div class="card-rows" style="margin-top: 6px;">
            <div class="card-row">
              <span class="card-row-label">Solde Poids Net (g):</span>
              <span class="card-row-value ${poidsNet > 0 ? "gold" : "success"}">${GoldShopApp.formatWeight(poidsNet)}</span>
            </div>
            <div class="card-row">
              <span class="card-row-label">Solde Compte (DA):</span>
              <span class="card-row-value ${soldeDa > 0 ? "danger" : "success"}">${GoldShopApp.formatMoney(soldeDa)}</span>
            </div>
            ${phone ? `
              <div class="card-row" style="margin-top: 4px;">
                <span class="card-row-label">Téléphone:</span>
                <span style="color: var(--gold-500); font-size: 12px;">📞 ${phone}</span>
              </div>
            ` : ""}
          </div>
        </div>
      `;
    });

    html += `</div>`;
    suppliersListView.innerHTML = html;
  }

  window.openSupplierLedger = async function(supplierId, supplierName) {
    currentSupplierId = supplierId;
    if (suppliersListView) suppliersListView.style.display = "none";
    if (supplierLedgerView) supplierLedgerView.style.display = "block";

    const titleEl = document.getElementById("supplierLedgerHeaderName");
    if (titleEl) titleEl.textContent = supplierName;

    const ledgerContainer = document.getElementById("supplierLedgerContainer");
    if (!ledgerContainer) return;

    ledgerContainer.innerHTML = `
      <div class="loading-box">
        <div class="spinner"></div>
        <div>Chargement du grand livre fournisseur...</div>
      </div>
    `;

    try {
      const res = await GoldShopApp.apiFetch(`/api/v1/suppliers/${supplierId}/ledger`);
      if (res && res.data) {
        renderLedgerTable(res.data);
      }
    } catch (err) {
      ledgerContainer.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">⚠️</div>
          <div>Erreur de chargement du grand livre.</div>
        </div>
      `;
    }
  };

  function renderLedgerTable(data) {
    const ledgerContainer = document.getElementById("supplierLedgerContainer");
    if (!ledgerContainer) return;

    const summary = data.summary || {};
    const rows = data.ledger_rows || data.rows || [];

    // Header cards
    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    };
    setVal("kpiLedgerPoidsNet", GoldShopApp.formatWeight(summary.poids_net || summary.final_weight_balance || 0));
    setVal("kpiLedgerSoldeDa", GoldShopApp.formatMoney(summary.solde_da || summary.final_money_balance || 0));

    if (rows.length === 0) {
      ledgerContainer.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">📖</div>
          <div>Aucune écriture comptable pour ce fournisseur.</div>
        </div>
      `;
      return;
    }

    // Render mobile spreadsheet cards and horizontal table matching the 5 Excel columns:
    // Date | Poids | Afaçon | Montant | Obs / Libellé
    let html = `
      <div class="table-responsive-container">
        <table class="data-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Poids (g)</th>
              <th>Afaçon (DA)</th>
              <th>Montant (DA)</th>
              <th>Obs / Libellé</th>
            </tr>
          </thead>
          <tbody>
    `;

    rows.forEach(r => {
      const dateStr = GoldShopApp.formatDate(r.date || r.Date);
      const poids = Number(r.poids || r.Poids || 0);
      const afacon = Number(r.afacon || r.Afaçon || 0);
      const montant = Number(r.montant || r.Montant || 0);
      const rawObs = String(r.obs || r.Obs || r.libelle || "");

      // Highlights
      let obsHtml = rawObs;
      let rowStyle = "";
      if (rawObs.includes("[COLOR:RED]")) {
        obsHtml = rawObs.replace("[COLOR:RED]", "");
        obsHtml = `<span class="card-badge badge-danger">⚠️ ${obsHtml}</span>`;
        rowStyle = "background: rgba(239, 68, 68, 0.05);";
      } else if (rawObs.toLowerCase().includes("régler") || rawObs.toLowerCase().includes("regler")) {
        obsHtml = `<span class="card-badge badge-success">✅ ${obsHtml}</span>`;
      } else if (rawObs.toLowerCase().includes("alliage")) {
        obsHtml = `<span class="card-badge badge-gold">✨ ${obsHtml}</span>`;
      }

      html += `
        <tr style="${rowStyle}">
          <td><b>${dateStr}</b></td>
          <td style="${poids !== 0 ? "font-weight: 700; color: var(--gold-500);" : ""}">${poids !== 0 ? GoldShopApp.formatWeight(poids) : "-"}</td>
          <td>${afacon !== 0 ? GoldShopApp.formatMoney(afacon) : "-"}</td>
          <td style="${montant !== 0 ? "font-weight: 700; color: var(--success);" : ""}">${montant !== 0 ? GoldShopApp.formatMoney(montant) : "-"}</td>
          <td>${obsHtml || "-"}</td>
        </tr>
      `;
    });

    html += `
          </tbody>
          <tfoot>
            <tr>
              <td>TOTAL</td>
              <td style="color: var(--gold-500);">${GoldShopApp.formatWeight(summary.total_poids || summary.poids_net || 0)}</td>
              <td>${GoldShopApp.formatMoney(summary.total_afacon || 0)}</td>
              <td style="color: var(--success);">${GoldShopApp.formatMoney(summary.total_montant || summary.solde_da || 0)}</td>
              <td>-</td>
            </tr>
          </tfoot>
        </table>
      </div>
    `;

    ledgerContainer.innerHTML = html;
  }

  function backToList() {
    currentSupplierId = null;
    if (supplierLedgerView) supplierLedgerView.style.display = "none";
    if (suppliersListView) suppliersListView.style.display = "block";
  }

  document.addEventListener("DOMContentLoaded", () => {
    if (searchInput) {
      searchInput.addEventListener("input", () => {
        renderSuppliersCards(allSuppliers);
      });
    }

    if (btnBackToSuppliers) {
      btnBackToSuppliers.addEventListener("click", backToList);
    }

    window.refreshCurrentPageData = function() {
      if (currentSupplierId) {
        openSupplierLedger(currentSupplierId, document.getElementById("supplierLedgerHeaderName").textContent);
      } else {
        fetchSuppliersList();
      }
    };

    fetchSuppliersList();
  });
})();

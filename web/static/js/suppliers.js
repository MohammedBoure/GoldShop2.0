/**
 * GoldShop 2.0 - French Supplier Ledger View Controller (suppliers.js)
 * Implements the French Excel Ledger spreadsheet format matching suppliers_view.py:
 * - 1. Top Bar: Supplier Selection combo + [🔄 Actualiser]
 * - 2. Prominent Header Card: Title, Poids Net, Solde DA
 * - 3. Action Toolbar: [➕ Nouvelle Opération], [✏️ Modifier], [🗑️ Supprimer], [🎨 Changer Couleur]
 * - 4. 5-column French Excel Table: Date | Poids | Afaçon | Montant | Obs / Libellé
 */

(function() {
  const supplierSelectCombo = document.getElementById("supplierSelectCombo");
  const btnRefresh = document.getElementById("btnRefreshSupplier");
  const headerTitle = document.getElementById("supplierHeaderCardTitle");
  const headerPoidsNet = document.getElementById("supplierHeaderPoidsNet");
  const headerSoldeDa = document.getElementById("supplierHeaderSoldeDa");

  const btnAddOp = document.getElementById("btnAddSupplierOp");
  const btnEditOp = document.getElementById("btnEditSupplierOp");
  const btnDeleteOp = document.getElementById("btnDeleteSupplierOp");
  const btnToggleColor = document.getElementById("btnToggleColorOp");

  const viewModePills = document.querySelectorAll("[data-supplier-view]");
  const ledgerSection = document.getElementById("supplierLedgerSection");
  const directorySection = document.getElementById("supplierDirectorySection");
  const searchInput = document.getElementById("suppliersSearchInput");
  const suppliersListView = document.getElementById("suppliersListView");
  const ledgerContainer = document.getElementById("supplierLedgerContainer");

  let allSuppliers = [];
  let currentSupplierId = null;
  let currentSupplierName = "";
  let currentViewMode = "ledger"; // 'ledger' or 'directory'
  let selectedLedgerRowIndex = null;

  async function loadSuppliersList() {
    if (!supplierSelectCombo) return;

    supplierSelectCombo.innerHTML = `<option value="">Chargement des fournisseurs...</option>`;

    try {
      const res = await GoldShopApp.apiFetch("/api/v1/suppliers?per_page=100");
      if (res && res.data) {
        allSuppliers = Array.isArray(res.data) ? res.data : (res.data.suppliers || []);
        
        if (allSuppliers.length === 0) {
          supplierSelectCombo.innerHTML = `<option value="">Aucun fournisseur disponible</option>`;
          if (headerTitle) headerTitle.textContent = "Aucun fournisseur";
          return;
        }

        supplierSelectCombo.innerHTML = "";
        allSuppliers.forEach((s, idx) => {
          const opt = document.createElement("option");
          opt.value = String(s.id);
          const pNet = Number(s.poids_net || s.weight_balance_g || 0);
          const solde = Number(s.solde_da || s.money_balance_da || 0);
          opt.textContent = `${s.name} (${GoldShopApp.formatWeight(pNet)} | ${GoldShopApp.formatMoney(solde)})`;
          supplierSelectCombo.appendChild(opt);
        });

        // Automatically select the first supplier so data loads immediately!
        if (!currentSupplierId && allSuppliers.length > 0) {
          currentSupplierId = allSuppliers[0].id;
          currentSupplierName = allSuppliers[0].name;
          supplierSelectCombo.value = String(currentSupplierId);
        }

        if (currentSupplierId) {
          fetchSupplierLedger(currentSupplierId);
        }

        if (directorySection && directorySection.style.display !== "none") {
          renderDirectoryCards(allSuppliers);
        }
      }
    } catch (err) {
      if (err.message !== "AUTH_REQUIRED") {
        supplierSelectCombo.innerHTML = `<option value="">Erreur de chargement</option>`;
      }
    }
  }

  async function fetchSupplierLedger(supplierId) {
    currentSupplierId = supplierId;
    const sup = allSuppliers.find(s => String(s.id) === String(supplierId));
    if (sup) {
      currentSupplierName = sup.name;
    }

    if (headerTitle) {
      headerTitle.textContent = currentSupplierName || `Fournisseur N° ${supplierId}`;
    }

    if (!ledgerContainer) return;

    ledgerContainer.innerHTML = `
      <div class="loading-box">
        <div class="spinner"></div>
        <div>Chargement du grand livre fournisseur... / جاري تحميل الحساب...</div>
      </div>
    `;

    try {
      const res = await GoldShopApp.apiFetch(`/api/v1/suppliers/${supplierId}/ledger`);
      if (res && res.data) {
        renderLedgerTable(res.data);
      }
    } catch (err) {
      if (err.message !== "AUTH_REQUIRED") {
        ledgerContainer.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">⚠️</div>
            <div>Erreur de chargement du grand livre pour ce fournisseur.</div>
            <button class="btn-secondary-light" onclick="window.refreshCurrentPageData()">Réessayer</button>
          </div>
        `;
      }
    }
  }

  function renderLedgerTable(data) {
    if (!ledgerContainer) return;

    const summary = data.summary || {};
    const rows = data.ledger_rows || data.rows || [];

    // Update Prominent Header Card Badges matching SuppliersView
    const poidsNetVal = Number(summary.poids_net || summary.final_weight_balance || (data.supplier && data.supplier.poids_net) || 0);
    const soldeDaVal = Number(summary.solde_da || summary.final_money_balance || (data.supplier && data.supplier.solde_da) || 0);

    if (headerPoidsNet) {
      headerPoidsNet.textContent = `Poids Net: ${GoldShopApp.formatWeight(poidsNetVal)}`;
    }
    if (headerSoldeDa) {
      headerSoldeDa.textContent = `Solde: ${GoldShopApp.formatMoney(soldeDaVal)}`;
    }

    if (rows.length === 0) {
      ledgerContainer.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">📖</div>
          <div style="font-size: 15px; font-weight: 700;">Aucune écriture comptable pour ce fournisseur.</div>
          <div style="font-size: 12px; color: var(--text-dim); margin-top: 4px;">دفتر الأستاذ فارغ حالياً لهذا المورد.</div>
        </div>
      `;
      return;
    }

    // 5 Columns matching desktop French spreadsheet:
    // Date | Poids (g) | Afaçon (DA) | Montant (DA) | Obs / Libellé
    let html = `
      <div class="table-responsive-container">
        <table class="data-table">
          <thead>
            <tr>
              <th style="min-width: 100px;">Date</th>
              <th style="min-width: 110px;">Poids (g)</th>
              <th style="min-width: 110px;">Afaçon (DA)</th>
              <th style="min-width: 120px;">Montant (DA)</th>
              <th style="min-width: 220px; text-align: left;">Obs / Libellé</th>
            </tr>
          </thead>
          <tbody>
    `;

    rows.forEach((r, idx) => {
      const dateStr = GoldShopApp.formatDate(r.date || r.Date);
      const poids = Number(r.poids || r.Poids || 0);
      const afacon = Number(r.afacon || r.Afaçon || 0);
      const montant = Number(r.montant || r.Montant || 0);
      const rawObs = String(r.obs || r.Obs || r.libelle || "");

      // Color Overrides
      let obsHtml = rawObs;
      let rowStyle = "";
      if (rawObs.includes("[COLOR:RED]")) {
        obsHtml = rawObs.replace("[COLOR:RED]", "").trim();
        obsHtml = `<span class="card-badge badge-danger">⚠️ ${obsHtml}</span>`;
        rowStyle = "background-color: #fff5f5; color: #b91c1c;";
      } else if (rawObs.toLowerCase().includes("règlement") || rawObs.toLowerCase().includes("reglement") || rawObs.toLowerCase().includes("versé")) {
        obsHtml = `<span class="card-badge badge-success">✅ ${obsHtml}</span>`;
      } else if (rawObs.toLowerCase().includes("alliage") || rawObs.toLowerCase().includes("lingot")) {
        obsHtml = `<span class="card-badge badge-gold">✨ ${obsHtml}</span>`;
      }

      html += `
        <tr style="${rowStyle}" onclick="selectLedgerRow(${idx}, this)">
          <td style="text-align: center; font-weight: 700;">${dateStr}</td>
          <td style="text-align: center; ${poids !== 0 ? 'font-weight: 800; color: var(--gold-500);' : ''}">
            ${poids !== 0 ? GoldShopApp.formatWeight(poids) : "-"}
          </td>
          <td style="text-align: right;">
            ${afacon !== 0 ? GoldShopApp.formatMoney(afacon) : "-"}
          </td>
          <td style="text-align: right; ${montant !== 0 ? 'font-weight: 800; color: var(--success);' : ''}">
            ${montant !== 0 ? GoldShopApp.formatMoney(montant) : "-"}
          </td>
          <td style="text-align: left; font-size: 12px;">${obsHtml || "-"}</td>
        </tr>
      `;
    });

    // Embedded Totals Row in Blue / Primary (#0f8f83 or #0284c7)
    html += `
          </tbody>
          <tfoot>
            <tr>
              <td style="text-align: center; font-weight: 900; font-size: 14px;">TOTAL</td>
              <td style="text-align: center; font-weight: 900; font-size: 14px;">${GoldShopApp.formatWeight(poidsNetVal)}</td>
              <td style="text-align: right; font-weight: 900; font-size: 13px;">${GoldShopApp.formatMoney(summary.total_afacon || 0)}</td>
              <td style="text-align: right; font-weight: 900; font-size: 14px;">${GoldShopApp.formatMoney(soldeDaVal)}</td>
              <td style="text-align: left; font-size: 12px;">${rows.length} écriture(s)</td>
            </tr>
          </tfoot>
        </table>
      </div>
    `;

    ledgerContainer.innerHTML = html;
  }

  function renderDirectoryCards(suppliers) {
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
          <div>Aucun fournisseur trouvé dans le répertoire.</div>
        </div>
      `;
      return;
    }

    let html = `<div class="data-list">`;

    filtered.forEach(sup => {
      const supId = sup.id;
      const name = sup.name || "Fournisseur";
      const phone = sup.phone || "";
      const pNet = Number(sup.poids_net || sup.weight_balance_g || 0);
      const solde = Number(sup.solde_da || sup.money_balance_da || 0);

      html += `
        <div class="mobile-card" onclick="switchToSupplier(${supId})" style="cursor: pointer;">
          <div class="card-top">
            <div class="card-title-group">
              <span class="card-badge badge-gold">🏢 Fournisseur</span>
              <span style="font-weight: 800; font-size: 15px;">${name}</span>
            </div>
            <span class="chevron" style="color: var(--primary); font-size: 16px;">➔</span>
          </div>

          <div class="card-rows">
            <div class="card-row">
              <span class="card-row-label">Solde Poids Net:</span>
              <span class="card-row-value gold" style="font-weight: 800;">${GoldShopApp.formatWeight(pNet)}</span>
            </div>
            <div class="card-row">
              <span class="card-row-label">Solde Compte (DA):</span>
              <span class="card-row-value ${solde > 0 ? "danger" : "success"}" style="font-weight: 800;">${GoldShopApp.formatMoney(solde)}</span>
            </div>
            ${phone ? `
              <div class="card-row">
                <span class="card-row-label">Téléphone:</span>
                <span style="color: var(--primary); font-weight: 700;">📞 ${phone}</span>
              </div>
            ` : ""}
          </div>
        </div>
      `;
    });

    html += `</div>`;
    suppliersListView.innerHTML = html;
  }

  window.switchToSupplier = function(supId) {
    if (supplierSelectCombo) {
      supplierSelectCombo.value = String(supId);
    }
    // Switch view mode back to ledger
    viewModePills.forEach(p => {
      if (p.getAttribute("data-supplier-view") === "ledger") p.classList.add("active");
      else p.classList.remove("active");
    });
    if (ledgerSection) ledgerSection.style.display = "block";
    if (directorySection) directorySection.style.display = "none";
    currentViewMode = "ledger";
    fetchSupplierLedger(supId);
  };

  window.selectLedgerRow = function(idx, el) {
    selectedLedgerRowIndex = idx;
    document.querySelectorAll(".data-table tr").forEach(r => r.style.outline = "");
    if (el) el.style.outline = "2px solid var(--primary)";
  };

  document.addEventListener("DOMContentLoaded", () => {
    if (supplierSelectCombo) {
      supplierSelectCombo.addEventListener("change", () => {
        const val = supplierSelectCombo.value;
        if (val) {
          fetchSupplierLedger(val);
        }
      });
    }

    if (btnRefresh) {
      btnRefresh.addEventListener("click", () => {
        if (currentSupplierId) {
          fetchSupplierLedger(currentSupplierId);
        } else {
          loadSuppliersList();
        }
      });
    }

    if (btnAddOp) {
      btnAddOp.addEventListener("click", () => {
        GoldShopApp.showToast("Pour enregistrer une nouvelle opération fournisseur, utilisez l'interface de gestion sur le PC.", "info");
      });
    }

    if (btnEditOp) {
      btnEditOp.addEventListener("click", () => {
        GoldShopApp.showToast("Pour modifier une ligne du grand livre, utilisez la fenêtre de modification sur le PC.", "info");
      });
    }

    if (btnDeleteOp) {
      btnDeleteOp.addEventListener("click", () => {
        GoldShopApp.showToast("La suppression d'écritures s'effectue avec confirmation administrative sur le PC.", "info");
      });
    }

    if (btnToggleColor) {
      btnToggleColor.addEventListener("click", () => {
        GoldShopApp.showToast("Le marquage couleur (Rouge/Normal) est géré via le clic droit sur la table du PC.", "info");
      });
    }

    if (searchInput) {
      searchInput.addEventListener("input", () => {
        renderDirectoryCards(allSuppliers);
      });
    }

    viewModePills.forEach(pill => {
      pill.addEventListener("click", () => {
        viewModePills.forEach(p => p.classList.remove("active"));
        pill.classList.add("active");
        currentViewMode = pill.getAttribute("data-supplier-view");

        if (currentViewMode === "ledger") {
          if (ledgerSection) ledgerSection.style.display = "block";
          if (directorySection) directorySection.style.display = "none";
          if (currentSupplierId) fetchSupplierLedger(currentSupplierId);
        } else {
          if (ledgerSection) ledgerSection.style.display = "none";
          if (directorySection) directorySection.style.display = "block";
          renderDirectoryCards(allSuppliers);
        }
      });
    });

    window.refreshCurrentPageData = function() {
      loadSuppliersList();
    };

    loadSuppliersList();
  });
})();

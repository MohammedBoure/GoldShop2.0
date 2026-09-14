/**
 * GoldShop 2.0 - French Supplier Ledger View Controller (suppliers.js)
 * Implements the French Excel Ledger spreadsheet format matching ui/widgets/suppliers/suppliers_view.py:
 * - 1. Top Bar: Supplier Selection combo + [🔄 Actualiser]
 * - 2. Prominent Header Card: Title, Poids Net, Solde DA
 * - 3. 5-column French Excel Table: Date | Poids | Afaçon | Montant | Obs / Libellé (Consultation lecture seule)
 * - 4. Embedded Totals Row: Light Blue background (#e0f2fe) with Navy bold text (#0369a1)
 */

(function() {
  const supplierSelectCombo = document.getElementById("supplierSelectCombo");
  const btnRefresh = document.getElementById("btnRefreshSupplier");
  const headerTitle = document.getElementById("supplierHeaderCardTitle");
  const headerPoidsNet = document.getElementById("supplierHeaderPoidsNet");
  const headerSoldeDa = document.getElementById("supplierHeaderSoldeDa");

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

  // ------------------------------------------------------------------
  // Number & Currency Formatters Matching Desktop SuppliersView
  // ------------------------------------------------------------------

  function formatPoids(grams) {
    const num = Number(grams) || 0;
    return (
      num.toLocaleString("fr-DZ", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }) + " g"
    );
  }

  function formatMoneyDa(amount) {
    const num = Math.round(Number(amount) || 0);
    return (
      num.toLocaleString("fr-DZ", {
        maximumFractionDigits: 0,
      }) + " DA"
    );
  }

  function formatNumberFR(num, decimals = 2) {
    const val = Number(num) || 0;
    if (Math.abs(val) < 0.00001) {
      return decimals === 0 ? "0" : "0,00";
    }
    return val.toLocaleString("fr-DZ", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  }

  function formatDateDDMMYYYY(rawDate) {
    if (!rawDate) return "-";
    const s = String(rawDate).trim();
    if (s.includes("/")) return s;
    try {
      const clean = s.split("T")[0].split(" ")[0];
      const parts = clean.split("-");
      if (parts.length === 3) {
        return `${parts[2]}/${parts[1]}/${parts[0]}`;
      }
      return clean;
    } catch {
      return s;
    }
  }

  // ------------------------------------------------------------------
  // Data Extraction Helper (Handles multiple API response formats)
  // ------------------------------------------------------------------

  function extractLedgerData(res) {
    let rows = [];
    let summary = {};
    let supplier = {};

    if (!res) return { rows, summary, supplier };

    const payload = res.data !== undefined ? res.data : res;

    if (Array.isArray(payload)) {
      rows = payload;
      summary = (res.meta && res.meta.totals) || res.totals || {};
      supplier = res.meta || {};
    } else if (payload && typeof payload === "object") {
      rows = payload.rows || payload.ledger_rows || (Array.isArray(payload.data) ? payload.data : []);
      summary = payload.summary || payload.totals || (res.meta && res.meta.totals) || {};
      supplier = payload.supplier || res.meta || {};
    }

    return { rows, summary, supplier };
  }

  // ------------------------------------------------------------------
  // Load Suppliers List for Dropdown and Directory
  // ------------------------------------------------------------------

  async function loadSuppliersList(autoSelect = true) {
    if (!supplierSelectCombo) return;

    supplierSelectCombo.innerHTML = `<option value="">Chargement des fournisseurs...</option>`;

    try {
      const res = await GoldShopApp.apiFetch("/api/v1/suppliers?all=true&per_page=500");
      if (res && res.data) {
        allSuppliers = Array.isArray(res.data) ? res.data : (res.data.suppliers || []);

        if (allSuppliers.length === 0) {
          supplierSelectCombo.innerHTML = `<option value="">Aucun fournisseur disponible</option>`;
          if (headerTitle) headerTitle.textContent = "Aucun fournisseur";
          if (headerPoidsNet) headerPoidsNet.textContent = "Poids Net: 0.00 g";
          if (headerSoldeDa) headerSoldeDa.textContent = "Solde: 0 DA";
          return;
        }

        supplierSelectCombo.innerHTML = "";
        allSuppliers.forEach(s => {
          const opt = document.createElement("option");
          opt.value = String(s.id);
          const pNet = Number(s.poids_net ?? s.weight_balance_g ?? 0);
          const solde = Number(s.solde_da ?? s.money_balance_da ?? 0);
          opt.textContent = `${s.name} (${formatPoids(pNet)} | ${formatMoneyDa(solde)})`;
          supplierSelectCombo.appendChild(opt);
        });

        // Determine target supplier to select
        if (autoSelect || !currentSupplierId) {
          // Prioritize supplier with operations or active transactions (e.g. supplier with operations_count > 0 or non-zero balance)
          const activeSup = allSuppliers.find(s => (s.operations_count && s.operations_count > 0) || Math.abs(Number(s.poids_net || 0)) > 0.001 || Math.abs(Number(s.solde_da || 0)) > 0.01);
          const chosen = activeSup || allSuppliers[0];
          currentSupplierId = chosen.id;
          currentSupplierName = chosen.name;
        }

        if (currentSupplierId) {
          supplierSelectCombo.value = String(currentSupplierId);
          const currentSupObj = allSuppliers.find(s => String(s.id) === String(currentSupplierId));
          if (currentSupObj) {
            currentSupplierName = currentSupObj.name;
          }
          fetchSupplierLedger(currentSupplierId);
        }

        if (directorySection && directorySection.style.display !== "none") {
          renderDirectoryCards(allSuppliers);
        }
      }
    } catch (err) {
      if (err.message !== "AUTH_REQUIRED") {
        supplierSelectCombo.innerHTML = `<option value="">Erreur de chargement des fournisseurs</option>`;
      }
    }
  }

  // ------------------------------------------------------------------
  // Fetch and Render French Supplier Ledger
  // ------------------------------------------------------------------

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
        <div>Chargement du grand livre fournisseur... / جاري تحميل كشف الحساب...</div>
      </div>
    `;

    try {
      const res = await GoldShopApp.apiFetch(`/api/v1/suppliers/${supplierId}/ledger`);
      if (res) {
        renderLedgerTable(res);
      }
    } catch (err) {
      if (err.message !== "AUTH_REQUIRED") {
        ledgerContainer.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">⚠️</div>
            <div style="font-weight: 700;">Erreur lors du chargement du grand livre fournisseur.</div>
            <div style="font-size: 13px; color: var(--text-dim); margin-top: 4px;">تعذر تحميل حساب هذا المورد حالياً.</div>
            <button class="btn-secondary-light" style="margin-top: 10px;" onclick="window.refreshCurrentPageData()">Réessayer</button>
          </div>
        `;
      }
    }
  }

  // ------------------------------------------------------------------
  // Render Ledger Table (100% French 5-column Excel Format)
  // ------------------------------------------------------------------

  function renderLedgerTable(res) {
    if (!ledgerContainer) return;

    const { rows, summary, supplier } = extractLedgerData(res);

    // Compute running totals across rows
    let computedPoids = 0.0;
    let computedMontant = 0.0;

    rows.forEach(r => {
      const p = r.poids !== undefined ? Number(r.poids) : (r.signed_weight_g !== undefined ? Number(r.signed_weight_g) : 0);
      const m = r.montant !== undefined ? Number(r.montant) : (r.signed_amount_da !== undefined ? Number(r.signed_amount_da) : 0);
      computedPoids += p;
      computedMontant += m;
    });

    const poidsNetVal = (summary && (summary.poids_net !== undefined ? Number(summary.poids_net) : (summary.total_poids_net !== undefined ? Number(summary.total_poids_net) : null))) ?? computedPoids;
    const soldeDaVal = (summary && (summary.solde_da !== undefined ? Number(summary.solde_da) : (summary.total_solde_da !== undefined ? Number(summary.total_solde_da) : null))) ?? computedMontant;

    // Update Header Card Title and Badges
    const finalSupplierName = (supplier && supplier.name) || currentSupplierName || (currentSupplierId ? `Fournisseur N° ${currentSupplierId}` : "Fournisseur");
    if (headerTitle) {
      headerTitle.textContent = finalSupplierName;
    }
    if (headerPoidsNet) {
      headerPoidsNet.textContent = `Poids Net: ${formatPoids(poidsNetVal)}`;
    }
    if (headerSoldeDa) {
      headerSoldeDa.textContent = `Solde: ${formatMoneyDa(soldeDaVal)}`;
    }

    if (rows.length === 0) {
      ledgerContainer.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">📖</div>
          <div style="font-size: 15px; font-weight: 700;">Aucune écriture comptable pour ce fournisseur.</div>
          <div style="font-size: 13px; color: var(--text-dim); margin-top: 4px;">دفتر الأستاذ فارغ حالياً لهذا المورد.</div>
        </div>
      `;
      return;
    }

    // French Excel Table Layout:
    // Date | Poids | Afaçon | Montant | Obs / Libellé
    let html = `
      <div class="table-responsive-container" style="border: 1px solid #cbd5e1; border-radius: 8px; overflow-x: auto; background: #ffffff;">
        <table class="data-table" style="width: 100%; border-collapse: collapse; font-size: 13px;">
          <thead>
            <tr style="background-color: #0f8f83; color: #ffffff;">
              <th style="min-width: 105px; padding: 9px 8px; text-align: center;">Date</th>
              <th style="min-width: 110px; padding: 9px 8px; text-align: right;">Poids (g)</th>
              <th style="min-width: 95px; padding: 9px 8px; text-align: center;">Afaçon</th>
              <th style="min-width: 125px; padding: 9px 8px; text-align: right;">Montant (DA)</th>
              <th style="min-width: 220px; padding: 9px 12px; text-align: left;">Obs / Libellé</th>
            </tr>
          </thead>
          <tbody>
    `;

    rows.forEach((r, idx) => {
      const dateStr = formatDateDDMMYYYY(r.date || r.iso_date || r.transaction_date || r.operation_date);
      const signedWeight = r.poids !== undefined ? Number(r.poids) : (r.signed_weight_g !== undefined ? Number(r.signed_weight_g) : 0);
      const signedAmount = r.montant !== undefined ? Number(r.montant) : (r.signed_amount_da !== undefined ? Number(r.signed_amount_da) : 0);
      
      const afaconStr = String(r.afacon || (r.afacon_da ? formatNumberFR(r.afacon_da, 0) : "0"));
      const rawObs = String(r.obs || r.libelle || r.notes || r.description || "");

      // Color detection matching desktop SuppliersView
      const isRed = Boolean(r.is_red || rawObs.includes("[COLOR:RED]") || rawObs.toLowerCase().includes("régler") || rawObs.toLowerCase().includes("regler"));
      const isBlue = Boolean(r.is_blue || rawObs.toLowerCase().includes("alliage"));

      let cleanObs = rawObs.replace("[COLOR:RED]", "").trim();

      // Poids styling: Green (+), Red (-), Normal (0)
      let poidsColor = "#1e293b";
      if (signedWeight > 0.0001) poidsColor = "#16a34a";
      else if (signedWeight < -0.0001) poidsColor = "#dc2626";

      // Montant styling: Green (+), Red (-), Normal (0)
      let montantColor = "#1e293b";
      if (signedAmount > 0.01) montantColor = "#16a34a";
      else if (signedAmount < -0.01) montantColor = "#dc2626";

      // Row text color for Date, Afaçon, Obs
      let rowTextColor = "#1e293b";
      let rowBgColor = idx % 2 === 0 ? "#ffffff" : "#f8fafc";
      if (isRed) {
        rowTextColor = "#dc2626";
        rowBgColor = "#fef2f2";
      } else if (isBlue) {
        rowTextColor = "#0284c7";
        rowBgColor = "#f0f9ff";
      }

      // Format numbers
      const poidsFormatted = r.poids_formatted || formatNumberFR(signedWeight, 2);
      const montantFormatted = r.montant_formatted || formatNumberFR(signedAmount, 0);

      html += `
        <tr style="background-color: ${rowBgColor}; cursor: pointer; transition: background-color 0.15s;" onclick="selectLedgerRow(${idx}, this)">
          <td style="text-align: center; font-weight: 700; color: ${rowTextColor}; padding: 8px 10px; border-bottom: 1px solid #e2e8f0;">
            ${dateStr}
          </td>
          <td style="text-align: right; font-weight: 800; color: ${poidsColor}; padding: 8px 10px; border-bottom: 1px solid #e2e8f0;">
            ${poidsFormatted}
          </td>
          <td style="text-align: center; color: ${rowTextColor}; padding: 8px 10px; border-bottom: 1px solid #e2e8f0;">
            ${afaconStr !== "0" && afaconStr !== "0,00" ? afaconStr : "-"}
          </td>
          <td style="text-align: right; font-weight: 800; color: ${montantColor}; padding: 8px 10px; border-bottom: 1px solid #e2e8f0;">
            ${montantFormatted}
          </td>
          <td style="text-align: left; color: ${rowTextColor}; padding: 8px 12px; border-bottom: 1px solid #e2e8f0; font-size: 13px;">
            ${isRed ? `<span class="card-badge badge-danger" style="margin-right: 4px;">⚠️ Règlement</span>` : ""}
            ${isBlue ? `<span class="card-badge badge-info" style="margin-right: 4px;">✨ Alliage</span>` : ""}
            <span>${cleanObs || "-"}</span>
          </td>
        </tr>
      `;
    });

    // Embedded Totals Row Matching SuppliersView:
    // Background #e0f2fe, Text Navy #0369a1, 14px bold
    const totPoidsStr = formatNumberFR(poidsNetVal, 2);
    const totMontantStr = formatNumberFR(soldeDaVal, 0);

    html += `
          </tbody>
          <tfoot>
            <tr style="background-color: #e0f2fe; color: #0369a1; border-top: 2px solid #0284c7;">
              <td style="text-align: center; font-weight: 900; font-size: 14px; padding: 10px 8px;">
                SOLDE / TOTAL
              </td>
              <td style="text-align: right; font-weight: 900; font-size: 14px; padding: 10px 8px; color: ${poidsNetVal >= 0 ? '#0369a1' : '#dc2626'};">
                ${totPoidsStr}
              </td>
              <td style="text-align: center; font-weight: 900; padding: 10px 8px;">
                -
              </td>
              <td style="text-align: right; font-weight: 900; font-size: 14px; padding: 10px 8px; color: ${soldeDaVal >= 0 ? '#0369a1' : '#dc2626'};">
                ${totMontantStr}
              </td>
              <td style="text-align: left; font-weight: 800; font-size: 13px; padding: 10px 12px;">
                --- Solde Général --- (${rows.length} écriture${rows.length > 1 ? "s" : ""})
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    `;

    ledgerContainer.innerHTML = html;
  }

  // ------------------------------------------------------------------
  // Render Directory View (Directory Cards)
  // ------------------------------------------------------------------

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
          <div style="font-weight: 700;">Aucun fournisseur trouvé dans le répertoire.</div>
          <div style="font-size: 13px; color: var(--text-dim); margin-top: 4px;">لم يتم العثور على مورد يطابق البحث.</div>
        </div>
      `;
      return;
    }

    let html = `<div class="data-list">`;

    filtered.forEach(sup => {
      const supId = sup.id;
      const name = sup.name || "Fournisseur";
      const phone = sup.phone || "";
      const pNet = Number(sup.poids_net ?? sup.weight_balance_g ?? 0);
      const solde = Number(sup.solde_da ?? sup.money_balance_da ?? 0);
      const opsCount = sup.operations_count || 0;

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
              <span class="card-row-value gold" style="font-weight: 800;">${formatPoids(pNet)}</span>
            </div>
            <div class="card-row">
              <span class="card-row-label">Solde Compte (DA):</span>
              <span class="card-row-value ${solde < 0 ? 'danger' : 'success'}" style="font-weight: 800;">${formatMoneyDa(solde)}</span>
            </div>
            ${opsCount > 0 ? `
              <div class="card-row">
                <span class="card-row-label">Écritures au registre:</span>
                <span style="font-weight: 700; color: var(--primary);">📑 ${opsCount} opération(s)</span>
              </div>
            ` : ""}
            ${phone ? `
              <div class="card-row">
                <span class="card-row-label">Téléphone:</span>
                <span style="color: var(--text-main); font-weight: 700;">📞 ${phone}</span>
              </div>
            ` : ""}
          </div>
        </div>
      `;
    });

    html += `</div>`;
    suppliersListView.innerHTML = html;
  }

  // ------------------------------------------------------------------
  // Global View Mode & Interaction Handlers
  // ------------------------------------------------------------------

  window.switchToSupplier = function(supId) {
    currentSupplierId = supId;
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
    document.querySelectorAll(".data-table tr").forEach(r => {
      r.style.outline = "";
      r.style.boxShadow = "";
    });
    if (el) {
      el.style.outline = "2px solid #0f8f83";
      el.style.boxShadow = "inset 0 0 0 1px #0f8f83";
    }
  };

  // ------------------------------------------------------------------
  // Initialization & Event Listeners
  // ------------------------------------------------------------------

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
          loadSuppliersList(false);
        } else {
          loadSuppliersList(true);
        }
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
      loadSuppliersList(true);
    };

    loadSuppliersList(true);
  });
})();

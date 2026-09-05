/**
 * GoldShop 2.0 - Core Mobile Web Client (app.js)
 * Manages API requests, Web Authentication, Number Formatters, and Global UI interactions.
 */

const GoldShopApp = (function() {
  const STORAGE_KEY_PASS = "goldshop_web_password";
  const STORAGE_KEY_LANG = "goldshop_lang";
  const HEADER_PASS = "X-GoldShop-Password";

  let currentLanguage = document.documentElement.lang || "ar";

  function getStoredPassword() {
    return localStorage.getItem(STORAGE_KEY_PASS) || "";
  }

  function setStoredPassword(pass) {
    if (pass) {
      localStorage.setItem(STORAGE_KEY_PASS, pass);
      document.cookie = `goldshop_web_password=${encodeURIComponent(pass)}; path=/; max-age=${60 * 60 * 24 * 30}; SameSite=Lax`;
    } else {
      localStorage.removeItem(STORAGE_KEY_PASS);
      document.cookie = "goldshop_web_password=; path=/; max-age=0";
    }
  }

  async function apiFetch(url, options = {}) {
    options.headers = options.headers || {};
    const pass = getStoredPassword();
    if (pass) {
      options.headers[HEADER_PASS] = pass;
    }
    options.headers["Accept"] = "application/json";

    try {
      const response = await fetch(url, options);

      if (response.status === 401 || response.status === 503) {
        showAuthModal(response.status === 503 ? "Server Web Access not configured" : "Authentication required");
        throw new Error("AUTH_REQUIRED");
      }

      if (response.status === 429) {
        showToast("Rate limit exceeded. Please wait a moment.", "error");
        throw new Error("RATE_LIMITED");
      }

      const data = await response.json();
      return data;
    } catch (err) {
      if (err.message !== "AUTH_REQUIRED") {
        console.error("API Request Error:", err);
      }
      throw err;
    }
  }

  function formatMoney(amount) {
    const num = Number(amount) || 0;
    const formatted = num.toLocaleString("fr-DZ", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return `${formatted} DA`;
  }

  function formatWeight(grams) {
    const num = Number(grams) || 0;
    const formatted = num.toLocaleString("fr-DZ", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 3,
    });
    return `${formatted} g`;
  }

  function formatDate(isoDate) {
    if (!isoDate) return "-";
    try {
      const parts = String(isoDate).split("T")[0].split("-");
      if (parts.length === 3) {
        return `${parts[2]}/${parts[1]}/${parts[0]}`;
      }
      return isoDate;
    } catch {
      return isoDate;
    }
  }

  function showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${type === "error" ? "⚠️" : type === "success" ? "✅" : "ℹ️"}</span> <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transition = "opacity 0.3s ease";
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  function showAuthModal(message = "") {
    const modal = document.getElementById("authModal");
    const errorBox = document.getElementById("authErrorBox");
    if (!modal) return;
    if (errorBox) {
      errorBox.textContent = message || "";
      errorBox.style.display = message ? "block" : "none";
    }
    modal.classList.add("show");
  }

  function hideAuthModal() {
    const modal = document.getElementById("authModal");
    if (modal) modal.classList.remove("show");
  }

  async function handleLoginSubmit(event) {
    if (event) event.preventDefault();
    const input = document.getElementById("authPasswordInput");
    const errorBox = document.getElementById("authErrorBox");
    const password = input ? input.value.trim() : "";

    if (!password) {
      if (errorBox) {
        errorBox.textContent = "Please enter password";
        errorBox.style.display = "block";
      }
      return;
    }

    try {
      const res = await fetch("/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: password }),
      });

      const data = await res.json();
      if (data && data.success) {
        setStoredPassword(password);
        hideAuthModal();
        showToast("Connected successfully", "success");
        // Trigger data reload
        if (window.refreshCurrentPageData) {
          window.refreshCurrentPageData();
        }
      } else {
        if (errorBox) {
          errorBox.textContent = data.error || "Invalid password";
          errorBox.style.display = "block";
        }
      }
    } catch (e) {
      if (errorBox) {
        errorBox.textContent = "Connection error";
        errorBox.style.display = "block";
      }
    }
  }

  function switchLanguage(lang) {
    document.cookie = `goldshop_lang=${lang}; path=/; max-age=${60 * 60 * 24 * 365}; SameSite=Lax`;
    const url = new URL(window.location.href);
    url.searchParams.set("lang", lang);
    window.location.href = url.toString();
  }

  // Initialize event listeners
  document.addEventListener("DOMContentLoaded", () => {
    const authForm = document.getElementById("authForm");
    if (authForm) {
      authForm.addEventListener("submit", handleLoginSubmit);
    }

    const btnLock = document.getElementById("btnAuthPrompt");
    if (btnLock) {
      btnLock.addEventListener("click", () => showAuthModal());
    }

    const btnRefresh = document.getElementById("btnGlobalRefresh");
    if (btnRefresh) {
      btnRefresh.addEventListener("click", () => {
        if (window.refreshCurrentPageData) {
          btnRefresh.classList.add("spinning");
          window.refreshCurrentPageData();
          setTimeout(() => btnRefresh.classList.remove("spinning"), 600);
        } else {
          window.location.reload();
        }
      });
    }

    // Auto-check auth status silently
    apiFetch("/api/v1/auth/status")
      .then(res => {
        if (res && res.data && res.data.password_required && !res.data.authenticated) {
          showAuthModal();
        }
      })
      .catch(() => {});
  });

  return {
    apiFetch,
    getStoredPassword,
    setStoredPassword,
    formatMoney,
    formatWeight,
    formatDate,
    showToast,
    showAuthModal,
    hideAuthModal,
    switchLanguage,
  };
})();

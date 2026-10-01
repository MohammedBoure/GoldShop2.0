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
    const fromStorage = localStorage.getItem(STORAGE_KEY_PASS);
    if (fromStorage) return fromStorage;
    const match = document.cookie.match(/(?:^|;\s*)goldshop_web_password=([^;]*)/);
    if (match && match[1]) {
      try {
        return decodeURIComponent(match[1]);
      } catch {
        return match[1];
      }
    }
    return "";
  }

  function setStoredPassword(pass) {
    if (pass) {
      localStorage.setItem(STORAGE_KEY_PASS, pass);
      document.cookie = `goldshop_web_password=${encodeURIComponent(pass)}; path=/; max-age=${60 * 60 * 24 * 30}; SameSite=Lax`;
    } else {
      localStorage.removeItem(STORAGE_KEY_PASS);
      document.cookie = "goldshop_web_password=; path=/; max-age=0; SameSite=Lax";
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
        setStoredPassword("");
        let errMsg = response.status === 503
          ? (currentLanguage === "ar" ? "واجهة البيانات مقفلة. عيّن كلمة مرور الويب أولاً من إعدادات البرنامج." : "Configuration requise : mot de passe Web non configuré sur le serveur.")
          : (currentLanguage === "ar" ? "يجب إدخال كلمة المرور للوصول إلى هذه البيانات." : "Mot de passe Web obligatoire pour accéder aux données.");
        try {
          const errData = await response.json();
          if (errData && errData.error) errMsg = errData.error;
        } catch {}
        showAuthModal(errMsg, true);
        throw new Error("AUTH_REQUIRED");
      }

      if (response.status === 429) {
        showToast(currentLanguage === "ar" ? "عدد محاولات كبير. أعد المحاولة بعد بضع دقائق." : "Trop de tentatives. Veuillez patienter.", "error");
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

  function showAuthModal(message = "", imperative = true) {
    const modal = document.getElementById("authModal");
    const errorBox = document.getElementById("authErrorBox");
    const btnClose = document.getElementById("btnAuthClose") || (modal ? modal.querySelector(".btn-close") : null);
    const btnLogout = document.getElementById("btnAuthLogout");
    const input = document.getElementById("authPasswordInput");

    if (!modal) return;
    if (errorBox) {
      errorBox.textContent = message || "";
      errorBox.style.display = message ? "block" : "none";
    }

    const isAuthed = Boolean(getStoredPassword());
    if (btnClose) {
      btnClose.style.display = (imperative && !isAuthed) ? "none" : "block";
    }
    if (btnLogout) {
      btnLogout.style.display = isAuthed ? "inline-block" : "none";
    }
    if (input) {
      input.value = "";
    }

    modal.classList.add("show");
    if (input) {
      setTimeout(() => input.focus(), 120);
    }
  }

  function hideAuthModal() {
    const modal = document.getElementById("authModal");
    // If not authenticated, cannot hide imperative modal
    if (!getStoredPassword()) {
      return;
    }
    if (modal) modal.classList.remove("show");
  }

  function logout() {
    setStoredPassword("");
    const btnLock = document.getElementById("btnAuthPrompt");
    if (btnLock) {
      btnLock.title = "Non connecté / غير متصل";
      btnLock.classList.remove("authenticated");
    }
    showAuthModal(currentLanguage === "ar" ? "تم تسجيل الخروج بنجاح." : "Déconnecté. Veuillez saisir le mot de passe pour continuer.", true);
    if (window.refreshCurrentPageData) {
      window.refreshCurrentPageData();
    }
  }

  async function handleLoginSubmit(event) {
    if (event) event.preventDefault();
    const input = document.getElementById("authPasswordInput");
    const errorBox = document.getElementById("authErrorBox");
    const password = input ? input.value.trim() : "";

    if (!password) {
      if (errorBox) {
        errorBox.textContent = currentLanguage === "ar" ? "يرجى إدخال كلمة المرور" : "Veuillez saisir le mot de passe Web";
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
        const btnLock = document.getElementById("btnAuthPrompt");
        if (btnLock) {
          btnLock.title = "Connecté / متصل";
          btnLock.classList.add("authenticated");
        }
        showToast(currentLanguage === "ar" ? "تم الاتصال بنجاح" : "Connecté avec succès", "success");
        // Trigger data reload
        if (window.refreshCurrentPageData) {
          window.refreshCurrentPageData();
        }
      } else {
        if (errorBox) {
          errorBox.textContent = (data && data.error) || (currentLanguage === "ar" ? "كلمة المرور غير صحيحة" : "Mot de passe incorrect");
          errorBox.style.display = "block";
        }
      }
    } catch (e) {
      if (errorBox) {
        errorBox.textContent = currentLanguage === "ar" ? "خطأ في الاتصال بالخادم" : "Erreur de connexion au serveur";
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

    const btnLogout = document.getElementById("btnAuthLogout");
    if (btnLogout) {
      btnLogout.addEventListener("click", logout);
    }

    const btnLock = document.getElementById("btnAuthPrompt");
    if (btnLock) {
      btnLock.addEventListener("click", () => {
        const isAuthed = Boolean(getStoredPassword());
        showAuthModal("", !isAuthed);
      });
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

    // Imperative password check on page load:
    const pass = getStoredPassword();
    if (!pass) {
      // Must prompt password imperatively
      showAuthModal("", true);
    } else {
      // Verify stored password with the server
      fetch("/api/v1/auth/status", {
        headers: { [HEADER_PASS]: pass, "Accept": "application/json" }
      })
        .then(r => r.json())
        .then(res => {
          if (res && res.data && res.data.authenticated) {
            const btnLock = document.getElementById("btnAuthPrompt");
            if (btnLock) {
              btnLock.title = "Connecté / متصل";
              btnLock.classList.add("authenticated");
            }
          } else {
            setStoredPassword("");
            showAuthModal(currentLanguage === "ar" ? "انتهت صلاحية الجلسة، أدخل كلمة المرور مجدداً." : "Session expirée ou mot de passe invalide. Veuillez vous reconnecter.", true);
          }
        })
        .catch(() => {});
    }
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
    logout,
    switchLanguage,
  };
})();

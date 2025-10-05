function formatPrice(price) {
  const numericPrice = typeof price === 'number' ? price : parseFloat(price) || 0;
  return new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: 'COP',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0
  }).format(numericPrice);
}

// API Configuration - Replace with your actual endpoints
const API_CONFIG = {
  baseURL: "http://localhost:8000/api", // Cambia si tu backend está en otra URL
  endpoints: {
    login: "/auth/login",
    payment: "/payments/process",
    validateCard: "/payments/validate-card",
    getOrderSummary: "/orders/summary",
  },
}

class FormHandler {
  constructor(orderManager) {
    this.orderManager = orderManager;
    this.setupCardFormatting()
    const paymentForm = document.getElementById("paymentForm")
    const loginForm = document.getElementById("loginForm")
    const applePayBtn = document.getElementById("applePayBtn")
    const closeModal = document.getElementById("closeModal")

    if (paymentForm) paymentForm.addEventListener("submit", this.handlePaymentSubmit.bind(this))
    if (loginForm) loginForm.addEventListener("submit", this.handleLoginSubmit.bind(this))
    if (applePayBtn) applePayBtn.addEventListener("click", this.handleApplePayClick.bind(this))
    if (closeModal) closeModal.addEventListener("click", this.closeLoginModal.bind(this))

    const forgotPassword = document.getElementById("forgotPassword")
    const createAccount = document.getElementById("createAccount")
    if (forgotPassword) forgotPassword.addEventListener("click", this.handleForgotPassword.bind(this))
    if (createAccount) createAccount.addEventListener("click", this.handleCreateAccount.bind(this))
  }

  setupCardFormatting() {
    const cardNumberInput = document.getElementById("cardNumber")
    const expiryDateInput = document.getElementById("expiryDate")
    const cvvInput = document.getElementById("cvv")

    if (cardNumberInput) {
      cardNumberInput.addEventListener("input", (e) => {
        const value = e.target.value.replace(/\s/g, "").replace(/[^0-9]/gi, "")
        const formattedValue = value.match(/.{1,4}/g)?.join(" ") || value
        e.target.value = formattedValue
      })
    }

    if (expiryDateInput) {
      expiryDateInput.addEventListener("input", (e) => {
        let value = e.target.value.replace(/\D/g, "")
        if (value.length > 4) value = value.slice(0, 4)
        if (value.length >= 3) {
          value = value.substring(0, 2) + "/" + value.substring(2, 4)
        }
        e.target.value = value
      })
    }

    if (cvvInput) {
      cvvInput.addEventListener("input", (e) => {
        e.target.value = e.target.value.replace(/[^0-9]/g, "")
      })
    }
  }

  async processPayment(paymentData) {
    try {
      const response = await fetch(`${API_CONFIG.baseURL}/payments/create-intent`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.getAuthToken()}`
        },
        body: JSON.stringify({
          amount: paymentData.amount,
          currency: paymentData.currency,
          cart: this.orderManager.items || []
        })
      })
      const data = await response.json()
      if (!response.ok) {
        return { success: false, error: data.detail || "Error al crear el intento de pago" }
      }
      return { success: true, clientSecret: data.clientSecret, message: 'PaymentIntent creado. Integra Stripe.js aquí.' }
    } catch (error) {
      console.error("Payment processing error:", error)
      return { success: false, error: "Error de conexión con el servidor" }
    }
  }

  async authenticateUser(loginData) {
    try {
      const response = await fetch(`${API_CONFIG.baseURL}${API_CONFIG.endpoints.login}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(loginData)
      })

      const data = await response.json()
      if (!response.ok) {
        return { success: false, error: data.detail || "Credenciales inválidas" }
      }
      if (data.token) {
        this.setAuthToken(data.token)
        return { success: true, user: data.user, token: data.token }
      }
      return { success: false, error: "Respuesta inválida del servidor" }
    } catch (error) {
      console.error("Login error:", error)
      return { success: false, error: "Error de conexión con el servidor" }
    }
  }

  async handlePaymentSubmit(e) {
    e.preventDefault()
    const paymentForm = document.getElementById("paymentForm")
    const payButton = document.getElementById("payButton") || document.getElementById("payButtonModal")
    if (!paymentForm) return

    const formData = new FormData(paymentForm)
    const paymentData = {
      email: formData.get("email"),
      cardNumber: formData.get("cardNumber")?.replace(/\s/g, ""),
      expiryDate: formData.get("expiryDate")?.replace(/\s/g, ""),
      cvv: formData.get("cvv"),
      cardholderName: formData.get("cardholderName"),
      country: formData.get("country"),
      amount: this.orderManager.total,
      currency: "COP",
    }

    try {
      this.setLoadingState(payButton, true)
      const response = await this.processPayment(paymentData)
      if (response.success) {
        this.showSuccessMessage("¡Pago procesado exitosamente!")
        setTimeout(() => {
          window.location.href = "/success"
        }, 2000)
      } else {
        this.showErrorMessage(response.error || "Error al procesar el pago")
      }
    } catch (error) {
      console.error("Payment error:", error)
      this.showErrorMessage("Error de conexión. Por favor, intenta nuevamente.")
    } finally {
      this.setLoadingState(payButton, false)
    }
  }

  async handleLoginSubmit(e) {
    e.preventDefault()
    const loginForm = document.getElementById("loginForm")
    if (!loginForm) return

    const formData = new FormData(loginForm)
    const loginData = {
      email: formData.get("loginEmail"),
      password: formData.get("loginPassword"),
    }

    try {
      this.setLoadingState(document.querySelector(".login-button"), true)
      const response = await this.authenticateUser(loginData)
      if (response.success) {
        this.showSuccessMessage("¡Inicio de sesión exitoso!")
        this.closeLoginModal()
        this.updateUIForLoggedInUser(response.user)
      } else {
        this.showErrorMessage(response.error || "Credenciales inválidas")
      }
    } catch (error) {
      console.error("Login error:", error)
      this.showErrorMessage("Error de conexión. Por favor, intenta nuevamente.")
    } finally {
      this.setLoadingState(document.querySelector(".login-button"), false)
    }
  }

  handleApplePayClick() {
    const ApplePaySession = window.ApplePaySession
    if (ApplePaySession && ApplePaySession.canMakePayments()) {
      this.initiateApplePay()
    } else {
      this.showErrorMessage("Apple Pay no está disponible en este dispositivo")
    }
  }

  handleForgotPassword(e) {
    e.preventDefault()
    alert("Funcionalidad de recuperación de contraseña - Implementar con API")
  }

  handleCreateAccount(e) {
    e.preventDefault()
    alert("Funcionalidad de crear cuenta - Implementar con API")
  }

  initiateApplePay() {
    console.log("Initiating Apple Pay...")
    // Implement actual Apple Pay integration here
  }

  setLoadingState(button, isLoading) {
    if (!button) return
    if (isLoading) {
      button.disabled = true
      button.innerHTML = '<span class="spinner"></span> Procesando...'
    } else {
      button.disabled = false
      button.innerHTML =
        button.id === "payButton"
          ? `Pagar ${document.getElementById("payButtonAmount")?.textContent || ""}`
          : "Iniciar Sesión"
    }
  }

  showSuccessMessage(message) {
    this.showNotification(message, "success")
  }

  showErrorMessage(message) {
    this.showNotification(message, "error")
  }

  showNotification(message, type) {
    const notification = document.createElement("div")
    notification.className = `notification ${type}`
    notification.textContent = message
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      padding: 12px 20px;
      border-radius: 6px;
      color: white;
      font-weight: 500;
      z-index: 1001;
      background: ${type === "success" ? "#10b981" : "#ef4444"};
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    `
    document.body.appendChild(notification)
    setTimeout(() => {
      notification.remove()
    }, 5000)
  }

  closeLoginModal() {
    const loginModal = document.getElementById("loginModal")
    if (loginModal) loginModal.style.display = "none"
  }

  openLoginModal() {
    const loginModal = document.getElementById("loginModal")
    if (loginModal) loginModal.style.display = "block"
  }

  updateUIForLoggedInUser(user) {
    console.log("User logged in:", user)
    // Implement UI updates for logged-in user
  }

  getAuthToken() {
    return localStorage.getItem("farmachelo_auth_token")
  }

  setAuthToken(token) {
    localStorage.setItem("farmachelo_auth_token", token)
  }
}

class OrderManager {
  constructor() {
    this.items = [];
    this.total = 0;
    window.addEventListener('focus', () => this.loadOrderData());
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) this.loadOrderData();
    });
    this.loadOrderData();
  }

  async loadOrderData() {
    try {
      const cartRaw = localStorage.getItem('cart');
      let cart = null;
      
      if (cartRaw) {
        try {
          cart = JSON.parse(cartRaw);
        } catch (e) { 
          console.error("Error parsing cart:", e);
          cart = null;
        }
      }
      
      if (cart && Array.isArray(cart.items)) {
        this.items = cart.items.map(item => ({
          name: item.name || 'Producto',
          quantity: item.quantity || 1,
          price: item.price || 0
        }));
        
        if (cart.total) {
          this.total = cart.total;
          this.updateTotalDisplay(this.total);
        } else {
          this.calculateTotal();
        }
        
        this.updateOrderDisplay();
      } else {
        this.calculateTotal();
      }
    } catch (error) {
      console.error("Error loading order data:", error);
      this.calculateTotal();
    }
  }

  updateTotalDisplay(total) {
    const totalAmount = document.getElementById("totalAmount");
    const payButtonAmount = document.getElementById("payButtonAmount");
    const formattedTotal = formatPrice(total);
    
    if (totalAmount) totalAmount.textContent = formattedTotal;
    if (payButtonAmount) payButtonAmount.textContent = formattedTotal;
  }

  calculateTotal() {
    this.total = this.items.reduce((acc, item) => acc + (item.price * item.quantity), 0);
    this.updateTotalDisplay(this.total);
  }

  addItem(item) {
    this.items.push(item)
    this.updateOrderDisplay()
  }

  removeItem(itemId) {
    this.items = this.items.filter((item) => item.id !== itemId)
    this.updateOrderDisplay()
  }

  updateOrderDisplay() {
    const itemsList = document.getElementById("itemsList")
    if (!itemsList) return
    itemsList.innerHTML = ""
    if (this.items.length === 0) {
      const li = document.createElement("li")
      li.textContent = "No hay productos en el carrito."
      li.style.opacity = "0.7"
      itemsList.appendChild(li)
    } else {
      this.items.forEach(item => {
        const li = document.createElement("li")
        li.textContent = `${item.name} x${item.quantity} - ${formatPrice(item.price * item.quantity)}`
        itemsList.appendChild(li)
      })
    }
    this.calculateTotal()
  }
}

// Inicialización
document.addEventListener("DOMContentLoaded", async () => {
  const orderManager = new OrderManager()
  const formHandler = new FormHandler(orderManager)

  const payBtn = document.getElementById("payButton")
  if (payBtn) {
    payBtn.addEventListener("click", (e) => {
      if (!formHandler.getAuthToken()) {
        formHandler.openLoginModal()
        return
      }
      const paymentModal = document.getElementById("paymentModal")
      if (paymentModal) {
        paymentModal.style.display = "block"
      }
    })
  }
})

if (typeof module !== "undefined" && module.exports) {
  module.exports = { FormHandler, OrderManager, API_CONFIG }
}
// cart.js - FIXED VERSION
document.addEventListener("DOMContentLoaded", () => {
  console.log("DOMContentLoaded: Cart initializing...");

  class CartManager {
    constructor() {
      this.cartCountEl = document.getElementById("cartCount");
      this.cartSidebar = document.getElementById("cartSidebar");
      this.cartOverlay = document.getElementById("cartOverlay");
      this.cartIcon = document.getElementById("cartIcon");
      this.isProcessing = false;

      if (!this.cartSidebar || !this.cartOverlay) {
        console.error("CartManager: Required elements missing");
        return;
      }

      this.init();
    }

    init() {
      this.attachEventListeners();
      this.updateCartDisplay();
      
      // 🔥 FIX: Handle browser back/forward navigation (bfcache)
      window.addEventListener('pageshow', (event) => {
        if (event.persisted || performance.getEntriesByType("navigation")[0]?.type === 'back_forward') {
          console.log('Page loaded from cache, forcing cart refresh...');
          setTimeout(() => this.updateCartDisplay(), 150);
        }
      });
      
      // 🔥 FIX: Refresh cart when page becomes visible again
      document.addEventListener('visibilitychange', () => {
        if (!document.hidden) {
          console.log('Page became visible, refreshing cart...');
          this.updateCartDisplay();
        }
      });

      console.log("CartManager: Fully initialized");
    }

    attachEventListeners() {
      // Cart icon toggle
      if (this.cartIcon) {
        this.cartIcon.addEventListener("click", () => this.openCart());
      }

      // Close button
      const closeBtn = document.getElementById("closeCartBtn");
      if (closeBtn) {
        closeBtn.addEventListener("click", () => this.closeCart());
      }

      // Overlay click to close
      this.cartOverlay.addEventListener("click", () => this.closeCart());

      // Add to cart buttons (event delegation)
      document.addEventListener("click", (e) => {
        if (e.target.classList.contains("add-to-cart-btn")) {
          e.preventDefault();
          e.stopPropagation();

          const btn = e.target;
          
          // 🔥 FIX: Read quantity from page if available (book detail page)
          const qtyDisplay = document.getElementById("qty-display");
          const quantity = qtyDisplay ? parseInt(qtyDisplay.textContent) || 1 : 1;
          
          this.addToCart({
            id: btn.dataset.id,
            type: btn.dataset.type,
            title: btn.dataset.title,
            price: btn.dataset.price,
            image: btn.dataset.image,
            quantity: quantity  // 🔥 ADD THIS LINE
          });
        }
      });

      // 🔥 FIX: Checkout button - Redirect to checkout page (NOT direct payment)
      const checkoutBtn = document.querySelector(".checkout-btn");
      if (checkoutBtn) {
        checkoutBtn.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();
          console.log('🔄 Redirecting to checkout page...');
          window.location.href = '/checkout/';
        });
      }
    }

    async addToCart(product) {
      console.log("CartManager.addToCart called with:", product);

      if (this.isProcessing) {
        console.warn("CartManager: Already processing a request");
        return;
      }

      this.isProcessing = true;
      const btn = document.querySelector(`[data-id="${product.id}"][data-type="${product.type}"]`);

      try {
        // Show loading state
        if (btn) {
          btn.disabled = true;
          btn.textContent = 'Adding...';
        }

        const csrfToken = this.getCSRFToken();
        const response = await fetch("/cart/add/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify(product),
        });

        const data = await response.json();
        console.log("Add to cart response:", data);

        if (data.success) {
          await this.updateCartDisplay();
          this.showNotification("Added to cart!");

          // Auto-open cart sidebar after adding
          setTimeout(() => {
            this.openCart();
          }, 300);
        } else {
          console.error("Add to cart failed:", data.error);
          alert("Failed to add to cart: " + data.error);
        }
      } catch (error) {
        console.error("Cart add error:", error);
        alert("Network error: " + error.message);
      } finally {
        this.isProcessing = false;
        if (btn) {
          btn.disabled = false;
          btn.textContent = 'Add to cart';
        }
      }
    }

    async removeFromCart(key) {
      if (this.isProcessing) return;
      this.isProcessing = true;

      try {
        const csrfToken = this.getCSRFToken();
        const response = await fetch("/cart/remove/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({ key }),
        });

        const data = await response.json();
        if (data.success) {
          await this.updateCartDisplay();
          this.showNotification("Item removed");
        } else {
          alert("Failed to remove: " + data.error);
        }
      } catch (error) {
        console.error("Remove error:", error);
        alert("Network error: " + error.message);
      } finally {
        this.isProcessing = false;
      }
    }

    async updateQuantity(key, quantity) {
      if (this.isProcessing) return;
      this.isProcessing = true;

      quantity = parseInt(quantity);
      if (isNaN(quantity) || quantity < 1) quantity = 1;

      try {
        const csrfToken = this.getCSRFToken();
        const response = await fetch("/cart/update/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrfToken,
          },
          body: JSON.stringify({ key, quantity }),
        });

        const data = await response.json();
        if (data.success) {
          await this.updateCartDisplay();
        } else {
          alert("Update failed: " + data.error);
        }
      } catch (error) {
        console.error("Update error:", error);
        alert("Network error: " + error.message);
      } finally {
        this.isProcessing = false;
      }
    }

    async updateCartDisplay() {
      try {
        console.log('📡 Fetching cart items from /cart/items/...');
        const response = await fetch("/cart/items/");
        
        if (!response.ok) {
          console.error(`HTTP error! status: ${response.status}`);
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log("📦 Cart data received:", data);

        // Support both cart_count and cartcount from backend
        const count = data.cart_count ?? data.cartcount ?? 0;

        if (this.cartCountEl) {
          if (count > 0) {
            this.cartCountEl.textContent = count;
            this.cartCountEl.style.display = "flex";
          } else {
            this.cartCountEl.style.display = "none";
          }
        }

        const badge = document.getElementById("cartCountBadge");
        if (badge) {
          if (count > 0) {
            badge.textContent = count;
            badge.style.display = "flex";
          } else {
            badge.style.display = "none";
          }
        }

        this.renderCartItems(
          data.items || [],
          data.total || 0,
          data.discount || 0,
          data.shipping || 0,
          data.addon_total || 0
        );
      } catch (error) {
        console.error("❌ Display error:", error);
        this.showNotification("Error loading cart", "error");
      }
    }

    renderCartItems(items, total, discount, shipping, addon_total) {
      const container = document.getElementById("cartItems");
      const footer = document.getElementById("cartFooter");

      if (!container) {
        console.error("Cart items container not found");
        return;
      }

      if (items.length === 0) {
        container.innerHTML = '<p class="empty-cart">Your cart is empty</p>';
        if (footer) footer.style.display = "none";
        return;
      }

      container.innerHTML = items
        .map(
          (item) => `
        <div class="cart-item" data-cart-key="${item.type}_${item.id}">
          <img src="${item.image}" alt="${
            item.title
          }" onerror="this.src='/static/images/placeholder.png'; this.onerror=null;">
          <div class="cart-item-details">
            <div class="cart-item-title">${item.title}</div>
            <div class="cart-item-price">₹${parseFloat(item.price).toFixed(
              2
            )}</div>
            <div class="cart-item-controls">
              <button class="quantity-btn" onclick="cartManager.updateQuantity('${
                item.type
              }_${item.id}', ${item.quantity - 1})">-</button>
              <input type="number" class="quantity-input" value="${
                item.quantity
              }" min="1" 
                     onchange="cartManager.updateQuantity('${item.type}_${
            item.id
          }', parseInt(this.value) || 1)">
              <button class="quantity-btn" onclick="cartManager.updateQuantity('${
                item.type
              }_${item.id}', ${item.quantity + 1})">+</button>
              <span class="remove-item" onclick="cartManager.removeFromCart('${
                item.type
              }_${item.id}')" 
                    style="cursor: pointer; color: #dc3545; margin-left: 8px;" title="Remove item">
                <i class="fas fa-trash"></i>
              </span>
            </div>
          </div>
        </div>
      `
        )
        .join("");

      // Add addons section
      const addonsContainer = document.createElement("div");
      addonsContainer.className = "reader-essentials";
      addonsContainer.innerHTML = `
        <h4 style="margin: 15px 0 10px; font-size: 14px; font-weight: 600;">Reader Essentials</h4>
        <div style="display: flex; flex-direction: column; gap: 12px;">
          <label style="display: flex; align-items: center; gap: 10px; font-size: 13px; cursor: pointer;">
            <input type="checkbox" class="addon-checkbox" data-addon="Bag" data-price="30">
            <img src="/static/images/todebag.jpg" alt="Bag" style="width: 40px; height: 40px; object-fit: cover; border-radius: 4px; border: 1px solid #ddd;">
            <span style="font-weight: 500;">Bag - ₹30</span>
          </label>
          <label style="display: flex; align-items: center; gap: 10px; font-size: 13px; cursor: pointer;">
            <input type="checkbox" class="addon-checkbox" data-addon="bookmark" data-price="20">
            <img src="/static/images/book_mark.jpg" alt="Bookmark" style="width: 40px; height: 40px; object-fit: cover; border-radius: 4px; border: 1px solid #ddd;">
            <span style="font-weight: 500;">Bookmark - ₹20</span>
          </label>
          <label style="display: flex; align-items: center; gap: 10px; font-size: 13px; cursor: pointer;">
            <input type="checkbox" class="addon-checkbox" data-addon="packing" data-price="20">
            <img src="/static/images/giftwrap.webp" alt="Packing" style="width: 40px; height: 40px; object-fit: cover; border-radius: 4px; border: 1px solid #ddd;">
            <span style="font-weight: 500;">Gift Wrap - ₹20</span>
          </label>
        </div>
      `;
      container.appendChild(addonsContainer);

      this.loadAddons();

      if (footer) {
        footer.style.display = "block";
        const cartTotalEl = document.getElementById("cartTotal");
        if (cartTotalEl) {
          cartTotalEl.textContent = `₹${parseFloat(total).toFixed(2)}`;
        }
      }
    }

    async loadAddons() {
      try {
        const response = await fetch("/cart/addons/get/");
        if (!response.ok)
          throw new Error(`HTTP error! status: ${response.status}`);

        const data = await response.json();

        document.querySelectorAll(".addon-checkbox").forEach((checkbox) => {
          const addon = checkbox.dataset.addon;
          checkbox.checked = data.addons[addon] || false;
          checkbox.replaceWith(checkbox.cloneNode(true));
        });

        document.querySelectorAll(".addon-checkbox").forEach((checkbox) => {
          checkbox.addEventListener("change", () => this.updateAddons());
        });
      } catch (error) {
        console.error("Load addons error:", error);
      }
    }

    async updateAddons() {
      try {
        const addons = {};
        document.querySelectorAll(".addon-checkbox").forEach((checkbox) => {
          addons[checkbox.dataset.addon] = checkbox.checked;
        });

        const response = await fetch("/cart/addons/update/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": this.getCSRFToken(),
          },
          body: JSON.stringify({ addons }),
        });

        const data = await response.json();

        if (data.success) {
          await this.updateCartDisplay();
        } else {
          console.error("Update addons failed:", data.error);
        }
      } catch (error) {
        console.error("Update addons error:", error);
      }
    }

    openCart() {
      this.cartSidebar.classList.add("active");
      this.cartOverlay.classList.add("active");
      document.body.style.overflow = "hidden";
    }

    closeCart() {
      this.cartSidebar?.classList.remove("active");
      this.cartOverlay?.classList.remove("active");
      document.body.style.overflow = "";
    }

    showNotification(message, type = "success") {
      const notification = document.createElement("div");
      notification.textContent = message;
      const bgColor = type === "error" ? "#f44336" : "#4CAF50";
      notification.style.cssText = `
        position: fixed; top: 20px; right: 20px; background: ${bgColor}; color: white;
        padding: 14px 24px; border-radius: 8px; z-index: 10000; font-weight: 500;
        transform: translateX(400px); transition: transform 0.3s ease; box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      `;
      document.body.appendChild(notification);
      setTimeout(() => (notification.style.transform = "translateX(0)"), 100);
      setTimeout(() => {
        notification.style.transform = "translateX(400px)";
        setTimeout(() => document.body.removeChild(notification), 300);
      }, 3000);
    }

    getCSRFToken() {
      const metaTag = document.querySelector('meta[name="csrf-token"]');
      if (metaTag) {
        console.log("CSRF Token from meta tag:", metaTag.content);
        return metaTag.content;
      }

      const cookie = document.cookie.match(/csrftoken=([\w-]+)/);
      if (cookie) {
        console.log("CSRF Token from cookie:", cookie[1]);
        return cookie[1];
      }

      console.warn("⚠️ CSRF token not found in meta tag or cookie!");
      return "";
    }
  }

  window.cartManager = new CartManager();
});
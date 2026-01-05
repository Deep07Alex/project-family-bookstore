// checkout.js - PRODUCTION READY
document.addEventListener("DOMContentLoaded", function () {
  // Check if checkout is locked
  async function checkCheckoutLock() {
    try {
      const response = await fetch("/api/check-checkout-lock/");
      const data = await response.json();

      if (data.locked) {
        const overlay = document.getElementById("checkoutOverlay");
        const overlayText = document.getElementById("checkoutOverlayText");
        if (overlay && overlayText) {
          overlayText.textContent = "A payment is already in progress. Please complete it or wait a few minutes...";
          overlay.classList.remove("hidden");
        }
        setTimeout(() => window.location.href = "/", 5000);
        return true;
      }
    } catch (error) {
      console.error("Lock check failed:", error);
    }
    return false;
  }

  checkCheckoutLock();

  // DOM References
  const emailInput = document.getElementById("emailInput");
  const pincodeInput = document.getElementById("pincode");
  const shippingOptions = document.getElementById("shippingOptions");
  const shippingLoading = document.getElementById("shippingLoading");
  const shippingError = document.getElementById("shippingError");
  const errorMessage = document.getElementById("errorMessage");
  const proceedToPaymentBtn = document.getElementById("proceedToPaymentBtn");
  const orderSummary = document.getElementById("orderSummary");
  const paymentRadios = document.querySelectorAll('input[name="paymentMethod"]');
  const payButtonText = document.getElementById("payButtonText");
  const summaryPaymentMethod = document.getElementById("summaryPaymentMethod");
  const checkoutOverlay = document.getElementById("checkoutOverlay");
  const checkoutOverlayText = document.getElementById("checkoutOverlayText");

  if (!emailInput || !pincodeInput || !orderSummary) {
    return;
  }

  let selectedPaymentMethod = "payu";

  // Helper: label for summary
  function getPaymentMethodLabel(method) {
    return method === "cod" ? "Cash on Delivery" : "Online Payment (PayU)";
  }

  // Listen for payment method changes
  paymentRadios.forEach((radio) => {
    radio.addEventListener("change", function () {
      if (this.checked) {
        selectedPaymentMethod = this.value;
        summaryPaymentMethod.textContent = getPaymentMethodLabel(selectedPaymentMethod);
        updateTotalAmount();
      }
    });
  });

  // Load order summary immediately
  loadOrderSummary();

  // Pincode blur event for shipping calculation
  pincodeInput.addEventListener("blur", function () {
    const pincode = this.value.trim();
    if (pincode.length === 6) {
      calculateShipping(pincode);
    }
  });

  async function calculateShipping(pincode) {
    shippingLoading.classList.remove("hidden");
    shippingError.classList.add("hidden");
    shippingOptions.innerHTML = "";
    proceedToPaymentBtn.disabled = true;

    try {
      const response = await fetch("/api/calculate-shipping/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCSRFToken(),
        },
        body: JSON.stringify({ pincode: pincode }),
      });

      const data = await response.json();
      shippingLoading.classList.add("hidden");

      if (data.success) {
        displayShippingOptions(data.rates);
      } else {
        showShippingError(data.error);
      }
    } catch (error) {
      shippingLoading.classList.add("hidden");
      console.error("Shipping error:", error);
      showShippingError("Unable to validate shipping for this PIN code");
    }
  }

  function displayShippingOptions(rates) {
    shippingError.classList.add("hidden");
    shippingOptions.innerHTML = `
      <div class="p-4 border-2 border-gray-200 rounded-lg bg-pink-50">
        <div class="flex justify-between items-start">
          <div>
            <div class="font-semibold text-gray-800">Standard Delivery</div>
            <div class="text-sm text-gray-600 mt-1">
              Est. delivery 3–6 days (courier selected automatically).
            </div>
          </div>
        </div>
      </div>
    `;
    proceedToPaymentBtn.disabled = false;
    updateTotalAmount();
  }

  function showShippingError(message) {
    shippingError.classList.remove("hidden");
    errorMessage.textContent = message;
    proceedToPaymentBtn.disabled = false;
    updateTotalAmount();
  }

  function getDisplayShipping(subtotal, paymentMethod) {
    const subtotalNum = parseFloat(subtotal);
    if (subtotalNum >= 499) {
      return paymentMethod === "cod" ? 49 : 0;
    } else {
      return paymentMethod === "cod" ? 89 : 40;
    }
  }

  function updateTotalAmount() {
    const subtotalEl = document.getElementById("subtotal");
    const shippingEl = document.getElementById("shippingCost");
    const discountEl = document.getElementById("discount");
    const totalEl = document.getElementById("totalAmount");

    const subtotal = parseFloat(subtotalEl.textContent.replace("₹", "")) || 0;
    const discount = parseFloat(discountEl.textContent.replace("₹", "")) || 0;

    const shippingCost = getDisplayShipping(subtotal, selectedPaymentMethod);

    shippingEl.textContent = `₹${shippingCost.toFixed(2)}`;
    const total = subtotal + shippingCost - discount;
    totalEl.textContent = `₹${total.toFixed(2)}`;

    if (selectedPaymentMethod === "cod") {
      payButtonText.textContent = `Place COD Order (₹${total.toFixed(2)})`;
    } else {
      payButtonText.textContent = `Pay ₹${total.toFixed(2)} with PayU`;
    }

    summaryPaymentMethod.textContent = getPaymentMethodLabel(selectedPaymentMethod);
  }

  // Order Summary
  function loadOrderSummary() {
    fetch("/cart/items/")
      .then((response) => response.json())
      .then((data) => {
        if (data.success !== false) {
          renderOrderSummary(data);
        }
      });
  }

  function renderOrderSummary(data) {
    const summaryEl = document.getElementById("orderSummary");
    const subtotalEl = document.getElementById("subtotal");
    const shippingEl = document.getElementById("shippingCost");
    const discountEl = document.getElementById("discount");
    const totalEl = document.getElementById("totalAmount");

    if (!data.items || data.items.length === 0) {
      summaryEl.innerHTML = '<p class="text-gray-500">Cart is empty</p>';
      return;
    }

    let html = "";

    // Render add-ons first if selected
    if (data.addons) {
      const addonInfo = {
        Bag: { name: "Bag", price: 30, image: "todebag.jpg" },
        bookmark: { name: "Bookmark", price: 20, image: "book_mark.jpg" },
        packing: { name: "Gift Wrap", price: 20, image: "giftwrap.webp" },
      };

      for (const [key, selected] of Object.entries(data.addons)) {
        if (selected && addonInfo[key]) {
          const addon = addonInfo[key];
          html += `
          <div class="flex items-center space-x-3 text-sm">
            <img src="/static/images/${addon.image}" 
                 alt="${addon.name}"
                 class="w-10 h-10 object-cover rounded"
                 onerror="this.src='/static/images/placeholder.png'">
            <div class="flex-1">
              <p class="font-medium truncate">${addon.name}</p>
              <p class="text-gray-500">₹${addon.price.toFixed(2)}</p>
            </div>
          </div>
        `;
        }
      }
    }

    // Then render book items
    html += data.items
      .map(
        (item) => `
        <div class="flex items-center space-x-3 text-sm">
          <img src="${item.image}" alt="${item.title}"
               class="w-10 h-10 object-cover rounded"
               onerror="this.src='/static/images/placeholder.png'">
          <div class="flex-1">
            <p class="font-medium truncate">${item.title}</p>
            <p class="text-gray-500">
              Qty: ${item.quantity} × ₹${parseFloat(item.price).toFixed(2)}
            </p>
          </div>
        </div>
      `
      )
      .join("");

    summaryEl.innerHTML = html;

    const subtotal = parseFloat(data.total) || 0;
    const discount = parseFloat(data.discount) || 0;
    const shippingCost = getDisplayShipping(subtotal, selectedPaymentMethod);

    subtotalEl.textContent = `₹${subtotal.toFixed(2)}`;
    shippingEl.textContent = `₹${shippingCost.toFixed(2)}`;
    discountEl.textContent = `₹${discount.toFixed(2)}`;

    const total = subtotal + shippingCost - discount;
    totalEl.textContent = `₹${total.toFixed(2)}`;
  }

  // Proceed to Payment
  proceedToPaymentBtn.addEventListener("click", async function () {
    const formData = {
      fullname: document.getElementById("fullname").value,
      phone: document.getElementById("phone").value,
      email: document.getElementById("emailInput").value,
      address: document.getElementById("address").value,
      city: document.getElementById("city").value,
      state: document.getElementById("state").value,
      pincode: document.getElementById("pincode").value,
      delivery: "Standard (3-6 days)",
      payment_method: selectedPaymentMethod || "payu",
    };

    const requiredFields = ["fullname", "phone", "email", "address", "city", "state", "pincode"];
    for (let field of requiredFields) {
      if (!formData[field]) {
        alert(`Please fill ${field} field`);
        return;
      }
    }

    // Validate phone and pincode client-side (server also validates)
    const phonePattern = /^[6-9]\d{9}$/;
    if (!phonePattern.test(formData.phone)) {
      alert("Please enter a valid 10-digit mobile number");
      return;
    }

    if (formData.pincode.length !== 6 || !/^\d+$/.test(formData.pincode)) {
      alert("Please enter a valid 6-digit pincode");
      return;
    }

    proceedToPaymentBtn.disabled = true;
    payButtonText.textContent = "Processing...";

    if (selectedPaymentMethod === "cod") {
      showOverlay("Placing your order...");
    } else {
      showOverlay("Redirecting to PayU payment...");
    }

    try {
      if (selectedPaymentMethod === "cod") {
        const response = await fetch("/api/place-cod-order/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCSRFToken(),
          },
          body: JSON.stringify(formData),
        });

        const data = await response.json();

        if (data.success && data.redirect_url) {
          window.location.href = data.redirect_url;
        } else {
          hideOverlay();
          alert("COD error: " + (data.error || "Unable to place order"));
          proceedToPaymentBtn.disabled = false;
          updateTotalAmount();
        }
      } else {
        const response = await fetch("/api/initiate-payment/", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCSRFToken(),
          },
          body: JSON.stringify(formData),
        });

        const data = await response.json();

        if (data.success) {
          const form = document.createElement("form");
          form.method = "POST";
          form.action = data.payu_url;
          form.style.display = "none";

          Object.entries(data.payu_params).forEach(([key, value]) => {
            const input = document.createElement("input");
            input.type = "hidden";
            input.name = key;
            input.value = value;
            form.appendChild(input);
          });

          document.body.appendChild(form);
          form.submit();
        } else {
          hideOverlay();
          alert("Payment error: " + data.error);
          proceedToPaymentBtn.disabled = false;
          updateTotalAmount();
        }
      }
    } catch (error) {
      hideOverlay();
      alert("Network error: " + error.message);
      proceedToPaymentBtn.disabled = false;
      updateTotalAmount();
    }
  });

  // Utility Functions
  function showOverlay(message) {
    if (checkoutOverlay && checkoutOverlayText) {
      checkoutOverlayText.textContent = message;
      checkoutOverlay.classList.remove("hidden");
    }
  }

  function hideOverlay() {
    if (checkoutOverlay) {
      checkoutOverlay.classList.add("hidden");
    }
  }

  function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]')?.content ||
           document.cookie.match(/csrftoken=([\w-]+)/)?.[1] || 
           '';
  }

  // Load initial data
  loadOrderSummary();
});
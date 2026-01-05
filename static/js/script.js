// ============================================
// Hero Section Slider (FIXED - Add null checks)
// ============================================
const slides = document.getElementById("slides");
const dotsContainer = document.getElementById("pagination");

// Only run if hero slider exists on the page
if (slides && dotsContainer) {
  let currentSlide = 0;
  const totalSlides = document.querySelectorAll(".slide").length;
  let sliderInterval;

  /* create dots */
  dotsContainer.innerHTML = "";
  for (let i = 0; i < totalSlides; i++) {
    const dot = document.createElement("div");
    dot.className = "dot" + (i === 0 ? " active" : "");
    dot.onclick = () => goToSlide(i);
    dotsContainer.appendChild(dot);
  }

  function updateSlider() {
    slides.style.transform = `translateX(-${currentSlide * 100}%)`;
    document
      .querySelectorAll(".dot")
      .forEach((d, i) => d.classList.toggle("active", i === currentSlide));
  }

  function nextSlide() {
    currentSlide = (currentSlide + 1) % totalSlides;
    updateSlider();
  }

  function prevSlide() {
    currentSlide = (currentSlide - 1 + totalSlides) % totalSlides;
    updateSlider();
  }

  function goToSlide(index) {
    currentSlide = index;
    updateSlider();
    restartAutoSlide();
  }

  function startAutoSlide() {
    clearInterval(sliderInterval);
    sliderInterval = setInterval(nextSlide, 4000);
  }

  function restartAutoSlide() {
    startAutoSlide();
  }

  /* init */
  startAutoSlide();
  window.nextSlide = nextSlide;
  window.prevSlide = prevSlide;
}

// ============================================
// Advertisement Slider (FIXED - Add null check)
// ============================================
let adIndex = 0;
const adSlides = document.getElementById("adSlides");

if (adSlides) {
  const totalAds = adSlides.children.length;

  function updateAd() {
    adSlides.style.transform = `translateX(-${adIndex * 100}%)`;
  }

  function nextAd() {
    adIndex = (adIndex + 1) % totalAds;
    updateAd();
  }

  function prevAd() {
    adIndex = (adIndex - 1 + totalAds) % totalAds;
    updateAd();
  }

  /* Auto Slide */
  setInterval(nextAd, 3000);
}

// ============================================
// Live Search with Dropdown (FIXED - Add null checks & debugging)
// ============================================
document.addEventListener("DOMContentLoaded", function () {
  const searchInput = document.getElementById("searchInput");
  const searchBtn = document.getElementById("searchBtn");
  const dropdown = document.getElementById("searchDropdown");

  console.log("Search: Elements found:", { searchInput, searchBtn, dropdown });

  // Exit if elements don't exist
  if (!searchInput || !dropdown) {
    console.log("Search: Elements missing, exiting");
    return;
  }

  console.log("Search: Initializing...");

  let debounceTimer;
  let currentQuery = "";

  // Toggle search bar
  searchBtn?.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    searchInput.classList.toggle("active");
    dropdown.style.display = searchInput.classList.contains("active")
      ? "block"
      : "none";
    console.log(
      "Search: Toggle clicked, active:",
      searchInput.classList.contains("active")
    );
  });

  // Hide dropdown when clicking outside
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".search-container")) {
      dropdown.style.display = "none";
      searchInput.classList.remove("active");
    }
  });

  // Live search input
  searchInput.addEventListener("input", function () {
    clearTimeout(debounceTimer);
    currentQuery = this.value.trim();
    console.log("Search: Input changed:", currentQuery);

    if (currentQuery.length < 2) {
      dropdown.style.display = "none";
      return;
    }

    dropdown.innerHTML = '<div class="search-item loading">Searching...</div>';
    dropdown.style.display = "block";

    debounceTimer = setTimeout(() => {
      console.log("Search: Fetching results for:", currentQuery);
      fetch(`/search/suggestions/?q=${encodeURIComponent(currentQuery)}`)
        .then((response) => response.json())
        .then((data) => {
          console.log("Search: Results received:", data);
          renderDropdownResults(data.results, currentQuery);
        })
        .catch((error) => {
          dropdown.style.display = "none";
          console.error("Search error:", error);
        });
    }, 250);
  });

  function renderDropdownResults(results, query) {
    dropdown.innerHTML = "";

    if (results.length === 0) {
      dropdown.innerHTML = `
                <div class="search-item no-results">
                    <i class="fas fa-search" style="font-size: 24px; margin-bottom: 10px; color: #ddd;"></i>
                    <div>No books found for "${query}"</div>
                </div>
            `;
      dropdown.style.display = "block";
      return;
    }

    results.forEach((item) => {
      const resultDiv = document.createElement("div");
      resultDiv.className = "search-item";

      const escapeHtml = (text) => {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
      };

      const regex = new RegExp(
        `(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`,
        "gi"
      );
      const safeTitle = escapeHtml(item.title);
      const highlightedTitle = safeTitle.replace(regex, "<strong>$1</strong>");

      resultDiv.innerHTML = `
                <img src="${
                  item.image
                }" alt="" onerror="this.src='/static/images/placeholder.png'; this.onerror=null;">
                <div class="search-item-info">
                    <div class="cart-item-title">${highlightedTitle}</div>
                    <div class="cart-item-price">Rs. ${escapeHtml(
                      item.price
                    )}</div>
                    <div class="cart-item-type">${item.type}</div>
                </div>
            `;

      resultDiv.addEventListener("click", () => {
        window.location.href = item.url;
      });

      dropdown.appendChild(resultDiv);
    });

    dropdown.style.display = "block";
  }

  console.log("Search: Fully initialized");
});

// ============================================
// Header Navigation (FIXED - Add null checks)
// ============================================
document.addEventListener("DOMContentLoaded", function () {
  const links = document.querySelectorAll(".nav-links a");
  links.forEach((link) => {
    const text = link.textContent.trim();
    if (!text) return;

    if (text === "Home") {
      link.addEventListener("click", function (e) {
        e.preventDefault();
        window.location.href = "/";
      });
    } else if (text === "Product Categories") {
      link.addEventListener("click", function (e) {
        e.preventDefault();
        window.location.href = "/productcatagory/";
      });
    } else if (text === "Bulk Purchase") {
      link.addEventListener("click", function (e) {
        e.preventDefault();
        window.location.href = "/bulkpurchase/";
      });
    } else if (text === "About Us") {
      link.addEventListener("click", function (e) {
        e.preventDefault();
        window.location.href = "/aboutus/";
      });
    } else if (text === "Return & Replacement") {
      link.addEventListener("click", function (e) {
        e.preventDefault();
        window.location.href = "/return/";
      });
    } else if (text === "Contact Us") {
      link.addEventListener("click", function (e) {
        e.preventDefault();
        window.location.href = "/contactinformation/";
      });
    } else if (text === "Privacy Policy") {
      link.addEventListener("click", function (e) {
        e.preventDefault();
        window.location.href = "/privacy-policy/";
      });
    }
  });
});

// ============================================
// Footer Navigation (FIXED - Add null checks)
// ============================================
document.addEventListener("DOMContentLoaded", function () {
  const footerLinks = document.querySelectorAll(".footer-section ul li a");
  footerLinks.forEach((link) => {
    const text = link.textContent.trim();
    if (!text) return;

    if (text === "About Us") {
      link.addEventListener("click", function (e) {
        e.preventDefault();
        window.location.href = "/aboutus/";
      });
    } else if (text === "Contact Us") {
      link.addEventListener("click", function (e) {
        e.preventDefault();
        window.location.href = "/contactinformation/";
      });
    } else if (text === "Bulk Purchase") {
      link.addEventListener("click", function (e) {
        e.preventDefault();
        window.location.href = "/bulkpurchase/";
      });
    } else if (text === "Return & Replacement") {
      link.addEventListener("click", function (e) {
        e.preventDefault();
        window.location.href = "/return/";
      });
    } else if (text === "Privacy Policy") {
      link.addEventListener("click", function (e) {
        e.preventDefault();
        window.location.href = "/privacy-policy/";
      });
    }
  });
});

// ============================================
// View Buttons (FIXED - Add null check)
// ============================================
document.addEventListener("DOMContentLoaded", function () {
  document.querySelectorAll(".view-btn").forEach((button) => {
    button.addEventListener("click", function (e) {
      e.preventDefault();
      const category = this.getAttribute("data-category");
      if (category) {
        window.location.href = `/category/${category}/`;
      }
    });
  });
});

// ============================================
// Quantity Counter (FIXED - Add null check)
// ============================================
document.addEventListener("DOMContentLoaded", () => {
  const qtyDisplay = document.getElementById("qty-display");
  const plus = document.getElementById("plus");
  const minus = document.getElementById("minus");

  if (!qtyDisplay || !plus || !minus) return;

  let quantity = 1;
  plus.addEventListener("click", () => {
    quantity++;
    qtyDisplay.textContent = quantity;
  });
  minus.addEventListener("click", () => {
    if (quantity > 1) {
      quantity--;
      qtyDisplay.textContent = quantity;
    }
  });
});

// ============================================
// Pagination (FIXED - Add null checks)
// ============================================
document.addEventListener("DOMContentLoaded", function () {
  const pagination = document.querySelector(".pagination");
  if (!pagination) return;

  const prevBtn = pagination.querySelector(".prev");
  const nextBtn = pagination.querySelector(".next");
  const dots = pagination.querySelector(".dots");

  if (!prevBtn || !nextBtn || !dots) return;

  const totalPages = 42;
  let currentPage = 1;

  function renderPagination() {
    if (!pagination) return;

    pagination.querySelectorAll(".page").forEach((p) => p.remove?.());
    const beforeDots = dots;

    const pagesToShow = getPagesToShow(currentPage, totalPages);

    pagesToShow.forEach((pageNum) => {
      const a = document.createElement("a");
      a.href = "#";
      a.textContent = pageNum;
      a.classList.add("page");
      if (pageNum === currentPage) a.classList.add("active");
      beforeDots.before(a);
    });

    dots.style.display = pagesToShow.includes(totalPages) ? "none" : "inline";
    prevBtn.classList.toggle("disabled", currentPage === 1);
    nextBtn.classList.toggle("disabled", currentPage === totalPages);
  }

  function getPagesToShow(current, total) {
    if (total <= 5) return Array.from({ length: total }, (_, i) => i + 1);
    if (current <= 3) return [1, 2, 3];
    if (current >= total - 2) return [total - 2, total - 1, total];
    return [current - 1, current, current + 1];
  }

  pagination.addEventListener("click", (e) => {
    e.preventDefault();
    if (e.target.classList.contains("page")) {
      currentPage = parseInt(e.target.textContent);
      renderPagination();
    }
    if (e.target.classList.contains("next") && currentPage < totalPages) {
      currentPage++;
      renderPagination();
    }
    if (e.target.classList.contains("prev") && currentPage > 1) {
      currentPage--;
      renderPagination();
    }
  });

  renderPagination();
});

// ============================================
// Hamburger Sidebar Toggle (FIXED - Add null checks)
// ============================================
document.addEventListener("DOMContentLoaded", function () {
  const hamburger = document.getElementById("hamburger");
  const sidebar = document.getElementById("sidebar");
  const closeSidebar = document.getElementById("closeSidebar");

  if (!hamburger || !sidebar || !closeSidebar) return;

  hamburger.addEventListener("click", () => {
    sidebar.classList.add("active");
  });

  closeSidebar.addEventListener("click", () => {
    sidebar.classList.remove("active");
  });

  document.addEventListener("click", (e) => {
    if (!sidebar.contains(e.target) && !hamburger.contains(e.target)) {
      sidebar.classList.remove("active");
    }
  });
});

// ============================================
// Mobile Pagination Dots (FIXED - Add null checks)
// ============================================
document.addEventListener("DOMContentLoaded", function () {
  // Only run on mobile
  if (window.innerWidth > 768) return;

  const bookSections = document.querySelectorAll(".book-sale");

  bookSections.forEach((section) => {
    const grid = section.querySelector(".book-grid");
    const dotsContainer = section.querySelector(".pagination-dots");
    if (!grid || !dotsContainer) return;

    const cards = grid.querySelectorAll(".book-card");
    const cardCount = cards.length;

    // Generate dots
    dotsContainer.innerHTML = "";
    for (let i = 0; i < cardCount; i++) {
      const dot = document.createElement("div");
      dot.className = "dot" + (i === 0 ? " active" : "");
      dot.addEventListener("click", () => {
        cards[i].scrollIntoView({
          behavior: "smooth",
          inline: "start",
          block: "nearest",
        });
      });
      dotsContainer.appendChild(dot);
    }

    // Update dots on scroll
    grid.addEventListener("scroll", () => {
      const scrollLeft = grid.scrollLeft;
      const cardWidth = cards[0]?.offsetWidth + 12 || 0;
      const activeIndex = Math.round(scrollLeft / cardWidth);

      dotsContainer.querySelectorAll(".dot").forEach((dot, idx) => {
        dot.classList.toggle("active", idx === activeIndex);
      });
    });
  });
});

// ============================================
// Universal Load More Functionality (FIXED FOR BOTH TEMPLATES)
// ============================================
document.addEventListener("DOMContentLoaded", function () {
  const loadMoreBtn = document.getElementById("loadMoreBtn");
  const bookGrid = document.getElementById("bookGrid");

  if (!loadMoreBtn || !bookGrid) {
    console.log("Load More: Elements not found - not a category page");
    return;
  }

  let currentPage = 1;
  const categorySlug = bookGrid.dataset.categorySlug;
  
  // Detect which type of category page we're on
  const isProductCategory = window.location.pathname.includes('/productcatagory/');
  
  console.log("Load More initialized:", {
    category: categorySlug,
    isProductCategory: isProductCategory
  });

  loadMoreBtn.addEventListener("click", async function () {
    loadMoreBtn.disabled = true;
    loadMoreBtn.textContent = "Loading...";

    try {
      currentPage++;
      
      // Use correct URL for product categories
      const url = isProductCategory 
        ? `/productcatagory/${categorySlug}/load-more/?page=${currentPage}`
        : `/category/${categorySlug}/load-more/?page=${currentPage}`;
      
      console.log("Load More: Fetching URL:", url);

      const response = await fetch(url);
      const data = await response.json();

      // Handle both 'books' and 'products' keys from backend
      const books = data.books || data.products || [];
      console.log("Load More: Items extracted:", books);

      if (data.success && books.length > 0) {
        // Append new books
        books.forEach((book) => {
          const bookCard = createBookCard(book, isProductCategory);
          if (bookCard) bookGrid.appendChild(bookCard);
        });

        // Hide button when no more books
        if (!data.has_next) {
          loadMoreBtn.style.display = "none";
        }
      } else {
        loadMoreBtn.style.display = "none";
      }
    } catch (error) {
      console.error("Load more error:", error);
      loadMoreBtn.textContent = "Error loading more books";
      setTimeout(() => {
        loadMoreBtn.disabled = false;
        loadMoreBtn.textContent = "Load More Books";
      }, 2000);
    } finally {
      loadMoreBtn.disabled = false;
      if (loadMoreBtn.style.display !== "none") {
        loadMoreBtn.textContent = "Load More Books";
      }
    }
  });

  function createBookCard(book, isProductCategory = false) {
    try {
      // Create card container (matches your template structure)
      const cardDiv = document.createElement("div");
      cardDiv.className = "book-card";

      // Create link
      const link = document.createElement("a");
      link.href = isProductCategory 
        ? `/productcatagory/product/${book.slug}/`
        : `/books/${book.slug}/`;
      link.className = "book-card-link";

      const priceHtml = book.old_price
        ? `<p class="price"><span class="old">Rs. ${book.old_price}</span> Rs. ${book.price}</p>`
        : `<p class="price">Rs. ${book.price}</p>`;

      const saleTag = book.on_sale ? `<span class="sale-tag">Sale</span>` : "";

      link.innerHTML = `
        <img src="${book.image_url}" alt="${book.title}" 
             onerror="this.src='/static/images/placeholder.png'; this.onerror=null;" />
        ${saleTag}
        <h3 class="book-title">${book.title}</h3>
        ${priceHtml}
      `;

      // Create button
      const button = document.createElement("button");
      button.className = "cart-btn add-to-cart-btn";
      button.setAttribute("data-id", book.id);
      button.setAttribute("data-type", "book");
      button.setAttribute("data-title", book.title);
      button.setAttribute("data-price", book.price);
      button.setAttribute("data-image", book.image_url);
      button.textContent = "Add to cart";

      // Attach cart listener if available
      if (window.attachCartListener) {
        window.attachCartListener(button);
      }

      // Assemble card
      cardDiv.appendChild(link);
      cardDiv.appendChild(button);

      return cardDiv;
    } catch (error) {
      console.error("Error creating book card:", error);
      return null;
    }
  }
  
});

// ============================================
// Video Showcase Slider - All Autoplay
// ============================================
document.addEventListener('DOMContentLoaded', function() {
  const videoSlider = document.getElementById('videoSlider');
  const videoPagination = document.getElementById('videoPagination');
  
  if (!videoSlider || !videoPagination) return;

  const videoSlides = videoSlider.querySelectorAll('.video-slide');
  const totalVideos = videoSlides.length;
  let currentVideoIndex = 0;
  let isDown = false;
  let startX;
  let scrollLeft;

  // Create pagination dots
  videoPagination.innerHTML = '';
  for (let i = 0; i < totalVideos; i++) {
    const dot = document.createElement('div');
    dot.className = 'dot' + (i === 0 ? ' active' : '');
    dot.addEventListener('click', () => scrollToVideo(i));
    videoPagination.appendChild(dot);
  }

  // Update active dot
  function updateActiveDot() {
    const dots = videoPagination.querySelectorAll('.dot');
    dots.forEach((dot, index) => {
      dot.classList.toggle('active', index === currentVideoIndex);
    });
  }

  // Scroll to specific video
  function scrollToVideo(index) {
    if (index < 0 || index >= totalVideos) return;
    
    currentVideoIndex = index;
    const slide = videoSlides[index];
    videoSlider.scrollTo({
      left: slide.offsetLeft,
      behavior: 'smooth'
    });
    updateActiveDot();
  }

  // Navigation functions
  window.nextVideoSlide = function() {
    const nextIndex = (currentVideoIndex + 1) % totalVideos;
    scrollToVideo(nextIndex);
  };

  window.prevVideoSlide = function() {
    const prevIndex = (currentVideoIndex - 1 + totalVideos) % totalVideos;
    scrollToVideo(prevIndex);
  };

  // Auto-detect current slide on scroll
  videoSlider.addEventListener('scroll', () => {
    const scrollLeft = videoSlider.scrollLeft;
    const slideWidth = videoSlides[0].offsetWidth + 20;
    
    const nearestIndex = Math.round(scrollLeft / slideWidth);
    if (nearestIndex !== currentVideoIndex && nearestIndex < totalVideos) {
      currentVideoIndex = nearestIndex;
      updateActiveDot();
    }
  });

  // Touch/Mobile swipe support
  videoSlider.addEventListener('touchstart', (e) => {
    isDown = true;
    startX = e.touches[0].pageX - videoSlider.offsetLeft;
    scrollLeft = videoSlider.scrollLeft;
  });

  videoSlider.addEventListener('touchmove', (e) => {
    if (!isDown) return;
    e.preventDefault();
    const x = e.touches[0].pageX - videoSlider.offsetLeft;
    const walk = (x - startX) * 2;
    videoSlider.scrollLeft = scrollLeft - walk;
  });

  videoSlider.addEventListener('touchend', () => {
    isDown = false;
  });

  // ENSURE VIDEOS KEEP PLAYING - Restart if stopped
  videoSlides.forEach(slide => {
    const video = slide.querySelector('video');
    if (video) {
      // Handle autoplay policy - restart if paused by browser
      video.addEventListener('pause', () => {
        // Don't restart if user manually paused
        if (video.readyState >= 2) {
          video.play().catch(e => console.log('Autoplay prevented:', e));
        }
      });

      // Ensure loop works flawlessly
      video.addEventListener('ended', () => {
        video.currentTime = 0;
        video.play();
      });
    }
  });
});
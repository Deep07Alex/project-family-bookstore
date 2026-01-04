// Replace your book_detail.js with this:

// Quantity Controls
function increaseQty() {
    let q = document.getElementById("qty-display");
    q.innerText = parseInt(q.innerText) + 1;
}

function decreaseQty() {
    let q = document.getElementById("qty-display");
    if (parseInt(q.innerText) > 1) {
        q.innerText = parseInt(q.innerText) - 1;
    }
}

// Buy Now - Fixed with Debug Logging
document.addEventListener("DOMContentLoaded", function() {
    const buyNowBtn = document.querySelector('.buy-now');
    
    if (buyNowBtn) {
        console.log("Buy Now button found");
        
        buyNowBtn.addEventListener('click', async function(e) {
            e.preventDefault();
            
            const bookId = this.dataset.id;
            const title = this.dataset.title;
            const price = this.dataset.price;
            const image = this.dataset.image;
            const quantity = parseInt(document.getElementById("qty-display").innerText);
            
            console.log('🛒 Buy Now initiated:', { bookId, title, quantity, price, image });
            
            try {
                // Get CSRF token
                const csrfToken = window.cartManager?.getCSRFToken() || '';
                console.log('🗝️ CSRF Token:', csrfToken);
                
                if (!csrfToken) {
                    alert('CSRF token not found. Please refresh the page.');
                    return;
                }
                
                // Clear existing cart first
                console.log('🧹 Clearing cart...');
                const clearResponse = await fetch('/cart/clear/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    }
                });
                
                const clearData = await clearResponse.json();
                console.log('Cart cleared:', clearData);
                
                // Add the book
                console.log(' Adding book to cart...');
                const addResponse = await fetch('/cart/add/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify({
                        id: bookId,
                        type: 'book',
                        title: title,
                        price: price,
                        image: image
                    })
                });
                
                const addData = await addResponse.json();
                console.log(' Book added:', addData);
                
                if (!addData.success) {
                    throw new Error(addData.error || 'Failed to add book');
                }
                
                // Update quantity if needed
                if (quantity > 1) {
                    console.log('Updating quantity to', quantity);
                    const updateResponse = await fetch('/cart/update/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken
                        },
                        body: JSON.stringify({
                            key: `book_${bookId}`,
                            quantity: quantity
                        })
                    });
                    
                    const updateData = await updateResponse.json();
                    console.log('Quantity updated:', updateData);
                }
                
                // Verify cart before redirect
                const verifyResponse = await fetch('/cart/items/');
                const verifyData = await verifyResponse.json();
                console.log('🛒 Final cart contents:', verifyData);
                
                if (verifyData.cart_count === 0) {
                    throw new Error('Cart is empty after adding items!');
                }
                
                // Redirect to checkout
                console.log('🔄 Redirecting to checkout...');
                window.location.href = '/checkout/';
                
            } catch (error) {
                console.error('❌ Buy Now error:', error);
                alert('Error: ' + error.message);
            }
        });
    } else {
        console.warn("⚠️ Buy Now button not found on page");
    }
});

// Countdown Timer
let countDownDate = new Date().getTime() + 12 * 60 * 60 * 1000;
setInterval(function () {
    let now = new Date().getTime();
    let distance = countDownDate - now;

    let hrs = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    let mins = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
    let secs = Math.floor((distance % (1000 * 60)) / 1000);

    document.getElementById("hrs").innerHTML = hrs;
    document.getElementById("mins").innerHTML = mins;
    document.getElementById("secs").innerHTML = secs;

    if (distance < 0) {
        document.getElementById("countdown").innerHTML = "Expired";
    }
}, 1000);
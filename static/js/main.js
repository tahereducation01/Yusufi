// Global cart badge live update helper
// Called by cart.html after AJAX quantity changes
function updateCartBadge(count) {
  const badge = document.getElementById('cart-badge');
  if (badge) badge.textContent = count;
}

document.addEventListener('DOMContentLoaded', () => {
    // Billing Page: Dynamic Bill Items and Total Calculation
    const billItemsContainer = document.getElementById('bill-items');
    const addItemBtn = document.getElementById('add-item');
    const totalAmountSpan = document.getElementById('total-amount');

    if (billItemsContainer && addItemBtn && totalAmountSpan) {
        let itemCount = 1;
        const products = JSON.parse(billItemsContainer.dataset.products || '[]');

        function calculateTotal() {
            let total = 0;
            const items = billItemsContainer.querySelectorAll('.bill-item');
            items.forEach((item, index) => {
                const productId = item.querySelector(`#items-${index}`).value;
                const quantity = parseInt(item.querySelector(`#quantities-${index}`).value) || 0;
                const product = products.find(p => p[0] == productId);
                if (product) {
                    total += product[2] * quantity;
                }
            });
            totalAmountSpan.textContent = total.toFixed(2);
        }

        function updateRemoveButtons() {
            const items = billItemsContainer.querySelectorAll('.bill-item');
            items.forEach((item, index) => {
                const removeBtn = item.querySelector('.remove-item-btn');
                if (removeBtn) {
                    removeBtn.style.display = index === 0 && items.length === 1 ? 'none' : 'inline-block';
                }
            });
        }

        addItemBtn.addEventListener('click', () => {
            const newItem = document.createElement('div');
            newItem.classList.add('bill-item');
            newItem.innerHTML = `
                <div class="form-group">
                    <label for="items-${itemCount}">Product</label>
                    <select name="items[]" id="items-${itemCount}" required>
                        <option value="">Select Product</option>
                        ${products.map(product => `
                            <option value="${product[0]}">${product[1]} - ₹${product[2]} (Stock: ${product[3]})</option>
                        `).join('')}
                    </select>
                </div>
                <div class="form-group">
                    <label for="quantities-${itemCount}">Quantity</label>
                    <input type="number" name="quantities[]" id="quantities-${itemCount}" min="1" required>
                    <button type="button" class="remove-item-btn">Remove</button>
                </div>
            `;
            billItemsContainer.appendChild(newItem);
            itemCount++;
            updateRemoveButtons();
            calculateTotal();
        });

        billItemsContainer.addEventListener('click', (e) => {
            if (e.target.classList.contains('remove-item-btn')) {
                e.target.parentElement.parentElement.remove();
                itemCount--;
                updateRemoveButtons();
                calculateTotal();
            }
        });

        billItemsContainer.addEventListener('change', (e) => {
            if (e.target.name === 'items[]' || e.target.name === 'quantities[]') {
                calculateTotal();
            }
        });

        // Initial setup
        updateRemoveButtons();
        calculateTotal();
    }

    // Bill History Page: Collapse Functionality for Bill Details
    const collapseButtons = document.querySelectorAll('[data-toggle="collapse"]');
    collapseButtons.forEach(button => {
        button.addEventListener('click', () => {
            const targetId = button.getAttribute('data-target');
            const target = document.querySelector(targetId);
            const isExpanded = button.getAttribute('aria-expanded') === 'true';
            button.setAttribute('aria-expanded', !isExpanded);
            target.classList.toggle('collapse');
            target.classList.toggle('show');
        });
    });

    // Inventory Page: Table Sorting (Optional)
    const inventoryTable = document.querySelector('.inventory-table');
    if (inventoryTable) {
        const headers = inventoryTable.querySelectorAll('th');
        headers.forEach((header, index) => {
            header.addEventListener('click', () => {
                const rows = Array.from(inventoryTable.querySelector('tbody').rows);
                const isAscending = header.classList.toggle('asc');
                header.classList.toggle('desc', !isAscending);

                rows.sort((a, b) => {
                    const aValue = a.cells[index].textContent.trim();
                    const bValue = b.cells[index].textContent.trim();
                    if (!isNaN(aValue) && !isNaN(bValue)) {
                        return isAscending ? aValue - bValue : bValue - aValue;
                    }
                    return isAscending ? aValue.localeCompare(bValue) : bValue.localeCompare(aValue);
                });

                const tbody = inventoryTable.querySelector('tbody');
                rows.forEach(row => tbody.appendChild(row));
            });
        });
    }
});
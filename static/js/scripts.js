document.addEventListener('DOMContentLoaded', () => {
    // Dynamic billing item addition
    const addItemBtn = document.getElementById('add-item');
    if (addItemBtn) {
        addItemBtn.addEventListener('click', () => {
            const container = document.getElementById('bill-items');
            const itemDiv = document.createElement('div');
            itemDiv.className = 'bill-item';
            itemDiv.innerHTML = `
                <select name="items[]">
                    ${document.querySelector('select[name="items[]"]').innerHTML}
                </select>
                <input type="number" name="quantities[]" min="1" placeholder="Quantity" required>
            `;
            container.appendChild(itemDiv);
        });
    }
});
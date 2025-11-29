document.addEventListener('DOMContentLoaded', () => {
    const currentDateEl = document.getElementById('currentDate');
    const remainingBalanceEl = document.getElementById('remainingBalance');
    const monthlyBudgetEl = document.getElementById('monthlyBudget');
    const totalSpentEl = document.getElementById('totalSpent');
    const transactionListEl = document.getElementById('transactionList');
    const expenseForm = document.getElementById('expenseForm');

    // Modal elements
    const budgetModal = document.getElementById('budgetModal');
    const editBudgetBtn = document.getElementById('editBudgetBtn');
    const cancelBudgetBtn = document.getElementById('cancelBudgetBtn');
    const saveBudgetBtn = document.getElementById('saveBudgetBtn');
    const newBudgetInput = document.getElementById('newBudgetInput');
    const resetAppBtn = document.getElementById('resetAppBtn');

    // Set Date
    const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
    currentDateEl.textContent = new Date().toLocaleDateString('en-US', options);

    // Fetch Initial Data
    fetchBalance();
    fetchTransactions();

    // Event Listeners
    resetAppBtn.addEventListener('click', async () => {
        if (confirm('Are you sure you want to RESET ALL DATA? This cannot be undone.')) {
            try {
                await fetch('/api/reset', { method: 'DELETE' });
                location.reload();
            } catch (error) {
                console.error('Error resetting data:', error);
                alert('Failed to reset data');
            }
        }
    });

    // Event Listeners
    expenseForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const item = document.getElementById('itemInput').value;
        const quantityInput = document.getElementById('quantityInput').value;
        const quantity = quantityInput ? quantityInput : 1;
        const cost = document.getElementById('costInput').value;

        if (item && cost) {
            await addExpense(item, cost, quantity);
            expenseForm.reset();
            // Reset default quantity
            document.getElementById('quantityInput').value = 1;
            fetchBalance();
            fetchTransactions();
        }
    });

    editBudgetBtn.addEventListener('click', () => {
        budgetModal.classList.remove('hidden');
        newBudgetInput.value = monthlyBudgetEl.textContent.replace('$', '').replace(',', '');
        // Ensure normal mode
        cancelBudgetBtn.style.display = '';
        document.querySelector('#budgetModal h3').textContent = 'Set Monthly Budget';
    });

    cancelBudgetBtn.addEventListener('click', () => {
        budgetModal.classList.add('hidden');
    });

    saveBudgetBtn.addEventListener('click', async () => {
        const amount = newBudgetInput.value;
        if (amount) {
            await setBudget(amount);
            budgetModal.classList.add('hidden');
            // Restore modal state
            cancelBudgetBtn.style.display = '';
            document.querySelector('#budgetModal h3').textContent = 'Set Monthly Budget';
            fetchBalance();
        }
    });

    // API Calls
    async function fetchBalance() {
        try {
            const res = await fetch('/api/balance');
            const data = await res.json();

            updateDisplay(data);

            // If budget is 0, prompt user to set it (First time setup)
            if (data.budget === 0) {
                budgetModal.classList.remove('hidden');
                document.querySelector('#budgetModal h3').textContent = 'Enter Initial Balance';
                cancelBudgetBtn.style.display = 'none'; // Force user to enter value
                newBudgetInput.focus();
            }
        } catch (error) {
            console.error('Error fetching balance:', error);
        }
    }

    async function fetchTransactions() {
        try {
            const res = await fetch('/api/expenses');
            const data = await res.json();
            renderTransactions(data);
        } catch (error) {
            console.error('Error fetching transactions:', error);
        }
    }

    async function addExpense(item, cost, quantity) {
        try {
            await fetch('/api/expenses', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ item, cost, quantity })
            });
        } catch (error) {
            console.error('Error adding expense:', error);
        }
    }

    async function setBudget(amount) {
        try {
            await fetch('/api/budget', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ amount })
            });
        } catch (error) {
            console.error('Error setting budget:', error);
        }
    }

    // UI Updates
    function updateDisplay(data) {
        const formatCurrency = (num) => {
            return new Intl.NumberFormat('en-US', {
                style: 'currency',
                currency: 'USD'
            }).format(num);
        };

        remainingBalanceEl.textContent = formatCurrency(data.remaining);
        monthlyBudgetEl.textContent = formatCurrency(data.budget);
        totalSpentEl.textContent = formatCurrency(data.total_expenses);

        // Update Progress Bar
        const progressBar = document.getElementById('budgetProgressBar');
        if (data.budget > 0) {
            const percentage = Math.min((data.total_expenses / data.budget) * 100, 100);
            progressBar.style.width = `${percentage}%`;

            // Change color if over budget
            if (data.total_expenses > data.budget) {
                progressBar.style.backgroundColor = 'var(--danger)';
            } else {
                progressBar.style.backgroundColor = 'var(--accent)';
            }
        } else {
            progressBar.style.width = '0%';
        }
    }

    function renderTransactions(transactions) {
        transactionListEl.innerHTML = '';

        if (transactions.length === 0) {
            transactionListEl.innerHTML = '<li style="text-align:center; color:var(--text-muted); padding: 20px;">No transactions yet</li>';
            return;
        }

        transactions.forEach(t => {
            const li = document.createElement('li');
            li.className = 'transaction-item';

            // Format date: "Nov 29, 10:30 PM"
            const dateObj = new Date(t.date);
            const dateStr = dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            const timeStr = dateObj.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });

            const quantityBadge = t.quantity > 1 ? `<span class="t-qty">x${t.quantity}</span>` : '';

            li.innerHTML = `
                <div class="t-info">
                    <div class="t-header">
                        <span class="t-name">${t.item}</span>
                        ${quantityBadge}
                    </div>
                    <span class="t-date">${dateStr} at ${timeStr}</span>
                </div>
                <span class="t-amount">-$${parseFloat(t.cost).toFixed(2)}</span>
            `;
            transactionListEl.appendChild(li);
        });
    }
});

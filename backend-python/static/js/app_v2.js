        // --- 1. Router & Tab Switching System ---
        const Router = {
            routes: ['deals', 'growth', 'news', 'ipo', 'funds'],
            init() {
                const isStockAdmin = window.ProTradeConfig && window.ProTradeConfig.user && window.ProTradeConfig.user.entitlements.includes('stock_admin');
                
                if (isStockAdmin) {
                    if (!this.routes.includes('volume')) this.routes.unshift('volume');
                    if (!this.routes.includes('admin')) this.routes.push('admin');
                } else {
                    this.routes = this.routes.filter(r => r !== 'volume' && r !== 'admin');
                }

                const defaultRoute = isStockAdmin ? 'volume' : 'deals';
                let path = window.location.pathname.replace('/', '').toLowerCase();
                if (!this.routes.includes(path)) {
                    path = defaultRoute;
                }
                this.switchView(path, false);

                // Bind click events to tab elements
                document.querySelectorAll('.tab-btn').forEach(btn => {
                    btn.addEventListener('click', () => {
                        const view = btn.getAttribute('data-view');
                        this.switchView(view);
                    });
                });

                // Support browser navigation buttons
                window.addEventListener('popstate', () => {
                    let path = window.location.pathname.replace('/', '').toLowerCase();
                    if (!this.routes.includes(path)) {
                        path = defaultRoute;
                    }
                    this.switchView(path, false);
                });
            },
            switchView(viewName, updateHistory = true) {
                // Update navigation active states
                document.querySelectorAll('.tab-btn').forEach(btn => {
                    if (btn.getAttribute('data-view') === viewName) {
                        btn.classList.add('active');
                    } else {
                        btn.classList.remove('active');
                    }
                });

                // Toggle visibility of panels
                document.querySelectorAll('.view-panel').forEach(panel => {
                    panel.classList.remove('active');
                });
                document.getElementById(`view-${viewName}`).classList.add('active');

                // Update tab titles & URL paths
                if (updateHistory) {
                    const newPath = viewName === 'volume' ? '/' : `/${viewName}`;
                    history.pushState(null, '', newPath);
                }

                // Update page metadata/subtitles dynamically
                const subtitle = document.getElementById('global-subtitle');
                if (viewName === 'volume') {
                    subtitle.innerText = 'NSE Intraday Scanner (5-Min Vol vs 5-Day Avg)';
                    VolumeController.init();
                } else if (viewName === 'deals') {
                    subtitle.innerText = 'Recent Large-Volume Block and Bulk Deals';
                    DealsController.init();
                } else if (viewName === 'growth') {
                    subtitle.innerText = 'Fundamental Compounders & Institutional Purchases';
                    GrowthController.init();
                } else if (viewName === 'news') {
                    subtitle.innerText = 'Real-Time Financial Sentiment Tracker';
                    NewsController.init();
                } else if (viewName === 'admin') {
                    subtitle.innerText = 'Platform Security & Entitlements Control';
                    AdminController.init();
                } else if (viewName === 'ipo') {
                    subtitle.innerText = 'Upcoming Public Offerings & Live Subscription Status';
                    IpoController.init();
                } else if (viewName === 'funds') {
                    subtitle.innerText = 'Explore and rank top-performing Indian Mutual Funds';
                    FundsController.init();
                } else if (viewName === 'ai-assistant') {
                    subtitle.innerText = 'Token-Efficient RAG AI Copilot Assistant';
                }
            }
        };

        // --- 2. Volume Radar Controller ---
        const VolumeController = {
            initialized: false,
            isPolling: false,
            currentResults: [],
            currentPage: 1,
            itemsPerPage: 15,

            init() {
                if (this.initialized) return;
                this.initialized = true;

                this.fetchBtn = document.getElementById('fetchBtn');
                this.btnText = document.getElementById('btnText');
                this.trendFilter = document.getElementById('trendFilter');
                this.priceMoveFilter = document.getElementById('priceMoveFilter');
                this.progressSection = document.getElementById('progressSection');
                this.progressBar = document.getElementById('progressBar');
                this.statusMsg = document.getElementById('statusMsg');
                this.progressPercent = document.getElementById('progressPercent');
                this.resultsBody = document.getElementById('resultsBody');
                this.emptyState = document.getElementById('emptyState');
                this.timerText = document.getElementById('timer');
                this.paginationControls = document.getElementById('paginationControls');
                this.prevBtn = document.getElementById('prevBtn');
                this.nextBtn = document.getElementById('nextBtn');
                this.pageInfo = document.getElementById('pageInfo');

                this.fetchBtn.addEventListener('click', () => this.startAnalysis());
                
                this.prevBtn.addEventListener('click', () => {
                    if (this.currentPage > 1) {
                        this.currentPage--;
                        this.updateTableDisplay();
                        this.scrollToTable();
                    }
                });

                this.nextBtn.addEventListener('click', () => {
                    const totalPages = Math.ceil(this.currentResults.length / this.itemsPerPage);
                    if (this.currentPage < totalPages) {
                        this.currentPage++;
                        this.updateTableDisplay();
                        this.scrollToTable();
                    }
                });

                // Perform status check on load
                this.pollStatus();
            },

            async startAnalysis() {
                try {
                    const endpoint = this.priceMoveFilter.checked ? '/api/analyze_price_move' : '/api/analyze';
                    const response = await fetch(endpoint, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            trend_filter: this.trendFilter.checked
                        })
                    });

                    if (response.ok) {
                        this.toggleLoading(true);
                        this.pollStatus();
                    } else {
                        const err = await response.json();
                        alert(err.error || 'Failed to start analysis');
                    }
                } catch (err) {
                    alert('Connection Error: Is the server running?');
                }
            },

            async pollStatus() {
                if (this.isPolling) return;
                this.isPolling = true;

                const interval = setInterval(async () => {
                    try {
                        const response = await fetch('/api/status');
                        const data = await response.json();

                        this.updateUI(data);

                        if (!data.running) {
                            clearInterval(interval);
                            this.isPolling = false;
                            this.toggleLoading(false);
                        }
                    } catch (err) {
                        console.error('Polling error:', err);
                    }
                }, 1500);
            },

            toggleLoading(active) {
                this.fetchBtn.disabled = active;
                this.btnText.innerText = active ? 'Scanning Market...' : 'Fetch Latest Data';
                this.progressSection.style.display = active ? 'block' : 'none';
            },

            updateUI(data) {
                if (data.total > 0) {
                    const percent = Math.round((data.progress / data.total) * 100);
                    this.progressBar.style.width = percent + '%';
                    this.progressPercent.innerText = percent + '%';
                }
                this.statusMsg.innerText = data.message;
                this.timerText.innerText = `Elapsed: ${data.elapsed}s`;

                if (data.results) {
                    document.getElementById('statMatches').innerText = data.results.matches.length;
                    document.getElementById('statScanned').innerText = data.results.total_scanned;
                    this.renderTable(data.results);
                }
            },

            renderTable(results) {
                this.currentResults = [...results.matches];
                if (this.currentResults.length === 0) {
                    this.currentResults.push(...results.top_spikes.slice(0, 50));
                }

                if (this.currentResults.length > 0) {
                    this.emptyState.style.display = 'none';
                    this.currentPage = 1;
                    this.updateTableDisplay();
                }
            },

            updateTableDisplay() {
                const startIndex = (this.currentPage - 1) * this.itemsPerPage;
                const endIndex = startIndex + this.itemsPerPage;
                const pageData = this.currentResults.slice(startIndex, endIndex);
                const totalPages = Math.ceil(this.currentResults.length / this.itemsPerPage) || 1;

                this.resultsBody.innerHTML = pageData.map(item => `
                    <tr>
                        <td style="font-weight: 600;"><span class="symbol-badge">${item.symbol}</span></td>
                        <td>
                            <span class="ratio-tag ${this.getRatioClass(item.ratio)}">
                                ${item.ratio.toFixed(2)}x
                            </span>
                        </td>
                        <td>₹ ${(item.avg_turnover / 100000).toFixed(2)} Lakhs</td>
                        <td style="color: #94a3b8;">${item.current_vol.toLocaleString()}</td>
                    </tr>
                `).join('');

                this.paginationControls.style.display = this.currentResults.length > this.itemsPerPage ? 'flex' : 'none';
                this.pageInfo.innerText = `Page ${this.currentPage} of ${totalPages}`;
                this.prevBtn.disabled = this.currentPage === 1;
                this.nextBtn.disabled = this.currentPage === totalPages;
            },

            getRatioClass(ratio) {
                if (ratio >= 2.0) return 'ratio-high';
                if (ratio >= 1.5) return 'ratio-mid';
                return 'ratio-low';
            },

            scrollToTable() {
                window.scrollTo({ top: document.querySelector('#view-volume .card').offsetTop - 100, behavior: 'smooth' });
            }
        };

        // --- 3. Recent Deals Controller ---
        const DealsController = {
            initialized: false,
            tableData: {
                'block': { data: [], page: 1 },
                'bulk': { data: [], page: 1 }
            },
            pageSize: 15,

            init() {
                if (this.initialized) return;
                this.initialized = true;

                this.loadDeals('block');
                this.loadDeals('bulk');
            },

            formatCurrency(num) {
                if (!num) return '₹0';
                return `₹${Number(num).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
            },

            getActionBadge(action) {
                if (!action) return '';
                if (action.toUpperCase().includes('BUY')) return `<span class="buy-badge">BUY</span>`;
                if (action.toUpperCase().includes('SELL')) return `<span class="sell-badge">SELL</span>`;
                return action;
            },

            renderTable(type) {
                const tbody = document.getElementById(`${type}-body`);
                tbody.innerHTML = '';

                const state = this.tableData[type];
                const start = (state.page - 1) * this.pageSize;
                const end = start + this.pageSize;
                const paginatedData = state.data.slice(start, end);

                paginatedData.forEach(item => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td style="color:#94a3b8; font-size:0.65rem;">${item.deal_date}</td>
                        <td><span class="symbol-badge">${item.symbol}</span></td>
                        <td>${item.client_name}</td>
                        <td>${this.getActionBadge(item.buy_sell)}</td>
                        <td>${Number(item.quantity_traded).toLocaleString('en-IN')}</td>
                        <td>${this.formatCurrency(item.trade_price)}</td>
                    `;
                    tbody.appendChild(tr);
                });

                const totalPages = Math.ceil(state.data.length / this.pageSize) || 1;
                const pageInfo = document.getElementById(`${type}-page-info`);
                pageInfo.innerHTML = '';

                let startPage = Math.max(1, state.page - 2);
                let endPage = Math.min(totalPages, state.page + 2);

                if (startPage > 1) {
                    pageInfo.innerHTML += `<button onclick="DealsController.jumpPage('${type}', 1)">1</button>`;
                    if (startPage > 2) pageInfo.innerHTML += `<span style="color:#94a3b8">...</span>`;
                }

                for (let i = startPage; i <= endPage; i++) {
                    const activeClass = i === state.page ? 'active' : '';
                    pageInfo.innerHTML += `<button class="${activeClass}" onclick="DealsController.jumpPage('${type}', ${i})">${i}</button>`;
                }

                if (endPage < totalPages) {
                    if (endPage < totalPages - 1) pageInfo.innerHTML += `<span style="color:#94a3b8">...</span>`;
                    pageInfo.innerHTML += `<button onclick="DealsController.jumpPage('${type}', ${totalPages})">${totalPages}</button>`;
                }

                document.getElementById(`${type}-prev`).disabled = state.page === 1;
                document.getElementById(`${type}-next`).disabled = state.page >= totalPages;
            },

            jumpPage(type, pageNum) {
                this.tableData[type].page = pageNum;
                this.renderTable(type);
            },

            changePage(type, dir) {
                this.tableData[type].page += dir;
                this.renderTable(type);
            },

            filterTimeout: null,
            handleFilterChange() {
                clearTimeout(this.filterTimeout);
                this.filterTimeout = setTimeout(() => {
                    this.loadDeals('block');
                    this.loadDeals('bulk');
                }, 250);
            },

            clearFilters() {
                document.getElementById("deal-symbol-search").value = "";
                document.getElementById("deal-date-from").value = "";
                document.getElementById("deal-date-to").value = "";
                this.handleFilterChange();
            },

            async loadDeals(type) {
                const loader = document.getElementById(`${type}-loading`);
                const table = document.getElementById(`${type}-table`);
                const pagination = document.getElementById(`${type}-pagination`);
                
                loader.style.display = 'block';
                loader.innerText = 'Loading deals list...';
                table.style.display = 'none';
                pagination.style.display = 'none';

                const symbol = document.getElementById("deal-symbol-search").value;
                const start = document.getElementById("deal-date-from").value;
                const end = document.getElementById("deal-date-to").value;

                try {
                    const params = new URLSearchParams();
                    if (symbol) params.append('symbol', symbol);
                    if (start) params.append('start_date', start);
                    if (end) params.append('end_date', end);

                    const response = await fetch(`/api/deals/${type}?${params.toString()}`);
                    const data = await response.json();
                    
                    this.tableData[type].data = data;
                    this.tableData[type].page = 1;

                    loader.style.display = 'none';
                    table.style.display = 'table';
                    pagination.style.display = 'flex';

                    if (data.length === 0) {
                        document.getElementById(`${type}-body`).innerHTML = `<tr><td colspan="6" style="text-align:center;">No data found matching criteria.</td></tr>`;
                        pagination.style.display = 'none';
                        return;
                    }
                    this.renderTable(type);
                } catch (err) {
                    console.error(`Error loading ${type} deals:`, err);
                    loader.style.display = 'block';
                    loader.innerText = 'Failed to load data matching filters.';
                }
            },

            async runAiAnalysis() {
                const btn = document.getElementById('deals-ai-btn');
                const panel = document.getElementById('deals-ai-panel');
                const loading = document.getElementById('deals-ai-loading');
                const table = document.getElementById('deals-ai-table');
                const tbody = document.getElementById('deals-ai-body');

                btn.disabled = true;
                btn.innerText = '🤖 Analyzing...';
                panel.style.display = 'block';
                loading.style.display = 'block';
                table.style.display = 'none';
                tbody.innerHTML = '';

                try {
                    const res = await fetch('/api/ai/predict');
                    const data = await res.json();

                    if (data.error) throw new Error(data.error);

                    loading.style.display = 'none';
                    table.style.display = 'table';

                    if (data.length === 0) {
                        tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;">AI could not identify any strong growth candidates.</td></tr>`;
                    } else {
                        data.forEach(item => {
                            const tr = document.createElement('tr');
                            tr.innerHTML = `
                                <td><span class="symbol-badge">${item.symbol || 'N/A'}</span></td>
                                <td style="font-weight: 600;">${item.company_name || 'N/A'}</td>
                                <td class="positive">+${item.predicted_growth_pct || 15}%</td>
                                <td style="font-size: 0.9rem; color: #cbd5e1;">${item.reasoning || ''}</td>
                            `;
                            tbody.appendChild(tr);
                        });
                    }
                } catch (err) {
                    loading.innerText = '❌ Failed to run AI Analysis: ' + err.message;
                } finally {
                    btn.disabled = false;
                    btn.innerText = '🤖 Predict Growth (Llama 3 AI)';
                }
            },

            async syncDeals() {
                const syncBtn = document.getElementById("deals-sync-btn");
                const syncIcon = document.getElementById("deals-sync-icon");
                const syncText = document.getElementById("deals-sync-text");

                syncBtn.disabled = true;
                syncIcon.classList.add("sync-spin");
                syncText.innerText = "Syncing...";

                try {
                    const response = await fetch("/api/deals/sync", {
                        method: "POST"
                    });

                    if (!response.ok) throw new Error("Sync failed");
                    const resData = await response.json();

                    if (resData.error) throw new Error(resData.error);

                    const toast = document.getElementById("toast");
                    const toastMsg = document.getElementById("toast-message");
                    toastMsg.innerText = `Sync complete! Added ${resData.new_bulk_deals} bulk deals and ${resData.new_block_deals} block deals.`;
                    toast.classList.add("show");

                    setTimeout(() => {
                        toast.classList.remove("show");
                    }, 4000);

                    // Reload the deals tables with fresh data
                    this.tableData['block'] = { data: [], page: 1 };
                    this.tableData['bulk'] = { data: [], page: 1 };
                    this.loadDeals('/api/deals/block', 'block');
                    this.loadDeals('/api/deals/bulk', 'bulk');

                } catch (err) {
                    console.error("Error during deals sync:", err);
                    alert("Failed to sync deals. Please check python console log.");
                } finally {
                    syncBtn.disabled = false;
                    syncIcon.classList.remove("sync-spin");
                    syncText.innerText = "Sync Deals";
                }
            }
        };

        // --- 4. Growth Engine Controller ---
        const GrowthController = {
            initialized: false,
            compData: [],
            fundData: [],
            dealsData: [],
            fundPage: 1,
            dealsPage: 1,
            pageSize: 10,

            init() {
                if (this.initialized) return;
                this.initialized = true;

                this.loadFundamentals();
                this.fetchCompounders();
                this.loadDeals();
            },

            formatCurrency(num) {
                if (!num) return '₹0';
                if (num > 10000000) return `₹${(num / 10000000).toFixed(2)} Cr`;
                if (num > 100000) return `₹${(num / 100000).toFixed(2)} L`;
                return `₹${num.toLocaleString('en-IN')}`;
            },

            formatPercent(num) {
                if (typeof num === 'string') return num;
                return num > 0 ? `+${num}%` : `${num}%`;
            },

            renderPagination(type, dataLength, currentPage, pageInfoId, prevId, nextId) {
                const totalPages = Math.ceil(dataLength / this.pageSize) || 1;
                const pageInfo = document.getElementById(pageInfoId);
                pageInfo.innerHTML = '';

                let startPage = Math.max(1, currentPage - 2);
                let endPage = Math.min(totalPages, currentPage + 2);

                if (startPage > 1) {
                    pageInfo.innerHTML += `<button onclick="GrowthController.jumpPage('${type}', 1)">1</button>`;
                    if (startPage > 2) pageInfo.innerHTML += `<span style="color:#94a3b8">...</span>`;
                }

                for (let i = startPage; i <= endPage; i++) {
                    const activeClass = i === currentPage ? 'active' : '';
                    pageInfo.innerHTML += `<button class="${activeClass}" onclick="GrowthController.jumpPage('${type}', ${i})">${i}</button>`;
                }

                if (endPage < totalPages) {
                    if (endPage < totalPages - 1) pageInfo.innerHTML += `<span style="color:#94a3b8">...</span>`;
                    pageInfo.innerHTML += `<button onclick="GrowthController.jumpPage('${type}', ${totalPages})">${totalPages}</button>`;
                }

                document.getElementById(prevId).disabled = currentPage === 1;
                document.getElementById(nextId).disabled = currentPage >= totalPages;
            },

            jumpPage(type, pageNum) {
                if (type === 'fund') {
                    this.fundPage = pageNum;
                    this.renderFundTable();
                } else if (type === 'deals') {
                    this.dealsPage = pageNum;
                    this.renderDealsTable();
                }
            },

            renderFundTable() {
                const tbody = document.getElementById('fund-body');
                tbody.innerHTML = '';

                const start = (this.fundPage - 1) * this.pageSize;
                const end = start + this.pageSize;
                const paginatedData = this.fundData.slice(start, end);

                paginatedData.forEach(item => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td><span class="symbol-badge">${item.symbol}</span></td>
                        <td class="positive">${this.formatPercent(item.revenue_growth_pct)}</td>
                        <td class="positive">${this.formatPercent(item.profit_growth_pct)}</td>
                        <td>${this.formatCurrency(item.latest_revenue)}</td>
                        <td>${this.formatCurrency(item.latest_net_income)}</td>
                    `;
                    tbody.appendChild(tr);
                });

                this.renderPagination('fund', this.fundData.length, this.fundPage, 'fund-page-info', 'fund-prev', 'fund-next');
            },

            changeFundPage(dir) {
                this.fundPage += dir;
                this.renderFundTable();
            },

            renderDealsTable() {
                const tbody = document.getElementById('deals-body');
                tbody.innerHTML = '';

                const start = (this.dealsPage - 1) * this.pageSize;
                const end = start + this.pageSize;
                const paginatedData = this.dealsData.slice(start, end);

                paginatedData.forEach(item => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td><span class="symbol-badge">${item.symbol}</span></td>
                        <td>${item.security_name}</td>
                        <td class="positive">${item.buy_count} Deals</td>
                        <td>${item.total_bought.toLocaleString('en-IN')} shares</td>
                    `;
                    tbody.appendChild(tr);
                });

                this.renderPagination('deals', this.dealsData.length, this.dealsPage, 'deals-page-info', 'deals-prev', 'deals-next');
            },

            changeDealsPage(dir) {
                this.dealsPage += dir;
                this.renderDealsTable();
            },

            fetchCompounders() {
                fetch('/api/fundamentals/compounders')
                    .then(res => res.json())
                    .then(data => {
                        this.compData = data;
                        document.getElementById('comp-loading').style.display = 'none';
                        if (this.compData.length > 0) {
                            document.getElementById('comp-table').style.display = 'table';
                            this.renderCompTable();
                        } else {
                            document.getElementById('comp-loading').style.display = 'block';
                            document.getElementById('comp-loading').innerText = 'No consistent compounders found yet. Run the historical fetch script.';
                        }
                    })
                    .catch(err => console.error(err));
            },

            renderCompTable() {
                const tbody = document.getElementById('comp-body');
                tbody.innerHTML = this.compData.map(item => `
                    <tr>
                        <td><span class="symbol-badge">${item.symbol}</span></td>
                        <td class="positive">+${item.avg_3yr_growth_pct.toFixed(2)}%</td>
                        <td style="color: #cbd5e1; font-size: 0.8rem; line-height: 1.4;">${item.ai_driving_factor}</td>
                    </tr>
                `).join('');
            },

            async loadFundamentals() {
                try {
                    const res = await fetch('/api/fundamentals/growth');
                    this.fundData = await res.json();

                    document.getElementById('fund-loading').style.display = 'none';
                    document.getElementById('fund-table').style.display = 'table';
                    document.getElementById('fund-pagination').style.display = 'flex';

                    if (this.fundData.length === 0) {
                        document.getElementById('fund-body').innerHTML = '<tr><td colspan="5" style="text-align:center;">No growth stocks found.</td></tr>';
                        document.getElementById('fund-pagination').style.display = 'none';
                        return;
                    }
                    this.renderFundTable();
                } catch (err) {
                    document.getElementById('fund-loading').innerText = 'Failed to load fundamental data.';
                }
            },

            async loadDeals() {
                try {
                    const res = await fetch('/api/deals/potential_growth');
                    this.dealsData = await res.json();

                    document.getElementById('deals-loading').style.display = 'none';
                    document.getElementById('deals-table').style.display = 'table';
                    document.getElementById('deals-pagination').style.display = 'flex';

                    if (this.dealsData.length === 0) {
                        document.getElementById('deals-body').innerHTML = '<tr><td colspan="4" style="text-align:center;">No deals data found.</td></tr>';
                        document.getElementById('deals-pagination').style.display = 'none';
                        return;
                    }
                    this.renderDealsTable();
                } catch (err) {
                    document.getElementById('deals-loading').innerText = 'Failed to load deals data.';
                }
            },

            async runAiAnalysis() {
                const btn = document.getElementById('growth-ai-btn');
                const panel = document.getElementById('growth-ai-panel');
                const loading = document.getElementById('growth-ai-loading');
                const table = document.getElementById('growth-ai-table');
                const tbody = document.getElementById('growth-ai-body');

                btn.disabled = true;
                btn.innerText = '🤖 Analyzing...';
                panel.style.display = 'block';
                loading.style.display = 'block';
                table.style.display = 'none';
                tbody.innerHTML = '';

                try {
                    const res = await fetch('/api/ai/predict');
                    const data = await res.json();

                    if (data.error) throw new Error(data.error);

                    loading.style.display = 'none';
                    table.style.display = 'table';

                    if (data.length === 0) {
                        tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;">AI could not identify any strong growth candidates.</td></tr>`;
                    } else {
                        data.forEach(item => {
                            const tr = document.createElement('tr');
                            tr.innerHTML = `
                                <td><span class="symbol-badge">${item.symbol || 'N/A'}</span></td>
                                <td style="font-weight: 600;">${item.company_name || 'N/A'}</td>
                                <td class="positive">+${item.predicted_growth_pct || 15}%</td>
                                <td style="font-size: 0.9rem; color: #cbd5e1;">${item.reasoning || ''}</td>
                            `;
                            tbody.appendChild(tr);
                        });
                    }
                } catch (err) {
                    loading.innerText = '❌ Failed to run AI Analysis: ' + err.message;
                } finally {
                    btn.disabled = false;
                    btn.innerText = '🤖 Predict Growth (Llama 3 AI)';
                }
            }
        };

        // --- 5. Live News Controller ---
        const NewsController = {
            initialized: false,
            selectedTicker: '',
            searchTimeout: null,
            activeRegion: 'India',

            init() {
                if (this.initialized) return;
                this.initialized = true;

                this.fetchNews();
            },

            debounceSearch() {
                clearTimeout(this.searchTimeout);
                this.searchTimeout = setTimeout(() => {
                    this.fetchNews();
                }, 300);
            },

            switchRegion(regionName) {
                this.activeRegion = regionName;
                
                const tabs = ['india', 'intl', 'all'];
                const mapping = {
                    'India': 'india',
                    'International': 'intl',
                    'All': 'all'
                };
                
                tabs.forEach(t => {
                    const btn = document.getElementById(`news-region-${t}`);
                    if (btn) {
                        if (t === mapping[regionName]) {
                            btn.classList.add('active');
                        } else {
                            btn.classList.remove('active');
                        }
                    }
                });
                
                this.fetchNews();
            },

            async fetchNews() {
                const loadingState = document.getElementById("loading-state");
                const emptyState = document.getElementById("empty-state");
                const newsGrid = document.getElementById("news-grid");

                loadingState.style.display = "flex";
                emptyState.style.display = "none";
                newsGrid.style.display = "none";

                const searchVal = document.getElementById("search-input").value;
                const sourceVal = document.getElementById("source-filter").value;
                const sentimentVal = document.getElementById("sentiment-filter").value;
                const tickerVal = document.getElementById("ticker-input").value || this.selectedTicker;

                const activeTickerContainer = document.getElementById("active-ticker-container");
                const tickerTagsList = document.getElementById("ticker-tags-list");
                if (this.selectedTicker) {
                    activeTickerContainer.style.display = "block";
                    tickerTagsList.innerHTML = `
                        <span class="filter-tag">
                            Stock: ${this.selectedTicker}
                            <span class="filter-tag-clear" onclick="NewsController.clearTickerFilter()">×</span>
                        </span>
                    `;
                    document.getElementById("ticker-input").value = this.selectedTicker;
                } else {
                    activeTickerContainer.style.display = "none";
                }

                try {
                    const params = new URLSearchParams();
                    if (searchVal) params.append("search", searchVal);
                    if (sourceVal) params.append("source", sourceVal);
                    if (sentimentVal) params.append("sentiment", sentimentVal);
                    if (tickerVal) params.append("ticker", tickerVal.trim());
                    if (this.activeRegion) params.append("region", this.activeRegion);
                    params.append("limit", 150);

                    const response = await fetch(`/api/news?${params.toString()}`);
                    if (!response.ok) throw new Error("Failed to fetch news data");
                    const data = await response.json();

                    this.updateStatsPanel(data.stats);

                    const articles = data.news;
                    if (!articles || articles.length === 0) {
                        loadingState.style.display = "none";
                        emptyState.style.display = "block";
                        return;
                    }

                    this.renderArticles(articles);

                    loadingState.style.display = "none";
                    newsGrid.style.display = "grid";

                } catch (err) {
                    console.error("Error fetching news feed:", err);
                    loadingState.style.display = "none";
                    emptyState.style.display = "block";
                    emptyState.querySelector("h3").innerText = "Network Error";
                    emptyState.querySelector("p").innerText = "Could not communicate with the Python backend server.";
                }
            },

            renderArticles(articles) {
                const grid = document.getElementById("news-grid");
                grid.innerHTML = "";

                articles.forEach(art => {
                    const card = document.createElement("div");
                    card.className = `news-card ${this.getSentimentClass(art.sentiment)}`;

                    const formattedDate = this.formatPubDate(art.published_at);
                    const sentimentBadge = `<span class="badge-sentiment ${this.getSentimentBadgeClass(art.sentiment)}">${art.sentiment}</span>`;

                    let tickersHtml = "";
                    if (art.ticker) {
                        const symbols = art.ticker.split(",");
                        tickersHtml = `
                            <div class="news-tickers">
                                ${symbols.map(sym => `<span class="ticker-pill" onclick="NewsController.filterByTicker('${sym}')">${sym}</span>`).join("")}
                            </div>
                        `;
                    }

                    card.innerHTML = `
                        <div class="news-card-meta">
                            <div class="meta-left">
                                <span class="badge-source">${art.source}</span>
                                ${sentimentBadge}
                            </div>
                            <span class="meta-date">${formattedDate}</span>
                        </div>
                        <a href="${art.url}" target="_blank" class="news-title">${art.title}</a>
                        <p class="news-summary">${art.summary || "No summary description available."}</p>
                        ${tickersHtml}
                    `;

                    grid.appendChild(card);
                });
            },

            getSentimentClass(sent) {
                if (sent === "Positive") return "pos-sentiment";
                if (sent === "Negative") return "neg-sentiment";
                return "neu-sentiment";
            },

            getSentimentBadgeClass(sent) {
                if (sent === "Positive") return "badge-pos";
                if (sent === "Negative") return "badge-neg";
                return "badge-neu";
            },

            formatPubDate(dateStr) {
                if (!dateStr) return "";
                try {
                    const parts = dateStr.split(/[- :]/);
                    const utcDate = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2], parts[3], parts[4], parts[5]));

                    const now = new Date();
                    const diffMs = now - utcDate;
                    const diffMin = Math.round(diffMs / 60000);
                    const diffHrs = Math.round(diffMs / 3600000);
                    const diffDays = Math.round(diffMs / 86400000);

                    if (diffMin < 60) {
                        return diffMin <= 1 ? "Just now" : `${diffMin}m ago`;
                    } else if (diffHrs < 24) {
                        return `${diffHrs}h ago`;
                    } else if (diffDays <= 7) {
                        return `${diffDays}d ago`;
                    }

                    const options = { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' };
                    return utcDate.toLocaleDateString(undefined, options);
                } catch (err) {
                    return dateStr;
                }
            },

            updateStatsPanel(stats) {
                const pos = stats.Positive || 0;
                const neg = stats.Negative || 0;
                const neu = stats.Neutral || 0;
                const total = pos + neg + neu;

                document.getElementById("stat-total").innerText = total;
                document.getElementById("stat-pos").innerText = pos;
                document.getElementById("stat-neg").innerText = neg;
                document.getElementById("stat-neu").innerText = neu;

                if (total > 0) {
                    const posPct = (pos / total) * 100;
                    const negPct = (neg / total) * 100;
                    const neuPct = (neu / total) * 100;

                    document.getElementById("bar-pos").style.width = `${posPct}%`;
                    document.getElementById("bar-neg").style.width = `${negPct}%`;
                    document.getElementById("bar-neu").style.width = `${neuPct}%`;
                } else {
                    document.getElementById("bar-pos").style.width = "0%";
                    document.getElementById("bar-neg").style.width = "0%";
                    document.getElementById("bar-neu").style.width = "0%";
                }
            },

            filterByTicker(symbol) {
                this.selectedTicker = symbol;
                document.getElementById("ticker-input").value = symbol;
                this.fetchNews();
            },

            clearTickerFilter() {
                this.selectedTicker = '';
                document.getElementById("ticker-input").value = '';
                this.fetchNews();
            },

            async syncNews() {
                const syncBtn = document.getElementById("sync-btn");
                const syncIcon = document.getElementById("sync-icon");
                const syncText = document.getElementById("sync-text");

                syncBtn.disabled = true;
                syncIcon.classList.add("sync-spin");
                syncText.innerText = "Syncing...";

                try {
                    const response = await fetch("/api/news/crawl", {
                        method: "POST"
                    });

                    if (!response.ok) throw new Error("Sync failed");
                    const resData = await response.json();

                    const toast = document.getElementById("toast");
                    const toastMsg = document.getElementById("toast-message");
                    toastMsg.innerText = `Sync complete! Added ${resData.new_articles_count} new articles.`;
                    toast.classList.add("show");

                    setTimeout(() => {
                        toast.classList.remove("show");
                    }, 4000);

                    this.fetchNews();

                } catch (err) {
                    console.error("Error during manual sync:", err);
                    alert("Failed to sync news. Please check python console log.");
                } finally {
                    syncBtn.disabled = false;
                    syncIcon.classList.remove("sync-spin");
                    syncText.innerText = "Sync";
                }
            }
        };


        // --- 5. Admin Controller ---
        const AdminController = {
            initialized: false,
            usersData: [],

            init() {
                if (this.initialized) return;
                this.initialized = true;
                this.fetchUsers();
            },

            async fetchUsers() {
                const tbody = document.getElementById("admin-users-body");
                if (!tbody) return;
                tbody.innerHTML = '<tr><td colspan="6" class="loading" style="text-align:center; padding:1rem; color:var(--text-secondary);">Loading user database...</td></tr>';
                const emptyState = document.getElementById("admin-empty-state");
                if (emptyState) emptyState.style.display = "none";

                try {
                    const response = await fetch("/api/admin/users");
                    if (!response.ok) {
                        const errData = await response.json();
                        throw new Error(errData.error || "Failed to fetch users");
                    }
                    const data = await response.json();
                    this.usersData = data;
                    this.renderUsers(data);
                } catch (err) {
                    console.error("Error fetching users list:", err);
                    tbody.innerHTML = `<tr><td colspan="6" class="loading" style="text-align:center; padding:1rem; color:var(--danger);">Error loading users: ${escapeHTML(err.message)}</td></tr>`;
                }
            },

            loadUsers() {
                return this.fetchUsers();
            },

            renderUsers(users) {
                const tbody = document.getElementById("admin-users-body");
                if (!tbody) return;
                tbody.innerHTML = "";

                const emptyState = document.getElementById("admin-empty-state");
                if (users.length === 0) {
                    if (emptyState) emptyState.style.display = "block";
                    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; padding:1rem; color:var(--text-secondary);">No registered users found.</td></tr>';
                    return;
                }
                if (emptyState) emptyState.style.display = "none";

                users.forEach(u => {
                    const tr = document.createElement("tr");
                    
                    const entList = u.entitlements ? u.entitlements.split(',').map(e => e.trim()).filter(Boolean) : [];
                    let entHtml = "";
                    if (entList.includes('stock_admin')) {
                        entHtml += `<span class="ratio-tag ratio-high" style="font-size:0.6rem; margin-right:4px;">stock_admin</span>`;
                    }
                    if (entList.length === 0 || (entList.length === 1 && entList[0] === '')) {
                        entHtml += `<span class="ratio-tag ratio-low" style="font-size:0.6rem;">None (User)</span>`;
                    } else {
                        entList.forEach(e => {
                            if (e !== 'stock_admin') {
                                entHtml += `<span class="ratio-tag ratio-mid" style="font-size:0.6rem; margin-right:4px;">${e}</span>`;
                            }
                        });
                    }

                    const isAdmin = entList.includes('stock_admin');
                    const actionBtnText = isAdmin ? "Revoke Admin" : "Grant Admin";
                    const actionBtnClass = isAdmin ? "btn-page" : "btn";
                    const actionBtnStyle = isAdmin ? "background:#ef4444; border-color:#ef4444; padding:0.2rem 0.5rem; font-size:0.6rem;" : "background:#10b981; border-color:#10b981; padding:0.2rem 0.5rem; font-size:0.6rem; color:white; box-shadow:none;";
                    
                    tr.innerHTML = `
                        <td>${u.id}</td>
                        <td style="font-weight:600; color:#fff;">${u.name || 'N/A'}</td>
                        <td>${u.email}</td>
                        <td style="color:#94a3b8; font-size:0.65rem;">${u.last_login || 'Never'}</td>
                        <td>${entHtml}</td>
                        <td>
                            <button class="${actionBtnClass}" style="${actionBtnStyle}" onclick="AdminController.toggleAdmin('${u.email}', ${isAdmin})">
                                ${actionBtnText}
                            </button>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            },

            filterUsers() {
                const query = document.getElementById("admin-search-input").value.toLowerCase();
                const filtered = this.usersData.filter(u => {
                    const name = (u.name || '').toLowerCase();
                    const email = (u.email || '').toLowerCase();
                    return name.includes(query) || email.includes(query);
                });
                this.renderUsers(filtered);
            },

            async toggleAdmin(email, currentIsAdmin) {
                let newEnts = "";
                if (!currentIsAdmin) {
                    newEnts = "stock_admin";
                }

                if (currentIsAdmin) {
                    const profileRes = await fetch("/api/user/profile");
                    if (profileRes.ok) {
                        const profile = await profileRes.json();
                        if (profile.email === email) {
                            alert("Cannot demote yourself to prevent lock out!");
                            return;
                        }
                    }
                }

                try {
                    const response = await fetch("/api/admin/users/update", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ email: email, entitlements: newEnts })
                    });
                    
                    const resData = await response.json();
                    if (!response.ok) {
                        throw new Error(resData.error || "Failed to update user entitlements");
                    }
                    
                    const toast = document.getElementById("toast");
                    const toastMsg = document.getElementById("toast-message");
                    toastMsg.innerText = `Success: Entitlements updated for ${email}`;
                    toast.classList.add("show");
                    setTimeout(() => toast.classList.remove("show"), 3000);
                    
                    this.fetchUsers();
                } catch (err) {
                    alert("Error: " + err.message);
                }
            },

            toggleEntitlement(email, role) {
                const isCurrentlyAdmin = role === 'user';
                return this.toggleAdmin(email, isCurrentlyAdmin);
            }
        };

        // --- 6. IPO Tracker Controller ---
        const IpoController = {
            initialized: false,
            iposData: [],
            activeFilter: 'All',
            currentPage: 1,
            pageSize: 10,
            dateFrom: '',
            dateTo: '',

            init() {
                if (this.initialized) return;
                this.initialized = true;
                this.fetchIpos();
            },

            async fetchIpos() {
                const loading = document.getElementById("ipo-loading");
                const content = document.getElementById("ipo-content");
                const empty = document.getElementById("ipo-empty");

                loading.style.display = "block";
                content.style.display = "none";
                empty.style.display = "none";

                try {
                    const response = await fetch("/api/ipos");
                    if (!response.ok) throw new Error("Failed to fetch IPOs");
                    const data = await response.json();
                    this.iposData = data;
                    this.renderIpos();
                } catch (err) {
                    console.error("Error loading IPOs:", err);
                    loading.innerHTML = `<span style="color:var(--danger)">Error loading IPO data. Network or server error.</span>`;
                }
            },

            renderIpos() {
                const loading = document.getElementById("ipo-loading");
                const content = document.getElementById("ipo-content");
                const empty = document.getElementById("ipo-empty");
                const grid = document.getElementById("ipo-grid");
                const paginationContainer = document.getElementById("ipo-pagination");

                loading.style.display = "none";
                grid.innerHTML = "";

                // Show/hide closed filters toolbar based on selection
                const closedFilters = document.getElementById("ipo-closed-filters");
                if (closedFilters) {
                    if (this.activeFilter === 'Closed') {
                        closedFilters.style.display = "flex";
                    } else {
                        closedFilters.style.display = "none";
                    }
                }

                let filtered = this.iposData.filter(ipo => {
                    if (this.activeFilter === 'All') return true;
                    return ipo.status.toLowerCase() === this.activeFilter.toLowerCase();
                });

                // Apply date range filters if Closed is selected
                if (this.activeFilter === 'Closed') {
                    if (this.dateFrom) {
                        filtered = filtered.filter(ipo => {
                            if (!ipo.issue_end_date || ipo.issue_end_date === "N/A") return false;
                            return ipo.issue_end_date >= this.dateFrom;
                        });
                    }
                    if (this.dateTo) {
                        filtered = filtered.filter(ipo => {
                            if (!ipo.issue_end_date || ipo.issue_end_date === "N/A") return false;
                            return ipo.issue_end_date <= this.dateTo;
                        });
                    }
                }

                // Apply custom sorting per tab
                if (this.activeFilter === 'Closed') {
                    filtered.sort((a, b) => {
                        const subA = parseFloat(a.total_x) || 0;
                        const subB = parseFloat(b.total_x) || 0;
                        if (subB !== subA) return subB - subA; // Most subscribed first
                        const dateA = a.issue_end_date && a.issue_end_date !== 'N/A' ? a.issue_end_date : '0000-00-00';
                        const dateB = b.issue_end_date && b.issue_end_date !== 'N/A' ? b.issue_end_date : '0000-00-00';
                        return dateB.localeCompare(dateA); // Latest date first
                    });
                } else if (this.activeFilter === 'Upcoming') {
                    filtered.sort((a, b) => {
                        const dateA = a.issue_start_date && a.issue_start_date !== 'N/A' ? a.issue_start_date : '9999-99-99';
                        const dateB = b.issue_start_date && b.issue_start_date !== 'N/A' ? b.issue_start_date : '9999-99-99';
                        return dateA.localeCompare(dateB); // Soonest start date first
                    });
                } else if (this.activeFilter === 'Active') {
                    filtered.sort((a, b) => {
                        const subA = parseFloat(a.total_x) || 0;
                        const subB = parseFloat(b.total_x) || 0;
                        if (subB !== subA) return subB - subA;
                        const dateA = a.issue_end_date && a.issue_end_date !== 'N/A' ? a.issue_end_date : '9999-99-99';
                        const dateB = b.issue_end_date && b.issue_end_date !== 'N/A' ? b.issue_end_date : '9999-99-99';
                        return dateA.localeCompare(dateB);
                    });
                } else {
                    const statusRank = { 'Active': 1, 'Upcoming': 2, 'Closed': 3 };
                    filtered.sort((a, b) => {
                        const rankA = statusRank[a.status] || 4;
                        const rankB = statusRank[b.status] || 4;
                        if (rankA !== rankB) return rankA - rankB;
                        const subA = parseFloat(a.total_x) || 0;
                        const subB = parseFloat(b.total_x) || 0;
                        if (subB !== subA) return subB - subA;
                        const dateA = a.issue_end_date && a.issue_end_date !== 'N/A' ? a.issue_end_date : '0000-00-00';
                        const dateB = b.issue_end_date && b.issue_end_date !== 'N/A' ? b.issue_end_date : '0000-00-00';
                        return dateB.localeCompare(dateA);
                    });
                }

                if (filtered.length === 0) {
                    content.style.display = "none";
                    empty.style.display = "block";
                    if (paginationContainer) paginationContainer.style.display = "none";
                    return;
                }

                empty.style.display = "none";
                content.style.display = "block";

                let displayList = filtered;
                const totalItems = filtered.length;
                const totalPages = Math.ceil(totalItems / this.pageSize);

                if (this.currentPage > totalPages) this.currentPage = totalPages;
                if (this.currentPage < 1) this.currentPage = 1;

                const startIndex = (this.currentPage - 1) * this.pageSize;
                const endIndex = startIndex + this.pageSize;
                displayList = filtered.slice(startIndex, endIndex);

                this.renderPagination(totalPages);

                displayList.forEach(ipo => {
                    const card = document.createElement("div");
                    card.className = "ipo-card";

                    const badgeClass = `status-${ipo.status.toLowerCase()}`;
                    
                    let subHtml = "";
                    if (ipo.status === 'Active' || ipo.status === 'Closed') {
                        const totalDemand = parseFloat(ipo.total_x) || 0;
                        const hasSubData = (parseFloat(ipo.retail_x) > 0 || parseFloat(ipo.hni_x) > 0 || parseFloat(ipo.qib_x) > 0 || totalDemand > 0);
                        
                        if (hasSubData) {
                            subHtml = `
                                <div class="ipo-subscriptions">
                                    <div class="ipo-sub-title">Subscription Demand (Multipliers)</div>
                                    ${this.renderProgressBar("Retail", ipo.retail_x, 15)}
                                    ${this.renderProgressBar("HNI (NII)", ipo.hni_x, 30)}
                                    ${this.renderProgressBar("Institutional (QIB)", ipo.qib_x, 50)}
                                    <div style="border-top:1px dashed rgba(255,255,255,0.05); padding-top:0.4rem; display:flex; justify-content:space-between; align-items:center;">
                                        <span style="font-size:0.6rem; color:var(--text-secondary);">Total Demand</span>
                                        <span class="ratio-tag ${totalDemand >= 1.0 ? 'ratio-high' : 'ratio-mid'}" style="font-size:0.65rem;">${totalDemand.toFixed(2)}x</span>
                                    </div>
                                </div>
                            `;
                        } else {
                            subHtml = `
                                <div class="ipo-subscriptions" style="text-align:center; padding:1rem; background:rgba(255,255,255,0.01); border-radius:8px;">
                                    <div style="font-size:0.65rem; color:var(--text-secondary); opacity:0.7;">
                                        <i style="font-size:0.8rem; margin-bottom:0.3rem; display:block;">📊</i>
                                        Subscription data not yet available
                                    </div>
                                    <div style="font-size:0.55rem; color:var(--text-secondary); opacity:0.5; margin-top:0.3rem;">
                                        Click Sync to fetch latest data from NSE
                                    </div>
                                </div>
                            `;
                        }
                    } else {
                        subHtml = `
                            <div class="ipo-subscriptions" style="text-align:center; padding:1.2rem; background:rgba(255,255,255,0.01); border-radius:8px;">
                                <span style="font-size:0.65rem; color:var(--text-secondary);">Subscription bids open on ${ipo.issue_start_date}</span>
                            </div>
                        `;
                    }

                    let gmpStyle = "background:rgba(148,163,184,0.1); color:#94a3b8; border:1px solid rgba(148,163,184,0.2);";
                    if (ipo.gmp && ipo.gmp !== 'N/A' && ipo.gmp !== '₹0' && !ipo.gmp.includes('-')) {
                        gmpStyle = "background:rgba(16,185,129,0.1); color:#10b981; border:1px solid rgba(16,185,129,0.2);";
                    } else if (ipo.gmp && ipo.gmp.includes('-')) {
                        gmpStyle = "background:rgba(239,68,68,0.1); color:#ef4444; border:1px solid rgba(239,68,68,0.2);";
                    }

                    card.innerHTML = `
                        <div class="ipo-header">
                            <div class="ipo-title">${ipo.company_name}</div>
                            <span class="ipo-status-badge ${badgeClass}">${ipo.status}</span>
                        </div>
                        <div style="font-size:0.6rem; color:#94a3b8; font-weight:600; display:flex; justify-content:space-between; align-items:center; margin-bottom:0.6rem;">
                            <span>Symbol: ${ipo.symbol}</span>
                            <span style="font-size:0.65rem; padding:0.1rem 0.4rem; border-radius:4px; font-weight:700; ${gmpStyle}">GMP: ${ipo.gmp || 'N/A'}</span>
                        </div>
                        <div class="ipo-details-grid">
                            <div class="ipo-detail-item">
                                <span class="ipo-detail-label">Issue Period</span>
                                <span class="ipo-detail-value" style="font-size:0.6rem;">${ipo.issue_start_date} to ${ipo.issue_end_date}</span>
                            </div>
                            <div class="ipo-detail-item">
                                <span class="ipo-detail-label">Price Range</span>
                                <span class="ipo-detail-value">${ipo.price_range}</span>
                            </div>
                            <div class="ipo-detail-item">
                                <span class="ipo-detail-label">Issue Size</span>
                                <span class="ipo-detail-value">${ipo.issue_size}</span>
                            </div>
                            <div class="ipo-detail-item">
                                <span class="ipo-detail-label">Min Lot Size</span>
                                <span class="ipo-detail-value">${ipo.lot_size} Shares</span>
                            </div>
                        </div>
                        ${subHtml}
                    `;
                    grid.appendChild(card);
                });
            },

            renderProgressBar(label, multiplier, maxScale) {
                const num = parseFloat(multiplier) || 0;
                const percentage = Math.min(100, Math.max(0, (num / maxScale) * 100));
                
                let fillClass = "fill-low";
                if (num === 0) fillClass = "fill-empty";
                else if (num >= 1.0) fillClass = "fill-high";
                else if (num >= 0.5) fillClass = "fill-mid";

                return `
                    <div class="sub-bar-container">
                        <div class="sub-bar-header">
                            <span style="color:var(--text-secondary); font-size:0.6rem;">${label}</span>
                            <span style="font-weight:600; color:#fff; font-size:0.6rem;">${num.toFixed(2)}x</span>
                        </div>
                        <div class="sub-bar-bg">
                            <div class="sub-bar-fill ${fillClass}" style="width: ${percentage}%;"></div>
                        </div>
                    </div>
                `;
            },

            filterStatus(status) {
                this.activeFilter = status;
                this.currentPage = 1;
                this.dateFrom = '';
                this.dateTo = '';

                const dateFromInput = document.getElementById("ipo-date-from");
                const dateToInput = document.getElementById("ipo-date-to");
                if (dateFromInput) dateFromInput.value = "";
                if (dateToInput) dateToInput.value = "";

                const buttons = ['all', 'active', 'upcoming', 'closed'];
                buttons.forEach(btn => {
                    const el = document.getElementById(`ipo-filter-${btn}`);
                    if (btn.toLowerCase() === status.toLowerCase()) {
                        el.classList.add('active');
                    } else {
                        el.classList.remove('active');
                    }
                });

                this.renderIpos();
            },

            handleDateChange() {
                const dateFromInput = document.getElementById("ipo-date-from");
                const dateToInput = document.getElementById("ipo-date-to");
                this.dateFrom = dateFromInput ? dateFromInput.value : '';
                this.dateTo = dateToInput ? dateToInput.value : '';
                this.currentPage = 1;
                this.renderIpos();
            },

            clearDateFilters() {
                const dateFromInput = document.getElementById("ipo-date-from");
                const dateToInput = document.getElementById("ipo-date-to");
                if (dateFromInput) dateFromInput.value = "";
                if (dateToInput) dateToInput.value = "";
                this.dateFrom = '';
                this.dateTo = '';
                this.currentPage = 1;
                this.renderIpos();
            },

            renderPagination(totalPages) {
                const container = document.getElementById("ipo-pagination");
                if (!container) return;

                if (totalPages <= 1) {
                    container.style.display = "none";
                    return;
                }

                container.style.display = "flex";
                container.innerHTML = "";

                // Previous
                const prevBtn = document.createElement("button");
                prevBtn.className = "btn-page";
                prevBtn.innerText = "‹ Prev";
                prevBtn.style.padding = "0.25rem 0.6rem";
                prevBtn.style.fontSize = "0.65rem";
                prevBtn.style.borderRadius = "6px";
                if (this.currentPage === 1) {
                    prevBtn.disabled = true;
                    prevBtn.style.opacity = "0.4";
                    prevBtn.style.cursor = "not-allowed";
                } else {
                    prevBtn.onclick = () => {
                        this.currentPage--;
                        this.renderIpos();
                    };
                }
                container.appendChild(prevBtn);

                const startPage = Math.max(1, this.currentPage - 2);
                const endPage = Math.min(totalPages, this.currentPage + 2);

                if (startPage > 1) {
                    const firstBtn = document.createElement("button");
                    firstBtn.className = "btn-page";
                    firstBtn.innerText = "1";
                    firstBtn.style.padding = "0.25rem 0.6rem";
                    firstBtn.style.fontSize = "0.65rem";
                    firstBtn.style.borderRadius = "6px";
                    firstBtn.onclick = () => {
                        this.currentPage = 1;
                        this.renderIpos();
                    };
                    container.appendChild(firstBtn);

                    if (startPage > 2) {
                        const dots = document.createElement("span");
                        dots.innerText = "...";
                        dots.style.color = "var(--text-secondary)";
                        dots.style.fontSize = "0.65rem";
                        container.appendChild(dots);
                    }
                }

                for (let i = startPage; i <= endPage; i++) {
                    const pageBtn = document.createElement("button");
                    pageBtn.className = `btn-page ${i === this.currentPage ? 'active' : ''}`;
                    pageBtn.innerText = i;
                    pageBtn.style.padding = "0.25rem 0.6rem";
                    pageBtn.style.fontSize = "0.65rem";
                    pageBtn.style.borderRadius = "6px";
                    pageBtn.onclick = () => {
                        this.currentPage = i;
                        this.renderIpos();
                    };
                    container.appendChild(pageBtn);
                }

                if (endPage < totalPages) {
                    if (endPage < totalPages - 1) {
                        const dots = document.createElement("span");
                        dots.innerText = "...";
                        dots.style.color = "var(--text-secondary)";
                        dots.style.fontSize = "0.65rem";
                        container.appendChild(dots);
                    }

                    const lastBtn = document.createElement("button");
                    lastBtn.className = "btn-page";
                    lastBtn.innerText = totalPages;
                    lastBtn.style.padding = "0.25rem 0.6rem";
                    lastBtn.style.fontSize = "0.65rem";
                    lastBtn.style.borderRadius = "6px";
                    lastBtn.onclick = () => {
                        this.currentPage = totalPages;
                        this.renderIpos();
                    };
                    container.appendChild(lastBtn);
                }

                // Next
                const nextBtn = document.createElement("button");
                nextBtn.className = "btn-page";
                nextBtn.innerText = "Next ›";
                nextBtn.style.padding = "0.25rem 0.6rem";
                nextBtn.style.fontSize = "0.65rem";
                nextBtn.style.borderRadius = "6px";
                if (this.currentPage === totalPages) {
                    nextBtn.disabled = true;
                    nextBtn.style.opacity = "0.4";
                    nextBtn.style.cursor = "not-allowed";
                } else {
                    nextBtn.onclick = () => {
                        this.currentPage++;
                        this.renderIpos();
                    };
                }
                container.appendChild(nextBtn);
            },

            async syncSubscriptions() {
                const btn = document.getElementById("ipo-sync-btn");
                const icon = document.getElementById("ipo-sync-icon");
                const text = document.getElementById("ipo-sync-text");

                btn.disabled = true;
                icon.classList.add("sync-spin");
                text.innerText = "Syncing...";

                try {
                    const response = await fetch("/api/ipos/sync", { method: "POST" });
                    if (!response.ok) throw new Error("Sync failed");
                    
                    const toast = document.getElementById("toast");
                    const toastMsg = document.getElementById("toast-message");
                    toastMsg.innerText = "Subscription multipliers sync completed!";
                    toast.classList.add("show");
                    setTimeout(() => toast.classList.remove("show"), 3000);

                    this.fetchIpos();
                } catch (err) {
                    console.error("Error during manual sync:", err);
                    alert("Failed to sync subscriptions.");
                } finally {
                    btn.disabled = false;
                    icon.classList.remove("sync-spin");
                    text.innerText = "Sync Subscriptions";
                }
            }
        };

        // --- 7. Mutual Funds Controllers System ---
        const FundsController = {
            activeSubView: 'explorer',
            initialized: false,
            
            init() {
                if (this.initialized) return;
                this.initialized = true;
                ExplorerController.init();
            },
            
            switchSubView(subViewName) {
                this.activeSubView = subViewName;
                
                const subtabs = ['explorer', 'details', 'compare', 'calculator'];
                subtabs.forEach(tab => {
                    const btn = document.getElementById(`fund-subtab-${tab}`);
                    const panel = document.getElementById(`fund-subview-${tab}`);
                    
                    if (btn) {
                        if (tab === subViewName) {
                            btn.classList.add('active');
                        } else {
                            btn.classList.remove('active');
                        }
                    }
                    
                    if (panel) {
                        if (tab === subViewName) {
                            panel.style.display = 'block';
                        } else {
                            panel.style.display = 'none';
                        }
                    }
                });
                
                if (subViewName === 'compare') {
                    CompareController.init();
                } else if (subViewName === 'calculator') {
                    CalculatorController.init();
                }
            }
        };

        const ExplorerController = {
            initialized: false,
            fundsData: [],
            currentPage: 1,
            pageSize: 10,
            top10Mode: false,

            init() {
                if (this.initialized) return;
                this.initialized = true;
                this.fetchFunds();
            },

            async fetchFunds() {
                const tbody = document.getElementById("funds-table-body");
                tbody.innerHTML = '<tr><td colspan="10" class="loading">Loading funds list...</td></tr>';
                
                const cat = document.getElementById("category-filter").value;
                const search = document.getElementById("fund-search").value;
                
                try {
                    const params = new URLSearchParams();
                    params.append('page', this.currentPage);
                    params.append('limit', this.pageSize);
                    
                    if (this.top10Mode) {
                        params.append('top10', 'true');
                    } else {
                        if (cat !== 'All') params.append('category', cat);
                        if (search) params.append('search', search);
                    }
                    
                    const response = await fetch(`/api/funds?${params.toString()}`);
                    if (!response.ok) throw new Error("Failed to fetch funds list");
                    const data = await response.json();
                    
                    this.fundsData = data.funds;
                    this.renderTable(data.funds);
                    
                    const pagContainer = document.getElementById("funds-pagination");
                    if (this.top10Mode) {
                        pagContainer.style.display = "none";
                    } else {
                        pagContainer.style.display = "flex";
                        const totalPages = Math.ceil(data.total / this.pageSize) || 1;
                        this.renderPagination(totalPages);
                    }
                } catch (err) {
                    console.error("Error fetching funds:", err);
                    tbody.innerHTML = '<tr><td colspan="10" class="loading" style="color:var(--danger)">Failed to load mutual funds.</td></tr>';
                }
            },

            renderTable(funds) {
                const tbody = document.getElementById("funds-table-body");
                tbody.innerHTML = "";
                
                if (funds.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="10" class="empty-state">No mutual funds found.</td></tr>';
                    return;
                }
                
                funds.forEach(f => {
                    const tr = document.createElement("tr");
                    tr.onclick = () => {
                        DetailsController.loadFund(f.amfi_code);
                    };
                    
                    tr.innerHTML = `
                        <td style="font-weight:600; color:#fff;">${f.amfi_code}</td>
                        <td style="color:#fff; font-weight:500;">${f.scheme_name}</td>
                        <td>${f.category}</td>
                        <td>${f.sub_category}</td>
                        <td>₹${f.aum.toLocaleString('en-IN')} Cr</td>
                        <td>${f.expense_ratio}%</td>
                        <td class="font-accent">${'★'.repeat(f.star_rating)}${'☆'.repeat(5 - f.star_rating)}</td>
                        <td class="font-accent font-bold">${f.stats ? f.stats.return_1y : '0.0'}%</td>
                        <td class="font-accent font-bold">${f.stats ? f.stats.return_3y : '0.0'}%</td>
                        <td class="font-accent font-bold">${f.stats ? f.stats.return_5y : '0.0'}%</td>
                    `;
                    tbody.appendChild(tr);
                });
            },

            renderPagination(totalPages) {
                const container = document.getElementById("funds-pagination");
                container.innerHTML = "";

                const prevBtn = document.createElement("button");
                prevBtn.className = "btn-page";
                prevBtn.innerText = "Previous";
                prevBtn.disabled = this.currentPage === 1;
                prevBtn.onclick = () => {
                    this.currentPage--;
                    this.fetchFunds();
                };
                container.appendChild(prevBtn);

                let startPage = Math.max(1, this.currentPage - 2);
                let endPage = Math.min(totalPages, this.currentPage + 2);

                if (startPage > 1) {
                    const firstBtn = document.createElement("button");
                    firstBtn.className = "btn-page";
                    firstBtn.innerText = "1";
                    firstBtn.onclick = () => {
                        this.currentPage = 1;
                        this.fetchFunds();
                    };
                    container.appendChild(firstBtn);
                    
                    if (startPage > 2) {
                        const dots = document.createElement("span");
                        dots.innerText = "...";
                        dots.style.color = "rgba(255,255,255,0.4)";
                        dots.style.padding = "0 0.25rem";
                        container.appendChild(dots);
                    }
                }

                for (let i = startPage; i <= endPage; i++) {
                    const btn = document.createElement("button");
                    btn.className = `btn-page ${i === this.currentPage ? 'active' : ''}`;
                    btn.innerText = i;
                    btn.onclick = () => {
                        this.currentPage = i;
                        this.fetchFunds();
                    };
                    container.appendChild(btn);
                }

                if (endPage < totalPages) {
                    if (endPage < totalPages - 1) {
                        const dots = document.createElement("span");
                        dots.innerText = "...";
                        dots.style.color = "rgba(255,255,255,0.4)";
                        dots.style.padding = "0 0.25rem";
                        container.appendChild(dots);
                    }
                    const lastBtn = document.createElement("button");
                    lastBtn.className = "btn-page";
                    lastBtn.innerText = totalPages;
                    lastBtn.onclick = () => {
                        this.currentPage = totalPages;
                        this.fetchFunds();
                    };
                    container.appendChild(lastBtn);
                }

                const nextBtn = document.createElement("button");
                nextBtn.className = "btn-page";
                nextBtn.innerText = "Next";
                nextBtn.disabled = this.currentPage === totalPages;
                nextBtn.onclick = () => {
                    this.currentPage++;
                    this.fetchFunds();
                };
                container.appendChild(nextBtn);
            },

            search() {
                this.top10Mode = false;
                this.updateTop10ButtonUI();
                this.currentPage = 1;
                this.fetchFunds();
            },

            filterCategory() {
                this.top10Mode = false;
                this.updateTop10ButtonUI();
                this.currentPage = 1;
                this.fetchFunds();
            },

            toggleTop10() {
                this.top10Mode = !this.top10Mode;
                this.updateTop10ButtonUI();
                this.currentPage = 1;
                this.fetchFunds();
            },

            updateTop10ButtonUI() {
                const btn = document.getElementById("btn-top10-funds");
                if (this.top10Mode) {
                    btn.style.background = "var(--accent)";
                    btn.style.borderColor = "var(--accent)";
                    btn.style.color = "#fff";
                    btn.style.boxShadow = "var(--accent-glow)";
                } else {
                    btn.style.background = "rgba(255,255,255,0.02)";
                    btn.style.borderColor = "rgba(255,255,255,0.08)";
                    btn.style.color = "#cbd5e1";
                    btn.style.boxShadow = "none";
                }
            }
        };

        const DetailsController = {
            currentAmfi: '',
            fundInfo: null,
            chart: null,
            chartMode: 'nav',

            async loadFund(amfiCode) {
                this.currentAmfi = amfiCode;
                
                const tab = document.getElementById("fund-subtab-details");
                if (tab) tab.style.display = "inline-block";
                
                FundsController.switchSubView('details');
                
                const loader = document.getElementById("detail-scheme-name");
                loader.innerText = "Loading details...";
                
                try {
                    const response = await fetch(`/api/funds/${amfiCode}`);
                    if (!response.ok) throw new Error("Failed to load details");
                    const data = await response.json();
                    this.fundInfo = data;
                    
                    document.getElementById("detail-scheme-name").innerText = data.scheme_name;
                    document.getElementById("detail-category").innerText = `${data.category} - ${data.sub_category}`;
                    document.getElementById("detail-aum").innerText = `₹${data.aum.toLocaleString('en-IN')} Cr`;
                    document.getElementById("detail-expense").innerText = `${data.expense_ratio}%`;
                    document.getElementById("detail-manager").innerText = data.fund_manager;
                    document.getElementById("detail-risk").innerText = data.risk_rating;
                    
                    const rEl = document.getElementById("detail-risk");
                    rEl.className = "meta-val";
                    if (data.risk_rating.includes("Very High")) rEl.classList.add("risk-very-high");
                    else if (data.risk_rating.includes("High")) rEl.classList.add("risk-high");
                    else rEl.classList.add("risk-moderate");
                    
                    document.getElementById("detail-stars").innerText = '★'.repeat(data.star_rating) + '☆'.repeat(5 - data.star_rating);
                    
                    document.getElementById("detail-volatility").innerText = `${data.stats.volatility}%`;
                    document.getElementById("detail-sharpe").innerText = data.stats.sharpe_ratio;
                    document.getElementById("detail-beta").innerText = data.stats.beta;
                    document.getElementById("detail-alpha").innerText = `${data.stats.alpha >= 0 ? '+' : ''}${data.stats.alpha}%`;
                    
                    this.renderHoldings(data.portfolio);
                    
                    this.chartMode = 'nav';
                    document.getElementById("chart-tab-nav").classList.add("active");
                    document.getElementById("chart-tab-predict").classList.remove("active");
                    this.renderChart();
                    
                    this.loadPredictionMetrics();
                    
                } catch (err) {
                    console.error("Error loading fund details:", err);
                    document.getElementById("detail-scheme-name").innerText = "Error loading details.";
                }
            },

            renderHoldings(holdings) {
                const tbody = document.getElementById("holdings-table-body");
                tbody.innerHTML = "";
                
                holdings.forEach(h => {
                    const tr = document.createElement("tr");
                    tr.innerHTML = `
                        <td style="color:#fff; font-weight:500;">${h.asset_name}</td>
                        <td>${h.sector}</td>
                        <td class="font-accent font-bold">${h.allocation_pct}%</td>
                    `;
                    tbody.appendChild(tr);
                });
            },

            async loadPredictionMetrics() {
                try {
                    const response = await fetch(`/api/funds/predict?amfi_code=${this.currentAmfi}&years=5`);
                    if (!response.ok) throw new Error("Prediction API error");
                    const data = await response.json();
                    
                    const preds = data.predictions;
                    const p1y = preds[Math.min(50, preds.length - 1)].expected;
                    const p3y = preds[Math.min(150, preds.length - 1)].expected;
                    const p5y = preds[preds.length - 1].expected;
                    
                    document.getElementById("pred-current-val").innerText = `₹${data.last_price.toFixed(2)}`;
                    document.getElementById("pred-1y-val").innerText = `₹${p1y.toFixed(2)}`;
                    document.getElementById("pred-3y-val").innerText = `₹${p3y.toFixed(2)}`;
                    document.getElementById("pred-5y-val").innerText = `₹${p5y.toFixed(2)}`;
                    
                } catch (err) {
                    console.error("Error loading predictions summary:", err);
                }
            },

            async renderChart() {
                const ctx = document.getElementById("detailsChart").getContext("2d");
                if (this.chart) this.chart.destroy();

                if (this.chartMode === 'nav') {
                    const labels = this.fundInfo.nav_history.map(item => item.date);
                    const prices = this.fundInfo.nav_history.map(item => item.price);

                    this.chart = new Chart(ctx, {
                        type: 'line',
                        data: {
                            labels: labels,
                            datasets: [{
                                label: 'Net Asset Value (NAV)',
                                data: prices,
                                borderColor: '#00d09c',
                                borderWidth: 2,
                                backgroundColor: 'rgba(0, 208, 156, 0.05)',
                                fill: true,
                                tension: 0.1,
                                pointRadius: 0
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: { display: false }
                            },
                            scales: {
                                x: {
                                    grid: { color: 'rgba(255, 255, 255, 0.02)' },
                                    ticks: { color: '#94a3b8', font: { size: 9 } }
                                },
                                y: {
                                    grid: { color: 'rgba(255, 255, 255, 0.02)' },
                                    ticks: { color: '#94a3b8', font: { size: 9 } }
                                }
                            }
                        }
                    });
                } else {
                    try {
                        const response = await fetch(`/api/funds/predict?amfi_code=${this.currentAmfi}&years=5`);
                        if (!response.ok) throw new Error("Failed to load predictions chart data");
                        const data = await response.json();
                        
                        const labels = data.predictions.map(item => item.date);
                        const expected = data.predictions.map(item => item.expected);
                        const optimistic = data.predictions.map(item => item.optimistic);
                        const pessimistic = data.predictions.map(item => item.pessimistic);
                        
                        this.chart = new Chart(ctx, {
                            type: 'line',
                            data: {
                                labels: labels,
                                datasets: [
                                    {
                                        label: 'Optimistic Projection',
                                        data: optimistic,
                                        borderColor: 'rgba(59, 130, 246, 0.4)',
                                        borderDash: [5, 5],
                                        borderWidth: 1,
                                        fill: false,
                                        pointRadius: 0
                                    },
                                    {
                                        label: 'Expected Trend',
                                        data: expected,
                                        borderColor: '#00d09c',
                                        borderWidth: 2,
                                        fill: false,
                                        pointRadius: 0
                                    },
                                    {
                                        label: 'Pessimistic Projection',
                                        data: pessimistic,
                                        borderColor: 'rgba(239, 68, 68, 0.4)',
                                        borderDash: [5, 5],
                                        borderWidth: 1,
                                        fill: false,
                                        pointRadius: 0
                                    }
                                ]
                            },
                            options: {
                                responsive: true,
                                maintainAspectRatio: false,
                                plugins: {
                                    legend: {
                                        display: true,
                                        labels: { color: '#e2e8f0', font: { size: 9 } }
                                    }
                                },
                                scales: {
                                    x: {
                                        grid: { color: 'rgba(255, 255, 255, 0.02)' },
                                        ticks: { color: '#94a3b8', font: { size: 9 } }
                                    },
                                    y: {
                                        grid: { color: 'rgba(255, 255, 255, 0.02)' },
                                        ticks: { color: '#94a3b8', font: { size: 9 } }
                                    }
                                }
                            }
                        });
                    } catch (err) {
                        console.error("Error drawing prediction chart:", err);
                    }
                }
            },

            switchChartMode(mode) {
                this.chartMode = mode;
                
                document.getElementById("chart-tab-nav").classList.remove("active");
                document.getElementById("chart-tab-predict").classList.remove("active");
                
                if (mode === 'nav') {
                    document.getElementById("chart-tab-nav").classList.add("active");
                } else {
                    document.getElementById("chart-tab-predict").classList.add("active");
                }
                
                this.renderChart();
            }
        };

        const CompareController = {
            initialized: false,
            fundsList: [],

            async init() {
                if (this.initialized) return;
                
                try {
                    const response = await fetch("/api/funds?limit=100");
                    if (!response.ok) throw new Error("Failed to load options");
                    const data = await response.json();
                    this.fundsList = data.funds || [];
                    
                    this.populateSelects();
                    this.initialized = true;
                } catch (err) {
                    console.error("Error initializing compare select options:", err);
                }
            },

            populateSelects() {
                const s1 = document.getElementById("compare-select-1");
                const s2 = document.getElementById("compare-select-2");
                
                s1.innerHTML = '<option value="">Choose First Scheme...</option>';
                s2.innerHTML = '<option value="">Choose Second Scheme...</option>';
                
                this.fundsList.forEach(f => {
                    const opt1 = `<option value="${f.amfi_code}">${f.scheme_name}</option>`;
                    const opt2 = `<option value="${f.amfi_code}">${f.scheme_name}</option>`;
                    s1.innerHTML += opt1;
                    s2.innerHTML += opt2;
                });
            },

            async compare() {
                const c1 = document.getElementById("compare-select-1").value;
                const c2 = document.getElementById("compare-select-2").value;
                
                const resultDiv = document.getElementById("compare-result");
                
                if (!c1 || !c2) {
                    resultDiv.style.display = "none";
                    return;
                }
                
                try {
                    const response = await fetch(`/api/funds/compare?codes=${c1}&codes=${c2}`);
                    if (!response.ok) throw new Error("Compare API error");
                    const data = await response.json();
                    
                    resultDiv.style.display = "block";
                    
                    const overlapVal = document.getElementById("compare-overlap-val");
                    overlapVal.innerText = `${data.overlap_pct}%`;
                    
                    const overlapRating = document.getElementById("compare-overlap-rating");
                    if (data.overlap_pct > 50) {
                        overlapRating.innerText = "High Concentration";
                        overlapRating.style.color = "var(--danger)";
                    } else if (data.overlap_pct > 25) {
                        overlapRating.innerText = "Moderate Overlap";
                        overlapRating.style.color = "var(--warning)";
                    } else {
                        overlapRating.innerText = "Well Diversified";
                        overlapRating.style.color = "var(--accent)";
                    }
                    
                    this.renderCompareColumn(data.schemes[0], 1);
                    this.renderCompareColumn(data.schemes[1], 2);
                    
                } catch (err) {
                    console.error("Error executing comparison:", err);
                    alert("Error running comparison. Please try again.");
                }
            },

            renderCompareColumn(scheme, colIndex) {
                const col = document.getElementById(`compare-fund-col-${colIndex}`);
                const stats = scheme.stats || {};
                col.innerHTML = `
                    <h3 style="font-size:0.78rem; font-weight:600; color:#fff; line-height:1.3; border-bottom:1px solid var(--border); padding-bottom:0.4rem;">${scheme.scheme_name}</h3>
                    <div class="metadata-list">
                        <div class="meta-item">
                            <span class="meta-label">Category</span>
                            <span>${scheme.category} (${scheme.sub_category})</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">Expense Ratio</span>
                            <span class="font-bold">${scheme.expense_ratio}%</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">AUM</span>
                            <span class="font-bold">₹${scheme.aum.toLocaleString('en-IN')} Cr</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">1-Year Return</span>
                            <span class="font-accent font-bold">${stats.return_1y || '0.0'}%</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">3-Year CAGR</span>
                            <span class="font-accent font-bold">${stats.return_3y || '0.0'}%</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">5-Year CAGR</span>
                            <span class="font-accent font-bold">${stats.return_5y || '0.0'}%</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">Volatility</span>
                            <span>${stats.volatility || '0.0'}%</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">Sharpe Ratio</span>
                            <span class="font-bold">${stats.sharpe_ratio || '0.0'}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">Beta</span>
                            <span>${stats.beta || '1.0'}</span>
                        </div>
                    </div>
                `;
            }
        };

        const CalculatorController = {
            initialized: false,
            calcType: 'sip',
            chart: null,

            init() {
                if (this.initialized) return;
                this.initialized = true;
                this.calculate();
            },

            switchType(type) {
                this.calcType = type;
                
                document.getElementById("calc-tab-sip").classList.remove("active");
                document.getElementById("calc-tab-lumpsum").classList.remove("active");
                
                const label = document.getElementById("calc-amount-label");
                
                if (type === 'sip') {
                    document.getElementById("calc-tab-sip").classList.add("active");
                    label.innerText = "Monthly Investment";
                } else {
                    document.getElementById("calc-tab-lumpsum").classList.add("active");
                    label.innerText = "Total Lumpsum Investment";
                }
                
                this.calculate();
            },

            calculate() {
                const amount = parseFloat(document.getElementById("calc-amount").value);
                const rate = parseFloat(document.getElementById("calc-rate").value);
                const years = parseInt(document.getElementById("calc-years").value);
                
                document.getElementById("slider-amount-txt").innerText = `₹${amount.toLocaleString('en-IN')}`;
                document.getElementById("slider-rate-txt").innerText = `${rate}%`;
                document.getElementById("slider-years-txt").innerText = `${years} Years`;
                
                let principal = 0;
                let wealth = 0;
                
                if (this.calcType === 'sip') {
                    principal = amount * 12 * years;
                    const monthlyRate = (rate / 12) / 100;
                    const months = years * 12;
                    wealth = amount * ((Math.pow(1 + monthlyRate, months) - 1) / monthlyRate) * (1 + monthlyRate);
                } else {
                    principal = amount;
                    wealth = amount * Math.pow(1 + (rate / 100), years);
                }
                
                const estReturns = wealth - principal;
                
                document.getElementById("calc-total-invested").innerText = `₹${Math.round(principal).toLocaleString('en-IN')}`;
                document.getElementById("calc-total-returns").innerText = `₹${Math.round(estReturns).toLocaleString('en-IN')}`;
                document.getElementById("calc-total-wealth").innerText = `₹${Math.round(wealth).toLocaleString('en-IN')}`;
                
                this.renderChart(principal, estReturns);
            },

            renderChart(principal, returns) {
                const ctx = document.getElementById("calculatorChart").getContext("2d");
                if (this.chart) this.chart.destroy();
                
                this.chart = new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: ['Invested Principal', 'Estimated Returns'],
                        datasets: [{
                            data: [principal, returns],
                            backgroundColor: ['#171c26', '#00d09c'],
                            borderColor: 'rgba(255, 255, 255, 0.05)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: {
                                position: 'bottom',
                                labels: { color: '#94a3b8', font: { size: 9 } }
                            }
                        },
                        cutout: '65%'
                    }
                });
            }
        };

        // --- 8. Initialize Router on Load ---
        document.addEventListener("DOMContentLoaded", () => {
            Router.init();
        });

// --- 9. RAG AI Copilot Controller ---
window.toggleRAGDrawer = function() {
    const drawer = document.getElementById("rag-floating-drawer");
    if (drawer) {
        if (drawer.style.display === "none" || !drawer.style.display) {
            drawer.style.display = "flex";
        } else {
            drawer.style.display = "none";
        }
    }
};

window.sendRAGQueryDrawer = function(text) {
    const input = document.getElementById("rag-drawer-input");
    if (input) {
        input.value = text;
        const form = input.closest("form");
        if (form) {
            form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
        }
    }
};

window.handleRAGSubmitDrawer = async function(event) {
    event.preventDefault();
    const input = document.getElementById("rag-drawer-input");
    const sendBtn = document.getElementById("rag-drawer-send-btn");
    const chatHistory = document.getElementById("rag-drawer-chat-history");

    const query = input.value.trim();
    if (!query) return;

    // Append User Message
    const userMsgDiv = document.createElement("div");
    userMsgDiv.style.cssText = "display: flex; gap: 0.5rem; justify-content: flex-end;";
    userMsgDiv.innerHTML = `
        <div style="background: #4f46e5; color: #fff; padding: 0.6rem 0.85rem; border-radius: 10px; font-size: 0.75rem; max-width: 85%;">
            ${escapeHTML(query)}
        </div>
    `;
    chatHistory.appendChild(userMsgDiv);
    input.value = "";
    chatHistory.scrollTop = chatHistory.scrollHeight;

    sendBtn.disabled = true;
    sendBtn.innerHTML = "...";

    const aiMsgDiv = document.createElement("div");
    aiMsgDiv.style.cssText = "display: flex; gap: 0.5rem; background: rgba(99,102,241,0.1); padding: 0.6rem; border-radius: 10px; border: 1px solid rgba(99,102,241,0.2);";
    aiMsgDiv.innerHTML = `
        <span style="font-size: 1rem;">👳‍♂️</span>
        <div style="font-size: 0.75rem; color: #94a3b8; font-style: italic;">Mota Bhai is analyzing RAG context...</div>
    `;
    chatHistory.appendChild(aiMsgDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;

    try {
        const response = await fetch('/api/ai/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: query })
        });
        const data = await response.json();

        if (data.error) {
            aiMsgDiv.querySelector("div:last-child").innerHTML = `<span style="color: #ef4444;">Error: ${escapeHTML(data.error)}</span>`;
        } else {
            let ansContent = formatRAGAnswerToHTML(data.answer);
            const tokenTag = data.cached ? "0 Tokens (Cached ⚡)" : `${data.estimated_tokens_used || 150} Tokens`;
            ansContent += `<div style="font-size: 0.6rem; color: #34d399; margin-top: 0.5rem; font-weight: 600;">⚡ ${tokenTag}</div>`;
            aiMsgDiv.querySelector("div:last-child").innerHTML = ansContent;
        }
    } catch (err) {
        aiMsgDiv.querySelector("div:last-child").innerHTML = `<span style="color: #ef4444;">Network error.</span>`;
    } finally {
        sendBtn.disabled = false;
        sendBtn.innerHTML = "Send ➔";
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }
};

window.sendRAGQuery = function(queryText) {
    const input = document.getElementById("rag-input");
    if (input) {
        input.value = queryText;
        const form = document.getElementById("rag-query-form");
        if (form) {
            form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
        }
    }
};

window.handleRAGSubmit = async function(event) {
    event.preventDefault();
    const input = document.getElementById("rag-input");
    const sendBtn = document.getElementById("rag-send-btn");
    const chatHistory = document.getElementById("rag-chat-history");
    const savingsVal = document.getElementById("rag-savings-val");

    const query = input.value.trim();
    if (!query) return;

    // Append User Message
    const userMsgDiv = document.createElement("div");
    userMsgDiv.className = "rag-msg rag-msg-user";
    userMsgDiv.style.cssText = "display: flex; gap: 0.75rem; justify-content: flex-end; align-items: flex-start;";
    userMsgDiv.innerHTML = `
        <div style="background: rgba(99,102,241,0.25); color: #fff; padding: 0.75rem 1rem; border-radius: 12px; border: 1px solid rgba(99,102,241,0.4); max-width: 80%;">
            <strong>You:</strong> ${escapeHTML(query)}
        </div>
        <div style="font-size: 1.2rem;">👤</div>
    `;
    chatHistory.appendChild(userMsgDiv);
    input.value = "";
    chatHistory.scrollTop = chatHistory.scrollHeight;

    // Loading State
    sendBtn.disabled = true;
    sendBtn.innerHTML = "Processing...";

    const aiMsgDiv = document.createElement("div");
    aiMsgDiv.className = "rag-msg rag-msg-ai";
    aiMsgDiv.style.cssText = "display: flex; gap: 0.75rem; background: rgba(99,102,241,0.08); padding: 0.85rem; border-radius: 10px; border: 1px solid rgba(99,102,241,0.2);";
    aiMsgDiv.innerHTML = `
        <div style="font-size: 1.2rem;">🤖</div>
        <div style="flex: 1;">
            <p style="color: var(--text-secondary); font-style: italic;">Retrieving relevant data & compressing context...</p>
        </div>
    `;
    chatHistory.appendChild(aiMsgDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;

    try {
        const response = await fetch('/api/ai/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: query })
        });
        const data = await response.json();

        if (data.error) {
            aiMsgDiv.querySelector("div:last-child").innerHTML = `<p style="color: var(--danger);">Error: ${escapeHTML(data.error)}</p>`;
        } else {
            let ansContent = formatRAGAnswerToHTML(data.answer);
            aiMsgDiv.querySelector("div:last-child").innerHTML = ansContent;

            if (data.cached) {
                savingsVal.innerText = "0 Tokens (Cached ⚡)";
                savingsVal.style.color = "#34d399";
            } else {
                savingsVal.innerText = `${data.estimated_tokens_used || 150} Tokens (Compressed)`;
                savingsVal.style.color = "#60a5fa";
            }
        }
    } catch (err) {
        aiMsgDiv.querySelector("div:last-child").innerHTML = `<p style="color: var(--danger);">Network error querying AI Copilot.</p>`;
    } finally {
        sendBtn.disabled = false;
        sendBtn.innerHTML = "Send ➔";
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }
};

function formatRAGAnswerToHTML(answer) {
    if (answer === null || answer === undefined) {
        return '<p style="color:var(--text-secondary);">No response returned.</p>';
    }

    function formatValue(val) {
        if (val === null || val === undefined) return '';
        if (typeof val === 'object') {
            if (Array.isArray(val)) {
                return val.map(formatValue).join(', ');
            }
            return Object.entries(val)
                .map(([k, v]) => `<span style="color:#a5b4fc; font-weight:600;">${escapeHTML(k)}:</span> <span style="color:#fff;">${escapeHTML(typeof v === 'object' ? JSON.stringify(v) : String(v))}</span>`)
                .join(' | ');
        }
        return escapeHTML(String(val));
    }
    
    if (typeof answer === 'string') {
        const lines = answer.split('\n').filter(l => l.trim().length > 0);
        let html = '';
        lines.forEach(line => {
            const clean = line.trim();
            if (clean.startsWith('-') || clean.startsWith('*')) {
                html += `<li style="margin-bottom:0.25rem;">${escapeHTML(clean.substring(1).trim())}</li>`;
            } else {
                html += `<p style="margin-bottom:0.4rem;">${escapeHTML(clean)}</p>`;
            }
        });
        return html;
    }
    
    if (typeof answer === 'object') {
        let html = '';
        if (answer.answer) {
            html += `<p style="font-weight:600; color:#fff; margin-bottom:0.4rem;">${escapeHTML(String(answer.answer))}</p>`;
        }
        if (Array.isArray(answer.details)) {
            html += '<ul style="margin-top:0.3rem; padding-left:1.2rem; color:#cbd5e1;">';
            answer.details.forEach(d => {
                html += `<li style="margin-bottom:0.35rem; font-size:0.75rem;">${formatValue(d)}</li>`;
            });
            html += '</ul>';
        }
        
        for (const [key, value] of Object.entries(answer)) {
            if (key === 'answer' || key === 'details') continue;
            
            const title = key.replace(/_/g, ' ').toUpperCase();
            html += `<div style="margin-top:0.5rem;"><strong style="color:#a5b4fc; font-size:0.88rem;">${escapeHTML(title)}:</strong>`;
            
            if (Array.isArray(value)) {
                html += '<ul style="margin-top:0.25rem; padding-left:1.2rem; color:#e2e8f0;">';
                value.forEach(item => {
                    html += `<li style="margin-bottom:0.35rem; font-size:0.75rem;">${formatValue(item)}</li>`;
                });
                html += '</ul>';
            } else if (typeof value === 'object' && value !== null) {
                html += `<div style="margin-top:0.2rem; font-size:0.75rem; color:#e2e8f0;">${formatValue(value)}</div>`;
            } else {
                html += `<span style="color:#fff; margin-left:0.4rem; font-weight:600;">${escapeHTML(String(value))}</span>`;
            }
            html += '</div>';
        }
        return html || `<p style="color:#fff;">${escapeHTML(JSON.stringify(answer))}</p>`;
    }
    
    return `<p style="color:#fff;">${escapeHTML(String(answer))}</p>`;
}

function escapeHTML(str) {
    return str.replace(/[&<>'"]/g, 
        tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
    );
}

        // --- 1. Router & Tab Switching System ---
        const Router = {
            routes: ['volume', 'deals', 'growth', 'news'],
            init() {
                // Add admin route if user is entitled
                if (window.ProTradeConfig && window.ProTradeConfig.user && window.ProTradeConfig.user.entitlements.includes('stock_admin')) {
                    if (!this.routes.includes('admin')) {
                        this.routes.push('admin');
                    }
                }
                // Determine initial view based on URL path
                let path = window.location.pathname.replace('/', '').toLowerCase();
                if (!this.routes.includes(path)) {
                    path = 'volume';
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
                        path = 'volume';
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

                this.loadDeals('/api/deals/block', 'block');
                this.loadDeals('/api/deals/bulk', 'bulk');
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

            async loadDeals(endpoint, type) {
                try {
                    const res = await fetch(endpoint);
                    this.tableData[type].data = await res.json();

                    document.getElementById(`${type}-loading`).style.display = 'none';
                    document.getElementById(`${type}-table`).style.display = 'table';
                    document.getElementById(`${type}-pagination`).style.display = 'flex';

                    if (this.tableData[type].data.length === 0) {
                        document.getElementById(`${type}-body`).innerHTML = `<tr><td colspan="6" style="text-align:center;">No data found.</td></tr>`;
                        document.getElementById(`${type}-pagination`).style.display = 'none';
                        return;
                    }
                    this.renderTable(type);
                } catch (err) {
                    document.getElementById(`${type}-loading`).innerText = 'Failed to load data.';
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
                tbody.innerHTML = '<tr><td colspan="6" class="loading">Loading user database...</td></tr>';
                document.getElementById("admin-empty-state").style.display = "none";

                try {
                    const response = await fetch("/api/admin/users");
                    if (!response.ok) throw new Error("Failed to fetch users");
                    const data = await response.json();
                    this.usersData = data;
                    this.renderUsers(data);
                } catch (err) {
                    console.error("Error fetching users list:", err);
                    tbody.innerHTML = '<tr><td colspan="6" class="loading" style="color:var(--danger);">Error loading users list. Forbidden or server offline.</td></tr>';
                }
            },

            renderUsers(users) {
                const tbody = document.getElementById("admin-users-body");
                tbody.innerHTML = "";

                if (users.length === 0) {
                    document.getElementById("admin-empty-state").style.display = "block";
                    return;
                }
                document.getElementById("admin-empty-state").style.display = "none";

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
            }
        };
        // --- 6. Initialize Router on Load ---
        document.addEventListener("DOMContentLoaded", () => {
            Router.init();
        });

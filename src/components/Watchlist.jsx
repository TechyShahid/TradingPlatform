import { useState } from 'react';
import { TrendingUp, TrendingDown, Plus, Trash2, ListPlus, X } from 'lucide-react';
import '../styles/App.css';

const Watchlist = ({
    watchlists,
    activeWatchlist,
    onSelectWatchlist,
    onCreateWatchlist,
    onDeleteWatchlist,
    stocks,
    onSelectStock,
    onAddStock,
    onRemoveStock,
    currentSymbol
}) => {
    const [isAdding, setIsAdding] = useState(false);
    const [newSymbol, setNewSymbol] = useState('');
    const [isCreatingList, setIsCreatingList] = useState(false);
    const [newListName, setNewListName] = useState('');

    const handleAddSubmit = (e) => {
        e.preventDefault();
        if (newSymbol.trim()) {
            onAddStock(newSymbol.toUpperCase().trim());
            setNewSymbol('');
            setIsAdding(false);
        }
    };

    const handleCreateListSubmit = (e) => {
        e.preventDefault();
        if (newListName.trim()) {
            onCreateWatchlist(newListName.trim());
            setNewListName('');
            setIsCreatingList(false);
        }
    };

    return (
        <div className="watchlist-container">
            {/* Header: List Selection */}
            <div className="watchlist-header">
                <div className="watchlist-selector">
                    <select
                        value={activeWatchlist}
                        onChange={(e) => onSelectWatchlist(e.target.value)}
                        className="watchlist-dropdown"
                    >
                        {Object.keys(watchlists).map(name => (
                            <option key={name} value={name}>{name}</option>
                        ))}
                    </select>
                    <button
                        className="icon-btn"
                        title="New Watchlist"
                        onClick={() => setIsCreatingList(!isCreatingList)}
                    >
                        <ListPlus size={18} />
                    </button>
                </div>
                {/* Create List Form */}
                {isCreatingList && (
                    <form onSubmit={handleCreateListSubmit} className="inline-form">
                        <input
                            type="text"
                            placeholder="List Name"
                            value={newListName}
                            onChange={(e) => setNewListName(e.target.value)}
                            autoFocus
                            className="inline-input"
                        />
                        <button type="submit" className="icon-btn small"><Plus size={14} /></button>
                        <button type="button" onClick={() => setIsCreatingList(false)} className="icon-btn small"><X size={14} /></button>
                    </form>
                )}
            </div>

            {/* Add Symbol Bar */}
            <div className="watchlist-actions">
                {!isAdding ? (
                    <button className="add-btn" onClick={() => setIsAdding(true)}>
                        <Plus size={16} /> Add Symbol
                    </button>
                ) : (
                    <form onSubmit={handleAddSubmit} className="add-form">
                        <input
                            type="text"
                            placeholder="Symbol (e.g. INFY)"
                            value={newSymbol}
                            onChange={(e) => setNewSymbol(e.target.value)}
                            autoFocus
                            className="symbol-input"
                        />
                        <button type="submit" className="icon-btn"><Plus size={16} /></button>
                        <button type="button" onClick={() => setIsAdding(false)} className="icon-btn"><X size={16} /></button>
                    </form>
                )}
            </div>

            <div className="watchlist-items">
                {stocks.length === 0 ? (
                    <div className="empty-state">No stocks in this list</div>
                ) : (
                    stocks.map((stock) => {
                        const isPositive = stock.change >= 0;
                        const isSelected = currentSymbol === stock.symbol;

                        return (
                            <div
                                key={stock.symbol}
                                className={`watchlist-item ${isSelected ? 'active' : ''}`}
                                onClick={() => onSelectStock(stock.symbol)}
                            >
                                <div className="item-left">
                                    <span className="stock-symbol">{stock.symbol}</span>
                                    <span className="stock-price">{stock.price ? stock.price.toFixed(2) : '-'}</span>
                                </div>
                                <div className={`item-right ${isPositive ? 'success' : 'danger'}`}>
                                    <span className="stock-change">
                                        {stock.change ? (isPositive ? '+' : '') + stock.change.toFixed(2) : '-'}
                                    </span>
                                    <span className="stock-percent">
                                        {stock.changePercent ? (isPositive ? '+' : '') + stock.changePercent.toFixed(2) + '%' : '-'}
                                    </span>
                                </div>
                                <button
                                    className="delete-btn"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onRemoveStock(stock.symbol);
                                    }}
                                >
                                    <Trash2 size={14} />
                                </button>
                            </div>
                        );
                    })
                )}
            </div>
        </div>
    );
};

export default Watchlist;

import yfinance as yf
ticker = yf.Ticker('RELIANCE.NS')
fin = ticker.financials
bs = ticker.balance_sheet
print("Financials columns:", fin.columns)
if len(fin.columns) >= 4:
    print("Net Income over 4 years:")
    try:
        print(fin.loc['Net Income'])
    except:
        print("No Net Income")

"""
market.py — Daily stock price simulation.
"""
import random
import data


class stockMarket:
    # (recession_mu, recession_sigma, bull_mu, bull_sigma) per company
    _PARAMS = [
        (-0.018, 0.0300, 0.018, 0.0300),   # TechCorp  – high volatility
        (-0.010, 0.0200, 0.010, 0.0200),  # RetailCo
        (-0.008, 0.0150, 0.008, 0.0150),  # MidCap
        (-0.004, 0.0100, 0.004, 0.0100),  # StableCo
        (-0.002, 0.0040, 0.002, 0.0040),  # BondProxy – low volatility
    ]

    def make_market(self, turn):
        rec = data.indics.recession
        for i, (rm, rs, bm, bs) in enumerate(self._PARAMS):
            mu    = rm if rec else bm
            sigma = rs if rec else bs
            prev  = data.stock_markets.companies[i][turn - 1]
            new_p = max(0.01, prev * (1 + random.gauss(mu, sigma)))
            data.stock_markets.companies[i].append(new_p)


funny_market = stockMarket()
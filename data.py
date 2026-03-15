"""
data.py — Stock market prices and macroeconomic indicators.
"""
import random


class Companies:
    def __init__(self, initial_prices):
        self.companies = [[float(p)] for p in initial_prices]


class indicators:
    def __init__(self, bs, bl, u, g, c, r):
        self.bondYields3Months  = [bs]
        self.bondYields5yrs     = [bl]
        self.unemployment       = [u]
        self.gdp                = [g]
        self.consumption        = [c]
        self.recession          = r
        self.recession_duration = 0   # turns spent in recession

    def summarise(self):
        return (
            f"{'In' if self.recession else 'Not in'} a recession. "
            f"Unemployment: {self.unemployment[-1]*100:.1f}%. "
            f"GDP growth: {self.gdp[-1]*100:.2f}%. "
            f"Short bond: {self.bondYields3Months[-1]*100:.2f}%. "
            f"Long bond: {self.bondYields5yrs[-1]*100:.2f}%."
        )

    def updateIndicators(self):
        def clamp(v, lo, hi): return max(lo, min(v, hi))
        if self.recession:
            # Recovery: central bank cuts → short falls; growth returns → long rises
            self.recession_duration += 1
            sc = random.gauss(-0.00045, 0.00018)   # short bond falling  (~-1.8% over 40t)
            lc = random.gauss( 0.00035, 0.00015)   # long bond rising    (~+1.4% over 40t)
            uc = random.gauss(-0.000080, 0.00040)   # unemployment falling
            gc = random.gauss( 0.000150, 0.00080)   # GDP recovering
            cc = random.gauss( 0.000150, 0.00080)   # consumption recovering
            # Recession ends after minimum 20 turns, then ~5% chance/turn
            if self.recession_duration >= 20 and random.random() < 0.05:
                self.recession          = False
                self.recession_duration = 0
        else:
            # Pre-recession: short rises from 1% toward 3% cap (~120 turns to converge)
            #                long  falls from 4.5% toward ~2%   (yield curve flattens/inverts)
            sc = random.gauss( 0.00015, 0.00008)   # short rising  (~+1.8% over 120t)
            lc = random.gauss(-0.00020, 0.00010)   # long  falling (~-2.4% over 120t)
            uc = random.gauss( 0.000080, 0.00040)   # unemployment rising
            gc = random.gauss(-0.000120, 0.00080)   # GDP falling
            cc = random.gauss(-0.000120, 0.00080)   # consumption falling

        # Short bond capped at 3%, long bond capped at 5%
        self.bondYields3Months.append(clamp(self.bondYields3Months[-1]+sc, 0.0,  0.03))
        self.bondYields5yrs.append(   clamp(self.bondYields5yrs[-1]   +lc, 0.0,  0.05))
        self.unemployment.append(     clamp(self.unemployment[-1]     +uc, 0.02, 0.15))
        self.gdp.append(              clamp(self.gdp[-1]              +gc,-0.08, 0.08))
        self.consumption.append(      clamp(self.consumption[-1]      +cc,-0.05, 0.06))

    def recessionTrigger(self, threshold=0.20):
        """
        Trigger recession when the yield curve inverts (short bond ≥ long bond)
        AND at least 2 of: unemployment elevated, GDP negative, consumption weak.
        This naturally follows from updateIndicators' pre-recession dynamics.
        """
        if self.recession: return                    # already in one
        if len(self.bondYields3Months) < 5: return  # need a few turns of data

        short = self.bondYields3Months[-1]
        long_ = self.bondYields5yrs[-1]

        # Yield curve inversion: short has caught up to or crossed long
        inverted   = short >= long_ * 0.92
        gdp_neg    = self.gdp[-1]          < 0.000
        unemp_high = self.unemployment[-1] > 0.055
        cons_weak  = self.consumption[-1]  < 0.005

        if inverted and sum([gdp_neg, unemp_high, cons_weak]) >= 2:
            self.recession = True


stock_markets = Companies([1.0, 10.0, 25.0, 35.0, 50.0])
indics        = indicators(bs=0.010, bl=0.045, u=0.042, g=0.018, c=0.025, r=False)


def reset():
    global stock_markets, indics
    stock_markets = Companies([1.0, 10.0, 25.0, 35.0, 50.0])
    indics        = indicators(bs=0.010, bl=0.045, u=0.042, g=0.018, c=0.025, r=False)
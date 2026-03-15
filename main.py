"""
Controls:
  Mouse        — click everything
  1-5          — switch chart stock (Stocks view)
  Tab / G      — toggle Stocks ↔ Economy view
  E            — end day
  Esc          — close modal
  R            — restart (game-over screen)
"""

import pygame
import sys
import random
import math
import threading
import data
import market

try:
    import ai_funcs
    AI_OK = True
except Exception:
    AI_OK = False

# ─── Init ─────────────────────────────────────────────────────────────────────
pygame.init()
W, H = 1280, 750
screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("EconSim — Don't Go Bankrupt")
clock  = pygame.time.Clock()
FPS    = 60

# ─── Layout ───────────────────────────────────────────────────────────────────
HDR_H   = 56
BOT_H   = 128
MAIN_H  = H - HDR_H - BOT_H        # 566
LEFT_W  = 268
RGT_W   = 316
MID_W   = W - LEFT_W - RGT_W       # 696
TAB_H   = 26
CHART_H = 252
TABLE_H = MAIN_H - TAB_H - CHART_H - 4

MAX_TURNS  = 365
NUM_COMPS  = 5
DAILY_INT  = 0.00015   # savings interest per day (~5.5% APR)
EVENT_PROB = 0.14      # chance per turn of a random event

# YAPBOT config
AI_POPUP_TTL      = 380      # frames popup stays visible (~6 s at 60 fps)
AI_MIN_COOLDOWN   = 12       # min turns between advisor comments
AI_MAX_COOLDOWN   = 28       # max turns between advisor comments

# ─── Palette ──────────────────────────────────────────────────────────────────
BG      = (  5, 10, 20)
PANEL   = (  9, 15, 28)
PANEL_D = (  6, 10, 18)
BOR     = ( 22, 40, 70)
BOR_L   = ( 45,100,165)
BOR_H   = (  0,180,220)

TXT     = (168,198,228)
TXD     = ( 55, 82,118)
TXB     = (222,240,255)

GRN     = (  0,222,108)
RED     = (255, 52, 72)
GLD     = (255,192, 48)
CYN     = (  0,192,222)
ORG     = (255,142, 32)
PRP     = (152, 78,255)

CO_C = [CYN, PRP, ORG, GRN, RED]
CO_N = ["TechCorp", "RetailCo", "MidCap", "StableCo", "BondProxy"]

# ─── Fonts ────────────────────────────────────────────────────────────────────
_MONO = "monospace"
for _candidate in ["Consolas", "Courier New", "Lucida Console", "Courier"]:
    if pygame.font.match_font(_candidate):
        _MONO = _candidate
        break

def mf(sz, bold=False):
    return pygame.font.SysFont(_MONO, sz, bold=bold)

F = {
    "huge":  mf(44, True),
    "h1":    mf(20, True),
    "h2":    mf(16, True),
    "h3":    mf(13, True),
    "body":  mf(13),
    "small": mf(11),
    "tiny":  mf(10),
}

# ─── Drawing primitives ───────────────────────────────────────────────────────
def tx(surf, text, fk, col, x, y, align="left"):
    s = F[fk].render(str(text), True, col)
    if   align == "center": x -= s.get_width() // 2
    elif align == "right":  x -= s.get_width()
    surf.blit(s, (x, y))
    return s.get_width()

def hline(surf, x1, x2, y, col=BOR):
    pygame.draw.line(surf, col, (x1, y), (x2, y))

def vline(surf, x, y1, y2, col=BOR):
    pygame.draw.line(surf, col, (x, y1), (x, y2))

def mn(v):
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v):,.2f}"

def pc(v):
    return f"{'+'if v>=0 else''}{v:.2f}%"

def vc(v):
    return GRN if v > 0 else (RED if v < 0 else TXT)

def pbar(surf, r, val, maxv, fg, bg=(18, 28, 52)):
    r = pygame.Rect(r)
    pygame.draw.rect(surf, bg, r, border_radius=3)
    if maxv > 0:
        fill = max(0, min(r.w, int(r.w * val / maxv)))
        if fill > 0:
            pygame.draw.rect(surf, fg, pygame.Rect(r.x, r.y, fill, r.h), border_radius=3)
    pygame.draw.rect(surf, BOR, r, 1, border_radius=3)

def wrap_text(text, fk, max_w):
    words = text.split()
    lines, line = [], ""
    for w in words:
        test = (line + " " + w).strip()
        if F[fk].size(test)[0] <= max_w:
            line = test
        else:
            if line: lines.append(line)
            line = w
    if line: lines.append(line)
    return lines

# ─── Button ───────────────────────────────────────────────────────────────────
class Btn:
    def __init__(self, r, label, nc=(18,32,62), hc=(30,55,110),
                 tc=TXB, fk="h3", disabled=False):
        self.r  = pygame.Rect(r)
        self.label = label
        self.nc = nc;  self.hc = hc
        self.tc = tc;  self.fk = fk
        self.disabled = disabled
        self._hov = False

    def draw(self, surf):
        col = (30,40,60) if self.disabled else (self.hc if self._hov else self.nc)
        tc  = TXD        if self.disabled else self.tc
        bc  = BOR_H if self._hov and not self.disabled else (BOR_L if not self.disabled else BOR)
        pygame.draw.rect(surf, col, self.r, border_radius=4)
        pygame.draw.rect(surf, bc,  self.r, 1, border_radius=4)
        tx(surf, self.label, self.fk, tc,
           self.r.centerx, self.r.centery - F[self.fk].get_height()//2, "center")

    def check(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self._hov = self.r.collidepoint(ev.pos)
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.r.collidepoint(ev.pos) and not self.disabled:
                return True
        return False


# ─── TextInput ────────────────────────────────────────────────────────────────
class TInput:
    def __init__(self, r, ph="0", maxl=8, numeric=True):
        self.r     = pygame.Rect(r)
        self.ph    = ph
        self.maxl  = maxl
        self.num   = numeric
        self.text  = ""
        self.focus = False

    def val(self):
        try:   return int(self.text) if self.num else self.text
        except: return 0

    def clear(self):
        self.text = ""; self.focus = True

    def handle(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN:
            self.focus = self.r.collidepoint(ev.pos)
        if ev.type == pygame.KEYDOWN and self.focus:
            if ev.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif ev.key not in (pygame.K_RETURN, pygame.K_TAB, pygame.K_ESCAPE):
                ch = ev.unicode
                if self.num:
                    if ch.isdigit() and len(self.text) < self.maxl:
                        self.text += ch
                elif len(self.text) < self.maxl:
                    self.text += ch

    def draw(self, surf):
        bc = BOR_H if self.focus else (45, 90, 150)
        pygame.draw.rect(surf, (10,18,35), self.r, border_radius=3)
        pygame.draw.rect(surf, bc, self.r, 1, border_radius=3)
        txt = self.text if self.text else self.ph
        col = TXB if self.text else TXD
        cur = "|" if self.focus and (pygame.time.get_ticks() % 900 < 450) else ""
        tx(surf, txt + cur, "body", col,
           self.r.x + 8, self.r.centery - F["body"].get_height()//2)


# ─── Random Events ────────────────────────────────────────────────────────────
def _ev_bonus(g):     g.checkquing += random.randint(100, 500)
def _ev_medical(g):   g.checkquing -= random.randint(200, 600); g.health = max(0, g.health - random.randint(5,20))
def _ev_car(g):       g.checkquing -= random.randint(80, 350)
def _ev_freelance(g): g.checkquing += random.randint(60, 280)
def _ev_promo(g):     g.salary      = g.salary * 1.15
def _ev_layoff(g):    g.salary      = max(100, g.salary * 0.85)
def _ev_audit(g):     g.checkquing -= random.randint(150, 450)
def _ev_inherit(g):   g.savings    += random.randint(400, 2000)
def _ev_health(g):    g.health      = min(100, g.health + random.randint(10, 25))
def _ev_shock(_g):    pass   # handled separately

EVENTS = [
    ("💰 Salary Bonus!",   "You received a performance bonus.",          GRN,  _ev_bonus),
    ("🏥 Medical Bill",    "An emergency health expense struck.",        RED,  _ev_medical),
    ("🚗 Car Repair",      "Your car needed emergency work.",            ORG,  _ev_car),
    ("💼 Freelance Gig",   "A side project came through!",              CYN,  _ev_freelance),
    ("📈 Promotion!",      "Hard work paid off — salary +15%!",         GLD,  _ev_promo),
    ("📉 Restructuring",   "Company cuts — salary reduced 15%.",        RED,  _ev_layoff),
    ("🧾 Tax Audit",       "The IRS flagged your return.",              RED,  _ev_audit),
    ("🎁 Inheritance",     "A distant relative left you a windfall!",   GLD,  _ev_inherit),
    ("💪 Health Retreat",  "A wellness program restored vitality.",     GRN,  _ev_health),
    ("⚡ Market Shock!",   "Panic selling crashes all stocks hard.",    RED,  _ev_shock),
]


# ─── YAPBOT-9000 Advisor ──────────────────────────────────────────────────────
# Each entry: (trigger_id, human_readable_trigger, condition_fn(game) -> bool, one_shot)
# one_shot=True means it only fires once per game; False = can repeat

YAPBOT_TRIGGERS = [
    # one-shot story beats
    ("recession_start",  "the economy just entered a recession",
     lambda g: data.indics.recession and not g._seen_recession, True),

    ("near_broke",       f"player has less than $150 in checking and almost no savings",
     lambda g: g.checkquing < 150 and g.savings < 100,          True),

    ("health_critical",  "player health has dropped below 20% — they're basically falling apart",
     lambda g: g.health < 20,                                    True),

    ("broke_portfolio",  "player spent basically everything buying stocks and now has $0 in checking",
     lambda g: g.checkquing < 10 and sum(g.portfolio) > 0,       True),

    ("rich",             "player crossed $5000 net worth — they're doing suspiciously well",
     lambda g: g.networth() > 5000,                              True),

    ("day30",   "player survived 30 days",  lambda g: g.turn == 30,  True),
    ("day100",  "player survived 100 days", lambda g: g.turn == 100, True),
    ("day200",  "player survived 200 days", lambda g: g.turn == 200, True),
    ("day300",  "player survived 300 days", lambda g: g.turn == 300, True),
    ("day350",  "player is on day 350, almost done",
     lambda g: g.turn == 350, True),

    ("no_stocks",  "player has zero stocks in their portfolio after many days",
     lambda g: g.turn > 30 and sum(g.portfolio) == 0,            True),

    ("all_eggs",   "over 80% of net worth is in a single stock — dangerous concentration",
     lambda g: _single_stock_dominance(g) > 0.80,                True),

    ("salary_cut",  "player's salary just dropped significantly due to a restructuring event",
     lambda g: g._last_salary_drop,                              False),

    ("lost_money_day",  "player lost money today — net cash flow was negative",
     lambda g: g._last_net_day < -50,                             False),
]

def _single_stock_dominance(g):
    nw = g.networth()
    if nw <= 0: return 0
    return max(g.portfolio[i] * data.stock_markets.companies[i][-1]
               for i in range(NUM_COMPS)) / nw


# ─── Game ─────────────────────────────────────────────────────────────────────
class Game:
    def __init__(self):
        # Player state
        self.turn        = 1
        self.checkquing  = 1000.0
        self.savings     = 500.0
        self.health      = 50.0
        self.career_aura = 50.0
        self.salary      = 220.0
        self.expend      = 160.0
        self.portfolio   = [0] * NUM_COMPS

        # Game flow
        self.state       = "playing"
        self.messages    = []

        # UI
        self.sel_stock   = 0
        self.center_view = "stocks"   # "stocks" | "economy"
        self.sel_econ    = 0          # selected economy chart (0-3) for keyboard nav
        self.modal       = None
        self.modal_co    = 0
        self.modal_msg   = ""
        self.event_popup = None      # game event (top-center)

        # YAPBOT advisor
        self.ai_popup    = None      # {text, ttl, lines} — floating speech bubble
        self.ai_queue    = []        # pending texts to show
        self.ai_loading  = False
        self.ai_cooldown = random.randint(AI_MIN_COOLDOWN, AI_MAX_COOLDOWN)
        self._fired_triggers = set() # one-shot trigger ids already fired

        # State flags for trigger conditions (set each end_of_turn)
        self._seen_recession    = False
        self._last_net_day      = 0.0
        self._last_salary_drop  = False
        # Force a recession somewhere in day 120-150
        self._forced_rec_day    = random.randint(120, 150)

        # Input widgets
        self.inp_qty = TInput((0,0,100,34), ph="0",   maxl=6)
        self.inp_amt = TInput((0,0,100,34), ph="100", maxl=8)

        self._build_buttons()
        self.add_msg("Welcome to EconSim! Survive 365 days without going bankrupt.", CYN)
        self.add_msg(f"Starting capital — Checking: {mn(self.checkquing)},  "
                     f"Savings: {mn(self.savings)}", TXT)

    # ── Button construction ───────────────────────────────────────────────────
    def _build_buttons(self):
        bx = LEFT_W + MID_W + 12
        bw = RGT_W - 24

        self.action_btns = {
            "buy":     Btn((bx, HDR_H+20,  bw, 38), "▲  BUY SHARES",   ( 0,65,42), ( 0,130,80), GRN),
            "sell":    Btn((bx, HDR_H+64,  bw, 38), "▼  SELL SHARES",  (75,18,28), (148,36,52), RED),
            "xfer_cs": Btn((bx, HDR_H+110, bw, 38), "⇒  SAVE MONEY",  (15,35,65), (30,65,120), CYN),
            "xfer_sc": Btn((bx, HDR_H+154, bw, 38), "⇐  WITHDRAW",    (15,35,65), (30,65,120), CYN),
            "end":     Btn((bx, HDR_H + MAIN_H - 74, bw, 66),
                           "⏭  NEXT TURN",  ( 0,90,55), ( 0,170,100), GRN, "h1"),
        }

        cx, cy = W//2, H//2
        mw, mh = 460, 340
        mx, my = cx-mw//2, cy-mh//2
        bw2    = (mw-50)//2
        self.m_ok  = Btn((mx+15,      my+mh-55, bw2, 42), "CONFIRM", ( 0,70,42), ( 0,140,82), GRN)
        self.m_can = Btn((mx+35+bw2,  my+mh-55, bw2, 42), "CANCEL",  (70,16,26), (140,32,50), RED)

        tab_w  = (mw-40) // NUM_COMPS - 3
        self.m_co_btns = []
        for i in range(NUM_COMPS):
            bxi = mx+20 + i*(tab_w+3)
            self.m_co_btns.append(Btn((bxi, my+55, tab_w, 26), CO_N[i][:6]))

        self.modal_r = pygame.Rect(mx, my, mw, mh)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def add_msg(self, text, col=None):
        self.messages.append({"text": text, "col": col or TXT, "turn": self.turn})
        if len(self.messages) > 8:
            self.messages.pop(0)

    def networth(self):
        nw = self.checkquing + self.savings
        for i in range(NUM_COMPS):
            nw += self.portfolio[i] * data.stock_markets.companies[i][-1]
        return nw

    def portfolio_value(self):
        return sum(
            self.portfolio[i] * data.stock_markets.companies[i][-1]
            for i in range(NUM_COMPS)
        )

    def effective_salary(self):
        return self.salary * (0.5 + self.health / 200.0) + self.career_aura * 0.05

    def _game_summary(self):
        return (
            f"Day {self.turn}/{MAX_TURNS}. "
            f"Checking: ${self.checkquing:.0f}, Savings: ${self.savings:.0f}, "
            f"Portfolio value: ${self.portfolio_value():.0f}, "
            f"Net worth: ${self.networth():.0f}. "
            f"Salary: ${self.salary:.0f}/day, Expenses: ${self.expend:.0f}/day. "
            f"Health: {self.health:.0f}/100. "
            f"{'RECESSION in progress.' if data.indics.recession else 'Economy stable.'} "
            f"Unemployment: {data.indics.unemployment[-1]*100:.1f}%."
        )

    # ── Trading ───────────────────────────────────────────────────────────────
    def buy_stock(self, co, qty):
        if qty <= 0: return False, "Enter a valid quantity"
        price = data.stock_markets.companies[co][-1]
        cost  = price * qty
        if cost > self.checkquing:
            return False, f"Need {mn(cost)} but only have {mn(self.checkquing)}"
        self.checkquing    -= cost
        self.portfolio[co] += qty
        self.add_msg(f"Bought {qty}× {CO_N[co]} @ {mn(price)}  (spent {mn(cost)})", GRN)

        # Trigger advisor for large buy (>40% of original checking)
        if cost > 400:
            self._queue_ai_comment(
                f"the player just spent {mn(cost)} buying {qty} shares of {CO_N[co]} "
                f"at {mn(price)} each", forced=True)
        return True, ""

    def sell_stock(self, co, qty):
        if qty <= 0: return False, "Enter a valid quantity"
        if self.portfolio[co] < qty:
            return False, f"Only own {self.portfolio[co]} shares"
        price = data.stock_markets.companies[co][-1]
        gain  = price * qty
        self.checkquing    += gain
        self.portfolio[co] -= qty
        self.add_msg(f"Sold {qty}× {CO_N[co]} @ {mn(price)}  (received {mn(gain)})", GLD)
        # Advisor reacts to panic-sells (selling everything)
        if self.portfolio[co] == 0 and qty > 5:
            self._queue_ai_comment(
                f"the player just panic-sold all {qty} shares of {CO_N[co]} and received {mn(gain)}",
                forced=True)
        return True, ""

    def transfer_cs(self, amt):
        if amt <= 0:              return False, "Enter a valid amount"
        if amt > self.checkquing: return False, f"Only {mn(self.checkquing)} in checking"
        self.checkquing -= amt; self.savings += amt
        self.add_msg(f"Moved {mn(amt)} to savings.", CYN)
        return True, ""

    def transfer_sc(self, amt):
        if amt <= 0:          return False, "Enter a valid amount"
        if amt > self.savings:return False, f"Only {mn(self.savings)} in savings"
        self.savings -= amt; self.checkquing += amt
        self.add_msg(f"Withdrew {mn(amt)} from savings.", CYN)
        return True, ""

    # ── Random events ─────────────────────────────────────────────────────────
    def trigger_event(self):
        name, msg, col, fn = random.choice(EVENTS)
        if fn is _ev_shock:
            for i in range(NUM_COMPS):
                last = data.stock_markets.companies[i][-1]
                data.stock_markets.companies[i][-1] = last * random.uniform(0.90, 0.95)
            self._queue_ai_comment(
                "the market just had a shock event — all stocks crashed 5-10%", forced=True)
        else:
            fn(self)
        self.event_popup = {"title": name, "msg": msg, "col": col, "ttl": 240}
        self.add_msg(f"EVENT ▸ {name}  {msg}", col)

    # ── YAPBOT advisor ────────────────────────────────────────────────────────
    def _queue_ai_comment(self, trigger_desc: str, forced: bool = False):
        """Fire off a background thread to get a YAPBOT comment."""
        if not AI_OK: return
        if self.ai_loading and not forced: return

        self.ai_loading = True
        summary = self._game_summary()

        def worker():
            text = ai_funcs.get_commentary(summary, trigger_desc)
            self.ai_queue.append(text)
            self.ai_loading = False

        threading.Thread(target=worker, daemon=True).start()

    def _check_YAPBOT_triggers(self):
        """Called at end of each turn. Checks condition-based and periodic triggers."""
        # Check condition-based triggers
        for tid, trigger_desc, cond_fn, one_shot in YAPBOT_TRIGGERS:
            if one_shot and tid in self._fired_triggers:
                continue
            try:
                fired = cond_fn(self)
            except Exception:
                fired = False
            if fired:
                if one_shot:
                    self._fired_triggers.add(tid)
                self._queue_ai_comment(trigger_desc)
                return   # only one trigger per turn

        # Periodic roast (cooldown-based)
        self.ai_cooldown -= 1
        if self.ai_cooldown <= 0:
            self.ai_cooldown = random.randint(AI_MIN_COOLDOWN, AI_MAX_COOLDOWN)
            roast_triggers = [
                "the player is just drifting along doing nothing interesting",
                "the player keeps ending turns without investing anything",
                f"it's been a while — net worth is currently {mn(self.networth())}",
                f"player health is at {self.health:.0f}% — slowly deteriorating",
                f"the player has {sum(self.portfolio)} total shares across all companies",
                f"unemployment is at {data.indics.unemployment[-1]*100:.1f}% and the player seems unbothered",
            ]
            self._queue_ai_comment(random.choice(roast_triggers))

    def _tick_ai_popup(self):
        """Advance the popup queue — show next queued text if current expired."""
        if self.ai_popup:
            self.ai_popup["ttl"] -= 1
            if self.ai_popup["ttl"] <= 0:
                self.ai_popup = None
        if not self.ai_popup and self.ai_queue:
            text  = self.ai_queue.pop(0)
            lines = wrap_text(text, "small", 330)
            self.ai_popup = {"text": text, "lines": lines, "ttl": AI_POPUP_TTL}

    # ── End of turn ───────────────────────────────────────────────────────────
    def end_turn(self):
        if self.state != "playing": return

        prev_recession = data.indics.recession
        prev_salary    = self.salary

        eff_sal   = self.effective_salary()
        net_day   = eff_sal - self.expend
        self._last_net_day = net_day

        self.checkquing += net_day
        self.savings    += self.savings * DAILY_INT

        # Expenses grow ~0.5-2% every 10 days (inflation / lifestyle creep)
        if self.turn % 10 == 0:
            growth = random.uniform(0.005, 0.02)
            self.expend *= (1 + growth)
            self.add_msg(
                f"Expenses rose {growth*100:.1f}% to {mn(self.expend)}/day  (inflation)", ORG
            )

        if random.random() < EVENT_PROB:
            self.trigger_event()

        market.funny_market.make_market(self.turn)
        data.indics.updateIndicators()
        data.indics.recessionTrigger()

        # Force recession at the pre-chosen day (if one hasn't started yet)
        if not data.indics.recession and self.turn >= self._forced_rec_day:
            data.indics.recession = True

        # Detect salary drop from event
        self._last_salary_drop = self.salary < prev_salary * 0.95

        # Track whether we've seen a recession yet (for one-shot trigger)
        if data.indics.recession:
            self._seen_recession = True

        # Auto-rescue: pull from savings if checking is negative
        if self.checkquing < 0 and self.savings > 0:
            pull             = min(-self.checkquing, self.savings)
            self.savings    -= pull
            self.checkquing += pull
            self.add_msg("Auto-transferred from savings to cover expenses.", GLD)

        nw      = self.networth()
        rec_tag = "  ⚠ RECESSION" if data.indics.recession else ""
        self.add_msg(
            f"Day {self.turn}: net {mn(net_day)}/day | NW {mn(nw)}{rec_tag}",
            vc(net_day)
        )

        self.turn += 1

        # Check YAPBOT triggers for this turn
        self._check_YAPBOT_triggers()

        # Recession just started — also flag for one-shot trigger next check
        if data.indics.recession and not prev_recession:
            self._seen_recession = False   # let the trigger fire

        if nw <= 0 and self.checkquing <= 0 and self.savings <= 0:
            self.state = "bankrupt"
        elif self.turn > MAX_TURNS:
            self.state = "won"

    # ── Input routing ─────────────────────────────────────────────────────────
    def handle_event(self, ev):
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.modal = None; self.modal_msg = ""
            if ev.key == pygame.K_r and self.state in ("bankrupt","won"):
                return "restart"
            if not self.modal and self.state == "playing":
                if ev.key == pygame.K_e:
                    self.end_turn()
                elif ev.key in (pygame.K_TAB, pygame.K_g):
                    self.center_view = "economy" if self.center_view == "stocks" else "stocks"
                elif pygame.K_1 <= ev.key <= pygame.K_5:
                    if self.center_view == "stocks":
                        self.sel_stock = ev.key - pygame.K_1

        # Dismiss event popup
        if self.event_popup and ev.type == pygame.MOUSEBUTTONDOWN:
            self.event_popup = None; return None

        # Dismiss YAPBOT popup
        if self.ai_popup and ev.type == pygame.MOUSEBUTTONDOWN:
            if self._ai_popup_rect().collidepoint(ev.pos):
                self.ai_popup = None; return None

        if self.state in ("bankrupt","won"): return None

        if self.modal:
            self._handle_modal_event(ev)
        else:
            self._handle_main_event(ev)
        return None

    def _handle_main_event(self, ev):
        for key, btn in self.action_btns.items():
            if btn.check(ev):
                if   key == "buy":     self._open_modal("buy")
                elif key == "sell":    self._open_modal("sell")
                elif key == "xfer_cs": self._open_modal("xfer_cs")
                elif key == "xfer_sc": self._open_modal("xfer_sc")
                elif key == "end":     self.end_turn()

        if ev.type == pygame.MOUSEBUTTONDOWN:
            # Main view toggle tabs
            for i in range(2):
                if self._main_tab_rect(i).collidepoint(ev.pos):
                    self.center_view = ["stocks","economy"][i]

            if self.center_view == "stocks":
                for i in range(NUM_COMPS):
                    if self._stock_tab_rect(i).collidepoint(ev.pos):
                        self.sel_stock = i
            else:
                for i in range(4):
                    if self._econ_tab_rect(i).collidepoint(ev.pos):
                        self.sel_econ = i

    def _handle_modal_event(self, ev):
        m = self.modal
        if m in ("buy","sell"):
            for i, btn in enumerate(self.m_co_btns):
                if btn.check(ev): self.modal_co = i
            self.inp_qty.handle(ev)
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_RETURN:
                self._confirm()
        elif m in ("xfer_cs","xfer_sc"):
            self.inp_amt.handle(ev)
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_RETURN:
                self._confirm()
        if self.m_ok.check(ev):  self._confirm()
        if self.m_can.check(ev): self.modal = None; self.modal_msg = ""

    def _open_modal(self, kind):
        self.modal = kind; self.modal_co = 0; self.modal_msg = ""
        self.inp_qty.clear(); self.inp_amt.clear()

    def _confirm(self):
        m = self.modal
        if   m == "buy":     ok, msg = self.buy_stock(self.modal_co, self.inp_qty.val())
        elif m == "sell":    ok, msg = self.sell_stock(self.modal_co, self.inp_qty.val())
        elif m == "xfer_cs": ok, msg = self.transfer_cs(self.inp_amt.val())
        elif m == "xfer_sc": ok, msg = self.transfer_sc(self.inp_amt.val())
        else: return
        if ok:  self.modal = None
        else:   self.modal_msg = msg

    def _main_tab_rect(self, i):
        """Top-level view toggle: 0=Stocks, 1=Economy."""
        w = MID_W // 2
        return pygame.Rect(LEFT_W + i * w, HDR_H, w, TAB_H)

    def _stock_tab_rect(self, i):
        """Per-stock sub-tabs (shown only in Stocks view)."""
        tab_w = MID_W // NUM_COMPS
        return pygame.Rect(LEFT_W + i * tab_w, HDR_H + TAB_H, tab_w, TAB_H)

    def _econ_tab_rect(self, i):
        """Economy chart selector tabs (shown only in Economy view)."""
        ECON_TABS = ["Bonds","Unemployment","GDP","Consumption"]
        tab_w = MID_W // len(ECON_TABS)
        return pygame.Rect(LEFT_W + i * tab_w, HDR_H + TAB_H, tab_w, TAB_H)

    # kept for any legacy calls
    def _tab_rect(self, i):
        return self._stock_tab_rect(i)

    def _ai_popup_rect(self):
        pw, ph = 380, 170
        return pygame.Rect(W - pw - 8, HDR_H + MAIN_H - ph - 8, pw, ph)

    # ─────────────────────────────────────────────────────────────────────────
    # RENDERING
    # ─────────────────────────────────────────────────────────────────────────
    def draw(self):
        self._tick_ai_popup()
        screen.fill(BG)
        self._draw_header()
        self._draw_left()
        self._draw_center()
        self._draw_right()
        self._draw_bottom()
        if self.modal:       self._draw_modal()
        if self.event_popup: self._draw_event_popup()
        if self.ai_popup:    self._draw_ai_popup()
        if self.state == "bankrupt": self._draw_endscreen(won=False)
        if self.state == "won":      self._draw_endscreen(won=True)
        pygame.display.flip()

    # ── Header ────────────────────────────────────────────────────────────────
    def _draw_header(self):
        pygame.draw.rect(screen, PANEL_D, (0, 0, W, HDR_H))
        hline(screen, 0, W, HDR_H-1, BOR_L)

        tx(screen, "◈ ECOSIM", "h2", CYN, 14, 16)
        tx(screen, "Don't Go Bankrupt", "tiny", TXD, 14, 39)

        tx(screen, f"DAY {self.turn}/{MAX_TURNS}", "small", TXD, 165, 12)
        pr = pygame.Rect(165, 30, 190, 12)
        pbar(screen, pr, self.turn, MAX_TURNS, RED if data.indics.recession else CYN)

        nw     = self.networth()
        nw_col = GRN if nw > 1500 else (GLD if nw > 600 else RED)
        tx(screen, "NET WORTH", "tiny", TXD, 380, 11)
        tx(screen, mn(nw),      "h2",   nw_col, 380, 27)

        tx(screen, "CHECKING",  "tiny", TXD, 580, 11)
        tx(screen, mn(self.checkquing), "h3", vc(self.checkquing), 580, 28)

        tx(screen, "SAVINGS",   "tiny", TXD, 760, 11)
        tx(screen, mn(self.savings),    "h3", TXT, 760, 28)

        br = pygame.Rect(W-185, 10, 172, 34)
        if data.indics.recession:
            pygame.draw.rect(screen, (75,12,18), br, border_radius=5)
            pygame.draw.rect(screen, RED, br, 1, border_radius=5)
            tx(screen, "⚠  RECESSION", "h3", RED, br.centerx, br.y+9, "center")
        else:
            pygame.draw.rect(screen, (0,38,24), br, border_radius=5)
            pygame.draw.rect(screen, GRN, br, 1, border_radius=5)
            tx(screen, "✓  ECONOMY OK", "small", GRN, br.centerx, br.y+10, "center")

    # ── Left panel ────────────────────────────────────────────────────────────
    def _draw_left(self):
        lx0, ly0 = 0, HDR_H
        pygame.draw.rect(screen, PANEL,  (lx0, ly0, LEFT_W, MAIN_H))
        pygame.draw.rect(screen, BOR,    (lx0, ly0, LEFT_W, MAIN_H), 1)
        vline(screen, LEFT_W-1, HDR_H, HDR_H+MAIN_H, BOR_L)

        px, y = 12, HDR_H + 12

        tx(screen, "FINANCES", "h3", CYN, px, y); y += 20
        hline(screen, px, LEFT_W-px, y, BOR_L); y += 7

        eff_sal = self.effective_salary()
        net_day = eff_sal - self.expend
        for lbl, val, col in [
            ("Checking",  self.checkquing,      vc(self.checkquing)),
            ("Savings",   self.savings,          TXT),
            ("Portfolio", self.portfolio_value(),vc(self.portfolio_value())),
        ]:
            tx(screen, lbl,    "small", TXD, px, y)
            tx(screen, mn(val), "body", col, LEFT_W-px, y, "right")
            y += 18

        y += 4
        for lbl, val, col in [
            ("Salary/day", eff_sal,    GRN),
            ("Expenses",   self.expend,RED),
            ("Net/day",    net_day,    vc(net_day)),
        ]:
            tx(screen, lbl,    "small", TXD,  px, y)
            tx(screen, mn(val),"small", col, LEFT_W-px, y, "right")
            y += 15

        y += 10
        tx(screen, "HEALTH", "h3", CYN, px, y); y += 19
        hcol = GRN if self.health > 60 else (GLD if self.health > 30 else RED)
        hr   = pygame.Rect(px, y, LEFT_W-px*2, 13)
        pbar(screen, hr, self.health, 100, hcol)
        tx(screen, f"{self.health:.0f}%", "tiny", hcol, hr.right+5, y)
        y += 24
        tx(screen, "Career Aura", "small", TXD, px, y)
        tx(screen, f"{self.career_aura:.0f}", "small", PRP, LEFT_W-px, y, "right")
        y += 22

        y += 4
        tx(screen, "HOLDINGS", "h3", CYN, px, y); y += 20
        hline(screen, px, LEFT_W-px, y, BOR_L); y += 7

        has_any = False
        for i in range(NUM_COMPS):
            if self.portfolio[i] > 0:
                has_any   = True
                price     = data.stock_markets.companies[i][-1]
                val       = self.portfolio[i] * price
                prev      = data.stock_markets.companies[i][-2] if len(data.stock_markets.companies[i]) >= 2 else price
                chg_pct   = (price-prev)/prev*100 if prev else 0
                pygame.draw.circle(screen, CO_C[i], (px+5, y+7), 4)
                tx(screen, CO_N[i][:7],   "small", CO_C[i], px+14, y)
                tx(screen, f"{self.portfolio[i]}×", "tiny", TXD, px+95, y+2)
                tx(screen, mn(val), "small", vc(chg_pct), LEFT_W-px, y, "right")
                y += 16
        if not has_any:
            tx(screen, "No holdings yet", "small", TXD, px, y); y += 16

        # Economy section pinned to bottom
        ey = HDR_H + MAIN_H - 148
        hline(screen, px, LEFT_W-px, ey, BOR); ey += 8
        tx(screen, "ECONOMY", "h3", CYN, px, ey); ey += 20
        hline(screen, px, LEFT_W-px, ey, BOR_L); ey += 7

        unemp = data.indics.unemployment[-1]
        gdp   = data.indics.gdp[-1]
        for lbl, val, col in [
            ("Unemployment", f"{unemp*100:.1f}%",
             RED if unemp > 0.07 else (GLD if unemp > 0.05 else GRN)),
            ("GDP Growth",   f"{gdp*100:.2f}%",                      vc(gdp)),
            ("Short Bond",   f"{data.indics.bondYields3Months[-1]*100:.2f}%", TXT),
            ("Long Bond",    f"{data.indics.bondYields5yrs[-1]*100:.2f}%",    TXT),
            ("Consumption",  f"{data.indics.consumption[-1]*100:.2f}%",
             vc(data.indics.consumption[-1])),
        ]:
            tx(screen, lbl, "small", TXD, px, ey)
            tx(screen, val, "small", col, LEFT_W-px, ey, "right")
            ey += 16

    # ── Center panel ──────────────────────────────────────────────────────────
    def _draw_center(self):
        cx = LEFT_W

        # ── Row 1: main view tabs (STOCKS / ECONOMY) ──────────────────────────
        VIEW_LABELS = ["📈  STOCKS", "📊  ECONOMY"]
        for i, lbl in enumerate(VIEW_LABELS):
            tab    = self._main_tab_rect(i)
            active = (self.center_view == ["stocks","economy"][i])
            bg_col = (14,24,48) if active else PANEL_D
            bd_col = CYN        if active else BOR
            pygame.draw.rect(screen, bg_col, tab,
                             border_top_left_radius=3, border_top_right_radius=3)
            pygame.draw.rect(screen, bd_col, tab, 1,
                             border_top_left_radius=3, border_top_right_radius=3)
            fk  = "h3"   if active else "small"
            col = CYN    if active else TXD
            tx(screen, lbl, fk, col,
               tab.centerx, tab.centery - F[fk].get_height()//2, "center")

        # ── Row 2: sub-tabs + content ──────────────────────────────────────────
        content_r = pygame.Rect(cx, HDR_H + TAB_H*2, MID_W, MAIN_H - TAB_H*2)

        if self.center_view == "stocks":
            # Stock selector sub-tabs
            for i in range(NUM_COMPS):
                tab    = self._stock_tab_rect(i)
                active = (i == self.sel_stock)
                pygame.draw.rect(screen,
                                 (14,24,48) if active else PANEL_D, tab,
                                 border_top_left_radius=3, border_top_right_radius=3)
                pygame.draw.rect(screen,
                                 CO_C[i] if active else BOR, tab, 1,
                                 border_top_left_radius=3, border_top_right_radius=3)
                fk  = "small" if active else "tiny"
                col = CO_C[i] if active else TXD
                tx(screen, CO_N[i], fk, col,
                   tab.centerx, tab.centery - F[fk].get_height()//2, "center")

            chart_r = pygame.Rect(cx+2, HDR_H + TAB_H*2,
                                  MID_W-4, CHART_H)
            table_r = pygame.Rect(cx,   HDR_H + TAB_H*2 + CHART_H + 3,
                                  MID_W, MAIN_H - TAB_H*2 - CHART_H - 3)
            self._draw_chart(chart_r, self.sel_stock)
            self._draw_stock_table(table_r)

        else:
            # Economy indicator sub-tabs
            ECON_TABS   = ["Bonds", "Unemployment", "GDP", "Consumption"]
            ECON_COLS   = [GLD,     RED,             GRN,   CYN]
            for i, (lbl, col) in enumerate(zip(ECON_TABS, ECON_COLS)):
                tab    = self._econ_tab_rect(i)
                active = (i == self.sel_econ)
                pygame.draw.rect(screen,
                                 (14,24,48) if active else PANEL_D, tab,
                                 border_top_left_radius=3, border_top_right_radius=3)
                pygame.draw.rect(screen,
                                 col if active else BOR, tab, 1,
                                 border_top_left_radius=3, border_top_right_radius=3)
                fk  = "small" if active else "tiny"
                tc  = col     if active else TXD
                tx(screen, lbl, fk, tc,
                   tab.centerx, tab.centery - F[fk].get_height()//2, "center")

            self._draw_economy_view(content_r)

        vline(screen, cx+MID_W-1, HDR_H, HDR_H+MAIN_H, BOR_L)

    def _draw_chart(self, r, co_idx):
        prices = data.stock_markets.companies[co_idx]
        pygame.draw.rect(screen, PANEL_D, r)
        pygame.draw.rect(screen, BOR, r, 1)
        if len(prices) < 2:
            tx(screen, "Waiting for market data...", "small", TXD,
               r.centerx, r.centery-6, "center"); return

        visible  = prices[-80:]
        n        = len(visible)
        lo, hi   = min(visible), max(visible)
        spread   = hi - lo if hi - lo > 0.001 else hi * 0.04
        chart_lo = lo - spread * 0.05
        chart_hi = hi + spread * 0.05
        cr_span  = chart_hi - chart_lo

        PL,PR,PT,PB = 68,10,14,24
        gx,gy = r.x+PL, r.y+PT
        gw,gh = r.w-PL-PR, r.h-PT-PB

        for i in range(5):
            yg = gy + int(gh * i / 4)
            pv = chart_hi - cr_span * i / 4
            pygame.draw.line(screen, BOR, (gx, yg), (gx+gw, yg), 1)
            tx(screen, f"${pv:.2f}", "tiny", TXD, gx-4, yg-5, "right")

        step = max(1, n // 8)
        for i in range(0, n, step):
            xg  = gx + int(gw * i / max(n-1,1))
            day = self.turn - n + i
            pygame.draw.line(screen, BOR, (xg, gy), (xg, gy+gh), 1)
            tx(screen, str(max(1,day)), "tiny", TXD, xg, gy+gh+5, "center")

        pts = []
        for i, p in enumerate(visible):
            px_ = gx + int(gw * i / max(n-1,1))
            py_ = gy + int(gh * (1.0 - (p - chart_lo) / cr_span))
            py_ = max(gy+1, min(gy+gh-1, py_))
            pts.append((px_, py_))

        fill_s = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        rel    = [(p[0]-r.x, p[1]-r.y) for p in pts]
        poly   = [(gx-r.x, gy+gh)] + rel + [(gx+gw-r.x, gy+gh)]
        pygame.draw.polygon(fill_s, (*CO_C[co_idx], 32), poly)
        screen.blit(fill_s, r.topleft)

        if len(pts) >= 2:
            pygame.draw.lines(screen, CO_C[co_idx], False, pts, 2)
        if pts:
            lx_, ly_ = pts[-1]
            pygame.draw.circle(screen, CO_C[co_idx], (lx_, ly_), 5)
            pygame.draw.circle(screen, TXB,          (lx_, ly_), 2)
            tx(screen, f"${visible[-1]:.2f}", "small", CO_C[co_idx],
               min(lx_+8, r.right-64), max(gy+2, ly_-12))

        if len(prices) >= 2:
            chg   = (prices[-1]-prices[-2]) / prices[-2] * 100
            chg_s = f"{'▲'if chg>=0 else'▼'} {pc(chg)}"
            tx(screen, chg_s,       "h3", vc(chg), gx+4,       r.y+4)
            tx(screen, CO_N[co_idx],"h2", CO_C[co_idx], r.right-PR-4, r.y+4, "right")

        if len(prices) >= 7:
            ma_pts = []
            for i in range(6, n):
                avg  = sum(visible[i-6:i+1]) / 7
                px_  = gx + int(gw * i / max(n-1,1))
                py_  = gy + int(gh * (1.0 - (avg - chart_lo) / cr_span))
                py_  = max(gy+1, min(gy+gh-1, py_))
                ma_pts.append((px_, py_))
            if len(ma_pts) >= 2:
                ma_col = tuple(max(0, c-40) for c in CO_C[co_idx])
                pygame.draw.lines(screen, (*ma_col, 160), False, ma_pts, 1)

    def _draw_stock_table(self, r):
        pygame.draw.rect(screen, PANEL, r)
        pygame.draw.rect(screen, BOR, r, 1)
        row_h = (r.h - 22) // NUM_COMPS
        COL_X = [r.x+8, r.x+112, r.x+192, r.x+270, r.x+338, r.x+430, r.x+510]
        HDR_L = ["COMPANY","PRICE","1D CHG","OWNED","VALUE","52W HIGH","52W LOW"]

        hy = r.y + 4
        for x, lbl in zip(COL_X, HDR_L):
            tx(screen, lbl, "tiny", TXD, x, hy)
        hline(screen, r.x+2, r.right-2, hy+15, BOR_L)

        for i in range(NUM_COMPS):
            prices = data.stock_markets.companies[i]
            ry     = r.y + 22 + i * row_h
            if i == self.sel_stock:
                pygame.draw.rect(screen, (14,22,44), pygame.Rect(r.x+1,ry-1,r.w-2,row_h-1))
            price  = prices[-1]
            prev   = prices[-2] if len(prices) >= 2 else price
            chg    = (price-prev)/prev*100 if prev else 0
            pval   = self.portfolio[i] * price
            hi_52  = max(prices[-min(52,len(prices)):])
            lo_52  = min(prices[-min(52,len(prices)):])
            chg_s  = f"{'▲'if chg>=0 else'▼'}{abs(chg):.2f}%"

            pygame.draw.circle(screen, CO_C[i], (COL_X[0]+5, ry+row_h//2), 4)
            tx(screen, CO_N[i],  "body",  CO_C[i] if i==self.sel_stock else TXT,
               COL_X[0]+14, ry+(row_h-F["body"].get_height())//2)
            tx(screen, f"${price:.2f}", "body", TXB, COL_X[1], ry+(row_h-F["body"].get_height())//2)
            tx(screen, chg_s,    "small",vc(chg), COL_X[2], ry+(row_h-F["small"].get_height())//2)
            tx(screen, str(self.portfolio[i]), "body", TXT, COL_X[3], ry+(row_h-F["body"].get_height())//2)
            tx(screen, mn(pval) if pval > 0 else "—", "body",
               GRN if pval > 0 else TXD, COL_X[4], ry+(row_h-F["body"].get_height())//2)
            tx(screen, f"${hi_52:.2f}", "tiny", TXD, COL_X[5], ry+(row_h-F["tiny"].get_height())//2)
            tx(screen, f"${lo_52:.2f}", "tiny", TXD, COL_X[6], ry+(row_h-F["tiny"].get_height())//2)
            if i < NUM_COMPS - 1:
                hline(screen, r.x+4, r.right-4, ry+row_h-2, BOR)

    # ── Economy history view ───────────────────────────────────────────────────
    def _draw_economy_view(self, r):
        """
        Full-height economy panel. Shows 4 charts depending on sel_econ:
          0 — Bond Yields (short + long overlaid)
          1 — Unemployment
          2 — GDP Growth
          3 — Consumption
        Each chart uses the full content rect.
        A stat summary strip lives at the bottom.
        """
        ECON_TABS = ["Bonds","Unemployment","GDP","Consumption"]
        ECON_COLS = [GLD,    RED,            GRN,  CYN]

        pygame.draw.rect(screen, PANEL_D, r)
        pygame.draw.rect(screen, BOR, r, 1)

        STAT_H  = 52
        chart_r = pygame.Rect(r.x+2, r.y, r.w-4, r.h - STAT_H - 2)

        idx = self.sel_econ

        if idx == 0:
            # Bonds: two lines on one chart
            short = data.indics.bondYields3Months
            long_ = data.indics.bondYields5yrs
            self._draw_indicator_chart(
                chart_r,
                series=[(short, GLD, "Short Bond (3M)"),
                        (long_,  CYN, "Long Bond (5Y)")],
                title="Bond Yields",
                y_fmt=lambda v: f"{v*100:.2f}%",
                y_label="%",
                fill=False,
            )
        elif idx == 1:
            self._draw_indicator_chart(
                chart_r,
                series=[(data.indics.unemployment, RED, "Unemployment")],
                title="Unemployment Rate",
                y_fmt=lambda v: f"{v*100:.1f}%",
                y_label="%",
                fill=True,
            )
        elif idx == 2:
            self._draw_indicator_chart(
                chart_r,
                series=[(data.indics.gdp, GRN, "GDP Growth")],
                title="GDP Growth Rate",
                y_fmt=lambda v: f"{v*100:.2f}%",
                y_label="%",
                fill=True,
                zero_line=True,
            )
        else:
            self._draw_indicator_chart(
                chart_r,
                series=[(data.indics.consumption, CYN, "Consumption")],
                title="Consumption Rate",
                y_fmt=lambda v: f"{v*100:.2f}%",
                y_label="%",
                fill=True,
                zero_line=True,
            )

        # ── Stat strip ──────────────────────────────────────────────────────
        sy = r.bottom - STAT_H
        hline(screen, r.x+4, r.right-4, sy, BOR_L)

        stats = [
            ("Short Bond",   f"{data.indics.bondYields3Months[-1]*100:.2f}%", GLD),
            ("Long Bond",    f"{data.indics.bondYields5yrs[-1]*100:.2f}%",    CYN),
            ("Unemployment", f"{data.indics.unemployment[-1]*100:.1f}%",
             RED if data.indics.unemployment[-1] > 0.07 else GRN),
            ("GDP",          f"{data.indics.gdp[-1]*100:.2f}%",
             vc(data.indics.gdp[-1])),
            ("Consumption",  f"{data.indics.consumption[-1]*100:.2f}%",
             vc(data.indics.consumption[-1])),
        ]
        slot_w = (r.w - 8) // len(stats)
        for j, (lbl, val, col) in enumerate(stats):
            sx = r.x + 4 + j * slot_w
            tx(screen, lbl, "tiny",  TXD, sx + slot_w//2, sy + 8,  "center")
            tx(screen, val, "small", col, sx + slot_w//2, sy + 26, "center")
            if j > 0:
                vline(screen, sx, sy + 6, r.bottom - 4, BOR)

        # Recession badge
        if data.indics.recession:
            br = pygame.Rect(r.right - 118, r.y + 6, 110, 22)
            pygame.draw.rect(screen, (75,12,18), br, border_radius=4)
            pygame.draw.rect(screen, RED, br, 1, border_radius=4)
            tx(screen, "⚠ RECESSION", "tiny", RED, br.centerx, br.y+5, "center")

    def _draw_indicator_chart(self, r, series, title,
                              y_fmt=None, y_label="",
                              fill=True, zero_line=False):
        """
        Generic multi-series line chart for economic indicators.
        series: list of (data_list, color, legend_label)
        """
        if y_fmt is None:
            y_fmt = lambda v: f"{v:.3f}"

        # Collect all values to determine axis range
        all_vals = []
        for data_list, _, _ in series:
            all_vals.extend(data_list)

        if len(all_vals) < 2:
            tx(screen, "Not enough data yet", "small", TXD,
               r.centerx, r.centery, "center")
            return

        raw_lo, raw_hi = min(all_vals), max(all_vals)
        spread   = raw_hi - raw_lo if raw_hi - raw_lo > 1e-6 else abs(raw_hi) * 0.1 + 1e-6
        chart_lo = raw_lo - spread * 0.08
        chart_hi = raw_hi + spread * 0.12
        cr_span  = chart_hi - chart_lo

        PL, PR, PT, PB = 64, 12, 32, 28
        gx, gy = r.x + PL, r.y + PT
        gw, gh = r.w - PL - PR, r.h - PT - PB

        # Title
        tx(screen, title, "h3", TXB, gx + 4, r.y + 6)

        # Legend (top-right)
        leg_x = r.right - PR - 6
        for data_list, col, lbl in reversed(series):
            tw = tx(screen, lbl, "tiny", col, leg_x, r.y + 8, "right")
            pygame.draw.line(screen, col,
                             (leg_x - tw - 18, r.y + 12),
                             (leg_x - tw - 6,  r.y + 12), 2)
            leg_x -= tw + 28

        # Grid lines
        GRID_N = 5
        for i in range(GRID_N):
            yg = gy + int(gh * i / (GRID_N - 1))
            pv = chart_hi - cr_span * i / (GRID_N - 1)
            pygame.draw.line(screen, BOR, (gx, yg), (gx + gw, yg), 1)
            tx(screen, y_fmt(pv), "tiny", TXD, gx - 4, yg - 5, "right")

        # Vertical day guides
        n_pts = max(len(d) for d, _, _ in series)
        step  = max(1, n_pts // 8)
        for i in range(0, n_pts, step):
            xg  = gx + int(gw * i / max(n_pts - 1, 1))
            day = self.turn - n_pts + i
            pygame.draw.line(screen, BOR, (xg, gy), (xg, gy + gh), 1)
            tx(screen, str(max(1, day)), "tiny", TXD, xg, gy + gh + 5, "center")

        # Zero line
        if zero_line and chart_lo < 0 < chart_hi:
            yz = gy + int(gh * (1.0 - (0 - chart_lo) / cr_span))
            pygame.draw.line(screen, (80,80,80), (gx, yz), (gx + gw, yz), 1)

        # Series lines (drawn back to front)
        for data_list, col, _ in series:
            n = len(data_list)
            if n < 2:
                continue

            pts = []
            for i, v in enumerate(data_list):
                px_ = gx + int(gw * i / max(n - 1, 1))
                py_ = gy + int(gh * (1.0 - (v - chart_lo) / cr_span))
                py_ = max(gy + 1, min(gy + gh - 1, py_))
                pts.append((px_, py_))

            # Translucent fill
            if fill:
                fill_surf = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
                rel  = [(p[0] - r.x, p[1] - r.y) for p in pts]
                poly = [(gx - r.x, gy + gh)] + rel + [(gx + gw - r.x, gy + gh)]
                pygame.draw.polygon(fill_surf, (*col, 28), poly)
                screen.blit(fill_surf, r.topleft)

            pygame.draw.lines(screen, col, False, pts, 2)

            # Current value marker on last point
            lx_, ly_ = pts[-1]
            pygame.draw.circle(screen, col, (lx_, ly_), 5)
            pygame.draw.circle(screen, TXB, (lx_, ly_), 2)
            tx(screen, y_fmt(data_list[-1]), "tiny", col,
               min(lx_ + 7, r.right - PR - 2), max(gy + 2, ly_ - 13))

    # ── Right panel ───────────────────────────────────────────────────────────
    def _draw_right(self):
        rx = LEFT_W + MID_W
        pygame.draw.rect(screen, PANEL, (rx, HDR_H, RGT_W, MAIN_H))
        pygame.draw.rect(screen, BOR,   (rx, HDR_H, RGT_W, MAIN_H), 1)

        px, y = rx+12, HDR_H+8
        tx(screen, "ACTIONS", "h3", CYN, px, y); y += 18
        hline(screen, px, rx+RGT_W-12, y, BOR_L)

        # Draw all action buttons EXCEPT the end/next-turn button
        for key, btn in self.action_btns.items():
            if key != "end":
                btn.draw(screen)

        y = HDR_H + 210
        hline(screen, px, rx+RGT_W-12, y, BOR); y += 10
        tx(screen, "SHORTCUTS", "tiny", TXD, px, y); y += 16
        for key, desc in [("[1-5]","Switch stock chart"),("[Tab]","Economy view"),
                          ("[E]","Next turn"),("[Esc]","Close modal"), ("[R]","Restart")]:
            tx(screen, key,  "tiny", GLD, px, y)
            tx(screen, desc, "tiny", TXD, px+42, y)
            y += 14

        y += 8
        hline(screen, px, rx+RGT_W-12, y, BOR); y += 8
        eff = self.effective_salary()
        net = eff - self.expend
        tx(screen, "TODAY'S SUMMARY", "tiny", TXD, px, y); y += 16
        for lbl, val, col in [
            (f"  Salary (×{0.5+self.health/200:.2f})", mn(eff),  GRN),
            ("  Expenses",                              mn(self.expend), RED),
            ("  Net",                                   mn(net),  vc(net)),
            ("  Savings int.",  f"+{mn(self.savings*DAILY_INT)}",  CYN),
        ]:
            tx(screen, lbl, "tiny", TXD, px, y)
            tx(screen, val, "tiny", col, rx+RGT_W-14, y, "right")
            y += 14

        # YAPBOT status (tiny indicator)
        y += 8
        hline(screen, px, rx+RGT_W-12, y, BOR); y += 8
        if self.ai_loading:
            dots = "." * ((pygame.time.get_ticks()//400) % 4)
            tx(screen, f"🤖 YAPBOT-9000 typing{dots}", "tiny", PRP, px, y)
        elif not AI_OK:
            tx(screen, "🤖 YAPBOT-9000  [offline]", "tiny", TXD, px, y)
        else:
            next_in = self.ai_cooldown
            tx(screen, f"🤖 YAPBOT-9000  (next in ~{next_in}d)", "tiny", PRP, px, y)

        # ── NEXT TURN button with pulsing glow ────────────────────────────────
        end_btn = self.action_btns["end"]

        # Pulsing glow behind the button
        pulse   = (math.sin(pygame.time.get_ticks() / 420.0) + 1.0) / 2.0   # 0→1
        glow_a  = int(50 + 90 * pulse)
        glow_c  = (0, 220, 110, glow_a)
        inflate = int(3 + 4 * pulse)
        glow_r  = end_btn.r.inflate(inflate * 2, inflate * 2)
        glow_s  = pygame.Surface((glow_r.w, glow_r.h), pygame.SRCALPHA)
        pygame.draw.rect(glow_s, glow_c, (0, 0, glow_r.w, glow_r.h), border_radius=8)
        screen.blit(glow_s, glow_r.topleft)

        end_btn.draw(screen)

        # Day counter rendered inside the button (bottom strip)
        day_str  = f"DAY  {self.turn} / {MAX_TURNS}"
        day_surf = F["tiny"].render(day_str, True, (160, 230, 180))
        screen.blit(day_surf,
                    (end_btn.r.centerx - day_surf.get_width() // 2,
                     end_btn.r.bottom - day_surf.get_height() - 5))

        # Keyboard hint below button
        tx(screen, "or press  [ E ]", "tiny", TXD,
           end_btn.r.centerx, end_btn.r.bottom + 5, "center")

    # ── Bottom panel ──────────────────────────────────────────────────────────
    def _draw_bottom(self):
        y0 = HDR_H + MAIN_H
        pygame.draw.rect(screen, PANEL_D, (0, y0, W, BOT_H))
        hline(screen, 0, W, y0+1, BOR_L)
        pygame.draw.rect(screen, BOR, (0, y0, W, BOT_H), 1)

        tx(screen, "EVENT LOG", "small", CYN, 12, y0+7)
        hline(screen, 12, W-12, y0+21, BOR)

        y = y0 + 28
        for msg in reversed(self.messages[-5:]):
            if y + 17 > y0 + BOT_H: break
            tx(screen, f"Day {msg['turn']:3d} ›", "tiny", TXD, 12, y+1)
            tx(screen, msg["text"], "small", msg["col"], 82, y+1)
            y += 19

    # ── Modal ─────────────────────────────────────────────────────────────────
    def _draw_modal(self):
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((3, 6, 13, 215))
        screen.blit(dim, (0,0))

        m  = self.modal
        mr = self.modal_r

        pygame.draw.rect(screen, (8,14,28), mr, border_radius=7)
        pygame.draw.rect(screen, BOR_L,     mr, 1, border_radius=7)

        tr = pygame.Rect(mr.x, mr.y, mr.w, 40)
        pygame.draw.rect(screen, (14,24,52), tr,
                         border_top_left_radius=7, border_top_right_radius=7)
        hline(screen, mr.x, mr.right, mr.y+40, BOR_L)

        TITLES = {
            "buy":     "▲  BUY SHARES",
            "sell":    "▼  SELL SHARES",
            "xfer_cs": "⇒  MOVE TO SAVINGS",
            "xfer_sc": "⇐  WITHDRAW FROM SAVINGS",
        }
        tx(screen, TITLES.get(m,""), "h2", CYN, mr.centerx, mr.y+11, "center")
        y = mr.y + 50

        if m in ("buy","sell"):
            tx(screen, "Select company:", "small", TXD, mr.x+18, y); y += 20
            for i, btn in enumerate(self.m_co_btns):
                is_sel   = (i == self.modal_co)
                btn.nc   = CO_C[i] if is_sel else (15,25,50)
                btn.hc   = CO_C[i] if is_sel else (28,48,90)
                btn.tc   = (0,0,0) if (is_sel and sum(CO_C[i])>450) else (CO_C[i] if not is_sel else TXB)
                btn.draw(screen)

            ci    = self.modal_co
            price = data.stock_markets.companies[ci][-1]
            owned = self.portfolio[ci]
            y     = mr.y + 96

            tx(screen, "Current price:", "small", TXD, mr.x+18, y)
            tx(screen, mn(price),        "h2",    GLD, mr.x+18, y+17)

            if m == "buy":
                max_buy = int(self.checkquing // price)
                tx(screen, f"Available: {mn(self.checkquing)}  (max {max_buy} shares)",
                   "small", TXT, mr.x+18, y+42)
            else:
                tx(screen, f"Owned: {owned} share{'s' if owned != 1 else ''}",
                   "small", TXT, mr.x+18, y+42)

            y = mr.y + 165
            tx(screen, "Quantity:", "small", TXD, mr.x+18, y); y += 18
            self.inp_qty.r = pygame.Rect(mr.x+18, y, mr.w-36, 34)
            self.inp_qty.draw(screen)

            qty     = self.inp_qty.val()
            total   = price * qty
            over    = m == "buy" and total > self.checkquing
            tx(screen, f"{'Total cost' if m=='buy' else 'You receive'}: {mn(total)}",
               "h3", RED if over else TXB, mr.x+18, mr.y+225)

        elif m in ("xfer_cs","xfer_sc"):
            src_lbl = "Checking" if m=="xfer_cs" else "Savings"
            dst_lbl = "Savings"  if m=="xfer_cs" else "Checking"
            src_val = self.checkquing if m=="xfer_cs" else self.savings

            tx(screen, f"From {src_lbl}:", "small", TXD, mr.x+18, y)
            tx(screen, mn(src_val),        "h1",    TXB, mr.x+18, y+18); y += 52

            tx(screen, f"→  To {dst_lbl}", "small", TXD, mr.x+18, y); y += 22
            tx(screen, "Amount ($):",       "small", TXD, mr.x+18, y); y += 18
            self.inp_amt.r = pygame.Rect(mr.x+18, y, mr.w-36, 34)
            self.inp_amt.draw(screen)

        if self.modal_msg:
            tx(screen, f"⚠  {self.modal_msg}", "small", RED,
               mr.centerx, mr.y+mr.h-66, "center")

        bw2 = (mr.w-50)//2
        self.m_ok.r  = pygame.Rect(mr.x+15,     mr.y+mr.h-52, bw2, 42)
        self.m_can.r = pygame.Rect(mr.x+35+bw2, mr.y+mr.h-52, bw2, 42)
        self.m_ok.draw(screen)
        self.m_can.draw(screen)

    # ── Game event popup (top-center) ─────────────────────────────────────────
    def _draw_event_popup(self):
        ep = self.event_popup
        if not ep: return
        ep["ttl"] -= 1
        if ep["ttl"] <= 0: self.event_popup = None; return

        alpha = min(255, ep["ttl"] * 3)
        pw, ph = 400, 96
        px, py = (W-pw)//2, HDR_H+18

        surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
        surf.fill((8, 14, 28, min(240, alpha)))
        pygame.draw.rect(surf, (*ep["col"], min(255, alpha)), (0,0,pw,ph), 1, border_radius=6)
        screen.blit(surf, (px, py))

        tx(screen, ep["title"], "h2",    ep["col"], px+pw//2, py+12, "center")
        tx(screen, ep["msg"],   "small", TXT,       px+pw//2, py+40, "center")
        tx(screen, "click to dismiss", "tiny", TXD, px+pw//2, py+70, "center")

    # ── YAPBOT-9000 speech bubble (bottom-right) ───────────────────────────────
    def _draw_ai_popup(self):
        ap = self.ai_popup
        if not ap: return

        pr = self._ai_popup_rect()
        pw, ph = pr.w, pr.h

        # Fade in / fade out
        ttl      = ap["ttl"]
        fade_in  = AI_POPUP_TTL - 30
        fade_out = 60
        if ttl > fade_in:
            alpha = int(255 * (AI_POPUP_TTL - ttl) / 30)
        elif ttl < fade_out:
            alpha = int(255 * ttl / fade_out)
        else:
            alpha = 255

        alpha = max(0, min(255, alpha))

        # Background surface
        surf = pygame.Surface((pw, ph), pygame.SRCALPHA)
        surf.fill((10, 6, 22, min(235, alpha)))

        # PRP border with glow
        border_alpha = min(255, alpha)
        pygame.draw.rect(surf, (*PRP, border_alpha), (0, 0, pw, ph), 1, border_radius=8)
        pygame.draw.rect(surf, (*PRP, border_alpha//3), (2, 2, pw-4, ph-4), 1, border_radius=6)

        # Speech bubble tail (triangle at bottom-right)
        tail_pts = [(pw-40, ph), (pw-20, ph), (pw-18, ph+12)]
        pygame.draw.polygon(surf, (10, 6, 22, min(235, alpha)), tail_pts)
        pygame.draw.polygon(surf, (*PRP, border_alpha), tail_pts, 1)

        screen.blit(surf, pr.topleft)

        # Draw text content (blit with alpha manually by using a temp surface per element)
        txt_alpha = alpha

        # Header row: robot icon + name
        robot_r = pygame.Rect(pr.x+12, pr.y+10, 36, 36)
        pygame.draw.rect(screen, (30, 12, 52), robot_r, border_radius=5)
        pygame.draw.rect(screen, PRP, robot_r, 1, border_radius=5)

        # Robot face drawn with primitives
        rx, ry = robot_r.x, robot_r.y
        # eyes
        for ex in [rx+9, rx+22]:
            pygame.draw.rect(screen, PRP,  (ex,   ry+11, 5, 4), border_radius=1)
            pygame.draw.rect(screen, TXB,  (ex+1, ry+12, 3, 2), border_radius=1)
        # mouth
        for mx_ in range(rx+8, rx+28, 3):
            pygame.draw.rect(screen, PRP, (mx_, ry+22, 2, 2))
        # antenna
        pygame.draw.line(screen, PRP, (rx+18, ry+0), (rx+18, ry+5), 1)
        pygame.draw.circle(screen, GLD, (rx+18, ry+0), 2)

        # Name + tagline
        tx_alpha_surf = pygame.Surface((200, 36), pygame.SRCALPHA)
        tx(tx_alpha_surf, "YAPBOT-9000", "h3", (*PRP, txt_alpha), 0, 2)
        tx(tx_alpha_surf, "From da hood", "tiny", (*TXD, txt_alpha//2), 0, 20)
        screen.blit(tx_alpha_surf, (pr.x+54, pr.y+10))

        # Divider
        div_s = pygame.Surface((pw-24, 1), pygame.SRCALPHA)
        div_s.fill((*PRP, txt_alpha//3))
        screen.blit(div_s, (pr.x+12, pr.y+50))

        # Comment lines
        y_txt = pr.y + 58
        for line in ap["lines"][:5]:
            line_surf = pygame.Surface((pw-24, 16), pygame.SRCALPHA)
            tx(line_surf, line, "small", (*GLD, txt_alpha), 0, 0)
            screen.blit(line_surf, (pr.x+12, y_txt))
            y_txt += 16

        # Dismiss hint
        hint_surf = pygame.Surface((pw-24, 12), pygame.SRCALPHA)
        tx(hint_surf, "click to dismiss", "tiny", (*TXD, txt_alpha//2), pw-24, 0, "right")
        screen.blit(hint_surf, (pr.x+12, pr.y + ph - 18))

    # ── End screen ────────────────────────────────────────────────────────────
    def _draw_endscreen(self, won):
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((2, 4, 10, 240))
        screen.blit(dim, (0,0))

        nw    = self.networth()
        cy    = H // 2
        col   = GLD if won else RED
        title = "🏆  YOU SURVIVED!" if won else "💸  BANKRUPT"
        sub   = f"Final Net Worth: {mn(nw)}"
        info  = (f"You made it all {MAX_TURNS} days with your finances intact."
                 if won else
                 "You ran out of money. The market was stronger.")

        cw, ch = 520, 220
        csurf  = pygame.Surface((cw, ch), pygame.SRCALPHA)
        csurf.fill((9, 15, 28, 240))
        pygame.draw.rect(csurf, col, (0, 0, cw, ch), 1, border_radius=8)
        screen.blit(csurf, ((W-cw)//2, cy-ch//2))

        tx(screen, title, "huge", col, W//2, cy-ch//2+20,  "center")
        tx(screen, sub,   "h1",  TXB, W//2, cy-ch//2+90,  "center")
        tx(screen, info,  "body",TXT, W//2, cy-ch//2+128, "center")
        tx(screen, "Press  [R]  to restart", "h3", TXD, W//2, cy-ch//2+168, "center")


# ─── Main loop ────────────────────────────────────────────────────────────────
def main():
    game = Game()
    while True:
        clock.tick(FPS)
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            result = game.handle_event(ev)
            if result == "restart":
                data.reset()
                game = Game()
        game.draw()


if __name__ == "__main__":
    main()
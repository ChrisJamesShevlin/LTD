import tkinter as tk
import math
from math import comb, factorial

# --- Utility Functions ---
def zip_probability(lam, k, p_zero=0.0):
    """Zero-inflated Poisson probability."""
    if k == 0:
        return p_zero + (1 - p_zero) * math.exp(-lam)
    return (1 - p_zero) * ((lam ** k) * math.exp(-lam)) / math.factorial(k)

def fair_odds(prob):
    return (1/prob) if prob > 0 else float('inf')


# --- Calculation Logic ---
def calculate_insights():
    try:
        # input helpers
        getf = lambda k: float(entries[k].get()) if entries[k].get() else 0.0
        geti = lambda k: int(entries[k].get())   if entries[k].get() else 0

        # --- Gather inputs ---
        home_avg_scored   = getf("entry_home_avg_scored")
        home_avg_conceded = getf("entry_home_avg_conceded")
        away_avg_scored   = getf("entry_away_avg_scored")
        away_avg_conceded = getf("entry_away_avg_conceded")
        home_xg           = getf("entry_home_xg")
        away_xg           = getf("entry_away_xg")
        home_xg_ag        = getf("entry_home_xg_against")
        away_xg_ag        = getf("entry_away_xg_against")
        elapsed           = getf("entry_elapsed_minutes")
        home_goals        = geti("entry_home_goals")
        away_goals        = geti("entry_away_goals")
        in_xg_home        = getf("entry_in_game_home_xg")
        in_xg_away        = getf("entry_in_game_away_xg")
        home_poss         = getf("entry_home_possession")
        away_poss         = getf("entry_away_possession")
        home_sot          = geti("entry_home_sot")
        away_sot          = geti("entry_away_sot")
        home_box          = getf("entry_home_opp_box")
        away_box          = getf("entry_away_opp_box")
        home_corns        = getf("entry_home_corners")
        away_corns        = getf("entry_away_corners")
        balance           = getf("entry_account_balance")
        kelly_frac        = max(getf("entry_kelly_fraction")/100.0, 0.001)
        live_under        = getf("entry_live_under")      # single under‑market odds
        live_home         = getf("entry_live_home_odds")
        live_draw         = getf("entry_live_draw_odds")
        live_away         = getf("entry_live_away_odds")

        effective_balance = max(balance, 0)

        # --- Expected goals remaining with time decay ---
        frac = max(0.0, (90 - elapsed) / 90.0)
        def time_decay(xg):
            base = math.exp(-0.003 * elapsed)
            base = max(base, 0.5)
            if 90 - elapsed < 10:
                base *= 0.75
            return max(0.1, xg * base)

        lam_h = time_decay(home_xg * frac)
        lam_a = time_decay(away_xg * frac)

        # --- Adjust for current scoreline ---
        def adjust(h, a, lh, la):
            d = h - a
            if d == 1:
                lh, la = lh*0.9,  la*1.2
            elif d == -1:
                lh, la = lh*1.2,  la*0.9
            elif abs(d) >= 2:
                if d>0: lh, la = lh*0.8,  la*1.3
                else:   lh, la = lh*0.8,  la*0.8
            if elapsed>75 and abs(d)>=1:
                if d>0: lh, la = lh*0.85, la*1.15
                else:   lh, la = lh*1.15, la*0.85
            return lh, la

        lam_h, lam_a = adjust(home_goals, away_goals, lam_h, lam_a)

        # --- Seasonal & situational adjustments ---
        pm_h = home_avg_scored / max(0.75, away_avg_conceded)
        pm_a = away_avg_scored / max(0.75, home_avg_conceded)
        lam_h = lam_h*0.85 + pm_h*0.15*frac
        lam_a = lam_a*0.85 + pm_a*0.15*frac

        lam_h *= 1+((home_poss-50)/200)*frac
        lam_a *= 1+((away_poss-50)/200)*frac
        if in_xg_home>1.2: lam_h *= 1+0.15*frac
        if in_xg_away>1.2: lam_a *= 1+0.15*frac
        lam_h *= 1+(home_sot/20)*frac
        lam_a *= 1+(away_sot/20)*frac
        lam_h *= 1+((home_box-20)/200)*frac
        lam_a *= 1+((away_box-20)/200)*frac
        lam_h *= 1+((home_corns-4)/50)*frac
        lam_a *= 1+((away_corns-4)/50)*frac

        # --- Defensive quality adjustment ---
        lam_h *= 1 + (away_xg_ag - 1.0)*0.1*frac
        lam_a *= 1 + (home_xg_ag - 1.0)*0.1*frac

        # --- Bayesian win/draw/away probabilities ---
        def bayes(lam, k, r=3):
            p = r/(r+lam)
            return comb(k+r-1, k)*(p**r)*((1-p)**k)

        hw=aw=dw=0.0
        for gh in range(6):
            for ga in range(6):
                p = bayes(lam_h,gh)*bayes(lam_a,ga)
                if home_goals+gh > away_goals+ga:
                    hw+=p
                elif home_goals+gh < away_goals+ga:
                    aw+=p
                else:
                    dw+=p
        tot = hw+aw+dw
        if tot>0: hw,aw,dw = hw/tot, aw/tot, dw/tot

        # --- Blend with market odds ---
        m_h = 1/live_home  if live_home>0  else 0
        m_d = 1/live_draw  if live_draw>0  else 0
        m_a = 1/live_away  if live_away>0  else 0
        ms  = m_h+m_d+m_a
        if ms>0: m_h,m_d,m_a = m_h/ms, m_d/ms, m_a/ms

        f_h = 0.7*hw + 0.3*m_h
        f_d = 0.7*dw + 0.3*m_d
        f_a = 0.7*aw + 0.3*m_a
        fs  = f_h+f_d+f_a
        if fs>0: f_h,f_d,f_a = f_h/fs, f_d/fs, f_a/fs

        # --- Top 5 likely scorelines ---
        final_probs = {
            (home_goals+i, away_goals+j):
            zip_probability(lam_h,i)*zip_probability(lam_a,j)
            for i in range(10) for j in range(10)
        }
        top5 = sorted(final_probs.items(), key=lambda x:x[1], reverse=True)[:5]

        # --- Build output ---
        current_total = home_goals + away_goals
        limit = current_total + 1.5
        add_probs = {
            (i,j): zip_probability(lam_h,i)*zip_probability(lam_a,j)
            for i in range(10) for j in range(10)
        }
        # allow at most 1 additional goal for Under limit
        fair_under = sum(p for (i,j),p in add_probs.items() if i+j <= 1)

        output = "=== Betting Insights ===\n\n"
        output += "Top 5 Likely Scorelines:\n"
        for s,p in top5:
            output += f"  {s[0]}-{s[1]}: {p*100:.1f}% (Fair Odds: {fair_odds(p):.2f})\n"

        output += f"\nAggregate Probabilities:\n  Draw: {f_d*100:.1f}%\n"
        output += f"  Non-Draw: {(f_h+f_a)*100:.1f}%\n\n"

        # Only Under limit
        output += f"Under {limit} Goals: Fair {fair_odds(fair_under):.2f} | Live {live_under:.2f}\n\n"

        output += (
            f"Market Odds (Live | Fair):\n"
            f"  Home: {live_home:.2f} | {fair_odds(f_h):.2f}\n"
            f"  Draw: {live_draw:.2f} | {fair_odds(f_d):.2f}\n"
            f"  Away: {live_away:.2f} | {fair_odds(f_a):.2f}\n\n"
        )
        output += (
            f"Likely Goals Remaining:\n"
            f"  Total: {lam_h+lam_a:.2f} (Home: {lam_h:.2f}, Away: {lam_a:.2f})\n\n"
        )

        # Kelly‑based lay
        if live_under > 0 and live_under < fair_odds(fair_under):
            edge = (fair_odds(fair_under) - live_under) / fair_odds(fair_under)
            k = kelly_frac * edge
            liability = effective_balance * k
            stake = liability / (live_under - 1) if live_under > 1 else 0
            output += f"Lay Under {limit}: Edge {edge:.2%}, Liab {liability:.2f}, Stake {stake:.2f}\n"
        else:
            output += f"No lay value on Under {limit}\n"

        # display
        result_text.config(state="normal")
        result_text.delete("1.0", tk.END)
        for line in output.split("\n"):
            tag = ("insight" if line.startswith("===")
                   else "lay"     if line.strip().startswith("Lay")
                   else "normal")
            result_text.insert(tk.END, line + "\n", tag)
        result_text.config(state="disabled")

    except ValueError:
        result_text.config(state="normal")
        result_text.delete("1.0", tk.END)
        result_text.insert(tk.END, "Please enter valid numerical values.", "normal")
        result_text.config(state="disabled")


# --- Reset Function ---
def reset_all():
    for e in entries.values():
        e.delete(0, tk.END)
    result_text.config(state="normal")
    result_text.delete("1.0", tk.END)
    result_text.config(state="disabled")


# --- GUI Setup ---
root = tk.Tk()
root.title("Odds Apex - Unders")

canvas = tk.Canvas(root)
canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
vsb = tk.Scrollbar(root, orient=tk.VERTICAL, command=canvas.yview)
vsb.pack(side=tk.RIGHT, fill=tk.Y)
canvas.configure(yscrollcommand=vsb.set)

main = tk.Frame(canvas)
canvas.create_window((0,0), window=main, anchor="nw")
main.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

entries = {
    "entry_home_avg_scored":   tk.Entry(main),
    "entry_home_avg_conceded": tk.Entry(main),
    "entry_away_avg_scored":   tk.Entry(main),
    "entry_away_avg_conceded": tk.Entry(main),
    "entry_home_xg":           tk.Entry(main),
    "entry_away_xg":           tk.Entry(main),
    "entry_home_xg_against":   tk.Entry(main),
    "entry_away_xg_against":   tk.Entry(main),
    "entry_elapsed_minutes":   tk.Entry(main),
    "entry_home_goals":        tk.Entry(main),
    "entry_away_goals":        tk.Entry(main),
    "entry_in_game_home_xg":   tk.Entry(main),
    "entry_in_game_away_xg":   tk.Entry(main),
    "entry_home_possession":   tk.Entry(main),
    "entry_away_possession":   tk.Entry(main),
    "entry_home_sot":          tk.Entry(main),
    "entry_away_sot":          tk.Entry(main),
    "entry_home_opp_box":      tk.Entry(main),
    "entry_away_opp_box":      tk.Entry(main),
    "entry_home_corners":      tk.Entry(main),
    "entry_away_corners":      tk.Entry(main),
    "entry_account_balance":   tk.Entry(main),
    "entry_kelly_fraction":    tk.Entry(main),
    "entry_live_under":        tk.Entry(main),
    "entry_live_home_odds":    tk.Entry(main),
    "entry_live_draw_odds":    tk.Entry(main),
    "entry_live_away_odds":    tk.Entry(main),
}

labels = [
    "Home Avg Goals Scored","Home Avg Goals Conceded",
    "Away Avg Goals Scored","Away Avg Goals Conceded",
    "Home xG","Away xG","Home xG Against","Away xG Against",
    "Elapsed Minutes","Home Goals","Away Goals",
    "In-Game Home xG","In-Game Away xG",
    "Home Possession %","Away Possession %",
    "Home SOT","Away SOT",
    "Home Opp Box Touches","Away Opp Box Touches",
    "Home Corners","Away Corners",
    "Account Balance","Kelly Staking Fraction (%)",
    "Live Odds Under (dynamic .5)",
    "Live Odds Home","Live Odds Draw","Live Odds Away"
]

for i,(k,t) in enumerate(zip(entries,labels)):
    tk.Label(main, text=t).grid(row=i, column=0, sticky="e", padx=5, pady=2)
    entries[k].grid(row=i, column=1, padx=5, pady=2)

# result text box
res_frame = tk.Frame(main, width=800, height=250)
res_frame.grid(row=len(entries), column=0, columnspan=2, pady=10)
res_frame.grid_propagate(False)
result_text = tk.Text(res_frame, wrap=tk.WORD, bg="white")
result_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
tk.Scrollbar(res_frame, command=result_text.yview).pack(side=tk.RIGHT, fill=tk.Y)
result_text.config(yscrollcommand=lambda *a: None)

# buttons
tk.Button(main, text="Calculate Match Insights", command=calculate_insights)\
  .grid(row=len(entries)+1, column=0, columnspan=2, pady=5)
tk.Button(main, text="Reset All Fields", command=reset_all)\
  .grid(row=len(entries)+2, column=0, columnspan=2, pady=5)

# tag styling
result_text.tag_configure("insight", foreground="green")
result_text.tag_configure("lay",     foreground="red")
result_text.tag_configure("normal",  foreground="black")

root.mainloop()

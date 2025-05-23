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
        live_u25          = getf("entry_live_under_odds")
        live_o25          = getf("entry_live_over_odds")
        live_home         = getf("entry_live_home_odds")
        live_draw         = getf("entry_live_draw_odds")
        live_away         = getf("entry_live_away_odds")

        # --- Kelly fraction (%) ---
        try:
            kelly_frac = getf("entry_kelly_fraction") / 100.0
        except:
            kelly_frac = 0.125
        if kelly_frac <= 0:
            kelly_frac = 0.125

        # --- Parse target scores input (“1-0@3.4,2-1@5.2”) ---
        raw = entries["entry_target_scores"].get().split(',')
        target_scores = []
        for part in raw:
            p = part.strip()
            if '@' in p and '-' in p:
                sc,od = p.split('@')
                a,b = sc.split('-')
                try:
                    target_scores.append(((int(a), int(b)), float(od)))
                except:
                    pass

        effective_balance = max(balance, 0)

        # --- Expected goals remaining w/ time decay ---
        frac = max(0.0, (90 - elapsed) / 90.0)
        def time_decay(lg):
            base = math.exp(-0.003 * elapsed)
            base = max(base, 0.5)
            if 90 - elapsed < 10:
                base *= 0.75
            return max(0.1, lg * base)

        lam_h = time_decay(home_xg * frac)
        lam_a = time_decay(away_xg * frac)

        # --- Adjust for current scoreline ---
        def adjust_scoreline(h,a,lh,la):
            d = h - a
            if d == 1:
                lh, la = lh*0.9, la*1.2
            elif d == -1:
                lh, la = lh*1.2, la*0.9
            elif abs(d) >= 2:
                if d>0: lh,la = lh*0.8, la*1.3
                else:   lh,la = lh*0.8, la*0.8
            if elapsed>75 and abs(d)>=1:
                if d>0: lh,la = lh*0.85, la*1.15
                else:   lh,la = lh*1.15, la*0.85
            return lh, la

        lam_h, lam_a = adjust_scoreline(home_goals, away_goals, lam_h, lam_a)

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
                if home_goals+gh > away_goals+ga: hw+=p
                elif home_goals+gh < away_goals+ga: aw+=p
                else: dw+=p

        total = hw+aw+dw
        if total>0: hw,aw,dw = hw/total, aw/total, dw/total

        # --- Blend with market odds ---
        m_h = 1/live_home if live_home>0 else 0
        m_d = 1/live_draw if live_draw>0 else 0
        m_a = 1/live_away if live_away>0 else 0
        ms = m_h+m_d+m_a
        if ms>0: m_h,m_d,m_a = m_h/ms, m_d/ms, m_a/ms

        f_h = 0.7*hw + 0.3*m_h
        f_d = 0.7*dw + 0.3*m_d
        f_a = 0.7*aw + 0.3*m_a
        fs = f_h+f_d+f_a
        if fs>0: f_h,f_d,f_a = f_h/fs, f_d/fs, f_a/fs

        # --- Scoreline probabilities & Top 5 ---
        probs = {}
        for i in range(10):
            for j in range(10):
                probs[(home_goals+i, away_goals+j)] = zip_probability(lam_h,i)*zip_probability(lam_a,j)
        top5 = sorted(probs.items(), key=lambda x: x[1], reverse=True)[:5]

        # --- Over/Under 2.5 Goals ---
        totg = home_goals+away_goals
        under_p = sum(zip_probability(lam_h,i)*zip_probability(lam_a,j)
                      for i in range(10) for j in range(10) if totg+i+j<=2)
        over_p = 1-under_p

        # --- Likely goals remaining ---
        likely_h, likely_a = lam_h, lam_a

        # --- Build full output ---
        output = "=== Betting Insights ===\n\n"
        output += "Top 5 Likely Scorelines:\n"
        for s,p in top5:
            output += f"  {s[0]}-{s[1]}: {p*100:.1f}% (Fair Odds: {fair_odds(p):.2f})\n"
        output += f"\nAggregate Probabilities:\n  Draw: {f_d*100:.1f}%\n  Non-Draw: {(f_h+f_a)*100:.1f}%\n\n"
        output += f"Over/Under 2.5 Goals:\n  Over: Fair {fair_odds(over_p):.2f} | Live {live_o25:.2f}\n"
        output += f"  Under: Fair {fair_odds(under_p):.2f} | Live {live_u25:.2f}\n\n"
        output += f"Market Odds (Live | Fair):\n  Home: {live_home:.2f} | {fair_odds(f_h):.2f}\n"
        output += f"  Draw: {live_draw:.2f} | {fair_odds(f_d):.2f}\n"
        output += f"  Away: {live_away:.2f} | {fair_odds(f_a):.2f}\n\n"
        output += f"Likely Goals Remaining:\n  Total: {likely_h+likely_a:.2f} (Home: {likely_h:.2f}, Away: {likely_a:.2f})\n\n"

        # --- Correct‑Score Kelly Lay Recommendations only ---
        lays = []
        for score, live_odds in target_scores:
            p = probs.get(score,0.0)
            f_od = fair_odds(p)
            edge_l = (live_odds - f_od)/live_odds if live_odds>0 else 0
            if edge_l>0:
                k = kelly_frac * edge_l
                liability = effective_balance * k
                stake_lay = liability/(live_odds-1) if live_odds>1 else 0
                lays.append(
                    f"Lay {score[0]}-{score[1]}: "
                    f"Edge {edge_l:.2%}, Liab {liability:.2f}, Stake {stake_lay:.2f}"
                )

        output += "Correct‑Score Lay Recommendations:\n"
        if lays:
            for l in lays:
                output += f"  {l}\n"
        else:
            output += "  No lays.\n"

        # --- Display results ---
        result_text_widget.config(state="normal")
        result_text_widget.delete("1.0", tk.END)
        for line in output.split("\n"):
            if line.startswith("==="):
                tag = "insight"
            elif line.strip().startswith("Lay"):
                tag = "lay"
            else:
                tag = "normal"
            result_text_widget.insert(tk.END, line + "\n", tag)
        result_text_widget.config(state="disabled")

    except ValueError:
        result_text_widget.config(state="normal")
        result_text_widget.delete("1.0", tk.END)
        result_text_widget.insert(tk.END, "Please enter valid numerical values.", "normal")
        result_text_widget.config(state="disabled")


# --- Reset Function ---
def reset_all():
    for e in entries.values():
        e.delete(0, tk.END)
    result_text_widget.config(state="normal")
    result_text_widget.delete("1.0", tk.END)
    result_text_widget.config(state="disabled")


# --- GUI Setup ---
root = tk.Tk()
root.title("Odds Apex - LTD")

canvas = tk.Canvas(root)
canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
vsb = tk.Scrollbar(root, orient=tk.VERTICAL, command=canvas.yview)
vsb.pack(side=tk.RIGHT, fill=tk.Y)
canvas.configure(yscrollcommand=vsb.set)
main_frame = tk.Frame(canvas)
canvas.create_window((0,0), window=main_frame, anchor="nw")
main_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

entries = {
    "entry_home_avg_scored":   tk.Entry(main_frame),
    "entry_home_avg_conceded": tk.Entry(main_frame),
    "entry_away_avg_scored":   tk.Entry(main_frame),
    "entry_away_avg_conceded": tk.Entry(main_frame),
    "entry_home_xg":           tk.Entry(main_frame),
    "entry_away_xg":           tk.Entry(main_frame),
    "entry_home_xg_against":   tk.Entry(main_frame),
    "entry_away_xg_against":   tk.Entry(main_frame),
    "entry_elapsed_minutes":   tk.Entry(main_frame),
    "entry_home_goals":        tk.Entry(main_frame),
    "entry_away_goals":        tk.Entry(main_frame),
    "entry_in_game_home_xg":   tk.Entry(main_frame),
    "entry_in_game_away_xg":   tk.Entry(main_frame),
    "entry_home_possession":   tk.Entry(main_frame),
    "entry_away_possession":   tk.Entry(main_frame),
    "entry_home_sot":          tk.Entry(main_frame),
    "entry_away_sot":          tk.Entry(main_frame),
    "entry_home_opp_box":      tk.Entry(main_frame),
    "entry_away_opp_box":      tk.Entry(main_frame),
    "entry_home_corners":      tk.Entry(main_frame),
    "entry_away_corners":      tk.Entry(main_frame),
    "entry_account_balance":   tk.Entry(main_frame),
    "entry_kelly_fraction":    tk.Entry(main_frame),
    "entry_live_under_odds":   tk.Entry(main_frame),
    "entry_live_over_odds":    tk.Entry(main_frame),
    "entry_live_home_odds":    tk.Entry(main_frame),
    "entry_live_draw_odds":    tk.Entry(main_frame),
    "entry_live_away_odds":    tk.Entry(main_frame),
    "entry_target_scores":     tk.Entry(main_frame),
}

labels = [
    "Home Avg Goals Scored", "Home Avg Goals Conceded",
    "Away Avg Goals Scored", "Away Avg Goals Conceded",
    "Home xG", "Away xG",
    "Home xG Against", "Away xG Against",
    "Elapsed Minutes", "Home Goals", "Away Goals",
    "In-Game Home xG", "In-Game Away xG",
    "Home Possession %", "Away Possession %",
    "Home Shots on Target", "Away Shots on Target",
    "Home Opp Box Touches", "Away Opp Box Touches",
    "Home Corners", "Away Corners",
    "Account Balance", "Kelly Staking Fraction (%)",
    "Live Under 2.5 Odds", "Live Over 2.5 Odds",
    "Live Odds Home", "Live Odds Draw", "Live Odds Away",
    "Target Scores@LiveOdds (e.g. 1-0@3.4,2-1@5.2)"
]

for i,(k,t) in enumerate(zip(entries,labels)):
    tk.Label(main_frame, text=t).grid(row=i, column=0, sticky="e", padx=5, pady=2)
    entries[k].grid(row=i, column=1, padx=5, pady=2)

result_frame = tk.Frame(main_frame, width=800, height=250)
result_frame.grid(row=len(entries), column=0, columnspan=2, padx=5, pady=10)
result_frame.grid_propagate(False)

result_text_widget = tk.Text(result_frame, wrap=tk.WORD, bg="white")
result_text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
tk.Scrollbar(result_frame, command=result_text_widget.yview).pack(side=tk.RIGHT, fill=tk.Y)
result_text_widget.config(yscrollcommand=lambda *a: None)

tk.Button(main_frame, text="Calculate Match Insights", command=calculate_insights)\
  .grid(row=len(entries)+1, column=0, columnspan=2, pady=5)
tk.Button(main_frame, text="Reset All Fields", command=reset_all)\
  .grid(row=len(entries)+2, column=0, columnspan=2, pady=5)

result_text_widget.tag_configure("insight", foreground="green")
result_text_widget.tag_configure("lay",     foreground="red")
result_text_widget.tag_configure("normal",  foreground="black")

root.mainloop()

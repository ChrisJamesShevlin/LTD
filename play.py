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

def dynamic_kelly(edge):
    # This function is not used directly in the in-play version,
    # since we call the version defined in calculate_insights.
    try:
        multiplier = float(entries["entry_kelly_fraction"].get()) / 100.0
    except ValueError:
        multiplier = 0.125
    if multiplier <= 0:
        multiplier = 0.125
    return max(0, multiplier * edge)

# --- In-Play Calculation Logic ---
def calculate_insights():
    try:
        # 1) Retrieve all inputs from the entries dictionary
        getf = lambda k: float(entries[k].get())
        geti = lambda k: int(entries[k].get())

        home_avg_scored     = getf("entry_home_avg_scored")
        home_avg_conceded   = getf("entry_home_avg_conceded")
        away_avg_scored     = getf("entry_away_avg_scored")
        away_avg_conceded   = getf("entry_away_avg_conceded")

        home_xg             = getf("entry_home_xg")
        away_xg             = getf("entry_away_xg")
        # New inputs for xG Against
        home_xg_against     = getf("entry_home_xg_against")
        away_xg_against     = getf("entry_away_xg_against")

        elapsed_minutes     = getf("entry_elapsed_minutes")
        home_goals          = geti("entry_home_goals")
        away_goals          = geti("entry_away_goals")
        in_game_home_xg     = getf("entry_in_game_home_xg")
        in_game_away_xg     = getf("entry_in_game_away_xg")
        home_possession     = getf("entry_home_possession")
        away_possession     = getf("entry_away_possession")
        home_sot            = geti("entry_home_sot")
        away_sot            = geti("entry_away_sot")
        home_opp_box        = getf("entry_home_opp_box")
        away_opp_box        = getf("entry_away_opp_box")
        home_corners        = getf("entry_home_corners")
        away_corners        = getf("entry_away_corners")
        account_balance     = getf("entry_account_balance")

        live_under_odds     = getf("entry_live_under_odds")
        live_over_odds      = getf("entry_live_over_odds")
        live_odds_home      = getf("entry_live_home_odds")
        live_odds_draw      = getf("entry_live_draw_odds")
        live_odds_away      = getf("entry_live_away_odds")
        
        # 2) (Skipping any persistent history for simplicity.)
        effective_balance = account_balance if account_balance >= 0 else 0
        fraction_remaining = max(0.0, (90 - elapsed_minutes) / 90.0)

        # -----------------------------------------------------------------
        # MATCH ODDS CALCULATION (Using a Bayesian approach with time decay and blending with market)
        # -----------------------------------------------------------------
        home_xg_rem = home_xg * fraction_remaining
        away_xg_rem = away_xg * fraction_remaining

        def time_decay_adjustment(lambda_xg, elapsed):
            remaining = 90 - elapsed
            base_decay = math.exp(-0.003 * elapsed)
            base_decay = max(base_decay, 0.5)
            if remaining < 10:
                base_decay *= 0.75
            return max(0.1, lambda_xg * base_decay)

        lambda_home = time_decay_adjustment(home_xg_rem, elapsed_minutes)
        lambda_away = time_decay_adjustment(away_xg_rem, elapsed_minutes)

        def adjust_xg_for_scoreline(home, away, lam_home, lam_away, elapsed):
            diff = home - away
            if diff == 1:
                lam_home *= 0.9
                lam_away *= 1.2
            elif diff == -1:
                lam_home *= 1.2
                lam_away *= 0.9
            elif abs(diff) >= 2:
                if diff > 0:
                    lam_home *= 0.8
                    lam_away *= 1.3
                else:
                    lam_home *= 0.8
                    lam_away *= 0.8
            if elapsed > 75 and abs(diff) >= 1:
                if diff > 0:
                    lam_home *= 0.85
                    lam_away *= 1.15
                else:
                    lam_home *= 1.15
                    lam_away *= 0.85
            return lam_home, lam_away

        lambda_home, lambda_away = adjust_xg_for_scoreline(home_goals, away_goals, lambda_home, lambda_away, elapsed_minutes)

        pm_home = home_avg_scored / max(0.75, away_avg_conceded)
        pm_away = away_avg_scored / max(0.75, home_avg_conceded)
        lambda_home = (lambda_home * 0.85) + (pm_home * 0.15 * fraction_remaining)
        lambda_away = (lambda_away * 0.85) + (pm_away * 0.15 * fraction_remaining)

        lambda_home *= 1 + ((home_possession - 50) / 200) * fraction_remaining
        lambda_away *= 1 + ((away_possession - 50) / 200) * fraction_remaining
        if in_game_home_xg > 1.2:
            lambda_home *= (1 + 0.15 * fraction_remaining)
        if in_game_away_xg > 1.2:
            lambda_away *= (1 + 0.15 * fraction_remaining)
        lambda_home *= 1 + (home_sot / 20) * fraction_remaining
        lambda_away *= 1 + (away_sot / 20) * fraction_remaining
        lambda_home *= 1 + ((home_opp_box - 20) / 200) * fraction_remaining
        lambda_away *= 1 + ((away_opp_box - 20) / 200) * fraction_remaining
        lambda_home *= 1 + ((home_corners - 4) / 50) * fraction_remaining
        lambda_away *= 1 + ((away_corners - 4) / 50) * fraction_remaining
        
        # --- NEW: Incorporate Opponent xG Against for defensive quality adjustment ---
        # If an opposition concedes a higher xG than average, boost the expected goals.
        lambda_home *= 1 + (away_xg_against - 1.0) * 0.1 * fraction_remaining
        lambda_away *= 1 + (home_xg_against - 1.0) * 0.1 * fraction_remaining

        def bayesian_goal_probability(expected_lambda, k, r=2):
            p = r / (r + expected_lambda)
            return comb(k + r - 1, k) * (p ** r) * ((1 - p) ** k)

        home_win_prob = 0.0
        away_win_prob = 0.0
        draw_prob = 0.0
        for gh in range(6):
            for ga in range(6):
                prob = bayesian_goal_probability(lambda_home, gh, r=3) * bayesian_goal_probability(lambda_away, ga, r=3)
                # Adjust for the current scoreline when evaluating final result
                if (home_goals + gh) > (away_goals + ga):
                    home_win_prob += prob
                elif (home_goals + gh) < (away_goals + ga):
                    away_win_prob += prob
                else:
                    draw_prob += prob
        total_prob = home_win_prob + away_win_prob + draw_prob
        if total_prob > 0:
            home_win_prob /= total_prob
            away_win_prob /= total_prob
            draw_prob /= total_prob

        # Blend with market odds (70% model, 30% market)
        market_home = 1 / live_odds_home if live_odds_home > 0 else 0
        market_draw = 1 / live_odds_draw if live_odds_draw > 0 else 0
        market_away = 1 / live_odds_away if live_odds_away > 0 else 0
        market_total = market_home + market_draw + market_away
        if market_total > 0:
            market_home /= market_total
            market_draw /= market_total
            market_away /= market_total

        final_home_prob = 0.7 * home_win_prob + 0.3 * market_home
        final_draw_prob = 0.7 * draw_prob     + 0.3 * market_draw
        final_away_prob = 0.7 * away_win_prob + 0.3 * market_away
        final_sum = final_home_prob + final_draw_prob + final_away_prob
        if final_sum > 0:
            final_home_prob /= final_sum
            final_draw_prob /= final_sum
            final_away_prob /= final_sum

        fair_odds_home = fair_odds(final_home_prob)
        fair_odds_draw = fair_odds(final_draw_prob)
        fair_odds_away = fair_odds(final_away_prob)

        # -----------------------------------------------------------------
        # SCORELINE PROBABILITIES (using Poisson for likely outcomes)
        # Now accounting for the current score.
        # -----------------------------------------------------------------
        goal_range = 10
        scoreline_probs = {}
        for i in range(goal_range):
            for j in range(goal_range):
                # i and j represent additional goals from now until the end of the match.
                p = zip_probability(lambda_home, i) * zip_probability(lambda_away, j)
                final_h = home_goals + i
                final_a = away_goals + j
                scoreline_probs[(final_h, final_a)] = p
        sorted_scorelines = sorted(scoreline_probs.items(), key=lambda x: x[1], reverse=True)[:5]

        # For aggregate probabilities, we use the blended probabilities from the Bayesian approach.
        agg_draw_pct = draw_prob * 100
        agg_non_draw_pct = (home_win_prob + away_win_prob) * 100

        # -----------------------------------------------------------------
        # Over/Under 2.5 Goals
        # Now taking into account the current total goals.
        # -----------------------------------------------------------------
        current_total_goals = home_goals + away_goals
        under_prob_model = 0.0
        for i in range(goal_range):
            for j in range(goal_range):
                p = zip_probability(lambda_home, i) * zip_probability(lambda_away, j)
                if current_total_goals + i + j <= 2:
                    under_prob_model += p
        over_prob_model = 1 - under_prob_model
        fair_under_odds = fair_odds(under_prob_model)
        fair_over_odds  = fair_odds(over_prob_model)

        # --- NEW: Likely Goals Remaining ---
        # Since lambda_home and lambda_away represent the expected goals for the remainder,
        # we can use them to estimate the remaining goals in the match.
        likely_home_remaining = lambda_home
        likely_away_remaining = lambda_away
        likely_total_remaining = likely_home_remaining + likely_away_remaining

        # -----------------------------------------------------------------
        # Lay Draw Recommendation (only one calculation)
        # -----------------------------------------------------------------
        if live_odds_draw > 1 and fair_odds_draw > live_odds_draw:
            edge = (fair_odds_draw - live_odds_draw) / fair_odds_draw
            try:
                multiplier = float(entries["entry_kelly_fraction"].get()) / 100.0
            except ValueError:
                multiplier = 0.125
            if multiplier <= 0:
                multiplier = 0.125
            kelly = max(0, multiplier * edge)
            liability = effective_balance * kelly
            liability = min(liability, effective_balance * 0.10)
            lay_stake = liability / (live_odds_draw - 1) if (live_odds_draw - 1) > 0 else 0
            lay_draw_rec = f"Lay Draw: Edge {edge:.2%}, Liability {liability:.2f}, Stake {lay_stake:.2f}"
        else:
            lay_draw_rec = "No lay edge for Draw."

        # -----------------------------------------------------------------
        # Final Output (Matching Pre-Match Style)
        # -----------------------------------------------------------------
        output = "=== Betting Insights ===\n\n"
        output += "Top 5 Likely Scorelines:\n"
        for (score, prob) in sorted_scorelines:
            output += f"  {score[0]}-{score[1]}: {prob*100:.1f}% (Fair Odds: {fair_odds(prob):.2f})\n"
        output += "\nAggregate Scoreline Probabilities:\n"
        output += f"  Draw Scorelines: {final_draw_prob*100:.1f}%\n"
        output += f"  Non-Draw Scorelines: {(final_home_prob+final_away_prob)*100:.1f}%\n\n"
        output += "Over/Under 2.5 Goals:\n"
        output += f"  Over: Fair Odds {fair_over_odds:.2f} | Live Odds {live_over_odds:.2f}\n"
        output += f"  Under: Fair Odds {fair_under_odds:.2f} | Live Odds {live_under_odds:.2f}\n\n"
        output += "Market Odds (Live | Fair):\n"
        output += f"  Home: {live_odds_home:.2f} | {fair_odds_home:.2f}\n"
        output += f"  Draw: {live_odds_draw:.2f} | {fair_odds_draw:.2f}\n"
        output += f"  Away: {live_odds_away:.2f} | {fair_odds_away:.2f}\n\n"
        output += "Likely Goals Remaining:\n"
        output += f"  Total: {likely_total_remaining:.2f} (Home: {likely_home_remaining:.2f}, Away: {likely_away_remaining:.2f})\n\n"
        output += "Lay Draw Recommendation:\n"
        output += f"  {lay_draw_rec}\n"

        # Insert into the text widget with color tags
        result_text_widget.config(state="normal")
        result_text_widget.delete("1.0", tk.END)
        for line in output.split("\n"):
            if line.startswith("==="):
                result_text_widget.insert(tk.END, line + "\n", "insight")
            elif "Lay Draw" in line:
                result_text_widget.insert(tk.END, line + "\n", "lay")
            elif "Back" in line:
                result_text_widget.insert(tk.END, line + "\n", "back")
            else:
                result_text_widget.insert(tk.END, line + "\n", "normal")
        result_text_widget.config(state="disabled")

    except ValueError:
        result_text_widget.config(state="normal")
        result_text_widget.delete("1.0", tk.END)
        result_text_widget.insert(tk.END, "Please enter valid numerical values.", "normal")
        result_text_widget.config(state="disabled")

def reset_all():
    for e in entries.values():
        e.delete(0, tk.END)
    result_text_widget.config(state="normal")
    result_text_widget.delete("1.0", tk.END)
    result_text_widget.config(state="disabled")

# --- GUI Layout (Pre-Match Style) ---
root = tk.Tk()
root.title("Odds Apex")

# Do NOT force the entire window bigger with root.geometry(...)

# --- Create a canvas and scrollbar to make the entire window scrollable ---
canvas = tk.Canvas(root)
canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

vsb = tk.Scrollbar(root, orient="vertical", command=canvas.yview)
vsb.pack(side=tk.RIGHT, fill=tk.Y)
canvas.configure(yscrollcommand=vsb.set)

# Create a frame inside the canvas that will hold all widgets
main_frame = tk.Frame(canvas)
canvas.create_window((0,0), window=main_frame, anchor="nw")

def onFrameConfigure(event):
    canvas.configure(scrollregion=canvas.bbox("all"))
main_frame.bind("<Configure>", onFrameConfigure)

# Define input fields (same as pre-match) inside main_frame
entries = {
    "entry_home_avg_scored":      tk.Entry(main_frame),
    "entry_home_avg_conceded":    tk.Entry(main_frame),
    "entry_away_avg_scored":      tk.Entry(main_frame),
    "entry_away_avg_conceded":    tk.Entry(main_frame),
    "entry_home_xg":              tk.Entry(main_frame),
    "entry_away_xg":              tk.Entry(main_frame),
    # --- New Fields for xG Against ---
    "entry_home_xg_against":      tk.Entry(main_frame),
    "entry_away_xg_against":      tk.Entry(main_frame),
    "entry_elapsed_minutes":      tk.Entry(main_frame),
    "entry_home_goals":           tk.Entry(main_frame),
    "entry_away_goals":           tk.Entry(main_frame),
    "entry_in_game_home_xg":      tk.Entry(main_frame),
    "entry_in_game_away_xg":      tk.Entry(main_frame),
    "entry_home_possession":      tk.Entry(main_frame),
    "entry_away_possession":      tk.Entry(main_frame),
    "entry_home_sot":             tk.Entry(main_frame),
    "entry_away_sot":             tk.Entry(main_frame),
    "entry_home_opp_box":         tk.Entry(main_frame),
    "entry_away_opp_box":         tk.Entry(main_frame),
    "entry_home_corners":         tk.Entry(main_frame),
    "entry_away_corners":         tk.Entry(main_frame),
    "entry_account_balance":      tk.Entry(main_frame),
    "entry_kelly_fraction":       tk.Entry(main_frame),
    "entry_live_under_odds":      tk.Entry(main_frame),
    "entry_live_over_odds":       tk.Entry(main_frame),
    "entry_live_home_odds":       tk.Entry(main_frame),
    "entry_live_draw_odds":       tk.Entry(main_frame),
    "entry_live_away_odds":       tk.Entry(main_frame)
}

labels_text = [
    "Home Avg Goals Scored", "Home Avg Goals Conceded",
    "Away Avg Goals Scored", "Away Avg Goals Conceded",
    "Home Xg", "Away Xg",
    # --- New Labels for xG Against ---
    "Home Xg Against", "Away Xg Against",
    "Elapsed Minutes", "Home Goals", "Away Goals",
    "In-Game Home Xg", "In-Game Away Xg",
    "Home Possession %", "Away Possession %",
    "Home Shots on Target", "Away Shots on Target",
    "Home Opp Box Touches", "Away Opp Box Touches",
    "Home Corners", "Away Corners",
    "Account Balance", "Kelly Staking Fraction (%)",
    "Live Under 2.5 Odds", "Live Over 2.5 Odds",
    "Live Odds Home", "Live Odds Draw", "Live Odds Away"
]

for i, (key, text) in enumerate(zip(entries.keys(), labels_text)):
    label = tk.Label(main_frame, text=text)
    label.grid(row=i, column=0, padx=5, pady=5, sticky="e")
    entries[key].grid(row=i, column=1, padx=5, pady=5)

# Create a frame for the output with a FIXED size so the white box is forced to appear bigger
result_frame = tk.Frame(main_frame, width=800, height=250)
result_frame.grid(row=len(entries), column=0, columnspan=2, padx=5, pady=5)
result_frame.grid_propagate(False)

# Create a bigger Text widget inside that fixed-size frame
result_text_widget = tk.Text(result_frame, wrap=tk.WORD, background="white")
result_text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

scrollbar = tk.Scrollbar(result_frame, command=result_text_widget.yview)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
result_text_widget.config(yscrollcommand=scrollbar.set)

calc_button = tk.Button(main_frame, text="Calculate Match Insights", command=calculate_insights)
calc_button.grid(row=len(entries)+1, column=0, columnspan=2, padx=5, pady=10)

reset_button = tk.Button(main_frame, text="Reset All Fields", command=reset_all)
reset_button.grid(row=len(entries)+2, column=0, columnspan=2, padx=5, pady=10)

# Configure text tags
result_text_widget.tag_configure("insight", foreground="green")
result_text_widget.tag_configure("lay", foreground="red")
result_text_widget.tag_configure("normal", foreground="black")

root.mainloop()

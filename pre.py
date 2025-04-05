import tkinter as tk
import math

def zip_probability(lam, k, p_zero=0.0):
    """
    Zero-inflated Poisson probability.
    p_zero is set to 0.0 to remove extra weighting for 0 goals.
    """
    if k == 0:
        return p_zero + (1 - p_zero) * math.exp(-lam)
    return (1 - p_zero) * ((lam ** k) * math.exp(-lam)) / math.factorial(k)

def fair_odds(prob):
    return (1/prob) if prob > 0 else float('inf')

def dynamic_kelly(edge):
    # Read Kelly fraction from the new user input (as a percentage)
    try:
        multiplier = float(entries["entry_kelly_fraction"].get()) / 100.0
    except ValueError:
        multiplier = 0.125  # default to 12.5%
    if multiplier <= 0:
        multiplier = 0.125
    return max(0, multiplier * edge)

def calculate_insights():
    try:
        # --- 1) Retrieve all inputs ---
        avg_goals_home_scored   = float(entries["entry_home_scored"].get())
        avg_goals_home_conceded = float(entries["entry_home_conceded"].get())
        avg_goals_away_scored   = float(entries["entry_away_scored"].get())
        avg_goals_away_conceded = float(entries["entry_away_conceded"].get())
        
        injuries_home           = int(entries["entry_injuries_home"].get())
        injuries_away           = int(entries["entry_injuries_away"].get())
        position_home           = int(entries["entry_position_home"].get())
        position_away           = int(entries["entry_position_away"].get())
        form_home               = int(entries["entry_form_home"].get())
        form_away               = int(entries["entry_form_away"].get())
        
        home_xg_scored   = float(entries["entry_home_xg_scored"].get())
        away_xg_scored   = float(entries["entry_away_xg_scored"].get())
        home_xg_conceded = float(entries["entry_home_xg_conceded"].get())
        away_xg_conceded = float(entries["entry_away_xg_conceded"].get())
        
        live_under_odds = float(entries["entry_live_under_odds"].get())
        live_over_odds  = float(entries["entry_live_over_odds"].get())
        live_home_odds  = float(entries["entry_live_home_odds"].get())
        live_draw_odds  = float(entries["entry_live_draw_odds"].get())
        live_away_odds  = float(entries["entry_live_away_odds"].get())
        
        account_balance = float(entries["entry_account_balance"].get())
        
        # --- 2) Calculate adjusted expected goals for each team ---
        adjusted_home_goals = ((avg_goals_home_scored + home_xg_scored +
                                avg_goals_away_conceded + away_xg_conceded) / 4)
        adjusted_home_goals *= (1 - 0.03 * injuries_home)
        adjusted_home_goals += form_home * 0.1 - position_home * 0.01
        
        adjusted_away_goals = ((avg_goals_away_scored + away_xg_scored +
                                avg_goals_home_conceded + home_xg_conceded) / 4)
        adjusted_away_goals *= (1 - 0.03 * injuries_away)
        adjusted_away_goals += form_away * 0.1 - position_away * 0.01
        
        # --- 3) Calculate scoreline probabilities using zero-inflated Poisson ---
        goal_range = 10
        scoreline_probs = {}
        for i in range(goal_range):
            for j in range(goal_range):
                p = zip_probability(adjusted_home_goals, i) * zip_probability(adjusted_away_goals, j)
                scoreline_probs[(i, j)] = p
        
        # --- 4) Top 5 most likely scorelines ---
        sorted_scorelines = sorted(scoreline_probs.items(), key=lambda x: x[1], reverse=True)
        top5 = sorted_scorelines[:5]
        
        # --- 5) Match result probabilities from scorelines ---
        model_home_win = sum(p for (i, j), p in scoreline_probs.items() if i > j)
        model_draw     = sum(p for (i, j), p in scoreline_probs.items() if i == j)
        model_away_win = sum(p for (i, j), p in scoreline_probs.items() if i < j)
        
        # --- 6) Blend model probabilities with live odds for match result ---
        live_home_prob = 1 / live_home_odds if live_home_odds > 0 else 0
        live_draw_prob = 1 / live_draw_odds if live_draw_odds > 0 else 0
        live_away_prob = 1 / live_away_odds if live_away_odds > 0 else 0
        sum_live = live_home_prob + live_draw_prob + live_away_prob
        if sum_live > 0:
            live_home_prob /= sum_live
            live_draw_prob /= sum_live
            live_away_prob /= sum_live
        
        blend_factor = 0.3  # 30% live, 70% model
        final_home_win = model_home_win * (1 - blend_factor) + live_home_prob * blend_factor
        final_draw     = model_draw     * (1 - blend_factor) + live_draw_prob * blend_factor
        final_away_win = model_away_win * (1 - blend_factor) + live_away_prob * blend_factor
        sum_final = final_home_win + final_draw + final_away_win
        if sum_final > 0:
            final_home_win /= sum_final
            final_draw     /= sum_final
            final_away_win /= sum_final
        
        # --- 7) Compute fair odds for match result ---
        fair_home_odds = fair_odds(final_home_win)
        fair_draw_odds = fair_odds(final_draw)
        fair_away_odds = fair_odds(final_away_win)
        
        # --- 8) Over/Under 2.5 Goals (just computing fair odds) ---
        under_prob_model = 0.0
        for i in range(goal_range):
            for j in range(goal_range):
                if (i + j) <= 2:
                    under_prob_model += zip_probability(adjusted_home_goals, i) * zip_probability(adjusted_away_goals, j)
        over_prob_model = 1 - under_prob_model
        
        fair_under_odds = fair_odds(under_prob_model)
        fair_over_odds  = fair_odds(over_prob_model)
        
        # --- 9) Lay Draw Recommendation (only one calculation) ---
        if live_draw_odds > 1 and fair_draw_odds > live_draw_odds:
            edge = (fair_draw_odds - live_draw_odds) / fair_draw_odds
            liability = account_balance * dynamic_kelly(edge)
            liability = min(liability, account_balance * 0.10)
            lay_stake = liability / (live_draw_odds - 1) if (live_draw_odds - 1) > 0 else 0
            lay_draw_recommendation = f"Lay Draw: Edge {edge:.2%}, Liab {liability:.2f}, Stake {lay_stake:.2f}"
        else:
            lay_draw_recommendation = "No lay edge for Draw."
        
        # --- 10) Aggregate Scoreline Percentages ---
        agg_draw_pct = final_draw * 100
        agg_non_draw_pct = (final_home_win + final_away_win) * 100
        
        # --- 11) Build final output text ---
        output = "=== Betting Insights ===\n\n"
        
        # Top 5 Scorelines
        output += "Top 5 Likely Scorelines:\n"
        for (score, prob) in top5:
            output += f"  {score[0]}-{score[1]}: {prob*100:.1f}% (Fair Odds: {fair_odds(prob):.2f})\n"
        output += "\n"
        
        # Aggregate Draw vs Non-draw
        output += "Aggregate Scoreline Probabilities:\n"
        output += f"  Draw Scorelines: {agg_draw_pct:.1f}%\n"
        output += f"  Non-Draw Scorelines: {agg_non_draw_pct:.1f}%\n\n"
        
        # Over/Under 2.5 Goals: Fair Odds vs Live Odds
        output += "Over/Under 2.5 Goals:\n"
        output += f"  Over: Fair Odds {fair_over_odds:.2f} | Live Odds {live_over_odds:.2f}\n"
        output += f"  Under: Fair Odds {fair_under_odds:.2f} | Live Odds {live_under_odds:.2f}\n\n"
        
        # Match Odds (Home/Draw/Away) and Lay Draw
        output += "Market Odds (Live | Fair):\n"
        output += f"  Home: {live_home_odds:.2f} | {fair_home_odds:.2f}\n"
        output += f"  Draw: {live_draw_odds:.2f} | {fair_draw_odds:.2f}\n"
        output += f"  Away: {live_away_odds:.2f} | {fair_away_odds:.2f}\n\n"
        output += "Lay Draw Recommendation:\n"
        output += f"  {lay_draw_recommendation}\n"
        
        # --- Insert output line by line with color tags ---
        result_text_widget.delete("1.0", tk.END)
        lines = output.split("\n")
        for line in lines:
            if "Lay Draw" in line:
                result_text_widget.insert(tk.END, line + "\n", "lay")
            elif line.startswith("==="):
                result_text_widget.insert(tk.END, line + "\n", "insight")
            else:
                result_text_widget.insert(tk.END, line + "\n", "normal")
        
    except ValueError:
        result_text_widget.delete("1.0", tk.END)
        result_text_widget.insert(tk.END, "Please enter valid numerical values.", "normal")

def reset_fields():
    for entry in entries.values():
        entry.delete(0, tk.END)
    result_text_widget.delete("1.0", tk.END)

# --- GUI Layout ---
root = tk.Tk()
root.title("Odds Apex - Pre-Match")

# Create a canvas for the entire window content
canvas = tk.Canvas(root)
canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Add a vertical scrollbar to the canvas
vsb = tk.Scrollbar(root, orient="vertical", command=canvas.yview)
vsb.pack(side=tk.RIGHT, fill=tk.Y)
canvas.configure(yscrollcommand=vsb.set)

# Create a frame inside the canvas to hold all widgets
main_frame = tk.Frame(canvas)
canvas.create_window((0,0), window=main_frame, anchor="nw")

def onFrameConfigure(event):
    canvas.configure(scrollregion=canvas.bbox("all"))
main_frame.bind("<Configure>", onFrameConfigure)

# Define input fields inside main_frame
entries = {
    "entry_home_scored":      tk.Entry(main_frame),
    "entry_home_conceded":    tk.Entry(main_frame),
    "entry_away_conceded":    tk.Entry(main_frame),
    "entry_away_scored":      tk.Entry(main_frame),
    "entry_injuries_home":    tk.Entry(main_frame),
    "entry_injuries_away":    tk.Entry(main_frame),
    "entry_position_home":    tk.Entry(main_frame),
    "entry_position_away":    tk.Entry(main_frame),
    "entry_form_home":        tk.Entry(main_frame),
    "entry_form_away":        tk.Entry(main_frame),
    "entry_home_xg_scored":   tk.Entry(main_frame),
    "entry_away_xg_scored":   tk.Entry(main_frame),
    "entry_home_xg_conceded": tk.Entry(main_frame),
    "entry_away_xg_conceded": tk.Entry(main_frame),
    "entry_live_under_odds":  tk.Entry(main_frame),
    "entry_live_over_odds":   tk.Entry(main_frame),
    "entry_live_home_odds":   tk.Entry(main_frame),
    "entry_live_draw_odds":   tk.Entry(main_frame),
    "entry_live_away_odds":   tk.Entry(main_frame),
    "entry_account_balance":  tk.Entry(main_frame),
    "entry_kelly_fraction":   tk.Entry(main_frame)
}

labels_text = [
    "Avg Goals Home Scored", "Avg Goals Home Conceded", "Avg Goals Away Scored", "Avg Goals Away Conceded",
    "Injuries Home", "Injuries Away", "Position Home", "Position Away",
    "Form Home", "Form Away", "Home xG Scored", "Away xG Scored",
    "Home xG Conceded", "Away xG Conceded", "Live Under 2.5 Odds", "Live Over 2.5 Odds",
    "Live Home Win Odds", "Live Draw Odds", "Live Away Win Odds", "Account Balance",
    "Kelly Staking Fraction (%)"
]

for i, (key, text) in enumerate(zip(entries.keys(), labels_text)):
    label = tk.Label(main_frame, text=text)
    label.grid(row=i, column=0, padx=5, pady=5, sticky="e")
    entries[key].grid(row=i, column=1, padx=5, pady=5)

# Create a frame for the output (with a fixed size so the white box appears bigger)
result_frame = tk.Frame(main_frame, width=800, height=250)
result_frame.grid(row=len(entries), column=0, columnspan=2, padx=5, pady=5)
result_frame.grid_propagate(False)

result_text_widget = tk.Text(result_frame, wrap=tk.WORD, background="white")
result_text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
scrollbar = tk.Scrollbar(result_frame, command=result_text_widget.yview)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
result_text_widget.config(yscrollcommand=scrollbar.set)

calc_button = tk.Button(main_frame, text="Calculate Match Insights", command=calculate_insights)
calc_button.grid(row=len(entries)+1, column=0, columnspan=2, padx=5, pady=10)

reset_button = tk.Button(main_frame, text="Reset All Fields", command=reset_fields)
reset_button.grid(row=len(entries)+2, column=0, columnspan=2, padx=5, pady=10)

# Configure text tags: insights in green, lay bets in red, normal in black.
result_text_widget.tag_configure("insight", foreground="green")
result_text_widget.tag_configure("lay", foreground="red")
result_text_widget.tag_configure("normal", foreground="black")

root.mainloop()

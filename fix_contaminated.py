"""Fix contaminated live_side_snapshots data.

Contamination: the first snapshot file logged Game 2 Winner and BO3 Match Winner
while the live map was Map 1 (current_game_number=1). These rows must be dropped.

Rules applied:
- If current_game_number == "1" (or radiant_score/dire_score shows an in-progress game),
  keep ONLY markets that reference "Game 1" or "Map 1".
- Drop any row where market_name contains "Game 2", "Game 3", "Map 2", "Map 3", "(BO3)", "Match Winner"
  unless current_game_number explicitly matches.
"""
import re
import glob
import pandas as pd

SIDE_DIR = "logs/live_side_snapshots"

def should_keep(row):
    name = str(row.get("market_name", "")).lower()
    game_num_col = str(row.get("current_game_number", "")).strip()

    # Find explicit game/map number in market name
    m = re.search(r"(?:game|map)\s*(\d+)", name)
    market_map = int(m.group(1)) if m else None

    # If we know what map was live
    if game_num_col and game_num_col.isdigit():
        live_map = int(game_num_col)
        if market_map is not None:
            return market_map == live_map
        # No map number in name → it's a BO3/Match Winner → drop during active map
        return False

    # No game number recorded → keep (we have no basis to filter)
    return True


files = sorted(glob.glob(f"{SIDE_DIR}/*.parquet"))
for f in files:
    df = pd.read_parquet(f)
    before = len(df)
    mask = df.apply(should_keep, axis=1)
    df_clean = df[mask]
    after = len(df_clean)
    dropped = before - after
    if dropped:
        df_clean.to_parquet(f, index=False)
        print(f"FIXED {f}: dropped {dropped} contaminated rows ({before} -> {after})")
        print("  Dropped rows:")
        for _, row in df[~mask].iterrows():
            print(f"    {row['market_name']}")
    else:
        print(f"OK    {f}: {before} rows, nothing to drop")

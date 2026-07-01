from pathlib import Path
from dota2bot.paper_strategy_logger import _read_parquet_dir

frame = _read_parquet_dir(Path("logs/paper_positions"))
gtl = frame[frame["candidate_group"] == "gettoplive_candidate"]
print("Max Ask:", gtl["entry_ask"].max())
print("Min Mom:", gtl["side_kill_mom"].min())
print("Max Age (ms):", gtl["book_age_ms"].max())
print("Min Game Time:", gtl["game_time_sec"].min())


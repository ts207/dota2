import pandas as pd
from pathlib import Path
from dota2bot.position_report import run_position_report
import io
import sys

def test_position_report_strategy_name_filter_isolates_ask65_shadow(tmp_path: Path):
    frame = pd.DataFrame([
        {"position_id": "1", "strategy_name": "paper_gettoplive_kill_mom_favorite_hold_v1", "candidate_group": "gettoplive_candidate", "settled_win": True, "entry_ask": 0.5, "book_ask_size_log": 2, "position_pnl_2c": 0.5, "pnl_per_share_2c": 0.5, "map_exposure_id": "1", "blocked_reason": None},
        {"position_id": "2", "strategy_name": "paper_gettoplive_kill_mom_favorite_ask65_gt600_shadow_v1", "candidate_group": "gettoplive_candidate", "settled_win": True, "entry_ask": 0.5, "book_ask_size_log": 2, "position_pnl_2c": 0.3, "pnl_per_share_2c": 0.3, "map_exposure_id": "2", "blocked_reason": None},
    ])
    
    input_dir = tmp_path / "paper_positions"
    input_dir.mkdir()
    frame.to_parquet(input_dir / "latest.parquet", index=False)
    
    captured = io.StringIO()
    sys.stdout = captured
    run_position_report(
        logs_root=tmp_path,
        input_name="paper_positions",
        strategy_name="paper_gettoplive_kill_mom_favorite_ask65_gt600_shadow_v1"
    )
    sys.stdout = sys.__stdout__
    output = captured.getvalue()
    
    assert "strategy_name=paper_gettoplive_kill_mom_favorite_ask65_gt600_shadow_v1" in output
    assert "total position records: 1" in output

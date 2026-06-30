import pandas as pd
import numpy as np
from dota2bot.statistical_report import _bootstrap_ci
from dota2bot.exposure_manager import canonical_map_exposure_id, canonical_game_number

def test_canonical_map_id():
    assert canonical_game_number(1) == "1"
    assert canonical_game_number("1") == "1"
    assert canonical_game_number(1.0) == "1"
    assert canonical_game_number("1.0") == "1"
    assert canonical_game_number("MAPEQUIV") == "MAPEQUIV"
    assert canonical_game_number(None) == "MAPEQUIV"
    assert canonical_game_number(np.nan) == "MAPEQUIV"
    
    assert canonical_map_exposure_id({"match_id": "123", "current_game_number": 1}) == "123::1"
    assert canonical_map_exposure_id({"match_id": "123", "current_game_number": "1.0"}) == "123::1"

def test_bootstrap_shape():
    data = np.array([1.0, 2.0, -1.0])
    p5, p95, prob = _bootstrap_ci(data, samples=100)
    assert isinstance(p5, float)
    assert isinstance(p95, float)
    assert isinstance(prob, float)
    assert 0 <= prob <= 1


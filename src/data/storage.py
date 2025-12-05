import pandas as pd
from datetime import datetime
import os
from typing import List
from src.data.models import PlayerScore

def save_to_csv(data: List[PlayerScore], season: int) -> str:
    """Save captured data to CSV"""
    if not data:
        return ""
    
    # Convert list of PlayerScore objects to list of dicts
    dict_data = [p.to_dict() for p in data]
    
    df = pd.DataFrame(dict_data)
    df = df.sort_values("totalscore", ascending=False)
    
    # Ensure results directory exists
    os.makedirs("./results", exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"./results/Gunsmoke_Season{season}_{timestamp}.csv"
    
    df.to_csv(filename, index=False, encoding='utf-8')
    return filename

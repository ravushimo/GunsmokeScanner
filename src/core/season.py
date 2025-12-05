from datetime import datetime, timedelta
from typing import Tuple

def calculate_season() -> Tuple[int, str]:
    """Calculate current season based on date
    Season 17: Nov 30 - Dec 6, 2025 (Sunday to Saturday)
    Pattern: 7 days active + 14 days break = 21 day cycle
    """
    # Reference point
    reference_date = datetime(2025, 11, 30)  # Season 17 start
    reference_season = 17
    
    today = datetime.now()
    days_since_ref = (today.date() - reference_date.date()).days
    
    # Handle dates before reference
    if days_since_ref < 0:
        # Go backwards
        days_before = abs(days_since_ref)
        cycles_before = (days_before + 20) // 21  # Round up
        season_num = reference_season - cycles_before
        # Calculate where we are in that earlier cycle
        cycle_start = reference_date - timedelta(days=cycles_before * 21)
        days_in_cycle = (today.date() - cycle_start.date()).days % 21
    else:
        # Current or future dates
        cycle_num = days_since_ref // 21
        days_in_cycle = days_since_ref % 21
        season_num = reference_season + cycle_num
    
    # Determine if in active season or break
    if days_in_cycle < 7:
        return season_num, "Active"
    else:
        return season_num, "Break"

def get_season_dates(season_num: int) -> Tuple[datetime, datetime]:
    """Get start and end dates for a given season"""
    # Calculate offset from reference season
    reference_date = datetime(2025, 11, 30)
    reference_season = 17
    
    season_offset = season_num - reference_season
    days_offset = season_offset * 21  # Each cycle is 21 days
    
    start_date = reference_date + timedelta(days=days_offset)
    end_date = start_date + timedelta(days=6)  # 7 days inclusive
    
    return start_date, end_date

class SeasonManager:
    def __init__(self):
        self.season_num, self.status = calculate_season()
        self.is_manual = False

    def set_manual_season(self, season_num: int):
        self.season_num = season_num
        self.is_manual = True
        self.status = "Active" # Manual override assumes active

    def get_dates(self):
        return get_season_dates(self.season_num)

# backend/services/gameEngine.py
import random
import hashlib
import time
from decimal import Decimal

class GameEngine:
    def __init__(self):
        self.round_duration = 60  # seconds
        self.betting_phase = 30   # seconds
        self.reveal_phase = 30    # seconds
        self.house_edge = Decimal('0.05')  # 5% - fair for both sides!
        
    def determine_outcome(self, round_id, total_pump_bets, total_dump_bets):
        """
        Provably fair outcome determination
        Uses round ID + timestamp for randomness
        """
        # Create seed from round + secret + timestamp
        seed = f"{round_id}_{os.environ.get('GAME_SECRET')}_{int(time.time() / 60)}"
        hash_result = hashlib.sha256(seed.encode()).hexdigest()
        
        # Convert to number between 0-1
        hash_int = int(hash_result[:8], 16)
        random_value = hash_int / (16**8)
        
        # 50/50 chance (truly fair)
        return 'pump' if random_value > 0.5 else 'dump'
    
    def calculate_multiplier(self, total_pot, winning_pot, house_edge):
        """Calculate payout multiplier for winners"""
        if winning_pot == 0:
            return 0
            
        house_cut = total_pot * house_edge
        payout_pot = total_pot - house_cut
        
        # Each winner gets proportional share
        multiplier = payout_pot / winning_pot
        
        return round(multiplier, 2)
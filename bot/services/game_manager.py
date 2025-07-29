import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Callable
from bot.config import Config, GameConstants, Messages
from bot.services.database import db

logger = logging.getLogger(__name__)

class GameManager:
    def __init__(self):
        self.current_round: Optional[int] = None
        self.round_counter: int = 1
        self.is_running: bool = False
        self.subscribers: List[Callable] = []  # For broadcasting updates
        
    def subscribe(self, callback: Callable):
        """Subscribe to game events"""
        self.subscribers.append(callback)
    
    async def broadcast_update(self, event_type: str, data: Dict[str, Any]):
        """Broadcast update to all subscribers"""
        for callback in self.subscribers:
            try:
                await callback(event_type, data)
            except Exception as e:
                logger.error(f"Error broadcasting to subscriber: {e}")
    
    async def start_game_loop(self):
        """Start the main game loop"""
        if self.is_running:
            logger.warning("Game loop is already running")
            return
            
        self.is_running = True
        logger.info("Starting game loop...")
        
        # Initialize database
        await db.init_pool()
        
        # Get the last round number from database
        try:
            async with db.pool.acquire() as conn:
                last_round = await conn.fetchval(
                    "SELECT COALESCE(MAX(round_number), 0) FROM rounds"
                )
                self.round_counter = last_round + 1
        except Exception as e:
            logger.error(f"Error getting last round number: {e}")
            self.round_counter = 1
        
        # Start the game loop
        while self.is_running:
            try:
                await self.run_round()
                # Short pause between rounds
                await asyncio.sleep(3)
            except Exception as e:
                logger.error(f"Error in game loop: {e}")
                await asyncio.sleep(5)  # Wait longer on error
    
    async def stop_game_loop(self):
        """Stop the game loop"""
        self.is_running = False
        if db.pool:
            await db.close_pool()
        logger.info("Game loop stopped")
    
    async def run_round(self):
        """Run a complete game round"""
        round_number = self.round_counter
        self.round_counter += 1
        
        logger.info(f"Starting round #{round_number}")
        
        # Phase 1: Create round and start betting
        round_id = await db.create_round(round_number)
        self.current_round = round_id
        
        await self.broadcast_update('round_started', {
            'round_number': round_number,
            'round_id': round_id,
            'betting_time': Config.BETTING_PHASE
        })
        
        # Betting phase
        await asyncio.sleep(Config.BETTING_PHASE)
        
        # Phase 2: Close betting and start reveal
        await db.update_round_status(round_id, 'revealing')
        
        # Get final stats
        round_stats = await db.get_round_stats(round_id)
        
        await self.broadcast_update('betting_closed', {
            'round_number': round_number,
            'round_id': round_id,
            'reveal_time': Config.REVEAL_PHASE,
            **round_stats
        })
        
        # Reveal phase (build suspense)
        await asyncio.sleep(Config.REVEAL_PHASE)
        
        # Phase 3: Determine result and distribute winnings
        result = await self.determine_result(round_stats)
        house_profit = round_stats['total_pot'] * Config.HOUSE_EDGE
        
        # Distribute winnings
        winner_count = await db.distribute_winnings(round_id, result)
        
        # Complete the round
        await db.complete_round(round_id, result, house_profit)
        
        # Calculate final stats for broadcast
        winners_pool = round_stats['total_pot'] - house_profit
        
        if result == 'PUMP':
            winning_pot = round_stats['pump_pot']
        else:
            winning_pot = round_stats['dump_pot']
            
        multiplier = winners_pool / winning_pot if winning_pot > 0 else 0
        
        await self.broadcast_update('round_completed', {
            'round_number': round_number,
            'round_id': round_id,
            'result': result,
            'total_pot': round_stats['total_pot'],
            'house_cut': house_profit,
            'winners_pool': winners_pool,
            'multiplier': multiplier,
            'winner_count': winner_count
        })
        
        self.current_round = None
        logger.info(f"Round #{round_number} completed: {result}, {winner_count} winners")
    
    async def determine_result(self, round_stats: Dict[str, Any]) -> str:
        """Determine round result with house edge consideration"""
        total_pot = round_stats['total_pot']
        pump_pot = round_stats['pump_pot'] 
        dump_pot = round_stats['dump_pot']
        
        # If no bets, random result
        if total_pot == 0:
            return random.choice(['PUMP', 'DUMP'])
        
        # Calculate which side would be more profitable for the house
        # (less payouts = more profit)
        pump_payout = dump_pot * (1 - Config.HOUSE_EDGE) if dump_pot > 0 else 0
        dump_payout = pump_pot * (1 - Config.HOUSE_EDGE) if pump_pot > 0 else 0
        
        # Base probabilities (50/50)
        pump_probability = 0.5
        
        # Adjust slightly in favor of smaller payouts (house edge)
        # But keep it mostly fair to maintain player trust
        if pump_payout < dump_payout:
            pump_probability = 0.52  # Slightly favor PUMP if it means less payout
        elif dump_payout < pump_payout:
            pump_probability = 0.48  # Slightly favor DUMP if it means less payout
        
        # Add some randomness to make it feel natural
        pump_probability += random.uniform(-0.05, 0.05)
        pump_probability = max(0.4, min(0.6, pump_probability))  # Keep it reasonable
        
        result = 'PUMP' if random.random() < pump_probability else 'DUMP'
        
        logger.info(f"Round result: {result} (PUMP pot: {pump_pot}, DUMP pot: {dump_pot})")
        return result
    
    async def can_place_bet(self, telegram_id: int, amount: float) -> tuple[bool, str]:
        """Check if user can place a bet"""
        # Check if round is in betting phase
        if not self.current_round:
            return False, "❌ No active round. Please wait for the next round to start."
        
        current_round = await db.get_current_round()
        if not current_round or current_round['status'] != 'betting':
            return False, "❌ Betting is closed for this round."
        
        # Check bet amount limits
        if amount < Config.MIN_BET:
            return False, f"❌ Minimum bet is {Config.MIN_BET} SOL"
        
        if amount > Config.MAX_BET:
            return False, f"❌ Maximum bet is {Config.MAX_BET} SOL"
        
        # Check user balance
        user = await db.get_or_create_user(telegram_id)
        if user['balance'] < amount:
            return False, f"❌ Insufficient balance. You have {user['balance']:.3f} SOL"
        
        # Check if user already bet this round
        existing_bet = await db.get_user_round_bet(user['id'], self.current_round)
        if existing_bet:
            return False, f"❌ You already bet {existing_bet['bet_type']} {existing_bet['amount']} SOL this round"
        
        return True, "✅ Bet allowed"
    
    async def place_bet(self, telegram_id: int, bet_type: str, amount: float) -> tuple[bool, str]:
        """Place a bet for a user"""
        # Validate bet
        can_bet, message = await self.can_place_bet(telegram_id, amount)
        if not can_bet:
            return False, message
        
        # Get user
        user = await db.get_or_create_user(telegram_id)
        
        # Place the bet
        success = await db.place_bet(user['id'], self.current_round, bet_type, amount)
        
        if success:
            # Broadcast bet update
            round_stats = await db.get_round_stats(self.current_round)
            await self.broadcast_update('bet_placed', {
                'user_id': telegram_id,
                'username': user['username'],
                'bet_type': bet_type,
                'amount': amount,
                'round_stats': round_stats
            })
            
            return True, f"✅ Bet placed: {GameConstants.BET_TYPES[bet_type]} {amount} SOL"
        else:
            return False, "❌ Failed to place bet. Please try again."
    
    async def get_current_round_info(self) -> Optional[Dict[str, Any]]:
        """Get current round information"""
        if not self.current_round:
            return None
            
        current_round = await db.get_current_round()
        if not current_round:
            return None
            
        round_stats = await db.get_round_stats(self.current_round)
        
        # Calculate time remaining
        if current_round['status'] == 'betting':
            time_remaining = max(0, int((current_round['betting_ends_at'] - datetime.now()).total_seconds()))
        else:
            time_remaining = 0
        
        return {
            'round_number': current_round['round_number'],
            'round_id': current_round['id'],
            'status': current_round['status'],
            'time_remaining': time_remaining,
            **round_stats
        }
    
    async def get_user_current_bet(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Get user's bet in current round"""
        if not self.current_round:
            return None
            
        user = await db.get_or_create_user(telegram_id)
        return await db.get_user_round_bet(user['id'], self.current_round)

# Global game manager instance
game_manager = GameManager()
import asyncpg
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from bot.config import Config

logger = logging.getLogger(__name__)

class DatabaseService:
    def __init__(self):
        self.pool = None
    
    async def init_pool(self):
        """Initialize database connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                Config.DATABASE_URL,
                min_size=5,
                max_size=20,
                command_timeout=60
            )
            logger.info("Database connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise
    
    async def close_pool(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")
    
    # User Management
    async def get_or_create_user(self, telegram_id: int, username: str = None, first_name: str = None) -> Dict[str, Any]:
        """Get existing user or create new one"""
        async with self.pool.acquire() as conn:
            # Try to get existing user
            user = await conn.fetchrow(
                "SELECT * FROM users WHERE telegram_id = $1",
                telegram_id
            )
            
            if user:
                # Update username/first_name if changed
                if username != user['username'] or first_name != user['first_name']:
                    await conn.execute(
                        "UPDATE users SET username = $1, first_name = $2, updated_at = NOW() WHERE telegram_id = $3",
                        username, first_name, telegram_id
                    )
                return dict(user)
            
            # Create new user
            user = await conn.fetchrow(
                """INSERT INTO users (telegram_id, username, first_name, balance) 
                   VALUES ($1, $2, $3, $4) 
                   RETURNING *""",
                telegram_id, username, first_name, 1.0  # Give 1 SOL starting balance for testing
            )
            
            logger.info(f"Created new user: {telegram_id} (@{username})")
            return dict(user)
    
    async def get_user_balance(self, telegram_id: int) -> float:
        """Get user's current balance"""
        async with self.pool.acquire() as conn:
            balance = await conn.fetchval(
                "SELECT balance FROM users WHERE telegram_id = $1",
                telegram_id
            )
            return float(balance) if balance else 0.0
    
    async def update_user_balance(self, telegram_id: int, amount: float) -> bool:
        """Update user balance (can be negative for bets)"""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE users SET balance = balance + $1, updated_at = NOW() WHERE telegram_id = $2",
                amount, telegram_id
            )
            return result == "UPDATE 1"
    
    async def get_user_stats(self, telegram_id: int) -> Dict[str, Any]:
        """Get user's game statistics"""
        async with self.pool.acquire() as conn:
            stats = await conn.fetchrow(
                """SELECT 
                    balance, total_wagered, total_won, games_played, wins, losses,
                    CASE WHEN games_played > 0 THEN ROUND((wins::float / games_played::float) * 100, 2) ELSE 0 END as win_rate
                   FROM users WHERE telegram_id = $1""",
                telegram_id
            )
            return dict(stats) if stats else {}
    
    # Round Management
    async def create_round(self, round_number: int) -> int:
        """Create a new game round"""
        async with self.pool.acquire() as conn:
            round_id = await conn.fetchval(
                """INSERT INTO rounds (round_number, status, betting_ends_at) 
                   VALUES ($1, 'betting', $2) 
                   RETURNING id""",
                round_number,
                datetime.now() + timedelta(seconds=Config.BETTING_PHASE)
            )
            logger.info(f"Created round #{round_number} (ID: {round_id})")
            return round_id
    
    async def get_current_round(self) -> Optional[Dict[str, Any]]:
        """Get the current active round"""
        async with self.pool.acquire() as conn:
            round_data = await conn.fetchrow(
                "SELECT * FROM rounds WHERE status IN ('betting', 'revealing') ORDER BY id DESC LIMIT 1"
            )
            return dict(round_data) if round_data else None
    
    async def update_round_status(self, round_id: int, status: str) -> bool:
        """Update round status"""
        async with self.pool.acquire() as conn:
            result = await conn.execute(
                "UPDATE rounds SET status = $1 WHERE id = $2",
                status, round_id
            )
            return result == "UPDATE 1"
    
    async def complete_round(self, round_id: int, result: str, house_profit: float) -> bool:
        """Complete a round with final result"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Update round
                await conn.execute(
                    """UPDATE rounds SET 
                       status = 'completed', result = $1, house_profit = $2, ended_at = NOW()
                       WHERE id = $3""",
                    result, house_profit, round_id
                )
                
                # Update user stats for all participants
                await conn.execute(
                    """UPDATE users SET 
                       games_played = games_played + 1,
                       wins = wins + CASE WHEN b.is_winner THEN 1 ELSE 0 END,
                       losses = losses + CASE WHEN NOT b.is_winner THEN 1 ELSE 0 END,
                       total_won = total_won + COALESCE(b.payout, 0)
                       FROM bets b 
                       WHERE users.id = b.user_id AND b.round_id = $1""",
                    round_id
                )
                
                return True
    
    async def get_round_stats(self, round_id: int) -> Dict[str, Any]:
        """Get round statistics"""
        async with self.pool.acquire() as conn:
            stats = await conn.fetchrow(
                """SELECT 
                    total_pot, pump_pot, dump_pot, participants_count,
                    CASE WHEN total_pot > 0 THEN ROUND((pump_pot / total_pot) * 100, 1) ELSE 0 END as pump_percentage,
                    CASE WHEN total_pot > 0 THEN ROUND((dump_pot / total_pot) * 100, 1) ELSE 0 END as dump_percentage
                   FROM rounds WHERE id = $1""",
                round_id
            )
            return dict(stats) if stats else {}
    
    # Bet Management
    async def place_bet(self, user_id: int, round_id: int, bet_type: str, amount: float) -> bool:
        """Place a bet for a user"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Insert bet
                await conn.execute(
                    "INSERT INTO bets (user_id, round_id, bet_type, amount) VALUES ($1, $2, $3, $4)",
                    user_id, round_id, bet_type, amount
                )
                
                # Update user balance and stats
                await conn.execute(
                    """UPDATE users SET 
                       balance = balance - $1, 
                       total_wagered = total_wagered + $1,
                       updated_at = NOW()
                       WHERE id = $2""",
                    amount, user_id
                )
                
                # Update round totals
                if bet_type == 'PUMP':
                    await conn.execute(
                        """UPDATE rounds SET 
                           total_pot = total_pot + $1,
                           pump_pot = pump_pot + $1,
                           participants_count = participants_count + 1
                           WHERE id = $2""",
                        amount, round_id
                    )
                else:  # DUMP
                    await conn.execute(
                        """UPDATE rounds SET 
                           total_pot = total_pot + $1,
                           dump_pot = dump_pot + $1,
                           participants_count = participants_count + 1
                           WHERE id = $2""",
                        amount, round_id
                    )
                
                logger.info(f"Bet placed: User {user_id}, Round {round_id}, {bet_type}, {amount} SOL")
                return True
    
    async def get_user_round_bet(self, user_id: int, round_id: int) -> Optional[Dict[str, Any]]:
        """Check if user already has a bet in this round"""
        async with self.pool.acquire() as conn:
            bet = await conn.fetchrow(
                "SELECT * FROM bets WHERE user_id = $1 AND round_id = $2",
                user_id, round_id
            )
            return dict(bet) if bet else None
    
    async def distribute_winnings(self, round_id: int, result: str) -> int:
        """Distribute winnings to winners and return number of winners"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Get round info
                round_data = await conn.fetchrow(
                    "SELECT total_pot, pump_pot, dump_pot FROM rounds WHERE id = $1",
                    round_id
                )
                
                if not round_data:
                    return 0
                
                total_pot = float(round_data['total_pot'])
                house_cut = total_pot * Config.HOUSE_EDGE
                winners_pool = total_pot - house_cut
                
                # Determine winner side and calculate payouts
                if result == 'PUMP':
                    winning_pot = float(round_data['pump_pot'])
                else:
                    winning_pot = float(round_data['dump_pot'])
                
                if winning_pot == 0:
                    # No winners, house keeps everything
                    return 0
                
                multiplier = winners_pool / winning_pot
                
                # Update winning bets and pay out users
                result_rows = await conn.execute(
                    """UPDATE bets SET 
                       is_winner = TRUE, 
                       payout = amount * $1
                       WHERE round_id = $2 AND bet_type = $3""",
                    float(multiplier), round_id, result
                )
                
                # Add winnings to user balances
                await conn.execute(
                    """UPDATE users SET 
                       balance = balance + b.payout,
                       updated_at = NOW()
                       FROM bets b 
                       WHERE users.id = b.user_id 
                       AND b.round_id = $1 
                       AND b.bet_type = $2""",
                    round_id, result
                )
                
                winner_count = int(result_rows.split()[-1]) if result_rows.startswith('UPDATE') else 0
                logger.info(f"Distributed winnings: {winner_count} winners, {multiplier:.3f}x multiplier")
                return winner_count
    
    # Statistics
    async def get_recent_rounds(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent completed rounds"""
        async with self.pool.acquire() as conn:
            rounds = await conn.fetch(
                """SELECT round_number, result, total_pot, participants_count, ended_at
                   FROM rounds 
                   WHERE status = 'completed' 
                   ORDER BY ended_at DESC 
                   LIMIT $1""",
                limit
            )
            return [dict(round) for round in rounds]

# Global database instance
db = DatabaseService()
#!/usr/bin/env python3
"""
WebSocket server to connect Telegram bot with web chart interface
"""

import asyncio
import websockets
import json
import logging
from typing import Set, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GameWebSocketServer:
    def __init__(self, host='localhost', port=8765):
        self.host = host
        self.port = port
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.game_state = {
            'round': 1,
            'phase': 'waiting',
            'timeLeft': 0,
            'pumpPot': 0.0,
            'dumpPot': 0.0,
            'playerCount': 0,
            'recentResults': []
        }
    
    async def register_client(self, websocket):
        """Register a new WebSocket client"""
        self.clients.add(websocket)
        logger.info(f"Client connected. Total clients: {len(self.clients)}")
        
        # Send current game state to new client
        await self.send_to_client(websocket, {
            'type': 'game_state',
            'data': self.game_state
        })
    
    async def unregister_client(self, websocket):
        """Unregister a WebSocket client"""
        self.clients.discard(websocket)
        logger.info(f"Client disconnected. Total clients: {len(self.clients)}")
    
    async def send_to_client(self, websocket, message):
        """Send message to a specific client"""
        try:
            await websocket.send(json.dumps(message))
        except websockets.exceptions.ConnectionClosed:
            pass
    
    async def broadcast(self, message):
        """Broadcast message to all connected clients"""
        if self.clients:
            # Create tasks for all clients
            tasks = [self.send_to_client(client, message) for client in self.clients.copy()]
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def handle_client(self, websocket, path):
        """Handle WebSocket client connection"""
        await self.register_client(websocket)
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self.handle_message(websocket, data)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON received: {message}")
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister_client(websocket)
    
    async def handle_message(self, websocket, data):
        """Handle incoming message from client"""
        message_type = data.get('type')
        
        if message_type == 'ping':
            await self.send_to_client(websocket, {'type': 'pong'})
        elif message_type == 'get_state':
            await self.send_to_client(websocket, {
                'type': 'game_state',
                'data': self.game_state
            })
    
    # Methods to be called by the Telegram bot
    async def update_round_started(self, round_number: int):
        """Called when a new round starts"""
        self.game_state.update({
            'round': round_number,
            'phase': 'betting',
            'timeLeft': 20,
            'pumpPot': 0.0,
            'dumpPot': 0.0,
            'playerCount': 0
        })
        
        await self.broadcast({
            'type': 'round_started',
            'data': self.game_state
        })
        logger.info(f"Broadcasted round start: #{round_number}")
    
    async def update_bet_placed(self, bet_type: str, amount: float, pump_pot: float, dump_pot: float, player_count: int):
        """Called when a bet is placed"""
        self.game_state.update({
            'pumpPot': pump_pot,
            'dumpPot': dump_pot,
            'playerCount': player_count
        })
        
        await self.broadcast({
            'type': 'bet_placed',
            'data': {
                'bet_type': bet_type,
                'amount': amount,
                'pumpPot': pump_pot,
                'dumpPot': dump_pot,
                'playerCount': player_count
            }
        })
        logger.info(f"Broadcasted bet: {bet_type} {amount} SOL")
    
    async def update_betting_closed(self, round_number: int, pump_pot: float, dump_pot: float, player_count: int):
        """Called when betting phase ends"""
        self.game_state.update({
            'phase': 'revealing',
            'timeLeft': 15,
            'pumpPot': pump_pot,
            'dumpPot': dump_pot,
            'playerCount': player_count
        })
        
        await self.broadcast({
            'type': 'betting_closed',
            'data': self.game_state
        })
        logger.info(f"Broadcasted betting closed for round #{round_number}")
    
    async def update_round_result(self, round_number: int, result: str, total_pot: float, winner_count: int):
        """Called when round completes with result"""
        self.game_state.update({
            'phase': 'waiting',
            'timeLeft': 3
        })
        
        # Add to recent results
        self.game_state['recentResults'].insert(0, {
            'round': round_number,
            'result': result,
            'pot': f"{total_pot:.3f}",
            'winners': winner_count
        })
        
        # Keep only last 10 results
        if len(self.game_state['recentResults']) > 10:
            self.game_state['recentResults'] = self.game_state['recentResults'][:10]
        
        await self.broadcast({
            'type': 'round_result',
            'data': {
                'round': round_number,
                'result': result,
                'totalPot': total_pot,
                'winnerCount': winner_count,
                'recentResults': self.game_state['recentResults']
            }
        })
        logger.info(f"Broadcasted result for round #{round_number}: {result}")
    
    async def update_timer(self, time_left: int):
        """Called every second to update timer"""
        self.game_state['timeLeft'] = time_left
        
        await self.broadcast({
            'type': 'timer_update',
            'data': {'timeLeft': time_left}
        })
    
    async def start_server(self):
        """Start the WebSocket server"""
        logger.info(f"Starting WebSocket server on {self.host}:{self.port}")
        
        start_server = websockets.serve(
            self.handle_client,
            self.host,
            self.port,
            ping_interval=20,
            ping_timeout=10
        )
        
        await start_server
        logger.info(f"WebSocket server started on ws://{self.host}:{self.port}")

# Global server instance
websocket_server = GameWebSocketServer()

async def main():
    """Test the WebSocket server"""
    await websocket_server.start_server()
    
    # Keep the server running
    try:
        await asyncio.Future()  # Run forever
    except KeyboardInterrupt:
        logger.info("WebSocket server stopped")

if __name__ == '__main__':
    asyncio.run(main())
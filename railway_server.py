#!/usr/bin/env python3
"""
Improved WebSocket server for Railway with better browser compatibility
"""
import asyncio
import websockets
import json
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

connected_clients = set()

async def handle_client(websocket, path):
    """Handle WebSocket connections with proper error handling"""
    client_ip = websocket.remote_address[0] if websocket.remote_address else "unknown"
    logger.info(f"✅ New connection from {client_ip}")
    
    connected_clients.add(websocket)
    logger.info(f"📊 Total connections: {len(connected_clients)}")
    
    try:
        # Send initial game state
        initial_data = {
            'type': 'game_state',
            'data': {
                'round': 1,
                'phase': 'betting',
                'timeLeft': 15,
                'pumpPot': 0.5,
                'dumpPot': 0.3,
                'playerCount': 5,
                'recentBets': []
            }
        }
        await websocket.send(json.dumps(initial_data))
        logger.info(f"📤 Sent initial data to {client_ip}")
        
        # Send connection confirmation
        await websocket.send(json.dumps({
            'type': 'connection_confirmed',
            'data': {'status': 'connected', 'server': 'railway'}
        }))
        
        # Keep connection alive with periodic updates
        counter = 0
        while True:
            await asyncio.sleep(3)
            counter += 1
            
            # Send betting updates
            if counter % 2 == 0:
                bet_data = {
                    'type': 'bet_placed',
                    'data': {
                        'bet_type': 'PUMP' if counter % 4 == 0 else 'DUMP',
                        'amount': 0.1,
                        'pumpPot': 0.5 + (counter * 0.1),
                        'dumpPot': 0.3 + (counter * 0.05),
                        'playerCount': 5 + counter
                    }
                }
                await websocket.send(json.dumps(bet_data))
                logger.info(f"📤 Sent bet update to {client_ip}")
            
            # Send round updates
            if counter % 10 == 0:
                round_data = {
                    'type': 'round_started',
                    'data': {
                        'round': (counter // 10) + 1,
                        'phase': 'betting',
                        'timeLeft': 20,
                        'pumpPot': 0.0,
                        'dumpPot': 0.0,
                        'playerCount': 0
                    }
                }
                await websocket.send(json.dumps(round_data))
                logger.info(f"📤 Sent new round to {client_ip}")
                
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"📉 Connection closed normally: {client_ip}")
    except Exception as e:
        logger.error(f"❌ Error with client {client_ip}: {e}")
    finally:
        connected_clients.discard(websocket)
        logger.info(f"📊 Client {client_ip} disconnected. Total: {len(connected_clients)}")

async def health_check(websocket, path):
    """Simple health check endpoint"""
    await websocket.send("OK")
    await websocket.close()

async def main():
    """Start the WebSocket server"""
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"🚀 Starting WebSocket server on 0.0.0.0:{port}")
    
    # Start server with health check
    server = await websockets.serve(
        handle_client,
        "0.0.0.0", 
        port,
        ping_interval=20,
        ping_timeout=10,
        close_timeout=10
    )
    
    logger.info(f"✅ WebSocket server running on port {port}")
    print(f"🌐 Server URL: https://pump-dump-server-production.up.railway.app")
    
    await server.wait_closed()

if __name__ == '__main__':
    asyncio.run(main())

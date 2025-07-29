#!/usr/bin/env python3
"""
Simple WebSocket server for Railway
"""
import asyncio
import websockets
import json
import os

connected_clients = set()

async def handle_client(websocket, path):
    """Handle WebSocket connections"""
    connected_clients.add(websocket)
    print(f"✅ Client connected. Total: {len(connected_clients)}")
    
    try:
        # Send demo data immediately
        demo_data = {
            'type': 'game_state',
            'data': {
                'round': 1,
                'phase': 'betting',
                'pumpPot': 0.5,
                'dumpPot': 0.3,
                'playerCount': 5,
                'timeLeft': 15
            }
        }
        await websocket.send(json.dumps(demo_data))
        
        # Send periodic updates
        while True:
            await asyncio.sleep(2)
            update_data = {
                'type': 'bet_placed',
                'data': {
                    'pumpPot': 0.8,
                    'dumpPot': 0.6,
                    'playerCount': 8
                }
            }
            await websocket.send(json.dumps(update_data))
            
    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        print(f"❌ Client error: {e}")
    finally:
        connected_clients.discard(websocket)
        print(f"📉 Client disconnected. Total: {len(connected_clients)}")

async def main():
    """Start server"""
    port = int(os.environ.get('PORT', 8765))
    print(f"🚀 Starting on 0.0.0.0:{port}")
    
    server = await websockets.serve(handle_client, "0.0.0.0", port)
    print(f"✅ WebSocket server running!")
    
    await server.wait_closed()

if __name__ == '__main__':
    asyncio.run(main())

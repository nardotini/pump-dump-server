#!/usr/bin/env python3
"""
Simplified server for Railway deployment
"""
import asyncio
import websockets
import json
import os
from datetime import datetime

# Simple WebSocket server for Railway
connected_clients = set()

async def handle_client(websocket, path):
    """Handle WebSocket connections"""
    connected_clients.add(websocket)
    print(f"Client connected. Total: {len(connected_clients)}")
    
    try:
        # Send demo data to new client
        demo_data = {
            'type': 'game_state',
            'data': {
                'round': 1,
                'phase': 'betting',
                'pumpPot': 0.5,
                'dumpPot': 0.3,
                'playerCount': 5
            }
        }
        await websocket.send(json.dumps(demo_data))
        
        # Keep connection alive
        await websocket.wait_closed()
    except Exception as e:
        print(f"Client error: {e}")
    finally:
        connected_clients.discard(websocket)
        print(f"Client disconnected. Total: {len(connected_clients)}")

async def main():
    """Start the WebSocket server"""
    port = int(os.environ.get('PORT', 8765))
    print(f"🚀 Starting WebSocket server on port {port}")
    
    server = await websockets.serve(handle_client, "0.0.0.0", port)
    print(f"✅ Server running on port {port}")
    
    await server.wait_closed()

if __name__ == '__main__':
    asyncio.run(main())

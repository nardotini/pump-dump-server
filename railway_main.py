#!/usr/bin/env python3
import os
import asyncio
from main_with_websocket import main

if __name__ == '__main__':
    # Railway provides PORT environment variable
    port = int(os.environ.get('PORT', 8765))
    print(f"🚀 Starting on port {port}")
    asyncio.run(main())

import sys
import asyncio
import uvicorn

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

if __name__ == "__main__":
    # loop="none" tells Uvicorn to skip its internal loop override 
    # and respect the Proactor policy we set above!
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=True, 
        loop="none"  # <--- THIS IS THE KEY
    )
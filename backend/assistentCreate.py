import asyncio
from backboard import BackboardClient

async def get_my_id():
    # Ensure your API Key is correct from app.backboard.io
    client = BackboardClient(api_key="") 
    
    # Corrected call: removed 'memory' keyword
    assistant = await client.create_assistant(
        name="Educational Storyteller",
        description="A bot for the KingHacks Backboard track."
    )
    
    # Use .assistant_id to see your new ID
    print(f"SUCCESS! Your Assistant ID is: {assistant.assistant_id}")

if __name__ == "__main__":
    asyncio.run(get_my_id())
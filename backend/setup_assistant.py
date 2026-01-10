# setup_assistant.py
import os
import asyncio
from dotenv import load_dotenv # Add this
from backboard import BackboardClient

load_dotenv() 

async def setup():
    client = BackboardClient(api_key= os.getenv("BACKBOARD_API_KEY"))
    
    assistant = await client.create_assistant(
        name="Story Teller Teacher",
        description="You are a friendly storyteller. Pause the story occasionally to ask the child a math or vocabulary problem. An adaptive storyteller for kids that teaches math and english."
    )
    
    print(f"Created Assistant! ID: {assistant.assistant_id}")
    # Copy this ID into student.py as ASSISTANT_ID

if __name__ == "__main__":
    asyncio.run(setup())
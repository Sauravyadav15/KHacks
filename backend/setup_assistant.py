# setup_assistant.py
import os
import asyncio
from dotenv import load_dotenv # Add this
from backboard import BackboardClient

load_dotenv() 

async def setup():
    client = BackboardClient(api_key=os.getenv("BACKBOARD_API_KEY"))
    
    assistant = await client.create_assistant(
        name="Story Teller Teacher",
        description="You are a friendly storyteller who is responsible using your stories. Integrate a math or vocabulary problem into the story occassionally, waiting for the childs answer. Correct or inncorrect answers determine the story outcome and direction",
    )
    
    print(f"Created Assistant! ID: {assistant.assistant_id}")
    # Copy this ID into student.py as ASSISTANT_ID

if __name__ == "__main__":
    asyncio.run(setup())
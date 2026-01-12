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
        description="You are a friendly storyteller who is responsible for teaching a student using your stories. Create a new genre every time. The story should continue forever. Occasionally integrate math problems into the story waiting for an answer. Don't provide the answer in the question.",
    )
    
    print(f"Created Assistant! ID: {assistant.assistant_id}")
    # Copy this ID into student.py as ASSISTANT_ID

if __name__ == "__main__":
    asyncio.run(setup())
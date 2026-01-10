# setup_assistant.py
import asyncio
from backboard import BackboardClient

async def setup():
    client = BackboardClient("espr_Y49tajp6peEh9Salhr7h_bY4RMwGlbF9Nq9VMpesylA")
    
    assistant = await client.create_assistant(
        name="Story Teller Teacher",
        description="An adaptive storyteller for kids that teaches math and english.",
    )
    
    print(f"Created Assistant! ID: {assistant.assistant_id}")
    # Copy this ID into student.py as ASSISTANT_ID

if __name__ == "__main__":
    asyncio.run(setup())
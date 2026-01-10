import asyncio
from backboard import BackboardClient

async def createAssistant():
    # Ensure your API Key is correct from app.backboard.io
    client = BackboardClient(api_key="") 

    # Create an assistant
    assistant = await client.create_assistant(
        name="My First Assistant",
        description="A helpful assistant"
    )

    # Create a thread
    thread = await client.create_thread(assistant.assistant_id)

    # Send a message and get the complete response
    response = await client.add_message(
        thread_id=thread.thread_id,
        content="Hello! Tell me a fun fact about space.",
        llm_provider="openai",
        model_name="gpt-4o",
        stream=False
    )

    # Print the AI's response
    print(response.content)
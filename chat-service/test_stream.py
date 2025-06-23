import httpx, asyncio

async def test_stream():
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST",
            "http://127.0.0.1:8001/chat_stream",
            headers={
                "Accept": "text/event-stream",
                "Content-Type": "application/json"
            },
            json={"user_input": "Test streaming in Python"}
        ) as response:
            async for chunk in response.aiter_text():
                print(chunk, end="", flush=True)

asyncio.run(test_stream())


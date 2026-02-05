import asyncio
import time
from core.orchestrator import MegaBotOrchestrator
from core.config import load_config
from core.interfaces import Message

from unittest.mock import AsyncMock

async def benchmark_pipeline():
    print("🚀 Starting MegaBot Performance Benchmark...")
    config = load_config()
    # Mock external repos for benchmarking
    config.paths["external_repos"] = "/tmp/megabot_bench"
    
    orchestrator = MegaBotOrchestrator(config)
    
    # Mock Adapters to avoid network calls
    orchestrator.adapters["openclaw"] = AsyncMock()
    orchestrator.adapters["memu"] = AsyncMock()
    orchestrator.adapters["mcp"] = AsyncMock()
    orchestrator.adapters["messaging"] = AsyncMock()
    orchestrator.adapters["gateway"] = AsyncMock()
    
    # Measure Orchestrator Message Processing
    print("\n--- Orchestrator Latency ---")
    start_time = time.perf_counter()
    msg = Message(content="What is the status of the project?", sender="user")
    
    # Simulate gateway message arrival
    data = {
        "type": "message",
        "sender_id": "test-user-123",
        "content": msg.content,
        "sender_name": "Tester"
    }
    
    # We measure on_gateway_message which involves memory store and LLM dispatch (or relay)
    await orchestrator.on_gateway_message(data)
    end_time = time.perf_counter()
    print(f"Total processing time (no LLM): {(end_time - start_time) * 1000:.2f}ms")

    # Measure Unified Gateway to Messaging Server Hop
    print("\n--- Network Hop Latency ---")
    # This is more complex to measure without full network setup, 
    # but we can measure internal serialization/deserialization
    
    start_time = time.perf_counter()
    platform_msg = orchestrator._to_platform_message(msg)
    end_time = time.perf_counter()
    print(f"Message Conversion (Core -> Platform): {(end_time - start_time) * 1000:.2f}ms")

    # Measure policy check latency
    print("\n--- Security Policy Latency ---")
    policy_data = {
        "method": "shell.execute",
        "params": {"command": "ls -la"}
    }
    start_time = time.perf_counter()
    policy = orchestrator._check_policy(policy_data)
    end_time = time.perf_counter()
    print(f"Policy check ('{policy}'): {(end_time - start_time) * 1000:.2f}ms")

    print("\n✅ Benchmark Complete.")

async def benchmark_concurrency(num_users: int = 100):
    print(f"\n🚀 Starting Concurrency Benchmark ({num_users} users)...")
    config = load_config()
    config.paths["external_repos"] = "/tmp/megabot_bench"
    orchestrator = MegaBotOrchestrator(config)
    
    # Mock Adapters
    orchestrator.adapters["openclaw"] = AsyncMock()
    orchestrator.adapters["memu"] = AsyncMock()
    orchestrator.adapters["mcp"] = AsyncMock()
    orchestrator.adapters["messaging"] = AsyncMock()
    orchestrator.adapters["gateway"] = AsyncMock()
    
    # Mock LLM to return instant response
    orchestrator.llm = AsyncMock()
    orchestrator.llm.generate = AsyncMock(return_value="Benchmarked response")

    tasks = []
    start_time = time.perf_counter()
    
    for i in range(num_users):
        data = {
            "type": "message",
            "sender_id": f"user-{i}",
            "content": f"Message {i}",
            "sender_name": f"Tester-{i}"
        }
        tasks.append(orchestrator.on_gateway_message(data))
    
    await asyncio.gather(*tasks)
    end_time = time.perf_counter()
    
    total_time = end_time - start_time
    print(f"Processed {num_users} concurrent messages in {total_time:.2f}s")
    print(f"Throughput: {num_users / total_time:.2f} msg/s")
    print(f"Average latency: {(total_time / num_users) * 1000:.2f}ms")

if __name__ == "__main__":
    asyncio.run(benchmark_pipeline())
    asyncio.run(benchmark_concurrency(100))

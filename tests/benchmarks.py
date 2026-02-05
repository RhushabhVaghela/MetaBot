"""
MegaBot Performance Benchmarks
Measures throughput and latency for core components
"""

import asyncio
import time
import json
import os
from adapters.messaging import (
    MegaBotMessagingServer,
    PlatformMessage,
    SecureWebSocket,
)
from adapters.memu_adapter import MemUAdapter


async def benchmark_encryption():
    print("--- Encryption Benchmark ---")
    secure_ws = SecureWebSocket(password="benchmark-secret")
    message = "A" * 1024  # 1KB message

    start_time = time.time()
    iterations = 1000

    for _ in range(iterations):
        enc = secure_ws.encrypt(message)
        dec = secure_ws.decrypt(enc)

    elapsed = time.time() - start_time
    print(f"1KB Enc/Dec iterations: {iterations}")
    print(f"Total time: {elapsed:.4f}s")
    print(f"Average time: {(elapsed / iterations) * 1000:.4f}ms")
    print(f"Throughput: {iterations / elapsed:.2f} ops/s")


async def benchmark_memory_store():
    print("\n--- Memory Store Benchmark ---")
    # Use temporary DB
    db_url = "sqlite:///benchmark.db"
    adapter = MemUAdapter(memu_path="/tmp", db_url=db_url)

    start_time = time.time()
    iterations = 100

    for i in range(iterations):
        await adapter.store(f"key_{i}", f"content_{i}")

    elapsed = time.time() - start_time
    print(f"Store iterations: {iterations}")
    print(f"Total time: {elapsed:.4f}s")
    print(f"Average latency: {(elapsed / iterations) * 1000:.4f}ms")

    # Cleanup
    if os.path.exists("benchmark.db"):
        os.remove("benchmark.db")


async def benchmark_messaging_throughput():
    print("\n--- Messaging Throughput Benchmark ---")
    server = MegaBotMessagingServer(enable_encryption=True)

    # Mock message
    msg = PlatformMessage(
        id="bench-1",
        platform="native",
        sender_id="user-1",
        sender_name="Benchmarking",
        chat_id="chat-1",
        content="Hello world",
    )

    start_time = time.time()
    iterations = 500

    # Measure serialization + encryption overhead
    for _ in range(iterations):
        data = json.dumps(msg.to_dict())
        if server.secure_ws:
            enc = server.secure_ws.encrypt(data)
            dec = server.secure_ws.decrypt(enc)
            _ = json.loads(dec)
        else:
            _ = json.loads(data)

    elapsed = time.time() - start_time
    print(f"Message process iterations: {iterations}")
    print(f"Total time: {elapsed:.4f}s")
    print(f"Average latency: {(elapsed / iterations) * 1000:.4f}ms")


async def benchmark_layer_fetching():
    print("\n--- Layer Fetching Benchmark (Progressive Retrieval) ---")
    adapter = MemUAdapter(memu_path="/tmp", db_url="sqlite:///bench_layer.db")

    # 1. Fill with large amounts of data
    for i in range(1000):
        await adapter.store(f"item_{i}", "A" * 100)  # 100 bytes each

    start_time = time.time()

    # 2. Simulate Layered Fetching (Batch/Progressive)
    total_fetched = 0
    batch_size = 100
    for offset in range(0, 1000, batch_size):
        # In a real system, this would be a paginated API call
        # Here we simulate the overhead of selecting a 'layer' or 'range'
        results = await adapter.search("item_")
        total_fetched += len(results[:batch_size])

    elapsed = time.time() - start_time
    print(f"Total layers (batches): {1000 / batch_size}")
    print(f"Total items fetched: {total_fetched}")
    print(f"Total time: {elapsed:.4f}s")
    print(f"Latency per layer: {(elapsed / (1000 / batch_size)) * 1000:.4f}ms")

    if os.path.exists("bench_layer.db"):
        os.remove("bench_layer.db")


async def run_all_benchmarks():
    print("🚀 Starting MegaBot Benchmarks...")
    await benchmark_encryption()
    await benchmark_memory_store()
    await benchmark_messaging_throughput()
    await benchmark_layer_fetching()
    print("\n✅ Benchmarks Completed.")


if __name__ == "__main__":
    asyncio.run(run_all_benchmarks())

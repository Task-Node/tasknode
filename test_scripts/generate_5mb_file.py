# Generate a 5MB file with random data
import random
file_size = 5 * 1024 * 1024  # 5MB in bytes

print(f"Generating {file_size} bytes file...")

with open("5mb_file.txt", "wb") as f:
    # Write chunks of random bytes until we reach 5MB
    remaining = file_size
    chunk_size = 1024 * 1024  # 1MB chunks
    
    while remaining > 0:
        # Calculate size of next chunk
        current_chunk = min(chunk_size, remaining)
        # Generate random bytes
        data = bytearray([random.randint(0, 255) for _ in range(current_chunk)])
        # Write chunk
        f.write(data)
        remaining -= current_chunk
        
print("Done generating 5MB file")

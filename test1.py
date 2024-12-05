import time

# a test script with no files generated
for i in range(1, 11):
    print(f"{i}) It is now {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime())} (UTC)")
    time.sleep(10)

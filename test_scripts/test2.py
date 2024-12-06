# a test script with files generated
for i in range(10):
    print(i)

# open a new file and write "Hello, World!" to it
with open("test.txt", "w") as f:
    f.write("Hello, World!")

# get the html from a url
import requests

print("pinging example.com")
response = requests.get("https://www.example.com")
print("done pinging")

# put the html in a file
with open("example.html", "w") as f:
    f.write(response.text)

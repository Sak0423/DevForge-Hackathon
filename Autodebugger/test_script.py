# This is a sample user script that has a bug
print("Hello! I am about to do some math.")

x = 10
y = 0  # <--- This causes the error

print(f"The result is {x / y}") # Crash happens here

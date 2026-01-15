// build a function in python
def greet(name):
    return f"Hello, {name}!"

// write a function that returns the finbonacci sequence
def fibonacci(n):
    sequence = []
    a, b = 0, 1
    for _ in range(n):
        sequence.append(a)
        a, b = b, a + b
    return sequence



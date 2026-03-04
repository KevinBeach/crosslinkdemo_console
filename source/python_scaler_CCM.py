# Accept 6 real numbers on a single line
numbers = list(map(float, input("Enter 9 real numbers separated by spaces: ").split()))

# Ensure exactly 6 numbers were entered
if len(numbers) != 9:
    print("Error: Please enter exactly 9 numbers.")
else:
    # Find the maximum absolute value
    max_abs_value = max(abs(num) for num in numbers)

    # Prevent division by zero
    if max_abs_value == 0:
        scaled_numbers = [0 for _ in numbers]
    else:
        scale_factor = 99 / max_abs_value
        scaled_numbers = [num * scale_factor for num in numbers]

    # Output the scaled numbers
    print("\nScaled numbers (range -99 to +99):")
    for i, value in enumerate(scaled_numbers):
        print(f"Scaled Number {i+1}: {value}")
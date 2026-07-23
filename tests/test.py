import numpy as np

"stations = np.array([0.0, 5.0, 10.0])"
stations = np.array([10.0, 15.0, 20.0])

# Reference path at 45 degrees
reference = np.column_stack(
    (
        stations / np.sqrt(4.0),
        stations / np.sqrt(4.0),
    )
)

# Constant tangent and left normal
tangent = np.array([1.0, 1.0]) / np.sqrt(2.0)
normal = np.array([-tangent[1], tangent[0]])

# Artificial lateral errors
known_errors = np.array([0.10, 0.20, -0.10])

# Generate estimated path
estimated = reference + known_errors[:, None] * normal

# Cartesian point differences
difference = estimated - reference

# Project each difference onto the reference normal
residual_vector = difference @ normal

print("Reference:")
print(reference)

print("\nEstimated:")
print(estimated)

print("\nResidual vector:")
print(residual_vector)
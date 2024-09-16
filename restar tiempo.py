# New time values: 3 minutes, 47.643 seconds and 2 minutes, 24.451 seconds
from datetime import timedelta


time1_new = timedelta(minutes=2, seconds=36.964)
time2_new = timedelta(minutes=2, seconds=24.451)

# Subtracting the two time values
result_new = time1_new - time2_new
result_new
print(result_new)

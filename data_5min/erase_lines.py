import pandas as pd

# Define the input and output file paths
input_file_path = 'ada_usd_5min_data2.csv'
output_file_path = 'ada_usd_5min_data2.csv'

# Read the first 250000 lines of the CSV file
df = pd.read_csv(input_file_path, nrows=450000)

# Save these lines to a new CSV file
df.to_csv(output_file_path, index=False)

import pandas as pd
import os

def remove_duplicates(input_file, output_file):
    # Load the CSV file into a DataFrame
    df = pd.read_csv(input_file)

    # Remove duplicate rows
    df_cleaned = df.drop_duplicates()

    # Save the cleaned DataFrame back to a CSV file
    df_cleaned.to_csv(output_file, index=False)
    print(f"Duplicates removed and cleaned file saved as {output_file}")

def process_folder(folder_path):
    # Iterate over all files in the specified folder
    for filename in os.listdir(folder_path):
        if filename.endswith(".csv"):  # Process only CSV files
            input_file = os.path.join(folder_path, filename)
            output_file = os.path.join(folder_path, filename)
            remove_duplicates(input_file, output_file)

# Specify the folder path containing the CSV files
folder_path = 'data_5min'

# Process all CSV files in the specified folder
process_folder(folder_path)

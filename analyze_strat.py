import csv

def load_csv_to_list(filename):
    with open(filename, mode='r') as file:
        reader = csv.reader(file)
        # Skip the header row
        data = [row for row in reader]
    return data

def sort_data_by_last_element(data):
    return sorted(data, key=lambda x: float(x[-1]))

def print_sorted_data(data):
    for row in data:
        print(row)

if __name__ == '__main__':
    # Load CSV data into a list of lists
    filename = 'TCLM_strategy_results.csv'
    data = load_csv_to_list(filename)

    # Sort data by the last element (win percentage)
    sorted_data = sort_data_by_last_element(data)

    # Print sorted data
    print("Sorted Strategy Results (by Winning Percentage):")
    print_sorted_data(sorted_data)

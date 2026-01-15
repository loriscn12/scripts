def update_failed_websites_csv(website: str):
    """
    Updates a CSV file to record failed website fetches.
    Increments a counter for existing failed websites or adds a new entry.

    Args:
        website (str): The URL of the website that failed to fetch.
    """
    data = {}
    # Read existing data
    if os.path.exists(FAILED_WEBSITES_CSV):
        try:
            with open(FAILED_WEBSITES_CSV, mode='r', newline='') as infile:
                reader = csv.reader(infile)
                for row in reader:
                    if len(row) == 2:
                        try:
                            # Ensure the counter is an integer
                            data[row[0]] = int(row[1])
                        except ValueError:
                            print(f"Warning: Non-integer counter found for {row[0]}. Resetting to 1.")
                            data[row[0]] = 1
                    else:
                        print(f"Warning: Skipping malformed row in CSV: {row}")
        except Exception as e:
            print(f"Error reading {FAILED_WEBSITES_CSV}: {e}. Starting fresh.")
            data = {} # If read fails, start with empty data

    # Update or add the website counter
    if website in data:
        data[website] += 1
    else:
        data[website] = 1

    # Write all data back to the CSV
    try:
        with open(FAILED_WEBSITES_CSV, mode='w', newline='') as outfile:
            writer = csv.writer(outfile)
            for site, counter in data.items():
                writer.writerow([site, counter])
        print(f"Updated failure count for {website} in {FAILED_WEBSITES_CSV}: {data[website]}")
    except Exception as e:
        print(f"Error writing to {FAILED_WEBSITES_CSV}: {e}")

def get_readings(conn, station_id, start_date, end_date):
    # Step 1: Write a SQL query that asks daily_readings for the five columns.
    # Step 2: Keep only rows for this station and for dates from start_date to end_date (both ends count).
    # Step 3: Sort the rows by date, oldest first.
    # Step 4: Run the query with conn.execute, passing the three values for the ? marks.
    # Step 5: Turn each row into a dictionary that uses the column names as keys.
    # Step 6: Return the list of dictionaries (an empty list if nothing matches).
    pass

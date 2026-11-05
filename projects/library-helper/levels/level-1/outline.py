def get_books(conn, genre, start_number, end_number):
    # Step 1: Write a SQL query that asks library_books for all five columns.
    # Step 2: Keep only rows for this genre, with shelf_number from start_number to end_number (both ends count).
    # Step 3: Sort the rows by shelf_number, smallest first.
    # Step 4: Run the query with conn.execute, passing the three values for the ? marks.
    # Step 5: Turn each row into a dictionary that uses the column names as keys.
    # Step 6: Return the list of dictionaries (an empty list if nothing matches).
    pass

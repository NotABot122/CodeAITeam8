# Practice: Count Each Genre

```python
def count_books(conn, genre):
```

Return how many rows in `library_books` have that `genre`, as a whole number (0 if none).
Use `SELECT COUNT(*) ... WHERE genre = ?` with a parameter, like in Level 1.

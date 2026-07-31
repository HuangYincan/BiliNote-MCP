import sqlite3

def get_connection():
    return sqlite3.connect("bili_note.db")

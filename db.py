import os
import sqlite3
from contextlib import contextmanager

from flask import g


class dotdict(dict):
    '''dot.notation access to dictionary attributes'''
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


def row_factory(cursor, data):
    keys = [col[0] for col in cursor.description]
    d = {k: v for k, v in zip(keys, data)}
    return dotdict(d)


def get_db_conn(database_path):
    conn = sqlite3.connect(database_path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = row_factory
    return conn


def close_db_conn(e=None):
    conn = g.pop('conn', None)
    if conn is not None:
        conn.close()


def query_db(database_path, query, args=(), one=False, commit=False):
    conn = get_db_conn(database_path)
    cur = conn.execute(query, args)
    if commit:
        conn.commit()
        cur.close()
    else:
        results = cur.fetchall()
        cur.close()
        if results:
            if one:
                return results[0]
            return results
    return []


@contextmanager
def get_cursor(database_path):
    try:
        conn = sqlite3.connect(database_path, detect_types=sqlite3.PARSE_DECLTYPES)
        conn.row_factory = row_factory
        cursor = conn.cursor()
        yield cursor
    finally:
        cursor.close()
        conn.close()


def init_db(database_path):
    if not os.path.isfile(database_path):
        sql_strings = [
            '''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                created_datetime DATETIME NOT NULL
            )'''
            , '''
            CREATE TABLE IF NOT EXISTS files (
                file_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                filename_original TEXT NOT NULL,
                filename_secure TEXT NOT NULL UNIQUE,
                file_path TEXT NOT NULL UNIQUE,
                file_size_b INTEGER NOT NULL,
                file_type TEXT NOT NULL,
                upload_datetime DATETIME NOT NULL,
                delete_datetime DATETIME NOT NULL,
                FOREIGN KEY(user_id) REFERENCES user(user_id)
            )'''
            , '''
            CREATE TABLE IF NOT EXISTS texts (
                text_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                text_size_b INTEGER NOT NULL,
                upload_datetime DATETIME NOT NULL,
                delete_datetime DATETIME NOT NULL,
                FOREIGN KEY(user_id) REFERENCES user(user_id)
            )'''
            , '''
            CREATE TABLE IF NOT EXISTS logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                current_datetime DATETIME,
                x_forwarded_for TEXT,
                remote_addr TEXT,
                referrer TEXT,
                content_md5 TEXT,
                origin TEXT,
                scheme TEXT,
                method TEXT,
                root_path TEXT,
                path TEXT,
                query_string TEXT,
                user_agent TEXT,
                x_forwarded_proto TEXT,
                x_forwarded_host TEXT,
                x_forwarded_prefix TEXT,
                host TEXT,
                connection TEXT,
                content_length INTEGER
            )'''
        ]
        for sql_string in sql_strings:
            query_db(database_path, sql_string, commit=True)
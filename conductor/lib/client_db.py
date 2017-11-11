import os
import datetime
import logging
import sqlite3
import tempfile

from conductor.lib import file_utils

DB_FILENAME = "conductor_db"

logger = logging.getLogger(__name__)


def get_default_db_filepath():
    '''
    Return a default filepath to use for storing the sqlite.
    Depending on the platform, this will be located in some sort of temporary
    directory, such as:
        - /usr/temp  (linux)
        - c:\users\<username>\appdata\local\temp  (windows)

    '''
    return os.path.join(tempfile.gettempdir(), DB_FILENAME)




class TableDB(object):
    '''
    Represents a single sql table to query/operate upon.
    This has admittedly limited functionality (as there can only be as single
    table to interact with).
    '''
    table_name = None
    columns = []
    column_parameters = ["name", "sqlite_type"]

    def __init__(self, db_filepath, thread_safe=True):
        self.thread_safe = thread_safe
        self.db_filepath = db_filepath
        self.connection = self.connnect_to_db(db_filepath)
        self.create_table()

    @classmethod
    def sqlite_dict_factory(cls, cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d


    def close_connection(self):
        self.connection.close()


    @classmethod
    def connnect_to_db(cls, db_filepath, timeout=300, db_perms=0666):
        '''
        Create a connection to the database with the specified database filepath and
        return the connection object

        timeout: float.  The amount of seconds that a connection will wait to
                 establish itself before it times out and raises an
                 "OperationalError: database is locked" exception.  This is important
                 when threading bc sqlite can't handle that many concurrent
                 connections and will quickly throw that exception unless the timeout
                 is high enough. Honestly this is kind of a hack and may not
                 work in all circumstances.  We should really just query the db
                 in a single thread (IMO -lws)
        '''
        # If the db filepath does not exist, create one with open permissions
        if not os.path.exists(db_filepath):
            file_utils.create_file(db_filepath, mode=db_perms)

        # Check to make sure we have write permissions
        if not os.access(db_filepath, os.W_OK):
            raise Exception("database filepath is not writable: %s" % db_filepath)


        connection = sqlite3.connect(db_filepath, detect_types=sqlite3.PARSE_DECLTYPES, timeout=timeout)
        connection.row_factory = cls.sqlite_dict_factory
        connection.text_factory = str  # overrides text type to be unicode # TODO:(this) may not be a good idea, but too lazy to convert all text to unicode first
        return connection


    def sql_execute(self, sql, params=None, many=False):
        '''
        Execute the given sql command

        new_connection: bool.  If True, will instantiate a new sql connection
                        object.  This is necessary when running this method
                        across multiple threads.
                        
        many: bool. If True, will execute the given sql command in batch, using
                    the given params as a list of variables for each call.
                        
        '''
        params = params or []
        
        if self.thread_safe:
            self.connection = self.connnect_to_db(self.db_filepath)

        cursor = self.connection.cursor()

        if many:
            cursor.executemany(sql, params)
        else:
            cursor.execute(sql, params)

        self.connection.commit()
        cursor.close()


    def sql_fetch(self, sql, params=None):
        '''
        Fetch data from the db via the given sql string and paramaters
        '''
        params = params or []
        if self.thread_safe:
            self.connection = self.connnect_to_db(self.db_filepath)

        cursor = self.connection.cursor()
        cursor.execute(sql, params)
        data = cursor.fetchall()
        cursor.close()
        return data


    @classmethod
    def get_table_sql(cls):

        '''
        create a table with the columns defined in self.columns
        '''
        sql = 'CREATE TABLE IF NOT EXISTS %s (' % cls.table_name
        for column in cls.columns:
            sql += '\n%s %s NOT NULL %s,' % (column["name"],
                                             column["sqlite_type"],
                                             "PRIMARY KEY" if column.get('primary_key') else "")

        sql = sql.rstrip(",")
        sql += ');'
        return sql

    def create_table(self):
        '''
        create the table (if it does not already exist in the db), with the
        self.columns
        '''
        sql = self.get_table_sql()
#         logger.debug("sql: %s", sql)
        self.sql_execute(sql)


    @classmethod
    def row_to_dict(cls, row):
        '''
        Return the give sqlite row object as a python dict
        '''
        row_dict = {}
        for idx, row in enumerate(cls.rows):
            column_name = cls.columns[idx]["name"]
            row_dict[column_name] = row

        return row_dict

    @classmethod
    def dict_to_row_tuple(cls, input_dict):
        '''
        Convert the the given dictionary of data into a tuple of data that is
        suitable to use for a db row insert.
        '''
        row_data = []
        for column in cls.columns:
            column_name = column["name"]
            assert column_name in input_dict, "input dict does not have expected key (%s). Got %s" % (column_name, input_dict)
            column_data = input_dict[column_name]
            assert isinstance(column_data, column["python_type"]), "Wrong type (%s). Expected %s: %s" % (type(column_data), column["python_type"], column_data)
            row_data.append(column_data)

        return tuple(row_data)


    def insert_row(self, row_dict, replace=True):
        '''
        Add the given row data (dictionary) to the the db
        
        row_data: dict, where the keys are the columns names
        replace: bool. When True, will replace the the existing row in the db
                 (if there is one) that matches the row's Primary Key.
        
        '''
        return self.insert_rows([row_dict], replace=replace)


    def insert_rows(self, row_dicts, replace=True):
        '''
        Add the given list of of row data (dictionaries) to the the db
        
        row_data: dict, where the keys are the columns names
        replace: bool. When True, will replace the the existing row in the db
                 (if there is one) that matches the row's Primary Key.
        
        '''

        or_replace = "OR REPLACE" if replace else ""
        sql = 'INSERT %s INTO %s VALUES (%s)' % (or_replace, self.table_name, ','.join("?" * len(self.columns)))
#         logger.debug("sql: %s", sql)
        row_tuples = [self.dict_to_row_tuple(row_dict) for row_dict in row_dicts]
        return self.sql_execute(sql, row_tuples, many=True)



    @classmethod
    def get_column_names(cls):
        '''
        Return the name of all columns in the table
        '''
        names = [column["name"] for column in cls.columns]
        return names



class FilesDB(TableDB):
    table_name = "files"

    columns = (
                ##### FILEPATH #####
                # The path to the file
                {"name": "filepath",
                "python_type": str,
                "sqlite_type": "TEXT",
                "primary_key": True},

                ##### MODTIME #####
                # the timstamp for the files last modification time
                {"name": "modtime",
                "python_type": datetime.datetime,
                "sqlite_type": "TIMESTAMP"},

                ##### SIZE #####
                # the size of the file (in bytes)
                {"name": "size",
                "python_type": (int, long),
                "sqlite_type": "INTEGER"},

                ##### MD5 #####
                # the MD5 hash of the file
                {"name": "md5",
                "python_type": str,
                "sqlite_type": "TEXT"})


    def __init__(self, db_filepath, thread_safe=True):
        super(FilesDB, self).__init__(db_filepath, thread_safe=thread_safe)

    @classmethod
    def add_file(cls, file_info, db_filepath=None, thread_safe=True):
        '''
        Add the given file to the files table
        
        file_info: a dictionaries with the following keys:
                "filepath",
                "modtime"
                "filesize"
        
        
        '''
#         logger.debug("file_info: %s", file_info)
        cls.add_files([file_info], db_filepath=db_filepath, thread_safe=thread_safe)

    @classmethod
    def add_files(cls, files_info, db_filepath=None, thread_safe=True):
        '''
        Add the given list of files to the files db table.
        
        files_info: a list of dictionaries, each with the following keys:
                    "filepath",
                    "modtime"
                    "filesize"
        
        '''
        if not db_filepath:
            db_filepath = get_default_db_filepath()

        db = cls(db_filepath, thread_safe=thread_safe)
        db.insert_rows(files_info, replace=True)

        # close the connection.  Not sure if this is actually necesary
        db.close_connection()


    @classmethod
#     @common.dec_timer_exit(log_level=logging.DEBUG)
    def query_files(cls, filepaths, return_dict=False, db_filepath=None, thread_safe=True):
        '''
        Query the db for all files which match the given filepaths.
        
        Note that this achieved through chunked queries so not to breach sqlite's
        maximum of 999 arguments
        
        one: bool.  If True, treat th
        
        
        '''
        if not db_filepath:
            db_filepath = get_default_db_filepath()

        db = cls(db_filepath, thread_safe=thread_safe)


        files = []
        chunk_size = 500
        for filepaths_chunk in chunker(filepaths, chunk_size):
            # generate a sql string of files to match against
            files_sql = "(%s)" % ','.join("?" * len(filepaths_chunk))
            query = 'SELECT * FROM files WHERE filepath IN %s' % files_sql
            file_rows = db.sql_fetch(query, filepaths_chunk)
            for file_ in file_rows:
                files.append(file_)

        # close the connection.  Not sure if this is actually necesary
        db.close_connection()


        if return_dict:
            files = dict([(entry["filepath"], entry) for entry in files])



        return files


    @classmethod
    def query_file(cls, filepath, db_filepath=None, thread_safe=True):
        '''
        Query the db for all files which match the given filepaths.
        
        Note that this achieved through chunked queries so not to breach sqlite's
        maximum of 999 arguments
        
        '''
        filepaths = [filepath]
        files = cls.query_files(filepaths, return_dict=False, db_filepath=db_filepath,
                                thread_safe=thread_safe)
        if not files:
            return
        assert len(files) == 1, "More than one file entry found: %s" % files
        return files[0]



    @classmethod
    def get_comparison_column_names(cls):
        '''
        Return a list of column names whose data (for a given file row), should
        be used to compare against the data of a file from disk (e.g. to check
        whether a file on disk has stale cache or not).
        This should return names such as "filepath", "modtime, and "size", but
        not "md5" (bc the file on disk doesn't have the md5 info available...which
        is the whole point of quering the db for it :) )
        '''
        return [name for name in cls.get_column_names() if name != "md5"]


    @classmethod
    def get_cached_file(cls, file_info, db_filepath=None, thread_safe=True):

        '''
        For the given file (file_info), return it's db entry if is not considered
        "stale", otherwise return None
           
        '''
        filepath = file_info["filepath"]
        file_entry = cls.query_file(filepath, db_filepath=db_filepath, thread_safe=thread_safe)

        # if there is a file entry, check to see whether it's stale info
        if file_entry:
            # Cycle through column of the file data to ensure that the db cache matches the current file info
            for column_name in cls.get_comparison_column_names():
                # If there is any mismatch then break the loop
                if file_info.get(column_name) != file_entry[column_name]:
                    return

        # If all columns match, then return the file entry from the db
        return file_entry




def chunker(list_, chunk_size):
    '''
    For the given list, return a tuple which breaks creates smaller lists of the
    given size (length), containing the contents of the the orginal list

    '''
    return (list_[pos:pos + chunk_size] for pos in xrange(0, len(list_), chunk_size))




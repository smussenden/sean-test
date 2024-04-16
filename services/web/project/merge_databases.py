# Add all pages from one database to another.
# The pages are entries in the file table.
# We also need to copy the rows of layout_box which correspond to the pages.
# All other tables are kept from the first database.

import sqlite3
import sys
import argparse
import time
import shutil

from pathlib import Path

import pandas as pd

def merge_databases(db1_path, db2_path, output_path=None):
    ''' Add rows from file table in db1 to db2.
    '''
    # Open databases
    db1 = sqlite3.connect(db1_path)
    db2 = sqlite3.connect(db2_path)

    # Get all rows from file table in db1
    file_df1 = pd.read_sql_query('SELECT * FROM file', db1)
    layout_df1 = pd.read_sql_query('SELECT * FROM layout_box', db1)

    # Get all rows from file table in db2
    file_df2 = pd.read_sql_query('SELECT * FROM file', db2)
    layout_df2 = pd.read_sql_query('SELECT * FROM layout_box', db2)

    # Close databases
    db1.close()
    db2.close()

    # First, remove any rows from db2 that are already in db1.
    # Check based on filepath.
    file_df2 = file_df2[~file_df2['filepath'].isin(file_df1['filepath'])]
    layout_df2 = layout_df2[layout_df2['file_id'].isin(file_df2['file_id'])]

    # file_id column must be unique for all rows.
    # So, we need to add the max file_id from db1 to all rows in db2.
    file_df2.file_id += file_df1.file_id.max() + 1
    layout_df2.file_id += file_df1.file_id.max() + 1

    # Add rows from db2 to db1
    file_df1 = file_df1.append(file_df2, ignore_index=True)
    layout_df1 = layout_df1.append(layout_df2, ignore_index=True)

    # If no output_path then set to 'LayoutBoxes_merged_[timestamp of merge].db'
    if output_path is None:
        output_path = 'LayoutBoxes_merged_{}.db'.format(time.strftime('%Y%m%d-%H%M%S'))

    # Write to database.  Start by copying db1 to output_path.
    shutil.copyfile(db1_path, output_path)
    db = sqlite3.connect(output_path)
    # drop the file and layout_box tables
    db.execute('DROP TABLE file')
    db.execute('DROP TABLE layout_box')
    file_df1.to_sql('file', db, if_exists='replace', index=False)
    layout_df1.to_sql('layout_box', db, if_exists='replace', index=False)

    # Add metadata about which databases were merged
    # Do this in a new table, 'db_metadata'
    # This table will have two columns: 'timestamp' and 'description'
    # The timestamp is the time the database was merged.
    # The description is a string describing the merge.
    timestamp = time.strftime('%Y%m%d-%H%M%S')
    description = 'Merged {} and {}.'.format(db1_path, db2_path)
    df = pd.DataFrame({'timestamp': [timestamp], 'description': [description]})
    df.to_sql('db_metadata', db, if_exists='append', index=False)

    # Close database
    db.close()

# Parse args passed to main
def main(args=sys.argv[1:]):
    parser = argparse.ArgumentParser(description='Merge two databases.')
    parser.add_argument('database1', type=Path, help='The database to merge into.')
    parser.add_argument('database2', type=Path, help='The database to merge from.')
    args = parser.parse_args(args)
    merge_databases(args.database1, args.database2)

if __name__ == '__main__':
    main()


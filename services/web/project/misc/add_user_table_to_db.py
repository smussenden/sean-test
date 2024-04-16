# Add a new table "user" to the database

import shutil
import re
import sqlite3
import pandas as pd
from pathlib import Path

# The declaration of the table in sqlalchemy:
'''
# A model for users
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

    def __dict__(self):
        return {
            'id': self.id,
            'name': self.name
        }

    def __repr__(self):
        rstr = f'<User {self.name} with id {self.id}>'
        return rstr

'''

# Populate the database with these users:
users_list = [
    {'id': 0, 'name' : 'null', 'username': 'null', 'password': 'null'},
    {'id': 1, 'name': 'Mohamed Salama', 'username': 'mohamed_salama', 'password': 'msal_gecko_3'},
    {'id': 2, 'name': 'Sarah Meklir', 'username': 'sarah_meklir', 'password': 'smeklir_loop_5'},
    {'id': 3, 'name': 'Jack Rasiel', 'username': 'jack_rasiel', 'password': 'jrasiel_turkey_3'},
    {'id': 4, 'name': 'Sean Mussenden', 'username': 'sean_mussenden', 'password': 'smussenden_dance_9'},
    {'id': 5, 'name': 'Mary Dalrymple', 'username': 'mary_dalrymple', 'password': 'mdalrymple_owl_2'},
    {'id': 6, 'name': 'Rob Wells', 'username': 'rob_wells', 'password': 'rwells_lamp_1'}
]

src_db_path = Path('../db_dir/database.db')
dest_db_path = Path('../db_dir/database_updated_users.db')

# Copy the database to a new one
shutil.copyfile(src_db_path, dest_db_path)

# Load the database
conn = sqlite3.connect(dest_db_path)

# Create the table if it doesn't exist; otherwise, replace it:
conn.execute('DROP TABLE IF EXISTS user')
conn.execute('''CREATE TABLE user
                (id INTEGER PRIMARY KEY, name TEXT, username TEXT, password TEXT)
             ''')
# Populate the table
for user in users_list:
    conn.execute(f"INSERT INTO user VALUES ({user['id']}, '{user['name']}', '{user['username']}', '{user['password']}')")
conn.commit()

# Now, add user_id foreignkey column to Session and File tables.
# In Session, this is user_id. In file, this is last_modified_by.

# First, let';s try to recover the users from the Notes field of each file.
# If the note contains "MS", then it is Mohamed Salama.
# If the note contains "SM", then it is Sarah Meklir. 
# If it contains "Jack", then it is Jack Rasiel.
# Otherwise, it is null.
file_df = pd.read_sql_query("SELECT * FROM file", conn)
file_df['last_modified_by'] = 0
for idx, row in file_df.iterrows():
    notes = row['notes'].lower()
    ms_pat = re.compile(r'(?:^|\W)ms(?:$|\W)')
    sm_pat = re.compile(r'(?:^|\W)sm(?:$|\W)')
    jack_pat = re.compile(r'(?:^|\W)jack(?:$|\W)')
    if ms_pat.search(notes):
        file_df.loc[idx, 'last_modified_by'] = 1
    elif sm_pat.search(notes):
        file_df.loc[idx, 'last_modified_by'] = 2
    elif jack_pat.search(notes):
        file_df.loc[idx, 'last_modified_by'] = 3
    else:
        file_df.loc[idx, 'last_modified_by'] = 0

print('Num files per user:')
print(file_df['last_modified_by'].value_counts())

# Add last_modified_by_name column to file_df
file_df['last_modified_by_name'] = file_df['last_modified_by'].map(
    {0: 'null', 1: 'Mohamed Salama', 2: 'Sarah Meklir', 3: 'Jack Rasiel',
        4: 'Sean Mussenden', 5: 'Mary Dalrymple', 6: 'Rob Wells'})

# Save to the dest database:
file_df.to_sql('file', conn, if_exists='replace', index=False)

# Now add user column 
session_df = pd.read_sql_query("SELECT * FROM session", conn)
session_df['user_id'] = 0
session_df.to_sql('session', conn, if_exists='replace', index=False)


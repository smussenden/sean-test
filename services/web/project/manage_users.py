# Add new user to the DB.

#CREATE INDEX ix_last_backup_index ON last_backup ("index");
#CREATE TABLE user (
#        "index" BIGINT,
#        id BIGINT,
#        name TEXT
#);
import os
import random
import sys
import sqlite3

def add_new_user(db_name, name, username, password=None):
    print(f'Adding new user: {username}')

    # Check password for length and invalid characters.
    # Valid password length is 8-128 characters, and only printable characters are allowed.
    if password is not None:
        if len(password) < 8 or len(password) > 128:
            raise ValueError("Password must be between 8 and 128 characters long.")
        if not password.isprintable():
            raise ValueError("Password contains invalid characters. Only printable characters are allowed.")

    conn = sqlite3.connect(db_name)
    c = conn.cursor()

    # Check if this username already exists:
    c.execute("SELECT * FROM user WHERE username=?", (username,))
    if c.fetchone() is not None:
        conflicting_name = c.fetchone()[2]
        print("ERROR: Username already exists for user: " + conflicting_name)
    else:
        # Get last user id value and increment it by 1
        # This is the new user's id
        c.execute("SELECT MAX(id) FROM user")
        last_user_id = c.fetchone()[0]
        if last_user_id is None:
            last_user_id = 0
        user_id = last_user_id + 1

        # Generate a password if not provided:
        if password is None:
            password = generate_password()
        print("Password: " + password)

        c.execute("INSERT INTO user VALUES (?, ?, ?, ?)", (user_id, name, username, password))
        conn.commit()
        conn.close()

        print('Successfully added user: %s' % username)


def generate_password(num_words=2, max_length=40, delimiter='-'):
    """
    Generate a password using words from the standard dictionary.

    Args:
        num_words (int): Number of words in the password.
        max_length (int): Maximum length of the password.
        delimiter (str): Delimiter between words in the password.

    Returns:
        str: Generated password.
    """
    with open('/usr/share/dict/words', 'r') as f:
        words_list = [word.strip() for word in f.readlines()]

    if num_words <= 0:
        raise ValueError("Number of words must be greater than 0.")
    
    # Sample words but reject if a word is longer than 8 characters.
    # Keep sampling until num_words words are sampled.
    words = []
    while len(words) < num_words:
        word = random.choice(words_list)
        if len(word) <= 8:
            words.append(word)
    password = delimiter.join(words)

    return password[:max_length]

def add_users_from_file(db_name, csv_file):
    '''
    Add users from a CSV file to the database.

    CSV file format:
    username,name,password
    '''
    conn = sqlite3.connect(db_name)
    c = conn.cursor()

    with open(csv_file, 'r') as f:
        for line in f.readlines():
            # First line is columns
            if line.startswith('username'):
                continue
            name, username, password = line.strip().split(',')
            if password == '':
                password = None
            try:
                add_new_user(db_name, name, username, password)
            except ValueError as e:
                print(f"ERROR when inserting user {username}: {e}")

    conn.commit()
    conn.close()

def copy_users(db_name, new_db_name):
    '''Overwrite the users table in new_db_name with the users table in db_name.
    '''
    conn = sqlite3.connect(db_name)
    c = conn.cursor()

    c.execute("SELECT * FROM user")
    users = c.fetchall()

    conn.close()

    if not os.path.exists(new_db_name):
        raise ValueError(f"Database {new_db_name} does not exist.")
    else:
        if not database_schema_is_correct(new_db_name):
            raise ValueError(f"Database {new_db_name} does not have the correct schema.")
        else:
            # Ask user if sure about overwrite:
            print('WARNING: This will overwrite the users table in %s. Are you sure you want to continue? (y/n)' % new_db_name)
            if input() != 'y':
                print('Aborting...')
                sys.exit(1)
            else:
                conn = sqlite3.connect(new_db_name)
                c = conn.cursor()

                c.execute("DELETE FROM user")
                c.executemany("INSERT INTO user VALUES (?, ?, ?, ?)", users)
                conn.commit()
                conn.close()

                print('Successfully copied users from %s to %s' % (db_name, new_db_name))


def change_user_username(db_name, username, new_username):
    conn = sqlite3.connect(db_name)
    c = conn.cursor()

    # Check if query username exists:
    c.execute("SELECT * FROM user WHERE username=?", (username,))
    if c.fetchone() is None:
        print(f'ERROR: Username {username} does not exist.')
    c.execute("SELECT * FROM user WHERE username=?", (new_username,))
    if c.fetchone() is not None:
        # Get that user's display name:
        c.execute("SELECT name FROM user WHERE username=?", (new_username,))
        conflicting_name = c.fetchone()[2]
        print(f'ERROR: Username {new_username} already exists in the database. Display name: {conflicting_name}')
        print('Aborting...')
        sys.exit(1)

    sure = input(f'Are you sure you want to change the username of {username} to {new_username}? (y/n)')
    if sure.lower() == 'y':
        c.execute("UPDATE user SET username=? WHERE username=?", (new_username, username))
        conn.commit()
        conn.close()
        print(f'Successfully changed username: {username} -> {new_username}')
    else:
        print('Aborting username change.')
        sys.exit(1)

def change_user_display_name(db_name, username, name):
    conn = sqlite3.connect(db_name)
    c = conn.cursor()

    # Check if query username exists:
    c.execute("SELECT * FROM user WHERE username=?", (username,))
    if c.fetchone() is None:
        print(f'ERROR: Username {username} does not exist.')
    else:
        # If the same display name already exists, ask user if they're sure:
        c.execute("SELECT * FROM user WHERE name=?", (name,))
        user_with_same_name = c.fetchone()
        if user_with_same_name is not None and user_with_same_name[2] != username:
            print(f'WARNING: Display name "{name}" already exists in the database. Do you want to continue? (y/n)')
            if input() != 'y':
                print('Aborting...')
                sys.exit(1)

        c.execute("SELECT * FROM user WHERE username=?", (username,))
        old_display_name = c.fetchone()[1]
        print(f'Are you sure you want to change user {username}\'s display name: {old_display_name} -> {name}? (y/n)')
        if input() == 'y':
            c.execute("UPDATE user SET name=? WHERE username=?", (name, username))
            conn.commit()
            conn.close()

            print(f'Successfully changed user "{username}"\'s display name: {old_display_name} -> {name}')
        else:
            print('Aborting display name change.')

def database_schema_is_correct(db_name):
    '''Verify that db has table 'user' with columns 'index', 'id', 'name', 'username', and 'password'.'

    Assumes db exists.

    returns: bool
    '''
    conn = sqlite3.connect(db_name)
    c = conn.cursor()

    # Check if table 'user' exists:
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user'")
    if c.fetchone() is None:
        print('ERROR: Database schema is incorrect. Table \'user\' does not exist.')
        return False
    else:
        # Check if table 'user' has columns 'id', 'name', 'username', and 'password':
        c.execute("PRAGMA table_info(user)")
        columns = c.fetchall()
        required_columns = {'id', 'name', 'username', 'password'}
        existing_columns = {column[1] for column in columns}

        missing_columns = required_columns - existing_columns
        if missing_columns:
            print('ERROR: Database schema is incorrect. Table \'user\' is missing columns: %s' % ', '.join(missing_columns))
            return False
        else:
            return True

def main(args):
    # args:  action, path_to_database_file, display name, username, password
    # valid actions are:
    #
    #   add_new_user <path_to_database_file> <display_name> <username> <password>
    #       Add a new user to the database.
    #   copy_users <path_to_database_file> <path_to_new_database_file>
    #       Copy all users from one database's 'user' table to another.
    #   change_user_username <path_to_database_file> <username> <new_username>
    #       Change a user's username.
    #   change_user_display_name <path_to_database_file> <username> <new_display_name>
    #       Change a user's display name.

    #add_new_user_usage = "Usage: %s add_new_user <path_to_database_file> <display_name> <username> <password>" % sys.argv[0]
    #add_new_user_description = "Add a new user to the database."
    #copy_users_usage = "Usage: %s copy_users <path_to_database_file> <path_to_new_database_file>" % sys.argv[0]
    #copy_users_description = "Copy all users from one database's 'user' table to another."
    #change_user_username_usage = "Usage: %s change_user_username <path_to_database_file> <username> <new_username>" % sys.argv[0]
    #change_user_username_description = "Change a user's username."

    documentation = {
        'add_new_user': ('Usage: %s add_new_user <path_to_database_file> <display_name> <username> <password>' % sys.argv[0],
                         4,
                         "Add a new user to the database.",
                         add_new_user),
        'add_users_from_file': ('lol', 2, 'lol', add_users_from_file),
        'copy_users': ('Usage: %s copy_users <path_to_database_file> <path_to_new_database_file>' % sys.argv[0],
                       2,
                       'Copy all users from one database\'s \'user\' table to another.',
                       copy_users),
        'change_user_username' : ('Usage: %s change_user_username <path_to_database_file> <username> <new_username>' % sys.argv[0],
                                  3,
                                  'Change a user\'s username.',
                                  change_user_username),
        'change_user_display_name' : ('Usage: %s change_user_display_name <path_to_database_file> <username> <new_display_name>' % sys.argv[0],
                                      3,
                                      'Change a user\'s display name.',
                                      change_user_display_name),
    }

    if len(sys.argv) < 2:
        print('Usage: %s <action> <args>' % sys.argv[0])
        print('Valid actions are:')
        for action in documentation:
            print('    %s' % action)
            print('        %s' % documentation[action][2])
        sys.exit(1)

    action = sys.argv[1]
    if action not in documentation:
        print('ERROR: Invalid action: %s' % action)
        print('Valid actions are:')
        for action in documentation:
            print('    %s' % action)
            print('        %s' % documentation[action][2])
        sys.exit(1)
    else:
        # Verify correct num arguments and valid database file:
        if len(sys.argv) != documentation[action][1] + 2:
            print('ERROR: Invalid number of arguments for action %s' % action)
            print(documentation[action][0])
            sys.exit(1)
        else:
            # Verify database schema:
            if not database_schema_is_correct(sys.argv[2]):
                print("ERROR: Database schema is incorrect. Aborting...")
                sys.exit(1)

    # Perform action:
    documentation[action][3](*sys.argv[2:])

if __name__ == "__main__":
    main(sys.argv)

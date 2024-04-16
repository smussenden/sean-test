from icecream import ic

# print working dir:
import sys, os
print('Working dir:', os.getcwd())
# ls the contents:
print(os.listdir('.'))

# Import the models for our database
from project.models import db, Session, File, LayoutBox, LastBackup, User

import json
import ast
import os
import time
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

from flask import Flask, render_template, redirect, request, jsonify
from flask_socketio import *
from flask_sqlalchemy import SQLAlchemy
# import flask login:
from flask_login import current_user, LoginManager, login_user, logout_user, login_required

from sqlalchemy.sql import func
from sqlalchemy import event

from PIL import Image
from google.cloud import storage

MODIFICATIONS_PER_BACKUP = 50 # TODO put this in a proper config.py
BACKUP_DIR = Path('./backups/')

DB_PATH = Path('/usr/src/app/db_dir/database.db')

basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] =\
    'sqlite:///' + os.path.join(basedir, str(DB_PATH))
#! TODO! implement real secret key:
app.config['SECRET_KEY'] = 'Replace me with something real!'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['TEMPLATES_AUTO_RELOAD'] = True # TODO DEV ONLY

socketio = SocketIO(app, logger=True)

login_manager = LoginManager()

try:
    assert BACKUP_DIR.exists()
except AssertionError:
    # AssertionError message should contain the contents of the working dir.
    err_str = 'BACKUP_DIR does not exist! Contents of working dir:\n'
    for f in os.listdir('.'):
        err_str += f + '\n'
    raise AssertionError(err_str)

with app.app_context():
    db.init_app(app)
    db.create_all()

    db.session.commit()  # TODO
    # TODO logging.
    print('Deleted %d existing session records' % Session.query.delete())
    db.session.commit()


# TODO finish adding login functionality including the stuff below
login_manager.init_app(app)
login_manager.login_view = 'login_page'
@login_manager.user_loader
def load_user(user_id):
    ic(user_id)
    return User.query.filter_by(id=user_id).first()
@app.route('/login', methods=['POST'])
def login():
    # JSONify the form
    info = request.form.to_dict(flat=False)
    ic(info)

    #info = json.loads(request.data)
    username = info.get('username', 'guest')
    ic(username)
    password = info.get('password', '')
    ic(password)
    # Query user model to see if user exists
    user = User.query.filter_by(username=username[0], password=password[0]).first()
    ic(user)
    if user:
        login_user(user)
        # Redirect to the main page
        return redirect('/')
        #return jsonify(user.to_json())
    else:
        print('user login error for user %s' % username)
        return jsonify({"status": 401,
                        "reason": "Username or Password Error"})

# Route to a login page which will redirect to the main page if the user is already logged in.
@app.route('/login_page')
def login_page():
    if current_user.is_authenticated:
        return redirect('/')
    else:
        return render_template('login.html')

@app.route('/logout', methods=['POST','GET'])
def logout():
    logout_user()

    # redirect to login page
    return redirect('/login_page')

@app.route('/user_info', methods=['POST'])
def user_info():
    if current_user.is_authenticated:
        resp = {"result": 200,
                "data": current_user.to_json()}
    else:
        resp = {"result": 401,
                "data": {"message": "user no login"}}
    return jsonify(**resp)


def save_new_annotation_to_db(page_details, box_data, user_id):
    '''
    Save annotation to the database.

    params:
    '''
    ic('saving new!')
    # Update the original row for this page to mark it as having been annotated.
    orig = File.query.filter_by(
        #filepath= page_details['filepath'],
        batch=page_details['batch'],
        sn=page_details['sn'],
        year=page_details['year'],
        month=page_details['month'],
        day=page_details['day'],
        edition=page_details['ed'],
        page=page_details['seq'],
        mod_id = 0).first()
    orig.num_annotations += 1

    # Get latest mod_id for this page.
    # Also get page_width.
    query = File.query.filter_by(
        #filepath= page_details['filepath'],
        batch=page_details['batch'],
        sn=page_details['sn'],
        year=page_details['year'],
        month=page_details['month'],
        day=page_details['day'],
        edition=page_details['ed'],
        page=page_details['seq'])
    rows = query.all()

    last_mod_id = max([o.mod_id for o in rows])
    page_details['mod_id'] = last_mod_id + 1
    page_width = rows[0].page_width

    # Check if any article highlights were added to the page.
    has_article_highlights = False
    for box in box_data:
        if box['className'] == 'highlightactivated':
            has_article_highlights = True
            break

    # Make a new file_id for this page
    latest_file_id = db.session.query(func.max(File.file_id)).scalar()
    page_details['file_id'] = latest_file_id + 1

    # Set the last_modified user id and username for this page:
    user = User.query.filter_by(id=user_id).first()
    page_details['last_modified_by_name'] = user.name
    page_details['last_modified_by'] = user.id

    # Saving:
    # TODO not threadsafe. Need to lock db after getting latest_id, and only unlock after adding the new rows w/ new_id.
    # In practice this should barely ever happen.
    # ALSO: chance (even smaller) that mod_id could be stale by this point....

    # Create the new File row:
    new_row = File(
        page_width=page_width,
        file_id=page_details['file_id'],
        filepath=page_details['filepath'],
        newspaper_name=page_details['newspaper_name'],
        batch=page_details['batch'],
        sn=page_details['sn'],
        date=page_details['date'],
        year=page_details['year'],
        month=page_details['month'],
        day=page_details['day'],
        edition=page_details['ed'],
        page=page_details['seq'],
        mod_id=page_details['mod_id'],
        deleted=False,
        num_annotations=0,

        last_modified=datetime.now(timezone.utc),
        last_modified_by=page_details['last_modified_by'],
        last_modified_by_name=page_details['last_modified_by_name'],

        notes=page_details['notes'],
        flag_irrelevant=page_details['flag_irrelevant'],
        flag_other=page_details['flag_other'],
        flag_bad_layout=page_details['flag_bad_layout'],

        has_article_highlights = has_article_highlights,
        img_height = page_details['img_height'],
        img_width = page_details['img_width'],

    )
    db.session.add(new_row)
    db.session.commit()

    add_annotations_to_db(page_details, box_data, page_width)

    return 'success'


def update_existing_annotation_in_db(page_details, box_data, user_id):
    '''
    Replace annotation in the database.
    '''
    fquery = File.query.filter_by(
        file_id=page_details['file_id']
    )
    file = fquery.first()

    # (first, update the File row's notes and flags)
    file.notes = page_details['notes']
    file.flag_irrelevant= page_details['flag_irrelevant']
    file.flag_other = page_details['flag_other']
    file.flag_bad_layout = page_details['flag_bad_layout']
    file.last_modified = datetime.now(timezone.utc)
    
    # Now, set the last_modified user id and username for this page:
    user = User.query.filter_by(id=user_id).first()
    file.last_modified_by_name = user.name
    file.last_modified_by = user.id

    # Check if any article highlights were added to the page.
    has_article_highlights = False
    for box in box_data:
        if box['className'] == 'highlightactivated':
            has_article_highlights = True
            break
    file.has_article_highlights = has_article_highlights

    page_width = file.page_width
    db.session.commit()

    # Delete rows for this file_id + mod_id.
    # Also get page_width.
    query = LayoutBox.query.filter_by(
        file_id=page_details['file_id']
    )
    rows = query.all()

    query.delete()
    db.session.commit()

    # Saving:
    # TODO not threadsafe. Need to lock db after getting latest_id, and only unlock after adding the new rows w/ new_id.
    # In practice this should barely ever happen.
    # ALSO: chance (even smaller) that mod_id could be stale by this point....

    add_annotations_to_db(page_details, box_data,  page_width)

    return 'success'


def add_annotations_to_db(page_details, box_data, page_width):
    # Create the new layout box rows:

    # Box_data:  replace highlight with TextBlock etc.
    for box in box_data:
        if box['className'] == 'highlight':
            box['className'] = 'TextBlock'
        elif 'kw_highlight' in box['className']:
            box['className'] = 'KeyLine'
        elif box['className'] == 'highlightactivated':
            # TODO just make this a bool column in the db instead?
            box['className'] = 'selected_block'
        else:
            raise Exception(f"Unrecognized box class {box['className']}")

        # Box_data: reconstruct original dimensions (multiply by page_width).
        box['width'] = float(box['width'])*page_width
        box['height'] = float(box['height']) * page_width
        box['x'] = float(box['x']) * page_width
        box['y'] = float(box['y']) * page_width

    for box in box_data:
        new_row = LayoutBox(
            file_id=page_details['file_id'],
            element=box['className'],
            article_id=box['article_id'],
            ID=box['id'],
            HEIGHT=box['height'],
            WIDTH=box['width'],
            HPOS=box['x'],
            VPOS=box['y'],
            KEYWORD_STATS=str(box['KEYWORD_STATS']) if 'KEYWORD_STATS' in box.keys() else '' 
        )
        db.session.add(new_row)
    db.session.commit()
    return 'success'
    # TODO put calls to this function in a try-catch to judge success?


@socketio.on('get_table_state_update')
def get_table_state_update(thedata):
    '''
    Get all File rows which have changed since last_updated.

    params:
        data:  dict
            last_updated: UTC timestamp of last time client was updated on table state.
            rows_locked: list of file_ids of rows currently locked in the client table.
    '''
    # Things:
    # All rows modified since last_updated
    thedata['last_updated'] = datetime.fromisoformat(thedata['last_updated'])
    rows_to_update = File.query.filter(
        File.last_modified > thedata['last_updated']).all()

    # For each row_to_update, if that row has mod_id == 1, add its mod_id == 0 counterpart to the list:
    for F in rows_to_update.copy():
        if F.mod_id == 1:
            rows_to_update.append(File.query.filter_by(
                filepath=F.filepath, mod_id=0).first())

    rows_to_update = [F.get_page_data() for F in rows_to_update]

    # All rows locked since last_updated (get this from sessions)
    locks_since = Session.query.filter(
        Session.session_start_time > thedata['last_updated']).all()
    for sess in locks_since:
        rows_to_update.append(sess.file.get_page_data())

    # Last, iterate through all row entries to add the locked field:
    locked_page_ids = Session.query.with_entities(Session.file_id).all()
    locked_page_ids = [p[0] for p in locked_page_ids]
    for row in rows_to_update:
        row['last_modified'] = row['last_modified'].isoformat()
        if row['file_id'] in locked_page_ids:
            row['locked'] = True
        else:
            row['locked'] = False

    # Check which rows should be unlocked in the client's table:
    locked_for_client = {int(r_id) for r_id in thedata['rows_locked']}
    should_be_locked = Session.query.with_entities(Session.file_id, Session.is_original_page).all()
    should_be_locked = {int(f_id) for (f_id, is_orig_page) in should_be_locked if (f_id is not None and is_orig_page)}
    rows_to_unlock = list(locked_for_client - should_be_locked)
    rows_to_lock = list(should_be_locked - locked_for_client)

    ## Get the usernames for the last_modified_by user_ids:
    #for row in rows_to_update:
    #    # Get the user name based on the user id, and add it to the page details:
    #    if row['last_modified_by'] == 0:
    #        row['user_name'] = 'null'
    #    else:
    #        row['user_name'] = User.query.filter_by(
    #            id=row['last_modified_by']).first().name

    # Send the update to the client which requested it:
    thetime = datetime.now(timezone.utc)
    ic(rows_to_update)
    socketio.emit('table_update', {'rows_to_update': rows_to_update,
                                   'rows_to_unlock': rows_to_unlock,
                                   'rows_to_lock': rows_to_lock,
                                   'update_timestamp': thetime.isoformat()},
                  room=request.sid)


@socketio.on('save_page')
def save_annotation(data):
    '''
    Handle saving annotation data sent from the client.

    params:
        data: dict { page_details, box_data, is_new_annotation }
    '''
    page_details = data['page_details']
    box_data = data['box_data']
    is_new_annotation = data['is_new_annotation']

    # get user_id from the login manager
    user_id = current_user.id

    ic(page_details)

    # Validate the articles which are being saved.
    # All articles with class "selected_block" must have an article id which is non-negative int.
    # If such a case is found, send and error message to the client with socketio.
    for box in box_data:
        if box['className'] == 'highlightactivated' and box['article_id'] < 0:
            socketio.emit('save_failed', {'message': f'ERROR: Found an invalid article highlight.  Please reload the page and try to highlight again. (Details: invalid article id for highlighted block. Overlay id: {box["id"]} )'},
                          room=request.sid)
            return

    try:
        if is_new_annotation:
            result = save_new_annotation_to_db(page_details, box_data, user_id)
        else:
            result = update_existing_annotation_in_db(page_details, box_data, user_id)
    except Exception as e:
        socketio.emit('save_failed', {'message': f'ERROR: hit exception on save function.  Admin: see logs.'}) # TODO add logging you dolt
        print(f'ERROR: hit exception on save function.  The exception: {e}')
        return

    # Check if it's time to backup the db:
    last_backup_q = LastBackup.query
    last_backup = last_backup_q.first()
    if (last_backup.modifications_since >= MODIFICATIONS_PER_BACKUP):
        print('Backing up...')
        backup_filepath = str(backup_db())
        print(f'Backed up DB to {backup_filepath}')

        last_backup_q.delete()
        db.session.add(
            LastBackup(filepath = backup_filepath,
                       modifications_since = 0)
        )
        db.session.commit()
    else:
        filepath = last_backup.filepath
        num_modifications = last_backup.modifications_since

        last_backup_q.delete()
        db.session.add(
            LastBackup(filepath = filepath,
                       modifications_since = num_modifications + 1)
        )
        db.session.commit()
        print('Num files modified and/or created since last save backup: ', num_modifications + 1)

    if result == 'success':
        socketio.emit('save_successful', {})
    else:
        socketio.emit('save_failed', {'message': f'ERROR: {result}'})

def backup_db():
    ''' returns filepath of the backup '''
    tstamp = str(datetime.now(timezone.utc)).replace(' ','_')
    backup_file = BACKUP_DIR / Path(DB_PATH.stem + tstamp + '.db')

    def progress(status, remaining, total):
        print(f'Copied {total-remaining} of {total} pages...')

    con = sqlite3.connect(DB_PATH)
    bck = sqlite3.connect(backup_file)
    with bck:
        con.backup(bck, pages=1, progress=progress)
    bck.close()
    con.close()

    return backup_file

@socketio.on('disconnect')
def unlock_page():
    '''
    When an annotation page closes, get the file_id for that page,
    and unlock it for everyone.
    '''
    print('got a disconnect from', request.sid)
    target_session_q = Session.query.filter_by(id=request.sid)
    q_results = Session.query.filter_by(id=request.sid).all()
    if len(q_results) > 0:
        target_session = q_results[0]
        file_id = target_session.file_id
        is_original_page = target_session.is_original_page
        target_session_q.delete()
        db.session.commit()

        # Get the file entry for this file_id.
        # Session already has a foreign key to file_id, so this should work:
        ic(is_original_page)
        if is_original_page:
            socketio.emit('unlock_page_for_client', {
                          'file_id': file_id}, broadcast=True)

@socketio.on('set_user')
def set_user(data):
    '''
    Set the user for the current session.
    '''
    # Verify valid user_id by checking user table:
    user_id = data['user_id']
    if user_id == 0:
        # TODO proper error handling
        print(f'Invalid user_id: {user_id}.  This is the null placeholder.')
        return

    user_q = User.query.filter_by(id=user_id)
    if user_q.count() == 0:
        # TODO emit error to client
        print(f'User {user_id} does not exist in the database.')
        print('You need to implement proper error handling here buddy.')
        return

    # Check if session exists with this id:
    if (len(Session.query.filter_by(id=request.sid).all()) == 0):
        # Create a new session:
        new_sess = Session(id=request.sid, user_id=user_id)
        db.session.add(new_sess)
    else:
        # Update the user_id for the existing session:
        Session.query.filter_by(id=request.sid).update({'user_id': user_id})

    db.session.commit()
    print(f'User set to {user_q.first().name}.')

@socketio.on('page_opened')
def lock_page(data):
    '''
    If one client has opened an ORIGINAL page (i.e. mod_id = 0), lock it for all the other clients.
    '''

    # get the file entry from the database:
    file_id = data['file_id']
    file = File.query.filter_by(file_id=file_id).first()
    is_original_page = file.mod_id == 0


    if is_original_page:
        socketio.emit('lock_page_for_client', {
                      'file_id': data['file_id']}, broadcast=True)

    # Add this session to the db, unless it's already there.
    # (Annotator might send "page_opened" twice, to make sure it isn't missed.)
    if (len(Session.query.filter_by(id=request.sid).all()) == 0):
        # Update session tracker with this page and session:
        new_sess = Session(id=request.sid, file_id=data['file_id'],
                           is_original_page = is_original_page,
                           session_start_time=datetime.now(timezone.utc))
        db.session.add(new_sess)
        try:
            db.session.commit()
        except Exception as e:
            ic(e)
            ic(new_sess)
            ic(new_sess.id)
            ic(new_sess.file_id)
            ic(new_sess.is_original_page)
            ic(new_sess.session_start_time)
    else:
        # Update the session with the new file_id and is_original_page:
        Session.query.filter_by(id=request.sid).update(
            {'file_id': data['file_id'],
             'is_original_page': is_original_page})
        db.session.commit()

# Event listener for commit, updating summary stats for file table.
@event.listens_for(db.session, 'before_commit')
def update_stats(session):
    # Get all the instances that have been modified in this session:
    modified_files = session.new.union(session.dirty)
    orig_len = len(modified_files)
    modified_files = [file for file in modified_files if isinstance(file, File)]
    if len(modified_files) != orig_len:
        print(f'Info: {orig_len - len(modified_files)} non-file instances modified in this session.  Ignoring them.')

    if len(modified_files) == 0:
        print('No files modified in this session.  Not updating stats.')
        return
    else:
        print(f'{len(modified_files)} files modified in this session.  Updating stats.')
        print(f'The following files were modified: {modified_files}')

    # Summary stats to update:
    #  1 - total number pages annotated, and left to annotate.
    #  2 - how many annotations per user?
    #  3 - how many annotated pages WITH articles AND no flags?  (i.e., how many will make it into our dataset?)
    query = File.query.all()
    pages = [row.get_page_data() for row in query]
    num_pages_annotated = summary_stats_total_pages_annotated(pages)
    num_annotations_per_user, num_unique_pages_annotated_per_user, users_dict = summary_stats_num_annotations_per_user() # dict
    num_pages_going_to_the_dataset = summary_stats_num_pages_going_to_the_dataset()

    # Emit the stats to the client:
    socketio.emit('update_summary_stats', {
        'num_pages_annotated': num_pages_annotated,
        'num_annotations_per_user': num_annotations_per_user,
        'num_unique_pages_annotated_per_user': num_unique_pages_annotated_per_user,
        'users_dict': users_dict,
        'num_pages_going_to_the_dataset': num_pages_going_to_the_dataset
    })


def summary_stats_total_pages_annotated(pages):
    '''
    Return the total number pages annotated.

    params:
        pages: list of File instances
    '''
    # Get the total number of pages in the database, and the number of pages which have been annotated:
    original_page_rows = [page for page in pages if page['mod_id'] == 0] 
    num_pages = len(original_page_rows)

    num_pages_annotated = 0
    for page in original_page_rows:
        if page['num_annotations'] > 0:
            num_pages_annotated += 1

    return num_pages_annotated

def summary_stats_num_annotations_per_user():
    ''' 
    Compute stats on number of annotations made by each user.

    Returns:
        num_annotations_per_user: total annotations made per user.
        num_unique_pages_annotated_per_user: total unique pages annotated per user.
    '''
    #users = [user.as_dict() for user in User.query.all() if user.id != 0]
    users = [user.as_dict() for user in User.query.all() ]
    users_dict = {user['id']: user for user in users}

    # db query counting instances of each value in the last_modified_by column:
    query_num_annotations = db.session.query(File.last_modified_by,
                                             func.count(File.last_modified_by)).group_by(File.last_modified_by).all()

    # EDGE CASE: if there are no annotations, return empty dicts:
    if len(query_num_annotations) == 0:
        return {}, {}, users_dict

    # Group file table by filepath and get the max mod_id in each group.  Include the
    # last_modified_by in the retrieved information.  Exclude mod_id == 0
    query_unique_pages = db.session.query(File.filepath, File.last_modified_by, func.max(File.mod_id)).filter(File.mod_id > 0).group_by(File.filepath).all()

    # Count the occurrences of each user in that:
    num_unique_pages_annotated_per_user = dict()
    for row in query_unique_pages:
        try:
            num_unique_pages_annotated_per_user[row[1]] += 1
        except KeyError:
            num_unique_pages_annotated_per_user[row[1]] = 1

    # SPECIAL CASE: the "null" user (id 0).
    # This is used in two cases:
    #   1 - for original (mod_id == 0) pages, which are never annotated anyway.
    #   2 - user is unknown.  This is for legacy annotations, from before users were implemented.
    # 
    # We don't want to include case 1 in the stats for the null user.
    # So we need to perform a second query to count pages where last_modified_by == 0 AND mod_id != 0.
    query_for_null_user = db.session.query(File.last_modified_by, func.count(File.last_modified_by)).filter(File.last_modified_by == 0).filter(File.mod_id != 0).group_by(File.last_modified_by).all()
    num_pages_annotated_by_null_user = query_for_null_user[0][1]

    # Convert to dict:
    num_annotations_per_user = {}
    for row in query_num_annotations:
        if row[0] == 0:
            num_annotations_per_user[0] = num_pages_annotated_by_null_user
        else:
            num_annotations_per_user[row[0]] = row[1]

    return num_annotations_per_user, num_unique_pages_annotated_per_user, users_dict


def summary_stats_num_pages_going_to_the_dataset():
    '''
    How many annotated pages WITH articles AND no flags?  (i.e., how many will make it into our dataset?)
    '''
    # Get pages with articles and no flags:
    # i.e., where has_article_highlights is True and no flags are set.
    search_args = [ File.has_article_highlights == True, File.flag_bad_layout == False,
                   File.flag_irrelevant == False, File.flag_other == False ]
    with_valid_articles = File.query.filter(*search_args).all()

    # drop into ipy shell if there are no rows in the File table
    if len(File.query.all()) == 0:
        import IPython; IPython.embed()

    print(f'Total page rows in database with valid articles: {len(with_valid_articles)}')

    # Pages can be repeated, so get the latest mod_id for them all:
    instances_to_keep = {} # mapping filepath -> File instance.
    for page in with_valid_articles:
        # Sanity check: assert that none of the flags for this page are set:
        assert page.flag_bad_layout == False
        assert page.flag_irrelevant == False
        assert page.flag_other == False

        if page.filepath in instances_to_keep:
            if page.mod_id > instances_to_keep[page.filepath].mod_id:
                instances_to_keep[page.filepath] = page
        else:
            instances_to_keep[page.filepath] = page

    print(f'Total page rows in database with valid articles, after removing duplicates: {len(instances_to_keep)}')

    return len(instances_to_keep)


def is_page_annotated(page_data):
    ''' Check if a page has been annotated. 

    params:
        page_data: dict of page details (as returned by get_page_data())
    '''

    # Page has been annotated if any of these are true:
    #   - mod_id > 1
    #   - flag_bad_layout
    #   - flag_irrelevant
    #   - flag_other

    if page_data['mod_id'] > 1:
        return True
    else:
        return False

# AJAX route for table data:
@app.route('/table_data')
@login_required
def get_file_browser_table_data():
    ''' Get data for table. '''

    # Get the data:
    query = File.query.all()
    pages = [row.get_page_data() for row in query]

    locked_page_ids = Session.query.with_entities(Session.file_id).all()
    locked_page_ids = [p[0] for p in locked_page_ids]

    for page in pages:
        if page['file_id'] in locked_page_ids:
            page['locked'] = True
        else:
            page['locked'] = False


    return jsonify(data=pages)

# Try reformatting the data so that pages with the same filepath are grouped.
@app.route('/table_data_grouped')
@login_required
def get_file_browser_table_data_grouped():
    '''
    The final format of the data will be, for each row in the DataTable:
    {
        filepath: '/path/to/file',
            [ ... all the other page-level columns ]
        file_id: 123,
            [ ... all the other file-level columns FOR THIS ANNOTATION ]
        mod_entries : 
            [
                {
                    mod_id : 1,
                    [ ... all the other annotation-level columns ]
                },
                   [ ... all the other annotations ... ]
            ]
    }

    CRUCIAL NOTE:  each page will have UP TO TWO of these "top-level" entries:
        1:  an entry for the ORIGINAL non-annotated page (i.e. mod_id == 0)
        2:  an entry for the LATEST annotation (i.e. mod_id == max(mod_id) for that page)
    This is so that the user can filter the DataTable to show only the original pages, or only annotations.
    '''
    # Do a group_concat for the columns which can vary between annotations.
    # For the columns which are the same for all annotations of a page, just get the first one.
    single_value_query_fields = [getattr(File, col) for col in File.page_level_columns]
    # some columns contain commas in their values, so we need to use a non-ASCII character as the separator.
    group_concat_query_fields = [func.group_concat(getattr(File,col), '¶').label(col) for col in
                                 File.annotation_level_columns]
    query = db.session.query(*single_value_query_fields,
                             *group_concat_query_fields).group_by(File.filepath).all()

    print(f'NUMBER OF ROWS IN QUERY: {len(query)}')

    # TODO TODO need to sanitize all values saved to the db so that they don't include ¶.
    for i in range(10):
        print('TODO TODO need to sanitize all values saved to the db so that they don\'t include ¶.')

    # Now, convert the query results into a list of dicts.
    # See the docstring for the format of these dicts.
    table_rows_originals = []
    table_rows_latest_annotations = []
    # TODO NEXT keep debugging -- need to handle the fact that sometimes grouped fields have only
    # one value -- or none at all.  e.g. notes.
    for row in query:
        # Get the page-level columns:
        row = dict(row)

        # Debug if filepath is ak_albatross_ver01/sn84020657/1915/08/27/ed-1/seq-4
        #if row['filepath'] == 'ak_albatross_ver01/sn84020657/1915/08/27/ed-1/seq-4':
        #    print('DEBUG DEBUG DEBUG')
        #    import pdb; pdb.set_trace()

        page_level_data = {col: row[col] for col in File.page_level_columns}

        annotation_entries = []
        num_mod_ids = len(row['mod_id'].split('¶'))
        original_page_annotation_entry = None
        latest_annotation_entry = None

        if num_mod_ids == 1:
            # EDGE CASE: This page hasn't been annotated.  There's only one mod_id, and it's 0.
            # So, we'll just use the original page data for the "latest annotation" entry.
            original_page_annotation_entry = {col: row[col] for col in File.annotation_level_columns}
            latest_annotation_entry = None
        else:
            # This page has been annotated.  So, we'll need to create two entries:
            #   1:  the original page data
            #   2:  the latest annotation data
            for i in range(num_mod_ids):
                # Create an annotation entry dict for this annotation:
                annotation_entry = dict()
                for j, col in enumerate(File.annotation_level_columns):
                    if col == 'last_modified_by_name' and len(row[col].split('¶')) < num_mod_ids:
                        # TODO kludge. I think I forgot to initialize last_modified_by_name to "None".
                        row[col] = 'None¶' + row[col]
                    elif (col == 'last_modified_by' or col == 'has_article_highlights')  and len(row[col].split('¶')) < num_mod_ids:
                        # Also a kludge
                        row[col] = '0¶' + row[col]

                    try:
                        annotation_entry[col] = row[col].split('¶')[i]
                    except IndexError:
                        ic(num_mod_ids)
                        ic(i)
                        ic(j, col)
                        ic(row[col])
                        ic(row[col].split('¶'))
                        ic(row)
                        import IPython; IPython.embed()
                    except KeyError:
                        annotation_entry[col] = None # TODO might need to change based on column type...
                #annotation_entry = {col: row[j].split('¶')[i] for j, col in enumerate(File.annotation_level_columns)}

                # Store it as separate variable if this annotation will be a top-level row in the
                # DataTable:
                if annotation_entry['mod_id'] == '0':
                    original_page_annotation_entry = annotation_entry
                else:
                    annotation_entries.append(annotation_entry)
                    if (latest_annotation_entry is None or
                            int(annotation_entry['mod_id']) > int(latest_annotation_entry['mod_id'])):
                        latest_annotation_entry = annotation_entry

        # For table_rows_originals, we extract the annotation_entry for mod_id 0 and make it a
        # top-level field of the dict.
        original_page_row = page_level_data.copy()
        original_page_row.update(original_page_annotation_entry)
        original_page_row['annotation_entries'] = annotation_entries
        table_rows_originals.append(original_page_row)

        # For table_rows_latest_annotations, we extract the annotation_entry for the latest mod_id
        # and make it a top-level field of the dict.  We also remove that annotation_entry from the
        # annotation_entries list.
        if latest_annotation_entry is not None:
            latest_annotation_row = page_level_data.copy()
            latest_annotation_row.update(latest_annotation_entry)
            # NOTE TODO should probably make annotation_entries a dict so we don't have to iterate
            # here:
            annotation_entries_without_latest = [e for e in annotation_entries if e['mod_id'] !=
                                                 latest_annotation_entry['mod_id']]
            latest_annotation_row['annotation_entries'] = annotation_entries_without_latest
            table_rows_latest_annotations.append(latest_annotation_row)

    ic(len(table_rows_originals))
    ic(len(table_rows_latest_annotations))
    all_row_entries = table_rows_originals + table_rows_latest_annotations

    # Last, iterate through all row entries to add the locked field:
    locked_page_ids = Session.query.with_entities(Session.file_id).all()
    locked_page_ids = [p[0] for p in locked_page_ids]
    for entry in all_row_entries:
        try:
            if entry['file_id'] in locked_page_ids:
                entry['locked'] = True
            else:
                entry['locked'] = False
        except KeyError as e:
            ic(entry)
            raise e

        for annotation_entry in entry['annotation_entries']:
            if annotation_entry['file_id'] in locked_page_ids:
                annotation_entry['locked'] = True
            else:
                annotation_entry['locked'] = False

    print(f'Num pages in database: {len(all_row_entries)}')

    return jsonify(data=all_row_entries)


@app.route('/')
@login_required
def index():
    #new_stuff = get_file_browser_table_data_grouped()

    initial_update_time=datetime.now(timezone.utc).isoformat()

    session_user = current_user.as_dict()
    ic(session_user)

    # Get all summary stats for the dashboard:
    query = File.query.all()
    pages = [row.get_page_data() for row in query]
    num_pages_annotated = summary_stats_total_pages_annotated(pages)
    num_annotations_per_user, num_unique_pages_annotated_per_user, users_dict = summary_stats_num_annotations_per_user() # dict, dict
    num_pages_going_to_the_dataset = summary_stats_num_pages_going_to_the_dataset()

    ic(num_pages_annotated)
    ic(num_annotations_per_user)
    ic(num_unique_pages_annotated_per_user)
    ic(num_pages_going_to_the_dataset)

    original_page_rows = [page for page in pages if page['mod_id'] == 0] 
    num_original_pages = len(original_page_rows)
    annotation_progress = round(num_pages_annotated / num_original_pages * 100, 1)

    ic(len(pages))

    return render_template('file_browser.html', title='HCIJ Article Extractor', pages=pages,
                           #locked_page_ids = locked_page_ids, # TODO can remove once done w ajax refactor
                           initial_update_time=initial_update_time, 
                           num_pages_annotated = num_pages_annotated, 
                           num_original_pages = num_original_pages, 
                           annotation_progress = annotation_progress, 
                           users_dict = users_dict, 
                           session_user = session_user,
                           num_annotations_per_user = num_annotations_per_user,
                           num_unique_pages_annotated_per_user = num_unique_pages_annotated_per_user,
                           num_pages_going_to_the_dataset = num_pages_going_to_the_dataset,
                           # Used to dynamically create the child table in the file_table dropdowns:
                           page_level_columns = File.page_level_columns,
                           annotation_level_columns = File.annotation_level_columns)

def generate_upload_signed_url_v4(blob_name, bucket_name='phase-2-website-data'):
    """Generates a v4 signed URL for uploading a blob using HTTP PUT.

    Note that this method requires a service account key file. You can not use
    this if you are using Application Default Credentials from Google Compute
    Engine or from the Google Cloud SDK.

    source: https://cloud.google.com/functions/docs/writing/http#writing_http_signed-python
    """
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    url = blob.generate_signed_url(
        version="v4",
        # This URL is valid for 15 minutes
        expiration=timedelta(minutes=15),
        # Allow PUT requests using this URL.
        method="GET"
    )

    return url

# handler for Google Cloud health check.  Returns HTTP 200 if the server is up.
@app.route('/_ah/health')
def health_check():
    return 'ok', 200

@app.route('/pages/<file_id>/<batch>/<sn>/<year>/<month>/<day>/<ed>/<seq>/<mod_id>')
def annotation_page(file_id, batch, sn, year, month, day, ed, seq, mod_id):
    ## First, check if the session has a valid user_id:
    #ic(request)
    #ic(request.__dict__)
    #session = Session.query.filter_by(id=request.sid).first()
    #if session is None or session.user_id is None:
    #    template = render_template('error.html', error_message='You need to log in to access this page.')
    #if session.user_id == 0:
    #    template = render_template('error.html', error_message=f'Invalid user id {session.user_id}.')

    filepath = f'{batch}/{sn}/{year}/{month}/{day}/{ed}/{seq}'

    # Get page details:
    page_details = File.query.filter_by(
        file_id=file_id).first().get_page_data()

    ## Get the user name based on the user id, and add it to the page details:
    #if page_details['last_modified_by'] == 0:
    #    page_details['user_name'] = 'null'
    #else:
    #    page_details['user_name'] = User.query.filter_by(
    #        id=page_details['last_modified_by']).first().name

    # Get the layout boxes for this page:
    box_rows = LayoutBox.query.filter_by(file_id=file_id).all()

    page_width = float(page_details['page_width'])
    layout_dicts = []
    for row in box_rows:
        # Get highest-priority of keywords in this line 
        overlay = {
            'article_id': row.article_id,
            'ID': row.ID,
            'HEIGHT': float(row.HEIGHT)/page_width,
            'WIDTH': float(row.WIDTH)/page_width,
            'HPOS': float(row.HPOS)/page_width,
            'VPOS' : float(row.VPOS)/page_width,
            'KEYWORD_STATS': None
        }

        if row.element == 'TextBlock':
            overlay['element'] = 'highlight'
        elif row.element == 'selected_block':
            overlay['element'] = 'highlightactivated'
        elif row.element == 'KeyLine':
            overlay['element'] = 'kw_highlight'

            try:
                kw_stats = ast.literal_eval(row.KEYWORD_STATS) 
                overlay['KEYWORD_STATS'] = kw_stats

                # Determine highest priority keyword in this line:
                highest_priority = float('inf') # lower value = higher priority. a la DEFCON
                for num_occurrences, priority in kw_stats.values():
                    if priority < highest_priority:
                        highest_priority = priority
                overlay['element'] += f' priority{highest_priority}'
            except Exception as e:
                ic(e)
                ic(row.KEYWORD_STATS)
                overlay['KEYWORD_STATS'] = None

        else:
            raise Error(f"Unknown layout box type: {d['element']}")

        layout_dicts.append(overlay)


    # Get the image url and dimensions for this page:
    img_width, img_height = page_details['img_width'], page_details['img_height']
    ic(img_width, img_height)

    if img_width is None or img_height is None:
        print(f'Missing image dimensions for file id {file_id}')
        ic(page_details)
        raise Exception(f'Missing image dimensions for file id {file_id}')
    
    if img_width == 0 or img_height == 0:
        img_filepath = f'/static/data/{filepath}/scan.jpg'
        #placeholder_img_filepath = f'/static/data/{filepath}/scan_placeholder.jpg'
        im = Image.open('.' + img_filepath)
        img_width, img_height = im.size

    gcloud_url = generate_upload_signed_url_v4(f'data/{filepath}/scan.jpg')
    gcloud_placeholder_url = generate_upload_signed_url_v4(f'data/{filepath}/scan_thumb.jpg')
    ic(gcloud_url)

    # TODO standardize field names between File model and page_details convention...
    page_details['ed'] = page_details['edition']
    page_details['seq'] = page_details['page']

    return render_template('annotation_page.html', title='Annotation', overlay_boxes=layout_dicts,
                           img_url=gcloud_url, placeholder_img_url=gcloud_placeholder_url, img_width=img_width, img_height=img_height, page_details=page_details)

# Actually Start the App
if __name__ == '__main__':
    """ Run the app. """
    #socketio.run(app, port=62222, debug=False)
    socketio.run(app, host='0.0.0.0', port=8080, debug=False)

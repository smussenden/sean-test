from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# A model for users
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=False, nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.Text, nullable=False)
    ## TODO include email field?
    # email = db.Column(db.String(120), unique=True, nullable=False)

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "username": self.username,
            "password": self.password,
        }
    def is_authenticated(self):
        return True
    def is_active(self):
        return True
    def is_anonymous(self):
        return False
    def get_id(self):
        return str(self.id)

    def as_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'username': self.username,
        }

    def __str__(self):
        rstr = f'User {self.name} with id {self.id}.'
        return rstr

class Session(db.Model):
    ''' Client sessions including which file they have opened.'''
    id = db.Column('session_id', db.Text, primary_key = True)
    file_id = db.Column('file_id', db.BigInteger, db.ForeignKey('file.file_id'))
    is_original_page = db.Column('is_original_page', db.Boolean, default = True)
    session_start_time = db.Column(db.DateTime)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class LastBackup(db.Model):
    ''' Should only ever have one row. '''
    filepath = db.Column('filepath', db.Text, primary_key = True)
    modifications_since = db.Column('modifications_since', db.Integer)

    def __str__(self):
        rstr = 'LAST BACKUP:\n'
        rstr += f'\tlocation: {self.filepath}\n'
        rstr += f'\tmodifications since: {self.modifications_since}'
        return rstr


class LayoutBox(db.Model):
    element = db.Column('element', db.Text)
    article_id = db.Column('article_id', db.Integer)
    ID = db.Column('ID', db.Text, primary_key=True)
    HEIGHT = db.Column('HEIGHT', db.Text)
    WIDTH = db.Column('WIDTH', db.Text)
    HPOS = db.Column('HPOS', db.Text)
    VPOS = db.Column('VPOS', db.Text)
    KEYWORD_STATS = db.Column('KEYWORD_STATS', db.Text)
    file_id = db.Column('file_id', db.BigInteger, db.ForeignKey('file.file_id'), primary_key = True)

class File(db.Model):
    # List of names of columns which are properties of the page, and are not changed by the user:
    page_level_columns = [
        'filepath',
        'newspaper_name',
        'page_width',
        'batch',
        'sn',
        'date',
        'year',
        'month',
        'day',
        'edition',
        'page',
        'img_height',
        'img_width'
    ]
    # List of names of columns which may be changed when user annotates a page:
    annotation_level_columns = [
        'file_id', 
        'mod_id',
        'deleted',
        'num_annotations',
        'last_modified',
        'last_modified_by',
        'last_modified_by_name',
        'notes',
        'flag_irrelevant',
        'flag_other',
        'flag_bad_layout',
        'has_article_highlights',
    ]

    file_id = db.Column('file_id', db.BigInteger, primary_key=True)
    filepath = db.Column('filepath', db.Text)
    newspaper_name = db.Column('newspaper_name', db.Text)
    page_width = db.Column('page_width', db.Float)
    batch = db.Column('batch', db.Text)
    sn = db.Column('sn', db.Text)
    date = db.Column('date', db.Text)
    year = db.Column('year', db.Text)
    month = db.Column('month', db.Text)
    day = db.Column('day', db.Text)
    edition = db.Column('edition', db.Text)
    page = db.Column('page', db.Text)
    mod_id = db.Column('mod_id', db.BigInteger)
    deleted = db.Column('deleted', db.Boolean)
    num_annotations = db.Column('num_annotations', db.Integer) # number of saved annotations for this page.
    last_modified = db.Column('last_modified', db.DateTime) # number of saved annotations for this page.

    last_modified_by = db.Column('last_modified_by', db.Integer, db.ForeignKey('user.id'))
    last_modified_by_name = db.Column('last_modified_by_name', db.Text)

    notes = db.Column('notes', db.Text)
    flag_irrelevant = db.Column('flag_irrelevant', db.Boolean)
    flag_other = db.Column('flag_other', db.Boolean)
    flag_bad_layout = db.Column('flag_bad_layout', db.Boolean)

    has_article_highlights = db.Column('has_article_highlights', db.Boolean)

    img_height = db.Column('img_height', db.Integer)
    img_width = db.Column('img_width', db.Integer)

    layout_boxes = db.relationship('LayoutBox', backref='file', lazy=True)
    session = db.relationship('Session', backref='file', lazy=True)

    def get_page_data(self):
        d = {
            'file_id' : self.file_id,
            'filepath' : self.filepath,
            'newspaper_name' : self.newspaper_name,
            'page_width' : self.page_width,
            'batch' : self.batch,
            'sn' : self.sn,
            'date' : self.date,
            'year' : self.year,
            'month' : self.month,
            'day' : self.day,
            'edition' : self.edition,
            'page' : self.page,
            'mod_id' : self.mod_id,
            'deleted' : self.deleted,
            'num_annotations' : self.num_annotations,
            'last_modified' : self.last_modified,
            'last_modified_by' : self.last_modified_by,
            'last_modified_by_name' : self.last_modified_by_name,
            'notes' : self.notes,
            'flag_irrelevant' : self.flag_irrelevant,
            'flag_other' : self.flag_other,
            'flag_bad_layout' : self.flag_bad_layout,

            'has_article_highlights' : self.has_article_highlights,
            'img_height' : self.img_height,
            'img_width' : self.img_width,
        }
        return d

    def __str__(self):
        retstr = 'layout_originals row:'
        retstr += f'\n\tfile_id: {self.file_id}'
        retstr += f'\n\tfilepath: {self.filepath}'
        retstr += f'\n\tnewspaper_name: {self.newspaper_name}'
        retstr += f'\n\tpage_width: {self.page_width}'
        retstr += f'\n\tbatch: {self.batch}'
        retstr += f'\n\tsn: {self.sn}'
        retstr += f'\n\tdate: {self.date}'
        retstr += f'\n\tyear: {self.year}'
        retstr += f'\n\tmonth: {self.month}'
        retstr += f'\n\tday: {self.day}'
        retstr += f'\n\tedition: {self.edition}'
        retstr += f'\n\tpage: {self.page}'
        retstr += f'\n\tmod_id: {self.mod_id}'
        retstr += f'\n\tdeleted: {self.deleted}'
        retstr += f'\n\tnum_annotations: {self.num_annotations}'
        retstr += f'\n\tlast_modified: {self.last_modified}'
        retstr += f'\n\tlast_modified_by: {self.last_modified_by}'
        retstr += f'\n\tlast_modified_by_name: {self.last_modified_by_name}'
        retstr += f'\n\tnotes: {self.notes}'
        retstr += f'\n\tflag_irrelevant: {self.flag_irrelevant}'
        retstr += f'\n\tflag_other: {self.flag_other}'
        retstr += f'\n\tflag_bad_layout: {self.flag_bad_layout}'
        retstr += f'\n\thas_article_highlights: {self.has_article_highlights}'
        return retstr


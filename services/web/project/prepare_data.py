# Prepare the data and databases needed for the webapp.
# This includes:
#   - Converting PNGs to JPEGs with opj_decompress.
#   - Gathering all of the ALTO files and JPEGs under the data/ directory.
#   - Parsing all ALTO files to create a database of textboxes and keylines.

from pathlib import Path
from multiprocessing import Pool, cpu_count
import sys
import os
import subprocess
import re
import argparse
import wget
import shutil
import logging

from datetime import datetime, timezone

from tqdm import tqdm
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from PIL import Image
Image.MAX_IMAGE_PIXELS = None # else some pages wont open

tqdm.pandas()

from icecream import ic


def parse_alto(alto_fp, element_names=['TextBlock', 'KeyLine'],
               target_attrs=['ID', 'HEIGHT', 'WIDTH',
                             'HPOS', 'VPOS', 'KEYWORD_STATS']
               ):
    '''
    Convert ALTO into a dataframe of textbox metadata.

    params:
        alto_fp: the filepath of the alto file.
        target_attrs: the attributes to extract from the target elements.

    returns:  DataFrame
    '''
    with open(alto_fp, 'r') as f:
        alto_txt = f.read()

    # First get the page width.  (Needed for proper scaling in OpenSeaDragon)

    page_width = None
    pattern = re.compile(r'<%s[^>]*>' % 'Page')
    for txt in pattern.finditer(alto_txt):
        matchtxt = txt.string[txt.start():txt.end()]

        pat = re.compile(r' %s=\"([^\"]*)\"' % 'WIDTH')
        attr_match = pat.search(matchtxt)
        page_width = float(attr_match.groups()[0])

    alto_df = None
    for element_name in element_names:
        #pattern = re.compile(r'<[c|d][^>]*>(?P<text>[^<]*)</[c|d]>')
        pattern = re.compile(r'<%s[^>]*>' % element_name)
        #pattern = re.compile(r'<%s[^>]*>' % pat)
        attr_dicts = []
        for txt in pattern.finditer(alto_txt):
            matchtxt = txt.string[txt.start():txt.end()]

            attr_dict = {'filepath': alto_fp,
                         'element': element_name, 'page_width': page_width}
            for attr_name in target_attrs:
                pat = re.compile(r' %s=\"([^\"]*)\"' % attr_name)
                attr_match = pat.search(matchtxt)
                if attr_match is None:
                    attr_dict[attr_name] = None
                else:
                    attr_dict[attr_name] = attr_match.groups()[0]
            attr_dicts.append(attr_dict)

        df_for_this_element = pd.DataFrame(attr_dicts)
        if alto_df is None:
            alto_df = df_for_this_element
        else:
            alto_df = pd.concat([alto_df, df_for_this_element], join='outer')
            # <TextBlock ID="TB_l2588t17394r2924b17462" HEIGHT="40" WIDTH="136" HPOS="1048" VPOS="10144" type="simple" language="en" />

            # <KeyLine HEIGHT="156.0" WIDTH="3428.0" HPOS="15435.0" VPOS="23219.0" KEYWORD_STATS="{4: 1}" ID="KL_0">

    return alto_df


def standardize_dataset_fp(filepath):
    # Remove everything in the filepath until the batch name.
    # What remains is a consistent UID for the given file.
    filepath = Path(filepath)
    sn_idx = 0
    parts = filepath.parts

    pat = r'^(?:sn)?\d{8,10}$'
    for part in parts:
        if re.match(pat, part):
            break
        else:
            sn_idx += 1

    # Sometimes ends in filename, sometimes its containing directory.
    page_idx = len(parts) - 1
    if parts[page_idx][0:4] != 'seq-':
        page_idx -= 1

    # (batch name precedes the sn number)
    fp_old = filepath
    filepath = Path('/'.join(parts[sn_idx - 1:page_idx + 1]))

    return filepath

def shorten_newspaper_names(file_table):
    ########## Reformat newspaper_name column ##########
    # Want to make the newspaper names cleaner.
    # e.g.,The Brookhaven leader (Brookhaven, Miss.) 1883-1891 -> The Brookhaven Leader
    # BUT don't want to create ambiguous names.  So check for collisions after the change, and revert if necessary.
    
    # First, remove [volume] and similar, leaving the name, location, and years of existence.
    pat = r'([^\[]*)\.\s*\[.*\] (.+)'
    name_components = file_table.newspaper_name.str.extract(pat)
    file_table['newspaper_name'] = name_components[0] + ' ' + name_components[1]

    def clean_name(row):
        name = row['newspaper_name']
        # None or nan
        if name is None or name != name:
            row['name_without_date_range'] = None
            row['name_shortened'] = None
            return row

        # re for date ranges of form 1883-1891 and 18??-1???, 1920-current etc.  i.e. can have digit or question mark
        date_range_re = re.compile(r'(?:\d|\?){4}-(?:(?:\d|\?){4}|current)')
        # remove date ranges
        try:
            name = date_range_re.sub('', name)
        except Exception as e:
            print(f'Error removing date range from {name}')
            print(e)
            import ipdb; ipdb.set_trace()
        row['name_without_date_range'] = name
        # Check for place of publication in parentheses.  If longer than 15 characters, abbreviate.
        place_of_pub_re = re.compile(r'\(([^)]+)\)')
        match = place_of_pub_re.search(name)
        if match:
            place_of_pub = match.group(1)
            if len(place_of_pub) > 15:
                place_of_pub = f'({place_of_pub[:15]}...)'
                name = place_of_pub_re.sub(place_of_pub, name)
        name = name.strip()
        row['name_shortened'] = name
        return row
    file_table = file_table.apply(clean_name, axis=1)

    # Check for collisions.  Same name_shortened with differen LCCN
    for name, rows in file_table.groupby('name_shortened'):
        if name is None: continue
        if len(rows.sn.unique()) > 1:
            # First, try reverting to name_without_date_range.
            # If that doesn't work, revert to original name.
            rows['name_shortened'] = rows['name_without_date_range']
            # Check again
            for subname, subrows in rows.groupby('name_shortened'):
                if len(subrows.sn.unique()) > 1:
                    rows['name_shortened'] = rows['newspaper_name']
        file_table.loc[rows.index, 'name_shortened'] = rows['name_shortened']

    # Apply changes to newspaper_name and drop name_shortened column
    file_table.loc[:, 'newspaper_name'] = file_table['name_shortened']
    file_table.drop('name_shortened', axis=1, inplace=True)
    # Fix the datatypes that were changed somehow:
    try:
        file_table.file_id = file_table.file_id.astype(int)
    except Exception as e:
        # Get any NaNs in that column
        print(file_table[file_table.file_id.isnull()])
        import ipdb; ipdb.set_trace()
    file_table.mod_id = file_table.mod_id.astype(int)
    file_table.deleted = file_table.deleted.astype(int)
    file_table.num_annotations = file_table.num_annotations.astype(int)
    file_table.flag_bad_layout = file_table.flag_bad_layout.astype(int)
    file_table.flag_irrelevant = file_table.flag_irrelevant.astype(int)
    file_table.flag_other = file_table.flag_other.astype(int)

    return file_table


def main(args):
    # Argparse, including flags for create_jpeg, create_low_rez, and parse_alto
    parser = argparse.ArgumentParser(description='Prepare data for the webapp.')
    parser.add_argument('--create_jpeg', action='store_true', 
                        help='Create JPEGs from JP2s. Required for rendering in the webapp.')
    parser.add_argument('--create_low_rez', action='store_true',
                        help='Create low-resolution page scan placeholders from the page scan JPEGs.')
    parser.add_argument('--parse_alto', action='store_true',
                        help='Parse ALTO files to create a SQL database of textboxes and keylines.')
    parser.add_argument('--local_images_base_dir', type=Path, 
                        help='The base directory for local images.')
    parser.add_argument('--local_alto_base_dir', type=Path,
                        help='The base directory for local ALTO files.')
    parser.add_argument('--target_file_manifest', type=Path, 
                        help='CSV file containing a list of files to process. (if not provided, will search for them in image_base_dir')
    parser.add_argument('--NUM_PROC', type=int, default=-1,
                        help='The number of processes to use for multiprocessing. If unspecified, use all of them.')
    parser.add_argument('--alto_file_suffix', type=str, default='_annotated.xml',
                        help=f'The suffix of the local ALTO files. By default, this is "_annotated.xml"')
    parser.add_argument('--logs_dir', type=Path, default=Path('logs'),
                        help='The directory to store logs in.')

    args, unknown = parser.parse_known_args()

    if len(unknown) > 0:
        parser.error(f'Unknown arguments: {unknown}')

    if not (args.create_jpeg or args.create_low_rez or args.parse_alto):
        parser.error('Must specify at least one of --create_jpeg, --create_low_rez, or --parse_alto.')

    # Validate args
    if (args.create_jpeg or args.create_low_rez):
        if args.local_images_base_dir is None:
            parser.error('--local_images_base_dir is required when creating or modifying page scan JPEGs.')
        else: 
            assert args.local_images_base_dir.exists(), f'{args.local_images_base_dir} does not exist.'

    if args.parse_alto:
        if args.local_alto_base_dir is None:
            parser.error('--local_alto_base_dir is required when parsing ALTO files.')
        else:
            assert args.local_alto_base_dir.exists(), f'{args.local_alto_base_dir} does not exist.'

    # Must end in xml
    assert args.alto_file_suffix[-4:] == '.xml', f'ALTO file suffix must end in .xml (provided: {args.alto_file_suffix})'
    
    if args.target_file_manifest:
        if not args.target_file_manifest.suffix == '.csv':
            parser.error('target_file_manifest must be a CSV file.')
        assert args.target_file_manifest.exists(), f'{args.target_file_manifest} does not exist.'

    # Set nproc to the max num threads, if not specified OR if specified value is greater than the
    # actual maximum.
    nproc = None
    if args.NUM_PROC == -1 or args.NUM_PROC > cpu_count():
        nproc = str(cpu_count())
    else:
        nproc = str(args.NUM_PROC)

    # Flags for control flow etc.:
    CREATE_JPEGS = args.create_jpeg
    CREATE_LOW_REZ = args.create_low_rez
    PARSE_ALTO = args.parse_alto
    ALTO_SUFFIX = args.alto_file_suffix

    SRC_IMG_EXT = 'jp2'

    IMG_SRC_DIR = None
    if (CREATE_JPEGS or CREATE_LOW_REZ):
        IMG_SRC_DIR = args.local_images_base_dir
        DEST_DATA_DIR = args.local_images_base_dir
    ALTO_SRC_DIR = None
    if PARSE_ALTO:
        ALTO_SRC_DIR = args.local_alto_base_dir

    # Set up logging:
    if not args.logs_dir.exists():
        args.logs_dir.mkdir()
    log_file = args.logs_dir / f'prepare_data_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.log'
    logging.basicConfig(filename=log_file, level=logging.INFO)
    logging.info(f'Running with args: {args}')

    target_file_df = None 
    if args.target_file_manifest:
        # Read the target file manifest
        target_file_df = pd.read_csv(args.target_file_manifest)
        target_file_df.filepath = target_file_df.filepath.apply(lambda x: standardize_dataset_fp(x))

    # Find all of the imgs in the src data dir.
    # Assert that all images have matching ALTO files.
    if CREATE_JPEGS or CREATE_LOW_REZ:
        logging.info('Searching for all images...')
        all_imgs = None
        if target_file_df is not None:
            # Search for jp2 files in the parent dir of each target file:
            all_imgs = []
            print('Searching for images...')
            for idx, row in tqdm(list(target_file_df.iterrows())):
                fp = Path(IMG_SRC_DIR) / row.filepath
                #ic(fp)
                img_files = list(fp.glob(f'*.{SRC_IMG_EXT}'))
                if len(img_files) == 0:
                    tqdm.write(f'No {SRC_IMG_EXT} files found in {fp}')
                    logging.info(f'No {SRC_IMG_EXT} files found in {fp}')
                else:
                    all_imgs.append(img_files[0])
        else:
            print(f'No target file manifest provided. Searching for {SRC_IMG_EXT} files in {IMG_SRC_DIR}.')
            print('This may take a while.  If you know the files you want to process, consider providing a target file manifest.')
            all_imgs = IMG_SRC_DIR.rglob(f"*.{SRC_IMG_EXT}")

        # Make lists of files which need to be processed for each task:
        img_manifest = pd.DataFrame({'filepath': all_imgs, 'has_jpg': False, 'has_thumbnail': False})
        img_manifest.has_jpg = img_manifest.filepath.progress_apply(lambda x: x.with_suffix('.jpg').exists())
        # True if filepath dir contains a file ending in '_thumb.jpg':
        img_manifest.has_thumbnail = img_manifest.filepath.progress_apply(lambda x: len(list(x.parent.glob('*_thumb.jpg'))) > 0)
        to_convert_to_jpg = None
        to_create_thumbnail = None
        if CREATE_JPEGS:
            to_convert_to_jpg = img_manifest[~img_manifest.has_jpg]
            with open('to_convert_to_jpg.txt', 'w') as f:
                f.writelines([str(fp) + '\n' for fp in to_convert_to_jpg.filepath])
        if CREATE_LOW_REZ:
            to_create_thumbnail = img_manifest[~img_manifest.has_thumbnail]
            with open('to_create_thumbnail.txt', 'w') as f:
                f.writelines([str(fp) + '\n' for fp in to_create_thumbnail.filepath])

        if not os.path.exists(DEST_DATA_DIR):
            os.mkdir(DEST_DATA_DIR)

        ## Create JPEGs for all PNGs, in the data dir.
        ## TODO save to DEST_DATA_DIR if it's not == SRC_DATA_DIR
        #with open('./imgs_to_process.txt', 'w') as f:
        #    f.writelines([str(fp)+'\n' for fp in imgs_with_alto])
        #    print(f'Wrote manifest of {len(imgs_with_alto)} images to ./imgs_to_process.txt')

    if CREATE_JPEGS:
        print("Converting JP2's to JPEGS.  This could take a while...")
        with open('to_convert_to_jpg.txt', 'r') as f:
            img_paths = f.readlines()
            print(f'Found {len(img_paths)} images to convert to jpg.')
        cmd_to_parallelize = f'sh ./cvt_cmd.sh'
        convert_cmd = ['parallel', '-a', './to_convert_to_jpg.txt',
                       '-j', str(nproc), '--bar', cmd_to_parallelize]
        #convert_cmd = ['find', str(IMG_SRC_DIR), '-name', '*.jp2', '|', 'parallel', '-j', nproc, '--bar', cmd_to_parallelize]
        full_cmd = ' '.join(convert_cmd)

        out = subprocess.run(full_cmd, shell=True, executable='/bin/bash')

    if CREATE_LOW_REZ:
        print("Creating thumbnails and placeholder images from the scan JPEGs.")
        with open('to_create_thumbnail.txt', 'r') as f:
            img_paths = f.readlines()
            print(f'Found {len(img_paths)} images to create thumbnail for.')
        all_scans = IMG_SRC_DIR.rglob(f"*scan.jpg")
        cmd_to_parallelize = f'sh ./make_low_rez.sh'
        convert_cmd = ['parallel', '-a', './to_create_thumbnail.txt',
                       '-j', str(nproc), '--bar', cmd_to_parallelize]
        #convert_cmd = ['find', str(IMG_SRC_DIR), '-name', '*.jp2', '|', 'parallel', '-j', nproc, '--bar', cmd_to_parallelize]
        full_cmd = ' '.join(convert_cmd)

        out = subprocess.run(full_cmd, shell=True, executable='/bin/bash')

    if PARSE_ALTO:
        alto_files = None
        if target_file_df is not None:
            # Find ALTO files for each target file:
            alto_files = []
            for idx, row in tqdm(list(target_file_df.iterrows()), desc='Searching for ALTO files'):
                fp = Path(ALTO_SRC_DIR) / row.filepath
                files_found = list(fp.glob(f'*{ALTO_SUFFIX}'))
                if len(files_found) == 0:
                    tqdm.write(f'No {ALTO_SUFFIX} files found in {fp}')
                else:
                    alto_files.append(files_found[0])
        else:
            # Search file tree for ALTO files:
            print(f'No target file manifest provided. Searching for {ALTO_SUFFIX} files in {ALTO_SRC_DIR}.')
            print('This may take a while.  If you know the files you want to process, consider providing a target file manifest.')
            alto_files = ALTO_SRC_DIR.rglob(f"*.{ALTO_SUFFIX}")

        # parse all the alto files to create the database of layout boxes.
        # First, a dataframe for each ALTO file w one row per textblock/keyline/etc
        pool = Pool(os.cpu_count())
        alto_filepaths = alto_files
        #alto_filepaths = [fp.parent /
        #                  Path(fp.stem + ALTO_SUFFIX) for fp in alto_files]

        alto_dicts = list(tqdm(pool.imap_unordered(parse_alto, alto_filepaths),
                               total=len(alto_filepaths),
                               desc='Parsing ALTO files'))

        # This will be the new index:
        for i in range(len(alto_dicts)):
            alto_dicts[i]['file_id_idx'] = i
            alto_dicts[i]['file_id'] = i

        # Create SQLite db from this:
        all_files = pd.concat(alto_dicts, axis=0)
        all_files = all_files.set_index('file_id_idx')
        all_files.filepath = all_files.filepath.apply(standardize_dataset_fp)

        all_files['batch'] = all_files.filepath.apply(lambda s: s.parts[0])

        all_files['sn'] = all_files.filepath.apply(lambda s: s.parts[1])
        all_files['year'] = all_files.filepath.apply(lambda s: s.parts[2])
        all_files['month'] = all_files.filepath.apply(lambda s: s.parts[3])
        all_files['day'] = all_files.filepath.apply(lambda s: s.parts[4])
        all_files['edition'] = all_files.filepath.apply(lambda s: s.parts[5])
        all_files['page'] = all_files.filepath.apply(lambda s: s.parts[6])

        all_files.filepath = all_files.filepath.apply(str)

        # ISO date column:
        all_files['date'] = all_files.year + '-' + all_files.month + '-' + all_files.day

        # These columns are used in the webapp:
        all_files['mod_id'] = 0  # Which user annotation is this?
        all_files['article_id'] = -1  # Which article is this on a page?
        #all_files['was_modified'] = False  # Have flags / notes / annotations been added to this page?
        # Has this annotation been deleted by a user?
        all_files['deleted'] = False
        # How many user annotations have been saved for this page?
        all_files['num_annotations'] = False
        # Does this page have any user-highlighted boxes?
        all_files['has_article_highlights'] = False
        # User notes and flags for this page:
        all_files['notes'] = ''
        all_files['flag_irrelevant'] = False
        all_files['flag_other'] = False
        all_files['flag_bad_layout'] = False

        # Tracks the last time each row was modified:
        # Should always be UTC.
        all_files['last_modified'] = str(datetime.now(timezone.utc))
        all_files['last_modified_by'] = 0
        all_files['last_modified_by_name'] = 'None'

        # DB name includes timestamp to avoid overwriting:
        DB_NAME = f'LayoutBoxes_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        engine = create_engine(f'sqlite:///{DB_NAME}.db',
                               echo=False)

        # Split into LayoutBox and File tables:
        asdf = ['element', 'ID', 'HEIGHT', 'WIDTH', 'HPOS',
                                     'VPOS', 'KEYWORD_STATS', 'file_id', 'mod_id']

        layoutbox_table = all_files[['element', 'ID', 'HEIGHT', 'WIDTH', 'HPOS',
                                     'VPOS', 'KEYWORD_STATS', 'file_id', 'mod_id', 'article_id']].drop_duplicates()
        file_table = all_files[['file_id', 'filepath', 'page_width', 'batch', 'sn', 'date', 'year',
                                'month', 'day', 'edition', 'page', 'mod_id', 'deleted', 'num_annotations',
                                'last_modified',
                                'flag_irrelevant', 'flag_other', 'flag_bad_layout', 'notes']].drop_duplicates()

        # Get newspaper names based on LCCN (SN) numbers.
        newspapers_csv_path = Path('./static/newspapers.csv')
        NEWSPAPERS_CSV_URL = 'https://chroniclingamerica.loc.gov/newspapers.csv'
        if not newspapers_csv_path.exists():
            print(f'Downloading newspaper names from {NEWSPAPERS_CSV_URL}')
            newspapers_csv_path = Path(wget.download(NEWSPAPERS_CSV_URL))

        papers_df = pd.read_csv(newspapers_csv_path)
        # break the lambda below into two lines for debugging:
        try:
            file_table['newspaper_name'] = file_table.sn.apply(lambda x: list(papers_df[papers_df.LCCN == x].Title)[0])
        except IndexError:
            print(f'Could not find a newspaper name for one of the LCCNs.')
            print(f'This may be because the Chron Am newspapers CSV file is out of date.')
            print(f'Downloading the latest version of the file from {NEWSPAPERS_CSV_URL}:')
            new_manifest_path = Path(wget.download(NEWSPAPERS_CSV_URL))
            # Mv to ./static/
            shutil.move(new_manifest_path, newspapers_csv_path)
            print('\nTrying again with new newspaper manifest:')
            papers_df = pd.read_csv(newspapers_csv_path)
            #file_table['newspaper_name'] = file_table.sn.apply(lambda x: list(papers_df[papers_df.LCCN == x].Title)[0])
            def get_newspaper_name(row):
                try:
                    name_matches = list(papers_df[papers_df.LCCN == row.sn].Title)[0]
                    import ipdb; ipdb.set_trace()
                    return name_matches
                except IndexError:
                    tqdm.write(f'Could not find a newspaper name for LCCN {row.sn}')
                    return 'Unknown'
            file_table['newspaper_name'] = file_table.progress_apply(get_newspaper_name, axis=1)

        # Add page dimensions 'img_height' and 'img_width' to file table:
        print('Adding page image dimensions to database.')

        def add_page_dimensions_to_row(row):
            # Get page dimensions from image file:
            im_fp = args.local_images_base_dir / row.filepath / 'scan.jpg'
            tqdm.write(str(im_fp))
            tqdm.write(str(row.filepath))
            try:
                img = Image.open(im_fp)
                row['img_height'] = img.height
                row['img_width'] = img.width
            except Exception as e:
                tqdm.write(f'Could not open image file {im_fp}')
                tqdm.write(f'Error: {e}')
                row['img_height'] = np.nan
                row['img_width'] = np.nan
            return row
        file_table = file_table.progress_apply(add_page_dimensions_to_row, axis=1)
        # For some reason sometimes the page dimensions fail to load for one or more mod_id's of the same page.
        # See if we can fill in these missing values by checking the OTHER mod_ids for that page.
        
        # First, identify tows in file_table with missing page dimensions:
        missing_dims = file_table[(file_table.img_height.isna()) | (file_table.img_width.isna())]
        # Get all file_table entries with filepaths appearing in missing_dims:
        # use filepath isin(missing_dims.filepath.unique())
        missing_dims_all_mods = file_table[file_table.filepath.isin(missing_dims.filepath.unique())]
        # Group by filepath and check if any of the mod_ids have page dimensions:
        missing_dims_grouped = missing_dims_all_mods.groupby('filepath')
        for filepath, group in tqdm(missing_dims_grouped):
            print(group)
            # Get the first row with page dimensions:
            rows_with_dims = group[~group.img_height.isna()]
            if len(rows_with_dims) == 0:
                continue
            dims_row = rows_with_dims.iloc[0]
            # Fill in the missing dimensions for all rows with the same filepath:
            file_table.loc[file_table.filepath == filepath, 'img_height'] = dims_row.img_height
            file_table.loc[file_table.filepath == filepath, 'img_width'] = dims_row.img_width
            print('After fix')
            print(file_table.loc[file_table.filepath == filepath])
        print('Finished trying to fix missing page dimensions.')

        # If there are still pages with missing dimensions, drop those rows:
        # Log which rows those are
        still_missing_rows = file_table[file_table.img_height.isna() | file_table.img_width.isna()]
        if len(still_missing_rows) > 0:
            print(f'{len(still_missing_rows)} pages still missing image dimensions.  Dropping those rows from the database.')
            logging.warning(f'Could not find page dimensions for {len(still_missing_rows)} pages.')
            for missing_dims_filepath in still_missing_rows.filepath.unique():
                logging.warning(f'Dropping due to missing img dims: {missing_dims_filepath}')
            file_table = file_table.drop(still_missing_rows.index)

        file_table = shorten_newspaper_names(file_table)

        layoutbox_table.to_sql('layout_box', con=engine)
        file_table.to_sql('file', con=engine)

        # Lastly, create the DB backup tracking table:
        last_backup = pd.DataFrame.from_dict(
            {'filepath' : [''], 'modifications_since' : [0]}
        )
        last_backup.to_sql('last_backup', con=engine)
        print(f'Done.  Saved to {DB_NAME}.db')


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

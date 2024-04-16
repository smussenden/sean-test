from icecream import ic
import ipdb

# Find keywords in ALTO file, and add an attribute identifying the elements containing those
# keywords.
#

import ast
import os
import csv
import logging
import re
import sys
import argparse

from datetime import datetime, timezone
from string import punctuation
from pathlib import Path
from functools import partial
from multiprocessing import Pool
import xml.etree.ElementTree as ET

import pandas as pd
from tqdm import tqdm

def find_keylines(whole_file, file_lines, word_idxs, match_data, keyword_priority, debug_filepath=None):
    ''' Identify lines containing keywords, given the position of each keyword in the file.

    params:
        whole_file: txt file not split into lines.
        file_lines:  the raw lines of the txt file.
        word_idxs:  for each keyword occurrence, the tuple (start_idx, end_idx) character indices.
        match_data: (tuple) the details of each kw_match: (start_idx, end_idx, txt, kw_id)
        keyword_priority: dict mapping keyword id to its priority number.
        debug_filepath: fpath of the file.  TODO DEBUG.

    returns:  tuple text_block_ranges, lines_colored
        keyline_idxs: list of indices of keyword-containing line in the file.
        keyline_stats: the keyword ids and number of occurrences in each keyword-containing line.
    '''
    keyline_numbers = []  # list of indices of lines containing keywords
    keyline_stats = []  # list of indices of lines containing keywords
    # next_keyword_location = word_idxs[next_keyword_idx]  # + 3

    next_keyword_idx = 0  # idx in word_idxs
    line_start_idx = 0  # character index current line's start
    line_end_idx = None

    for line_idx in range(len(file_lines)):
        line_end_idx = line_start_idx + len(file_lines[line_idx])

        line = file_lines[line_idx].strip()

        # Color all the words in this line:
        line_parts = []
        keyword_occurrences = {}

        contains_keyword = False
        while next_keyword_idx < len(word_idxs):
            kw_start, kw_end = word_idxs[next_keyword_idx]
            kw_start, kw_end, txt, kw_id = match_data[next_keyword_idx]

            if kw_end < line_end_idx:
                contains_keyword = True

                # Update keyword occurrence stats for this line:
                try:
                    keyword_occurrences[kw_id] = keyword_occurrences[kw_id] + 1
                except KeyError:
                    keyword_occurrences[kw_id] = 1

                # Advance to next keyword.
                next_keyword_idx += 1
            else:
                if kw_start >= line_start_idx and kw_start < line_end_idx:
                    # EDGE CASE:  kw is split over two lines (e.g. for victim first and last name).
                    # TODO HANDLE THIS EDGE CASE PROPERLY.  Fixed in manual_review_tool.py
                    next_keyword_idx += 1
                break

        if contains_keyword:
            keyline_numbers.append(line_idx)
            keyline_stats.append(keyword_occurrences)

        line_start_idx += len(file_lines[line_idx])

    for stats_dict in keyline_stats:
        for kw_id, num_occ in stats_dict.items():
            priority = None
            if kw_id == -1:
                priority = 3  # TODO add to keywords.csv? Would need to ignore in other contexts.
            else:
                priority = keyword_priority[kw_id]

            stats_dict[kw_id] = (num_occ, priority)

    return keyline_numbers, keyline_stats


def reconstruct_ocr_text_from_line(textline):
    # Extract the content (words) of a textline as a single string.
    # used for debugging.
    ns = {'ns': 'http://www.loc.gov/standards/alto/ns-v2#'}
    strings = textline.findall('ns:String', ns)
    line_str = ''
    for s in strings:
        content = s.attrib['CONTENT']
        line_str += ' ' + content
    line_str += '\n'
    return line_str


def tag_key_elements(alto_tree, keyline_idxs, keyline_stats, debug_stuff=None, debug_file_lines=None):
    # Traverse the tree, counting the number of TextLine elements.
    # If count = next keyline, then add the relevant attribute(s) to the TextLine.
    # TODO rm debug_file_lines when done debugging
    root = alto_tree.getroot()
    ns = {'ns': '{*}'}
    layout = root.findall('{*}Layout')
    page = layout[0][0]
    printspace_search = page.findall('{*}PrintSpace')
    printspace = printspace_search[0] if len(printspace_search) > 0 else None
    #for el in page:
    #    ic(el, el.tag)
    #    if el.tag == 'PrintSpace':
    #        printspace = el
    #        break

    if printspace is None:
        print(f'Did not find tag PrintSpace where we expected.\nTree structure:')
        if debug_stuff is not None:
            for child in root: 
                print(child)
                for chil in child: 
                    print('\t' + str(chil))
                    for chi in chil: 
                        print('\t\t' + str(chi))
                        for ch in chi:
                            print('\t\t' + str(chi))
        raise Exception()
        #print(etree.tostring(t, encoding='unicode',pretty_print=True))

    #txtblocks = list(printspace)

    all_line_strings = []

    keylines_iter = iter(zip(keyline_idxs, keyline_stats))
    # TODO NEXT THIS IS THE ERROR LINE
    try:
        next_keyline, next_keyline_stats = keylines_iter.__next__()
        textline_counter = -1
        num_keylines_created = 0
        for blk in printspace:
            lines = blk.findall('{*}TextLine', ns)
            for line in lines:
                textline_counter += 1
                if textline_counter == next_keyline:
                    # Add a container element <KeyLine> for this line's children:
                    line = insert_keyline_element(line, next_keyline_stats, num_keylines_created)
                    num_keylines_created += 1

                    #print(f'Added annotation for line {next_keyline}:')
                    #print(f'Expecting line: "{debug_file_lines[next_keyline]}"')
                    #print(f'Got line: "{reconstruct_ocr_text_from_line(line)}"')
                    #ic(reconstruct_ocr_text_from_line(line))

                    next_keyline, next_keyline_stats  = keylines_iter.__next__()
    except StopIteration:
        pass

    return alto_tree

def insert_keyline_element(line, keyword_stats, line_id):
    '''
    Create a KeyLine element, and insert it as the child of line, and the parent of line's children.
    '''
    n_children = len(line)
    # In a previous run I added KeyLines but didn't make the necessary attr updates:
    keyline = line[0] if (n_children == 1 and 'KeyLine' in str(line[0])) else ET.Element('KeyLine')
    keyline.attrib = line.attrib.copy()
    keyline.attrib['ID'] = f'KL_{line_id}'
    keyline.attrib['KEYWORD_STATS'] = str(keyword_stats)

    if n_children > 1:
        for child in list(line):
            keyline.append(child)
            line.remove(child)
        line.insert(0, keyline)
        assert len(line) == 1
        assert len(keyline) == n_children
    return line


def annotate_alto(fulltxt, file_lines, occurrences, alto_tree, keyword_priority):
    '''  Do the annotation

    args:
        file_lines: TODO
        occurrences: string with kw occurrences. TODO cp format description from
                    ./search_for_keywords.py
            EXAMPLE:
                6898-6903:Black:1,13393-13405:Fred Johnson:-1,14439-14444:Black:1,18385-18392:charged:20,18397-18403:charge:20
        alto_tree:  etree of the alto file to be annotated.
        debug_filepath: TODO

    '''
    # TODO TODO TODO should do a sanity check: asserting ocr.txt line order matches reconstructed
    # ALTO?  See script in quack/useful_example_data/ for implementation.

    # Parse occurrences string to get word locations.
    occ = [s.strip() for s in occurrences.split(',')]

    occurrences_parsed = []
    # NOTE Filter out some keywords
    # TODO automate lookup of keywords so this isn't hard coded.
    keywords_to_exclude = [
        1, # black
        8, # indian
        10, # white
        20 # charge
    ]
    for occ_str in occ:
        try:
            idx_range, match_txt, kw_id = occ_str.split(':')

            kw_id = int(kw_id)
            if kw_id in keywords_to_exclude:
                continue

            start_idx, end_idx = idx_range.split('-')
            start_idx, end_idx = int(start_idx), int(end_idx)

            occurrences_parsed.append((start_idx, end_idx, match_txt, kw_id))
        except ValueError as e:
            tqdm.write(f'Error parsing occurrence string: {occ_str}')

    word_idxs = []
    for start_idx, end_idx, _, _ in occurrences_parsed:
        word_idxs.append((start_idx, end_idx))

    keyline_idxs, keyline_stats = \
        find_keylines(fulltxt, file_lines, word_idxs,
                      occurrences_parsed, keyword_priority)


    # now annotate the ALTO file with the keylines etc.
    alto_annotated = tag_key_elements(alto_tree, keyline_idxs, keyline_stats)

    return alto_annotated

def standardize_dataset_fp(filepath):
    # Remove everything in the filepath until the batch name.
    # What remains is a consistent UID for the given file.
    #
    # ocr.txt example fp in all_kw_hits:
    # ../victim_name_search/timely_match_pages/ak_gyrfalcon_ver01/sn86072239/1921/01/25/ed-1/seq-1/ocr.txt
    #
    # fp as given in file_to_review row csv's:
    # data/timely_match_pages/mnhi_orr_ver01/sn90059228/1894/06/07/ed-1/seq-3/ocr.txt
    #
    # fp as given in automatically_reviewed/obv_matches_with_kw_stats.csv:
    # dlc_echo_ver01/sn87062234/1899/04/25/ed-1/seq-1/ocr.txt
    filepath = Path(filepath)
    sn_idx = 0
    parts = filepath.parts
    for part in parts:
        if re.search(r'(?:sn)?\d{8}', part, flags=re.IGNORECASE):
            break
        else:
            sn_idx += 1

    # (batch name precedes the sn number)
    filepath = Path('/'.join(parts[sn_idx - 1::]))
    return filepath

def process_file(alto_fp, occurrences_dict, ocr_txt_root, keyword_priority):
    '''
    Annotate the alto file.

    Returns: tuple (Path filepath, bool was_successful, Exception reason_for_failure)
    '''
    try:
        with open(alto_fp, 'r') as alto_f:
            alto_txt = alto_f.read()
        # This is to correct for accidentally formatting alto xml as b'[XML]' in prev versions of
        # this script...
        if alto_txt[0] == 'b':
            alto_txt = ast.literal_eval(alto_txt)
            alto_txt = alto_txt.decode('utf-8')
        alto_tree = ET.ElementTree(ET.fromstring(alto_txt))
        #alto_tree = ET.parse(alto_fp)

        ocr_txt_fp = standardize_dataset_fp(alto_fp).parent / Path('ocr.txt')
        with open(ocr_txt_root / ocr_txt_fp, 'r') as txt_f:
            fulltxt = txt_f.read()
        with open(ocr_txt_root / ocr_txt_fp, 'r') as txt_f:
            file_lines = txt_f.readlines()


        occurrences = occurrences_dict[ocr_txt_fp]

        # call annotate_alto and save:
        if not alto_fp.exists():
            print(f'COULDNT FIND {alto_fp}')
        alto_annotated = annotate_alto(fulltxt, file_lines, occurrences, alto_tree, keyword_priority)
        new_fp = alto_fp.parent / Path('scan_annotated.xml')
        #alto_annotated.write(new_fp, default_namespace='')
        # Remove namespace from tags:
        tree_str = str(ET.tostring(alto_annotated.getroot()))
        tree_str = re.sub('ns0:','',tree_str)
        if tree_str[0] == 'b':
            tree_str = tree_str[2:-1]

        with open(new_fp, 'w') as outfile:
            outfile.write(tree_str)

        return (alto_fp, True, None)

    except Exception as e:
        tqdm.write(f'Failed: {str(alto_fp)}')
        #if not isinstance(e, ET.ParseError):
        raise e
        return (alto_fp, False, str(e))

kpdb = None

def main(args):
    # Annotate all the ALTO files in the given directory.
    #ALTO_DATA_ROOT = Path('/mnt/642c5478-8241-4cb0-b2ff-c4ec37b151c6/relevant_coverage_examples/')
    ALTO_DATA_ROOT = Path('./webapp/static/data/')
    #ALTO_DATA_ROOT = Path('./test_input/')
    NUM_FILES_TOTAL = 3058  # TODO NOTE adjust based on num files in ALTO_DATA_ROOT
    OCR_TXT_ROOT = Path('../data_cleaning/data/timely_match_pages/')
    #kw_occurrences_fp = Path('../data_cleaning/all_kw_hits.txt')
    #kw_metadata_fp = Path('../data_cleaning/keywords.csv')
    #test_alto_filepath = './'

    # Replace the above with argparse
    parser = argparse.ArgumentParser(description='Annotate ALTO files, adding elements to identify keylines.')
    # NOTE on args:
    # There are two kinds of keyword/phrase data.  At least one of them must be provided:
    #
    # 1. Keyword occurrences.  Provided in a kw_occurence.TXT file with format:
    #    <filepath> \n
    #    <kw_text>:<kw_id>:<kw_start_idx_in_words>:<kw_end_idx_in_words>, <kw_text>:<kw_id>:<kw_start_idx_in_words>:<kw_end_idx_in_words>, ...
    #  The kw_occurence.txt file must be accompanied by a kw_metadata.csv file with format:
    #   <kw_id>,<kw_text>,<kw_priority>
    #
    # 2. Keyphrase occurrences.  Provided in a keyphrase_occurences.CSV file, with columns including:
    #   <filepath>,<keyphrase_text>,<keyphrase_start_idx_in_words>,<keyphrase_end_idx_in_words>
    #
    # TODO NOTE, we should really reconcile these two different formats.  The keyphrase occurrences should be represented in the same way as the keywords.

    parser.add_argument('--alto_data_root', type=Path, default=ALTO_DATA_ROOT,
                        help= f'Path to the directory containing the ALTO files to annotate. Default: {ALTO_DATA_ROOT}')
    parser.add_argument('--ocr_txt_root', type=Path, default=OCR_TXT_ROOT,
                        help = f'Path to the directory containing the ocr.txt files. Default: {OCR_TXT_ROOT}')
    # Arguments for keyword highlighting: 
    parser.add_argument('--kw_metadata_fp', type=Path, default=None,
                        help = f'Path to the file containing the keyword metadata.')
    parser.add_argument('--kw_occurrences_fp', type=Path, default=None,
                        help = f'(Optional) Path to the file containing the keyword occurrences.')
    # Arguments for keyphrase highlighting (i.e. based on key phrase regexes):
    parser.add_argument('--keyphrase_data_fp', type=Path, default = None,
                        help = 'Path to the file containing the keyphrase data.')

    args, unknown = parser.parse_known_args()

    if len(unknown) > 0:
        parser.error(f'Unknown arguments: {unknown}')

    alto_data_root = args.alto_data_root
    ocr_txt_root = args.ocr_txt_root
    kw_occurrences_fp = args.kw_occurrences_fp
    kw_metadata_fp = args.kw_metadata_fp
    keyphrase_data_fp = args.keyphrase_data_fp

    # Validate args:
    if not (kw_occurrences_fp or keyphrase_data_fp):
        parser.error('Must provide either kw_occurrences_fp or keyphrase_data_fp')
    elif kw_occurrences_fp and not kw_metadata_fp:
        parser.error('Must provide kw_metadata_fp if kw_occurrences_fp is provided')

    assert alto_data_root.exists()
    assert ocr_txt_root.exists()
    if kw_occurrences_fp:
        assert kw_occurrences_fp.exists()
        assert kw_metadata_fp.exists()
    if keyphrase_data_fp:
        # TODO
        #raise NotImplementedError('Keyphrase highlighting not yet implemented')
        global kpdb
        kpdb = pd.read_csv(keyphrase_data_fp)
        assert keyphrase_data_fp.exists()

    tstamp = str(datetime.now(timezone.utc)).replace(' ','_')

    # Build kw occurrences dict mapping filepath : occurrences
    occurrences_dict= dict()
    with open(kw_occurrences_fp, 'r') as kw_f:
        occurrence_lines = kw_f.readlines()
    for i in range(0,len(occurrence_lines),2):
        line = occurrence_lines[i]
        line = standardize_dataset_fp(line.strip())
        occurrences_str = occurrence_lines[i+1].strip()

        occurrences_dict[line] = occurrences_str

    # Get list of ALTO files to annotate:
    #alto_files = list(alto_data_root.rglob("*scan.xml"))
    alto_files = []
    for ocr_file in occurrences_dict.keys():
        ocr_file = ocr_txt_root / ocr_file
        assert ocr_file.exists()
        xml_files = list(ocr_file.parent.glob('*scan.xml'))
        if len(xml_files) > 0:
            alto_files.append(xml_files[0])
        else:
            print(f'No ALTO file found for {ocr_file}')

    # Load keyword info and create dict mapping kw_id to priority.
    kwmd = pd.read_csv(kw_metadata_fp)
    keyword_priority = {kwid : priority for kwid, priority in 
                        zip(list(kwmd.id),list(kwmd.priority))}

    processing_fn = partial(process_file, occurrences_dict = occurrences_dict, ocr_txt_root =
                            ocr_txt_root, keyword_priority = keyword_priority)

    pool = Pool(os.cpu_count())
    ret = list(tqdm(pool.imap_unordered(processing_fn, alto_files),
                    total=len(alto_files),
                    desc='ANNOTATION PROGRESS'))

    ## For debugging
    #ret = []
    #for alto_fp in tqdm(alto_files[155::]):
    #    ret.append(processing_fn(alto_fp))
    #ic(ret)

    # Count successes and failures:
    fps, successes, exceptions = [], [], []
    for fp, success, exception in ret:
        fps.append(fp)
        successes.append(success)
        exceptions.append(exception)
    results_df = pd.DataFrame({ 'fp' : fps, 'successful' : successes, 'exception' : exceptions})

    results_csv_fp = Path('./alto_annotation_results_' + tstamp + '.csv')
    results_df.to_csv(results_csv_fp)

    ic(results_csv_fp)
    num_failed = len(results_df[~results_df.successful])
    print(f'{num_failed} of {len(results_df)} files failed.')



if __name__ == '__main__':
    sys.exit(main(args=sys.argv[1:]))

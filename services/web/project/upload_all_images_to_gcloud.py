# Upload images to Google Cloud Storage.

import argparse
import sys
import re

from pathlib import Path

import pandas as pd
from tqdm import tqdm
from google.cloud import storage
import google

# TODO DEBUG
from icecream import ic
#import http
#http.client.HTTPConnection.debuglevel=5

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

    # Sometimes ends in filename, sometimes its containing directory.
    page_idx = len(parts)
    #if parts[page_idx][0:4] != 'seq-':
    #    page_idx -= 1

    # (batch name precedes the sn number)
    fp_old = filepath
    #filepath = Path('/'.join(parts[sn_idx - 1:page_idx + 1]))
    filepath = Path('/'.join(parts[sn_idx - 1:page_idx]))

    return filepath

def upload_blob(bucket_name, source_filepath, destination_blob_base, overwrite_existing=False):
    """Uploads a file to the bucket.

    params:
        bucket_name: (string) The name of the bucket.
        source_filepath: (Path) The name of the file to upload.
        destination_blob_base: (string) The basepath of the destination blob in the bucket.
        dont_overwrite: (bool) If True, will not overwrite existing blobs.

    Modified from: https://cloud.google.com/storage/docs/uploading-objects#storage-upload-object-python
    """
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    full_dest_blob_name = str(Path(destination_blob_base) / standardize_dataset_fp(source_filepath))
    ic(full_dest_blob_name)

    blob = bucket.blob(full_dest_blob_name)

    if blob.exists() and not overwrite_existing:
        tqdm.write(f'Blob {full_dest_blob_name} already exists.')
    else:
        tqdm.write('Uploading blob {}...'.format(full_dest_blob_name))
        try:
            blob.upload_from_filename(str(source_filepath))
            tqdm.write(
                f"\nFile {source_filepath} uploaded to {full_dest_blob_name}."
            )
        except google.api_core.exceptions.ServiceUnavailable as e:
            tqdm.write(f'Error uploading {source_filepath} to {full_dest_blob_name}: {e}')

def main(args):
    # parse args
    # Should include root of images, image extension to match, and gcloud bucket name.
    parser = argparse.ArgumentParser(description='Upload images to Google Cloud Storage.')

    parser.add_argument('--local_image_basedir', type=Path, required=True, help='Dir containing all images to upload.')
    parser.add_argument('--target_file_manifest', type=Path, 
                        help='CSV file containing a list of files to process. (if not provided, will search for them in local_image_basedir.')
    parser.add_argument('--gcloud_bucket', type=str, required=True, help='Name of GCloud bucket to upload to.')
    parser.add_argument('--gcloud_blob_base', type=str, required=True, help='Base path of blob in GCloud bucket.')
    parser.add_argument('--img_extension', type=str, default='jpg', help=f'Extension of images to upload. Default: "jpg"')
    parser.add_argument('--overwrite_existing_images', action='store_true', help='If set, will overwrite existing images in GCloud bucket.')

    args, unknown = parser.parse_known_args(args)

    if len(unknown) > 0:
        parser.error(f'Unknown arguments: {unknown}')

    assert args.local_image_basedir.exists(), f'Local image base dir {args.local_image_basedir} does not exist.'

    # Verify bucket exists:
    storage_client = storage.Client()
    try:
        bucket = storage_client.bucket(args.gcloud_bucket)
    except google.cloud.exceptions.NotFound:
        print(f'Bucket {args.gcloud_bucket} does not exist.')
        sys.exit(1)

    if args.target_file_manifest:
        if not args.target_file_manifest.suffix == '.csv':
            parser.error('target_file_manifest must be a CSV file.')
        assert args.target_file_manifest.exists(), f'{args.target_file_manifest} does not exist.'

    if args.img_extension[0] == '.': args.img_extension = args.img_extension[1::]

    # Find all images:
    all_imgs = None
    if args.target_file_manifest:
        # Read the target file manifest
        target_files = pd.read_csv(args.target_file_manifest)
        target_files.filepath = target_files.filepath.apply(lambda x: standardize_dataset_fp(x))
        # Search for jp2 files in the parent dir of each target file:
        all_imgs = []
        for idx, row in tqdm(list(target_files.iterrows()), desc='Searching for images.'):
            fp = Path(args.local_image_basedir) / row.filepath
            img_files = list(fp.glob(f'*.{args.img_extension}'))
            if len(img_files) == 0:
                tqdm.write(f'No {args.img_extension} files found in {fp}')
            else:
                all_imgs += img_files
    else:
        print(f'No target file manifest provided. Searching for {args.img_extension} files in {args.local_image_basedir}.')
        print('This may take a while.  If you know the files you want to process, consider providing a target file manifest.')
        all_imgs = args.local_image_basedir.rglob(f"*.{args.img_extension}")

    for image_fp in tqdm(all_imgs, desc='Uploading images'):
        upload_blob(args.gcloud_bucket, image_fp, args.gcloud_blob_base, overwrite_existing=args.overwrite_existing_images)
    
    # Upload all images to GCloud bucket.

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))


SRC_FILE=$1
BASENAME="${SRC_FILE%.*}"

opj_decompress -i $SRC_FILE -o $BASENAME.tif
gm convert $BASENAME.tif $BASENAME.jpg
# If over 10MB, downscale to <=10MB based on resolution.
if [ $(stat -c%s "$BASENAME.jpg") -gt 10000000 ]; then
    # Get scaling factor (as a percentage, not decimal)
    SCALE=$(echo "scale=2; 1000000000/$(stat -c%s "$BASENAME.jpg")" | bc)
    #SCALE=$(echo "scale=2; 10000000/$(stat -c%s "$BASENAME.jpg")" | bc)
    echo "Scaling $BASENAME.jpg by $SCALE"
    gm convert -scale $SCALE% $BASENAME.jpg $BASENAME.jpg

    # If still over 10MB, downscale by 50% until it's not.
    while [ $(stat -c%s "$BASENAME.jpg") -gt 10000000 ]; do
        SCALE=$(echo "scale=2; 50/100" | bc)
        echo "Scaling $BASENAME.jpg AGAIN by $SCALE"
        gm convert -scale $SCALE% $BASENAME.jpg $BASENAME.jpg
    done
fi

rm $BASENAME.tif

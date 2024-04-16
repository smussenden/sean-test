SRC_FILE=$1
BASENAME="${SRC_FILE%.*}"

if ! test -f "${BASENAME}_placeholder.jpg"; then
    convert $BASENAME.jpg -resize 17%x17% -define jpeg:extent=50kb "${BASENAME}_placeholder.jpg"
fi

if ! test -f "${BASENAME}_thumb.jpg"; then
    convert $BASENAME.jpg -resize 5%x5% -define jpeg:extent=5kb "${BASENAME}_thumb.jpg"
fi

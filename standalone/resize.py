import cv2
import os
import argparse

def main():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("file", type=str, help="Name of input file.")
    parser.add_argument("steps", type=int, help="Number of steps")
    parser.add_argument("--overwrite", "-o", dest="overwrite", action="store_true")
    args = parser.parse_args()

    if args.steps == 0:
        return
    if args.steps < 0 or args.steps > 8:
        print("Steps must be an integer between 1 and 8")
        return
    else:
        factor = 0.5**args.steps

    if args.overwrite:
        newfile = args.file
    else:
        fname,ext = os.path.splitext(args.file)
        if fname[-5:-1] == "-res" and fname[-1].isdigit():
            fname = fname[:-5]
            args.file = fname + ext
        newfile = "%s-res%d%s" % (fname, args.steps, ext)

    if not os.path.isfile(args.file):
        print("The file %s does not exist" % args.file)
        return
    if os.path.isfile(newfile) and not args.overwrite:
        print("%s already exists" % os.path.basename(newfile))
        return

    img = cv2.imread(args.file, cv2.IMREAD_UNCHANGED)
    rows,cols = img.shape[0:2]
    newrows = max(4, int(factor*rows))
    newcols = max(4, int(factor*cols))
    newimg = cv2.resize(img, (newcols,newrows), interpolation=cv2.INTER_AREA)
    print("%s: (%d, %d) => (%d %d)" % (os.path.basename(newfile), rows, cols, newrows, newcols))
    cv2.imwrite(os.path.join(args.file, newfile), newimg)

main()

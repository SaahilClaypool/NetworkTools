import csv
import sys
import re
from os import listdir
from os.path import isfile, join

import matplotlib.pyplot as plt


def main():
    if (len(sys.argv) < 4):
        print("enter more args")
        print("""\
1: directory
2: name part
3. name
4. should_show (blank if false)
""")
        exit(1)
    dirname = sys.argv[1]
    r_pattern = re.compile(".*{}.*csv".format(sys.argv[2]))
    name = sys.argv[3]
    print(r_pattern)
    files = []
    for f in listdir(dirname):
        if (isfile(join(dirname, f)) and r_pattern.search(str(f))):
            f = join(dirname, f)
            print(f)
            plot_one(f)
    
    plt.ylabel("throughput (mbps)")
    if (len(sys.argv) > 5):
        plt.ylabel(sys.argv[5])
    plt.xlabel("time (s)")
    if (len(sys.argv) > 6):
        plt.xlabel(sys.argv[6])
    plt.title(name)
    plt.ylim(ymin=0)
    plt.savefig(name)
    if (len(sys.argv) > 4 and sys.argv[4] == "show"):
        plt.show()

def plot_one(filename):
    x = []
    y = []
    with open(filename, 'r') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            x.append(float(row[0]) / 1000)
            y.append(float(row[1].strip()))
    plt.plot(x,y)

if __name__ == '__main__':
    main()

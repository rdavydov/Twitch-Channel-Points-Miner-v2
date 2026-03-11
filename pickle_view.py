#!/usr/bin/env python

# Simple script to view contents of a cookie file stored in a pickle format

import pickle
import sys

if __name__ == '__main__':
    argv = sys.argv
    if len(argv) != 2:
        print("Specify a pickle file as a parameter, e.g. cookies/user.pkl")
    else:
        with open(argv[1], "rb") as f:
            print(pickle.load(f))

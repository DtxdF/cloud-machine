#!/usr/bin/env python

import sys
import commentjson

def main(*args):
    print(commentjson.dumps(commentjson.load(sys.stdin)))

def usage():
    print("usage: parse-json.py")

if __name__ == "__main__":
    sys.exit(main(*sys.argv))

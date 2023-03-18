all:
	cxfreeze --include-msvcr -c main.py --target-dir dist

db:
	echo .read make.sql | sqlite3 b4.db
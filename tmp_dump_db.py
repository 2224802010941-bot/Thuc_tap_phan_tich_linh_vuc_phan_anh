import sqlite3

db_path = 'hethong_dichvucong.db'
con = sqlite3.connect(db_path)
cur = con.cursor()
print('TABLES:', cur.execute("select name from sqlite_master where type='table' order by name").fetchall())

print('SAMPLE dia_chi:')
rows = cur.execute('''
    select dia_chi
    from phan_anh
    where dia_chi is not null and trim(dia_chi)<>''
    limit 20
''').fetchall()
for i,(r,) in enumerate(rows,1):
    print(i, repr(r))

print('\nSAMPLE GROUP BY keywords (contains Phường/Xã/Quận/Huyện/Thành phố/Thị trấn):')
keys = ['Phường','Xã','Quận','Huyện','Thành phố','Thị trấn']
for k in keys:
    cnt = cur.execute('select count(*) from phan_anh where dia_chi is not null and instr(dia_chi, ?) > 0', (k,)).fetchone()[0]
    print(k, cnt)

con.close()


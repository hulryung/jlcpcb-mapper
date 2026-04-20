import sqlite3
import sys
from pathlib import Path

def build(path):
    path = Path(path)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(str(path))
    c = conn.cursor()
    c.execute("""CREATE TABLE parts (
        lcsc TEXT PRIMARY KEY,
        category TEXT,
        mfr TEXT,
        mfr_part TEXT,
        package TEXT,
        description TEXT,
        basic INTEGER,
        preferred INTEGER,
        stock INTEGER,
        price REAL
    )""")
    rows = [
        ("C17168","Chip Resistor - Surface Mount","UNI-ROYAL","0402WGF0000TCE","0402","0Ω ±1% 1/16W 0402",1,0,2300000,0.0008),
        ("C21189","Chip Resistor - Surface Mount","YAGEO","RC0402JR-070RL","0402","0Ω 0402",0,1,890000,0.0009),
        ("C11702","Chip Resistor - Surface Mount","UNI-ROYAL","0402WGF1001TCE","0402","1KΩ ±1% 1/16W 0402",1,0,1500000,0.0008),
        ("C440198","Multilayer Ceramic Capacitors MLCC - SMD/SMT","Samsung","CL05A225MP5NSNC","0402","2.2µF ±20% 10V X5R 0402",1,0,950000,0.0015),
        ("C262679","Wire To Board / Wire To Wire Connector","XKB","AFC24-S06FIA-00","FPC-6P-P0.5mm","FPC 6Pin 0.5mm",0,0,500,0.15),
    ]
    c.executemany("INSERT INTO parts VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    build(Path(sys.argv[1]))

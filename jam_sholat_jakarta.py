# py jam_sholat_jakarta1.py

import argparse
import math
import os
import shutil
import signal
import sys
import time
from datetime import date, datetime, timedelta, timezone

KOTA = "JAKARTA"
LAT, LON = -6.2088, 106.8456         
WIB = timezone(timedelta(hours=7))     

FAJR_ANGLE = 20.0                      
ISHA_ANGLE = 18.0                      
ASR_FACTOR = 1                         
MAGHRIB_ANGLE = 0.833                  

OFFSET_MENIT = {
    "Subuh": 0,
    "Terbit": 0,
    "Dzuhur": 0,
    "Ashar": 0,
    "Maghrib": 0,
    "Isya": 0,
}

MANUAL_TIMES = {}

BUNYI_ADZAN = True                     
ADZAN_TAMPIL_DETIK = 60                

HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember"]

SHOLAT = ["Subuh", "Dzuhur", "Ashar", "Maghrib", "Isya"]
SEMUA = ["Subuh", "Terbit", "Dzuhur", "Ashar", "Maghrib", "Isya"]


def _sin(d): return math.sin(math.radians(d))
def _cos(d): return math.cos(math.radians(d))
def _tan(d): return math.tan(math.radians(d))
def _asin(x): return math.degrees(math.asin(x))
def _acos(x): return math.degrees(math.acos(x))
def _atan2(y, x): return math.degrees(math.atan2(y, x))
def _acot(x): return math.degrees(math.atan(1.0 / x))


def _fix(a, mod):
    a = a - mod * math.floor(a / mod)
    return a + mod if a < 0 else a


def _julian(y, m, d):
    if m <= 2:
        y -= 1
        m += 12
    a = math.floor(y / 100)
    b = 2 - a + math.floor(a / 4)
    return math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5


def _sun_position(jd):
    """Deklinasi matahari (derajat) dan equation of time (jam)."""
    D = jd - 2451545.0
    g = _fix(357.529 + 0.98560028 * D, 360)
    q = _fix(280.459 + 0.98564736 * D, 360)
    L = _fix(q + 1.915 * _sin(g) + 0.020 * _sin(2 * g), 360)
    e = 23.439 - 0.00000036 * D
    ra = _atan2(_cos(e) * _sin(L), _cos(L)) / 15.0
    eqt = q / 15.0 - _fix(ra, 24)
    decl = _asin(_sin(e) * _sin(L))
    return decl, eqt


def _hitung_waktu_desimal(tanggal: date):
    """Hitung waktu sholat (jam desimal, waktu lokal WIB) untuk satu tanggal."""
    jd = _julian(tanggal.year, tanggal.month, tanggal.day) - LON / (15.0 * 24.0)
    tz = 7.0

    def mid_day(t):
        _, eqt = _sun_position(jd + t)
        return _fix(12 - eqt, 24)

    def sun_angle_time(angle, t, ccw=False):
        decl, _ = _sun_position(jd + t)
        noon = mid_day(t)
        x = (-_sin(angle) - _sin(decl) * _sin(LAT)) / (_cos(decl) * _cos(LAT))
        x = max(-1.0, min(1.0, x))
        return noon + (-1 if ccw else 1) * _acos(x) / 15.0

    def asr_time(factor, t):
        decl, _ = _sun_position(jd + t)
        angle = -_acot(factor + _tan(abs(LAT - decl)))
        return sun_angle_time(angle, t)

    fajr = sun_angle_time(FAJR_ANGLE, 5 / 24.0, ccw=True)
    sunrise = sun_angle_time(MAGHRIB_ANGLE, 6 / 24.0, ccw=True)
    dhuhr = mid_day(12 / 24.0)
    asr = asr_time(ASR_FACTOR, 13 / 24.0)
    maghrib = sun_angle_time(MAGHRIB_ANGLE, 18 / 24.0)
    isha = sun_angle_time(ISHA_ANGLE, 18 / 24.0)

    adj = tz - LON / 15.0
    return {
        "Subuh": fajr + adj,
        "Terbit": sunrise + adj,
        "Dzuhur": dhuhr + adj,
        "Ashar": asr + adj,
        "Maghrib": maghrib + adj,
        "Isya": isha + adj,
    }


def jadwal_hari(tanggal: date) -> dict:
    """Return {nama: datetime WIB} untuk tanggal tertentu (sudah termasuk kalibrasi)."""
    mentah = _hitung_waktu_desimal(tanggal)
    hasil = {}
    awal = datetime(tanggal.year, tanggal.month, tanggal.day, tzinfo=WIB)
    for nama in SEMUA:
        menit = round(mentah[nama] * 60) + OFFSET_MENIT.get(nama, 0)
        hasil[nama] = awal + timedelta(minutes=menit)

    if MANUAL_TIMES and tanggal == datetime.now(WIB).date():
        for nama, jam in MANUAL_TIMES.items():
            if nama in hasil:
                h, m = map(int, jam.split(":"))
                hasil[nama] = awal.replace(hour=h, minute=m)
    return hasil

FONT = {
    "0": ["###", "# #", "# #", "# #", "###"],
    "1": [" # ", "## ", " # ", " # ", "###"],
    "2": ["###", "  #", "###", "#  ", "###"],
    "3": ["###", "  #", "###", "  #", "###"],
    "4": ["# #", "# #", "###", "  #", "  #"],
    "5": ["###", "#  ", "###", "  #", "###"],
    "6": ["###", "#  ", "###", "# #", "###"],
    "7": ["###", "  #", "  #", "  #", "  #"],
    "8": ["###", "# #", "###", "# #", "###"],
    "9": ["###", "# #", "###", "  #", "###"],
    ":": [" ", "#", " ", "#", " "],
}


def jam_besar(teks: str) -> list:
    """Ubah '14:32:07' jadi 5 baris tulisan blok besar."""
    baris = []
    for r in range(5):
        bagian = []
        for ch in teks:
            pola = FONT[ch][r]
            bagian.append("".join("██" if c == "#" else "  " for c in pola))
        baris.append(" ".join(bagian))
    return baris


RESET, BOLD, DIM = "\033[0m", "\033[1m", "\033[2m"
GREEN, YELLOW, CYAN, GREY = "\033[92m", "\033[93m", "\033[96m", "\033[90m"
LEBAR = 50                              
PAD_JADWAL = 9                          

def _fmt_hms(td: timedelta) -> str:
    total = max(0, int(td.total_seconds()))
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


def _garis(ch="─"):
    return f"{CYAN}{ch * LEBAR}{RESET}"


def _tengah(teks: str, warna: str = "") -> str:
    """Tengahkan teks polos, lalu beri warna (panjang dihitung tanpa kode warna)."""
    kiri = max(0, (LEBAR - len(teks)) // 2)
    return " " * kiri + warna + teks + (RESET if warna else "")


def cari_berikutnya(sekarang: datetime, hari_ini: dict):
    """Cari sholat berikutnya (bisa Subuh besok). Return (nama, datetime)."""
    for nama in SHOLAT:
        if hari_ini[nama] > sekarang:
            return nama, hari_ini[nama]
    besok = jadwal_hari(sekarang.date() + timedelta(days=1))
    return "Subuh", besok["Subuh"]


def cari_adzan_aktif(sekarang: datetime, hari_ini: dict):
    """Nama sholat yang waktunya baru masuk (dalam ADZAN_TAMPIL_DETIK terakhir)."""
    for nama in SHOLAT:
        selisih = (sekarang - hari_ini[nama]).total_seconds()
        if 0 <= selisih < ADZAN_TAMPIL_DETIK:
            return nama
    return None


def render(sekarang: datetime, hari_ini: dict) -> str:
    nama_berikut, waktu_berikut = cari_berikutnya(sekarang, hari_ini)
    adzan = cari_adzan_aktif(sekarang, hari_ini)
    jam = sekarang.strftime("%H:%M:%S")
    tgl = f"{HARI[sekarang.weekday()]}, {sekarang.day} {BULAN[sekarang.month]} {sekarang.year}"

    b = []
    b.append(_garis("═"))
    b.append(_tengah(f"{KOTA}  ·  WIB (UTC+7)", DIM))
    b.append("")

    if shutil.get_terminal_size((80, 24)).columns >= LEBAR:
        for baris in jam_besar(jam):
            b.append(_tengah(baris, BOLD + GREEN))
    else:  
        b.append(_tengah(jam, BOLD + GREEN))
    b.append("")

    b.append(_tengah(tgl))
    b.append(_garis())

    for nama in SEMUA:
        w = hari_ini[nama]
        jam_str = w.strftime("%H:%M")
        pad = " " * PAD_JADWAL
        if nama == "Terbit":
            b.append(f"{pad}  {GREY}{nama:<10}{jam_str}   (info){RESET}")
        elif nama == nama_berikut and waktu_berikut.date() == sekarang.date():
            b.append(f"{pad}{YELLOW}{BOLD}▶ {nama:<10}{jam_str}   ← berikutnya{RESET}")
        elif w <= sekarang:
            b.append(f"{pad}  {nama:<10}{jam_str} ")
        else:
            b.append(f"{pad}  {nama:<10}{jam_str}")

    b.append(_garis())
    sisa = _fmt_hms(waktu_berikut - sekarang)
    label = nama_berikut + (" (besok)" if waktu_berikut.date() != sekarang.date() else "")
    b.append(_tengah(f"Menuju {label}: {sisa}", YELLOW))
    if adzan:
        b.append(_tengah(f"Waktu {adzan} telah tiba - saatnya sholat", BOLD + GREEN))
    else:
        b.append("")
    b.append(_tengah("Ctrl+C untuk keluar", DIM))
    b.append(_garis("═"))
    return "\n".join(b)


def cetak_sekali():
    sekarang = datetime.now(WIB)
    j = jadwal_hari(sekarang.date())
    print(f"{KOTA} - {HARI[sekarang.weekday()]}, {sekarang.day} {BULAN[sekarang.month]} {sekarang.year}")
    for nama in SEMUA:
        print(f"{nama:<8}{j[nama].strftime('%H:%M')}")


IS_WIN = os.name == "nt"
if IS_WIN:
    import msvcrt
else:
    import select
    import termios


class KunciTerminal:

    def __enter__(self):
        os.system("") if IS_WIN else None          
        self.fd = None
        self.lama = None
        self.sinyal_lama = {}
        if not IS_WIN and sys.stdin.isatty():
            self.fd = sys.stdin.fileno()
            self.lama = termios.tcgetattr(self.fd)
            baru = termios.tcgetattr(self.fd)
            baru[3] &= ~(termios.ECHO | termios.ICANON)   
            termios.tcsetattr(self.fd, termios.TCSADRAIN, baru)
            for nama in ("SIGTSTP", "SIGQUIT"):
                sig = getattr(signal, nama, None)
                if sig is not None:
                    self.sinyal_lama[sig] = signal.signal(sig, signal.SIG_IGN)
        sys.stdout.write("\033[?1049h\033[2J\033[?25l")    
        sys.stdout.flush()
        return self

    def __exit__(self, *exc):
        sys.stdout.write("\033[?25h\033[0m\033[?1049l")    
        sys.stdout.flush()
        if self.fd is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.lama)
            for sig, handler in self.sinyal_lama.items():
                signal.signal(sig, handler)
        return exc[0] is KeyboardInterrupt                 

    def tunggu(self, detik: float):
        """Tunggu `detik` sambil membuang semua tombol yang ditekan."""
        akhir = time.time() + detik
        while True:
            sisa = akhir - time.time()
            if sisa <= 0:
                return
            if IS_WIN:
                while msvcrt.kbhit():
                    if msvcrt.getwch() == "\x03":           
                        raise KeyboardInterrupt
                time.sleep(min(sisa, 0.05))
            elif self.fd is not None:
                siap, _, _ = select.select([self.fd], [], [], sisa)
                if siap:
                    os.read(self.fd, 4096)                  
            else:
                time.sleep(sisa)


def main():
    ap = argparse.ArgumentParser(description="Jam digital live Jakarta + jadwal sholat")
    ap.add_argument("--once", action="store_true", help="cetak jadwal hari ini sekali saja")
    args = ap.parse_args()

    if args.once:
        cetak_sekali()
        return

    sudah_bunyi = None
    cache_tgl, cache_jadwal = None, None
    with KunciTerminal() as term:
        while True:
            sekarang = datetime.now(WIB)
            if cache_tgl != sekarang.date():
                cache_tgl, cache_jadwal = sekarang.date(), jadwal_hari(sekarang.date())

            frame = render(sekarang, cache_jadwal).replace("\n", "\033[K\n")
            sys.stdout.write("\033[H" + frame + "\033[K\033[J")

            aktif = cari_adzan_aktif(sekarang, cache_jadwal)
            if aktif and BUNYI_ADZAN and sudah_bunyi != (cache_tgl, aktif):
                sys.stdout.write("\a")
                sudah_bunyi = (cache_tgl, aktif)
            sys.stdout.flush()

            term.tunggu(1.0 - (time.time() % 1.0))


if __name__ == "__main__":
    main()
# -*- coding: utf-8 -*-
import json
import math
import os
import re
import sys
import tempfile
import unittest
from fractions import Fraction as F

KOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(KOK, "src"))
import uret_v2  # noqa: E402
from uret import T, P, FP  # noqa: E402


# --------------------------------------------------------------------------
# Bagimsiz ayristirici (testin kendi kopyasi): metin -> (A, B) dogrusal form
# --------------------------------------------------------------------------
class Ayristirici:
    def __init__(self, metin, v):
        metin = metin.replace("−", "-").replace("·", "*")
        self.v = v
        self.tok = re.findall(r"\d+|[A-Za-z]|[-+*/()]", metin.replace(" ", ""))
        assert "".join(self.tok) == metin.replace(" ", ""), metin
        self.i = 0

    def bak(self):
        return self.tok[self.i] if self.i < len(self.tok) else None

    def al(self):
        t = self.tok[self.i]
        self.i += 1
        return t

    @staticmethod
    def carp(p, q):
        assert p[0] == 0 or q[0] == 0, "dogrusal degil"
        return (p[0] * q[1] + q[0] * p[1], p[1] * q[1])

    def ifade(self):
        isaret = 1
        if self.bak() in ("+", "-"):
            isaret = -1 if self.al() == "-" else 1
        a = self.terim()
        a = (a[0] * isaret, a[1] * isaret)
        while self.bak() in ("+", "-"):
            op = self.al()
            b = self.terim()
            if op == "-":
                b = (-b[0], -b[1])
            a = (a[0] + b[0], a[1] + b[1])
        return a

    def terim(self):
        a = self.carpan()
        while True:
            t = self.bak()
            if t == "*":
                self.al()
                a = self.carp(a, self.carpan())
            elif t == "/":
                self.al()
                b = self.carpan()
                assert b[0] == 0 and b[1] != 0
                a = (a[0] / b[1], a[1] / b[1])
            elif t == self.v or t == "(":
                a = self.carp(a, self.carpan())
            else:
                return a

    def carpan(self):
        t = self.al()
        if t.isdigit():
            return (F(0), F(int(t)))
        if t == self.v:
            return (F(1), F(0))
        if t == "(":
            e = self.ifade()
            assert self.al() == ")"
            return e
        raise AssertionError(f"beklenmeyen simge {t!r}")


def ayristir(metin, v):
    p = Ayristirici(metin, v)
    r = p.ifade()
    assert p.bak() is None, metin
    return r


def denklem_coz(metin, v):
    sol, sag = metin.split(" = ") if " = " in metin else metin.split("=")
    (al, bl), (ar, br) = ayristir(sol, v), ayristir(sag, v)
    a, b = al - ar, br - bl
    if a == 0:
        return "yok" if b != 0 else "sonsuz"
    return F(b) / F(a)


def taraf_formlari(metin, v):
    sol, sag = metin.split(" = ") if " = " in metin else metin.split("=")
    return ayristir(sol, v), ayristir(sag, v)


def sayi_degeri(metin):
    a, b = ayristir(metin, "\0")
    assert a == 0, metin
    return b


def ust_duzey_terim_sayisi(metin):
    """Parantez disindaki + / - ile ayrilan terim sayisi."""
    derinlik, n = 0, 1
    metin = metin.strip()
    for i, ch in enumerate(metin):
        if ch == "(":
            derinlik += 1
        elif ch == ")":
            derinlik -= 1
        elif derinlik == 0 and ch in "+-" and i > 0 and metin[i - 1] == " ":
            n += 1
    return n


def metin(sol, sag, v="x", sozel=None):
    return uret_v2.asistan_metni(sol, sag, v, sozel)[0]


class ElleYazilmisTest(unittest.TestCase):
    def kontrol(self, sol, sag, beklenen, v="x", sozel=None):
        self.assertEqual(metin(sol, sag, v, sozel), beklenen)

    def test_3x53_4x62(self):
        self.kontrol(
            [P(3, [T(1), T(53, False)])], [P(4, [T(1), T(62, False)])],
            """Denklem: 3(x + 53) = 4(x + 62)

1. adım: Parantezleri açalım (dağılma özelliği): 3·x = 3x, 3·53 = 159, 4·x = 4x, 4·62 = 248.
3x + 159 = 4x + 248

2. adım: Bilinmeyenli terimleri solda toplamak için her iki taraftan 4x çıkaralım.
3x - 4x + 159 = 248
-x + 159 = 248

3. adım: Sabit terimi sağa geçirmek için her iki taraftan 159 çıkaralım.
-x = 248 - 159
-x = 89

4. adım: Her iki tarafı -1 ile çarpalım.
x = -89

Sağlama: x = -89 değerini ilk denklemde yerine koyalım.
Sol taraf: 3·(-89 + 53) = 3·(-36) = -108
Sağ taraf: 4·(-89 + 62) = 4·(-27) = -108
İki taraf eşit, çözüm doğru.

Sonuç: x = -89""")

    def test_benzer_terimler(self):
        self.kontrol(
            [T(4), T(188, False), T(-7), T(-127, False)], [T(181, False)],
            """Denklem: 4x + 188 - 7x - 127 = 181

1. adım: Benzer terimleri birleştirelim: 4x - 7x = -3x, 188 - 127 = 61.
-3x + 61 = 181

2. adım: Sabit terimi sağa geçirmek için her iki taraftan 61 çıkaralım.
-3x = 181 - 61
-3x = 120

3. adım: Her iki tarafı -3'e bölelim.
x = 120/(-3)
x = -40 (çünkü -3·(-40) = 120)

Sağlama: x = -40 değerini ilk denklemde yerine koyalım.
Sol taraf: 4·(-40) + 188 - 7·(-40) - 127 = -160 + 188 + 280 - 127 = 181
Sağ taraf: 181
İki taraf eşit, çözüm doğru.

Sonuç: x = -40""")

    def test_sadelesen_kesir(self):
        self.kontrol(
            [T(6), T(-29, False)], [T(34, False)],
            """Denklem: 6x - 29 = 34

1. adım: Sabit terimi sağa geçirmek için her iki tarafa 29 ekleyelim.
6x = 34 + 29
6x = 63

2. adım: Her iki tarafı 6'ya bölelim.
x = 63/6
x = 21/2 (pay ve payda 3 ile sadeleşti)

Sağlama: x = 21/2 değerini ilk denklemde yerine koyalım.
Sol taraf: 6·(21/2) - 29 = 63 - 29 = 34
Sağ taraf: 34
İki taraf eşit, çözüm doğru.

Sonuç: x = 21/2""")

    def test_t15(self):
        self.kontrol(
            [T(10, False), T(-2)], [T(4), T(-8, False)],
            """Denklem: 10 - 2x = 4x - 8

1. adım: Terimleri düzenleyelim.
-2x + 10 = 4x - 8

2. adım: Bilinmeyenli terimleri solda toplamak için her iki taraftan 4x çıkaralım.
-2x - 4x + 10 = -8
-6x + 10 = -8

3. adım: Sabit terimi sağa geçirmek için her iki taraftan 10 çıkaralım.
-6x = -8 - 10
-6x = -18

4. adım: Her iki tarafı -6'ya bölelim.
x = -18/(-6)
x = 3 (çünkü -6·3 = -18)

Sağlama: x = 3 değerini ilk denklemde yerine koyalım.
Sol taraf: 10 - 2·3 = 10 - 6 = 4
Sağ taraf: 4·3 - 8 = 12 - 8 = 4
İki taraf eşit, çözüm doğru.

Sonuç: x = 3""")

    def test_payda_carpimi(self):
        self.kontrol(
            [T(F(1, 12)), T(F(1, 2))], [T(7, False)],
            """Denklem: m/12 + m/2 = 7

1. adım: Paydalardan kurtulmak için her iki tarafı 12 ile çarpalım: 12·(m/12) = m, 12·(m/2) = 6m, 12·7 = 84.
m + 6m = 84

2. adım: Benzer terimleri birleştirelim: m + 6m = 7m.
7m = 84

3. adım: Her iki tarafı 7'ye bölelim.
m = 84/7
m = 12 (çünkü 7·12 = 84)

Sağlama: m = 12 değerini ilk denklemde yerine koyalım.
Sol taraf: 12/12 + 12/2 = 1 + 6 = 7
Sağ taraf: 7
İki taraf eşit, çözüm doğru.

Sonuç: m = 12""", v="m")

    def test_11x36(self):
        self.kontrol(
            [P(11, [T(1), T(36, False)])], [P(-11, [T(1), T(-168, False)])],
            """Denklem: 11(x + 36) = -11(x - 168)

1. adım: Parantezleri açalım (dağılma özelliği): 11·x = 11x, 11·36 = 396, -11·x = -11x, -11·(-168) = 1848.
11x + 396 = -11x + 1848

2. adım: Bilinmeyenli terimleri solda toplamak için her iki tarafa 11x ekleyelim.
11x + 11x + 396 = 1848
22x + 396 = 1848

3. adım: Sabit terimi sağa geçirmek için her iki taraftan 396 çıkaralım.
22x = 1848 - 396
22x = 1452

4. adım: Her iki tarafı 22'ye bölelim.
x = 1452/22
x = 66 (çünkü 22·66 = 1452)

Sağlama: x = 66 değerini ilk denklemde yerine koyalım.
Sol taraf: 11·(66 + 36) = 11·102 = 1122
Sağ taraf: -11·(66 - 168) = -11·(-102) = 1122
İki taraf eşit, çözüm doğru.

Sonuç: x = 66""")

    def test_ozel_yok(self):
        self.kontrol(
            [T(3), T(1, False)], [T(3), T(5, False)],
            """Denklem: 3x + 1 = 3x + 5

1. adım: Bilinmeyenli terimleri solda toplamak için her iki taraftan 3x çıkaralım.
3x - 3x + 1 = 5

Bilinmeyen sadeleşti ve geriye 1 = 5 kaldı. Bu eşitlik hiçbir zaman doğru değildir.

Sonuç: Denklemin çözümü yoktur (çözüm kümesi boş kümedir).""")

    def test_ozel_sonsuz(self):
        self.kontrol(
            [P(2, [T(1), T(3, False)])], [T(2), T(6, False)],
            """Denklem: 2(x + 3) = 2x + 6

1. adım: Parantezleri açalım (dağılma özelliği): 2·x = 2x, 2·3 = 6.
2x + 6 = 2x + 6

2. adım: Bilinmeyenli terimleri solda toplamak için her iki taraftan 2x çıkaralım.
2x - 2x + 6 = 6

Bilinmeyen sadeleşti ve geriye 6 = 6 kaldı. Bu eşitlik her zaman doğrudur.

Sonuç: Denklem her x değeri için sağlanır (sonsuz çözüm vardır).""")

    def test_yas(self):
        k = uret_v2.s_yas1(("Ali", "Ali'nin"), 3, 15)
        self.assertEqual(k.metin, "Ali'nin yaşının 3 katı 45 ise Ali kaç yaşındadır?")
        self.kontrol(
            k.sol, k.sag,
            """Ali'nin yaşına x diyelim.

Denklem: 3x = 45

1. adım: Her iki tarafı 3'e bölelim.
x = 45/3
x = 15 (çünkü 3·15 = 45)

Sağlama: x = 15 değerini ilk denklemde yerine koyalım.
Sol taraf: 3·15 = 45
Sağ taraf: 45
İki taraf eşit, çözüm doğru.

Sonuç: x = 15 (Ali 15 yaşındadır)""", sozel=k)

    def test_yas_burak_eki(self):
        k = uret_v2.s_yas3(("Burak", "Burak'ın"), 5, 20)
        self.assertEqual(k.metin, "Burak 5 yıl sonra 25 yaşında olacak. Burak şimdi kaç yaşındadır?")
        self.kontrol(
            k.sol, k.sag,
            """Burak'ın yaşına x diyelim.

Denklem: x + 5 = 25

1. adım: Sabit terimi sağa geçirmek için her iki taraftan 5 çıkaralım.
x = 25 - 5
x = 20

Sağlama: x = 20 değerini ilk denklemde yerine koyalım.
Sol taraf: 20 + 5 = 25
Sağ taraf: 25
İki taraf eşit, çözüm doğru.

Sonuç: x = 20 (Burak 20 yaşındadır)""", sozel=k)

    def test_ardisik_buyuk(self):
        k = uret_v2.s_ard2("buyuk", 20)
        self.assertEqual(k.metin, "Ardışık iki tam sayının toplamı 41. Büyük sayı kaçtır?")
        self.assertEqual((str(k.x0), str(k.aranan)), ("20", "21"))
        self.kontrol(
            k.sol, k.sag,
            """Küçük sayıya x diyelim. Büyük sayı x + 1 olur.

Denklem: x + x + 1 = 41

1. adım: Benzer terimleri birleştirelim: x + x = 2x.
2x + 1 = 41

2. adım: Sabit terimi sağa geçirmek için her iki taraftan 1 çıkaralım.
2x = 41 - 1
2x = 40

3. adım: Her iki tarafı 2'ye bölelim.
x = 40/2
x = 20 (çünkü 2·20 = 40)

Sağlama: x = 20 değerini ilk denklemde yerine koyalım.
Sol taraf: 20 + 20 + 1 = 41
Sağ taraf: 41
İki taraf eşit, çözüm doğru.

Sonuç: x = 20 (büyük sayı 21)""", sozel=k)

    def test_para(self):
        k = uret_v2.s_para(("Ayşe", "Ayşe'nin"), 4, 15, 40)
        self.assertEqual(
            k.metin,
            "Ayşe'nin parasının 4 katının 15 TL fazlası 175 TL ediyor. Ayşe'nin kaç TL'si vardır?",
        )
        self.kontrol(
            k.sol, k.sag,
            """Ayşe'nin parasına x TL diyelim.

Denklem: 4x + 15 = 175

1. adım: Sabit terimi sağa geçirmek için her iki taraftan 15 çıkaralım.
4x = 175 - 15
4x = 160

2. adım: Her iki tarafı 4'e bölelim.
x = 160/4
x = 40 (çünkü 4·40 = 160)

Sağlama: x = 40 değerini ilk denklemde yerine koyalım.
Sol taraf: 4·40 + 15 = 160 + 15 = 175
Sağ taraf: 175
İki taraf eşit, çözüm doğru.

Sonuç: x = 40 (Ayşe'nin 40 TL'si vardır)""", sozel=k)

    def test_t16(self):
        self.kontrol(
            [T(2), T(5, False), T(-1)], [T(3), T(-7, False), T(4, False)],
            """Denklem: 2x + 5 - x = 3x - 7 + 4

1. adım: Benzer terimleri birleştirelim: 2x - x = x, -7 + 4 = -3.
x + 5 = 3x - 3

2. adım: Bilinmeyenli terimleri solda toplamak için her iki taraftan 3x çıkaralım.
x - 3x + 5 = -3
-2x + 5 = -3

3. adım: Sabit terimi sağa geçirmek için her iki taraftan 5 çıkaralım.
-2x = -3 - 5
-2x = -8

4. adım: Her iki tarafı -2'ye bölelim.
x = -8/(-2)
x = 4 (çünkü -2·4 = -8)

Sağlama: x = 4 değerini ilk denklemde yerine koyalım.
Sol taraf: 2·4 + 5 - 4 = 8 + 5 - 4 = 9
Sağ taraf: 3·4 - 7 + 4 = 12 - 7 + 4 = 9
İki taraf eşit, çözüm doğru.

Sonuç: x = 4""")

    def test_kesirli_saglama(self):
        self.kontrol(
            [T(-3), T(1, False)], [T(8, False)],
            """Denklem: -3x + 1 = 8

1. adım: Sabit terimi sağa geçirmek için her iki taraftan 1 çıkaralım.
-3x = 8 - 1
-3x = 7

2. adım: Her iki tarafı -3'e bölelim.
x = 7/(-3)
x = -7/3

Sağlama: x = -7/3 değerini ilk denklemde yerine koyalım.
Sol taraf: -3·(-7/3) + 1 = 7 + 1 = 8
Sağ taraf: 8
İki taraf eşit, çözüm doğru.

Sonuç: x = -7/3""")

    def test_kesirli_parantez_ve_eksi_parantez(self):
        self.kontrol(
            [FP([T(1), T(3, False)], 2)], [T(5, False)],
            """Denklem: (x + 3)/2 = 5

1. adım: Paydalardan kurtulmak için her iki tarafı 2 ile çarpalım: 2·((x + 3)/2) = x + 3, 2·5 = 10.
x + 3 = 10

2. adım: Sabit terimi sağa geçirmek için her iki taraftan 3 çıkaralım.
x = 10 - 3
x = 7

Sağlama: x = 7 değerini ilk denklemde yerine koyalım.
Sol taraf: (7 + 3)/2 = 10/2 = 5
Sağ taraf: 5
İki taraf eşit, çözüm doğru.

Sonuç: x = 7""")
        self.kontrol(
            [P(-1, [T(1), T(-2, False)])], [T(5, False)],
            """Denklem: -(x - 2) = 5

1. adım: Parantezleri açalım (dağılma özelliği): -1·x = -x, -1·(-2) = 2.
-x + 2 = 5

2. adım: Sabit terimi sağa geçirmek için her iki taraftan 2 çıkaralım.
-x = 5 - 2
-x = 3

3. adım: Her iki tarafı -1 ile çarpalım.
x = -3

Sağlama: x = -3 değerini ilk denklemde yerine koyalım.
Sol taraf: -(-3 - 2) = -(-5) = 5
Sağ taraf: 5
İki taraf eşit, çözüm doğru.

Sonuç: x = -3""")

    def test_saglama_patlar(self):
        with self.assertRaises(AssertionError):
            uret_v2.saglama([T(2), T(1, False)], [T(8, False)], F(3), "x")


class KotaTest(unittest.TestCase):
    def test_kotalar(self):
        for n in (100, 1000, 13100, 273):
            self.assertEqual(sum(uret_v2.kotalar(n)), n)
        ad = [t for t, _, _ in uret_v2.TIPLER]
        k = dict(zip(ad, uret_v2.kotalar(10000)))
        self.assertEqual((k["t15"], k["t16"], k["sozel"]), (800, 300, 1000))


# --------------------------------------------------------------------------
# Rastgele ornekler uzerinde bagimsiz denetim
# --------------------------------------------------------------------------
SONUC_RE = re.compile(r"^Sonuç: (\S+) = (-?\d+(?:/\d+)?)(?: \((.+)\))?$")
SAGLAMA_RE = re.compile(r"^Sağlama: (\S+) = (-?\d+(?:/\d+)?) değerini ilk denklemde yerine koyalım\.$")
ADIM_RE = re.compile(r"^(\d+)\. adım: (.*)$")
SATIR_YORUM_RE = re.compile(r"^(.*?)(?: \((çünkü .+|pay ve payda \d+ ile sadeleşti)\))?$")
BOL_RE = re.compile(r"^(\S+) = (-?\d+)/\(?(-?\d+)\)?$")


def sablon_regex(sablon, v):
    desen = re.escape(sablon)
    desen = desen.replace(re.escape("{eq}"), "(?P<eq>.+?)")
    desen = desen.replace(re.escape("{v_belirtme}"), "(?:" + re.escape(uret_v2.BELIRTME[v]) + "|"
                          + re.escape(uret_v2.BELIRTME[v][0].upper() + uret_v2.BELIRTME[v][1:]) + ")")
    desen = desen.replace(re.escape("{v}"), "[" + v + v.upper() + "]")
    return re.compile("^" + desen + "$")


def kullanici_denklemi(mesaj, v):
    for s in sorted(uret_v2.SABLONLAR, key=lambda t: -len(t.replace("{eq}", ""))):
        m = sablon_regex(s, v).match(mesaj)
        if m and "=" in m.group("eq"):
            return m.group("eq").replace(v.upper(), v)
    raise AssertionError(f"şablon bulunamadı: {mesaj!r}")


def denetle(test, s):
    meta = s["meta"]
    v = meta["degisken"]
    user, asst = s["messages"][0]["content"], s["messages"][1]["content"]
    satirlar = asst.split("\n")
    sozel = meta["tip"] == "sozel"
    test.assertEqual(set(meta), {"tip", "denklem", "cevap", "aranan", "degisken"})
    test.assertEqual([m["role"] for m in s["messages"]], ["user", "assistant"])

    dl = [x for x in satirlar if x.startswith("Denklem: ")]
    test.assertEqual(len(dl), 1, asst)
    denk = dl[0][len("Denklem: "):]
    beklenen = denklem_coz(denk, v)
    if beklenen in ("yok", "sonsuz"):
        test.assertEqual(meta["cevap"], beklenen)
        test.assertEqual(meta["aranan"], beklenen)
    else:
        test.assertEqual(F(meta["cevap"]), beklenen)
        test.assertEqual(meta["cevap"], str(beklenen))
    if sozel:
        test.assertEqual(meta["denklem"], user)
        test.assertEqual(v, "x")
        ilk = satirlar[0]
        test.assertTrue(ilk.endswith("."), ilk)
        test.assertEqual(satirlar[1], "")
        test.assertTrue(satirlar[2].startswith("Denklem: "))
    else:
        test.assertEqual(meta["denklem"], denk)
        test.assertEqual(meta["aranan"], meta["cevap"])
        test.assertTrue(satirlar[0].startswith("Denklem: "))

    # Sonuc
    son = satirlar[-1]
    if beklenen == "yok":
        test.assertEqual(son, "Sonuç: Denklemin çözümü yoktur (çözüm kümesi boş kümedir).")
    elif beklenen == "sonsuz":
        test.assertEqual(son, f"Sonuç: Denklem her {v} değeri için sağlanır (sonsuz çözüm vardır).")
    else:
        m = SONUC_RE.match(son)
        test.assertIsNotNone(m, son)
        test.assertEqual(m.group(1), v)
        test.assertEqual(F(m.group(2)), beklenen)
        if sozel:
            test.assertIsNotNone(m.group(3), son)
            sayilar = re.findall(r"-?\d+", m.group(3))
            test.assertIn(meta["aranan"], sayilar)
            test.assertTrue(F(meta["aranan"]) >= F(meta["cevap"]))
        else:
            test.assertIsNone(m.group(3))

    # adimlar
    adim_idx = [i for i, x in enumerate(satirlar) if ADIM_RE.match(x)]
    nos = [int(ADIM_RE.match(satirlar[i]).group(1)) for i in adim_idx]
    test.assertEqual(nos, list(range(1, len(nos) + 1)))
    test.assertGreaterEqual(len(nos), 1)
    son_adim_son_satir = None
    for i in adim_idx:
        aciklama = ADIM_RE.match(satirlar[i]).group(2)
        liste = None
        if aciklama.startswith("Paydalardan kurtulmak"):
            mm = re.match(r"^Paydalardan kurtulmak için her iki tarafı (\d+) ile çarpalım: (.+)\.$", aciklama)
            test.assertIsNotNone(mm, aciklama)
            liste = mm.group(2)
            test.assertEqual(i, adim_idx[0])  # ilk adim
            n = int(mm.group(1))
            ogeler = liste.split(", ")
            sol_m, sag_m = denk.split(" = ")
            test.assertEqual(len(ogeler), ust_duzey_terim_sayisi(sol_m) + ust_duzey_terim_sayisi(sag_m))
            for o in ogeler:
                test.assertTrue(o.startswith(f"{n}·"), o)
        elif aciklama.startswith("Parantezleri açalım"):
            mm = re.match(r"^Parantezleri açalım \(dağılma özelliği\): (.+)\.$", aciklama)
            test.assertIsNotNone(mm, aciklama)
            liste = mm.group(1)
            for o in liste.split(", "):
                test.assertIn("·", o)
        elif aciklama.startswith("Benzer terimleri birleştirelim"):
            mm = re.match(r"^Benzer terimleri birleştirelim: (.+)\.$", aciklama)
            test.assertIsNotNone(mm, aciklama)
            liste = mm.group(1)
            for o in liste.split(", "):
                sol_t = o.split(" = ")[0]
                test.assertGreaterEqual(ust_duzey_terim_sayisi(sol_t), 2, o)  # yalniz gercekten birlesenler
        else:
            test.assertNotIn(": ", aciklama)
        if liste:
            for o in liste.split(", "):
                a, b = o.split(" = ")
                test.assertEqual(ayristir(a, v), ayristir(b, v), (o, asst))
        # govde satirlari
        j = i + 1
        onceki = None
        while j < len(satirlar) and satirlar[j] != "":
            ln = satirlar[j]
            m = SATIR_YORUM_RE.match(ln)
            eq, yorum = m.group(1), m.group(2)
            test.assertEqual(denklem_coz(eq, v), beklenen, (ln, asst))
            if yorum:
                if yorum.startswith("çünkü"):
                    c = re.match(r"^çünkü (.+) = (-?\d+)$", yorum)
                    test.assertIsNotNone(c, yorum)
                    test.assertEqual(sayi_degeri(c.group(1)), F(c.group(2)))
                    bm = BOL_RE.match(onceki)
                    test.assertIsNotNone(bm, onceki)
                    test.assertEqual(F(bm.group(2)), F(c.group(2)))  # pay
                    test.assertEqual(F(bm.group(3)) * F(eq.split(" = ")[1]), F(bm.group(2)))
                    # carpan = bolen
                    test.assertTrue(c.group(1).startswith(bm.group(3) + "·"), (c.group(1), onceki))
                else:
                    g = int(re.search(r"payda (\d+) ile", yorum).group(1))
                    bm = BOL_RE.match(onceki)
                    test.assertIsNotNone(bm, onceki)
                    pay, payda = int(bm.group(2)), int(bm.group(3))
                    test.assertEqual(math.gcd(abs(pay), abs(payda)), g)
                    test.assertGreater(g, 1)
                    sonuc_f = F(eq.split(" = ")[1])
                    test.assertEqual(sonuc_f, F(pay, payda))
                    test.assertNotEqual(sonuc_f.denominator, 1)
            onceki = eq
            son_adim_son_satir = eq
            j += 1
    ozel = beklenen in ("yok", "sonsuz")
    if not ozel:
        sm = re.match(r"^(\S+) = (-?\d+(?:/\d+)?)$", son_adim_son_satir)
        test.assertIsNotNone(sm, son_adim_son_satir)
        test.assertEqual(F(sm.group(2)), beklenen)

    # ozel durum: saglama yok
    test.assertEqual(any(x.startswith("Sağlama") for x in satirlar), not ozel)
    if ozel:
        test.assertTrue(any(x.startswith("Bilinmeyen sadeleşti") for x in satirlar))
    else:
        test.assertFalse(any(x.startswith("Bilinmeyen sadeleşti") for x in satirlar))
        k = [i for i, x in enumerate(satirlar) if x.startswith("Sağlama")]
        test.assertEqual(len(k), 1)
        k = k[0]
        m = SAGLAMA_RE.match(satirlar[k])
        test.assertIsNotNone(m, satirlar[k])
        test.assertEqual(m.group(1), v)
        test.assertEqual(F(m.group(2)), beklenen)
        sol_l, sag_l = satirlar[k + 1], satirlar[k + 2]
        test.assertTrue(sol_l.startswith("Sol taraf: ") and sag_l.startswith("Sağ taraf: "))
        test.assertEqual(satirlar[k + 3], "İki taraf eşit, çözüm doğru.")
        sol_m, sag_m = denk.split(" = ")
        degerler = []
        for etiket, zincir_m, orijinal in (("Sol", sol_l, sol_m), ("Sağ", sag_l, sag_m)):
            zincir = zincir_m.split(": ", 1)[1].split(" = ")
            test.assertLessEqual(len(zincir), 4)
            vals = [sayi_degeri(p) for p in zincir]
            test.assertEqual(len(set(vals)), 1, zincir_m)  # her '=' bolumu esit
            test.assertRegex(zincir[-1], r"^-?\d+(?:/\d+)?$")
            test.assertEqual(str(vals[-1]), zincir[-1])
            for p in zincir:
                test.assertNotIn("+ -", p)
                test.assertNotIn("- -", p)
            a, b = ayristir(orijinal, v)
            test.assertEqual(vals[0], a * beklenen + b)  # yerine koyma sadik
            degerler.append(vals[-1])
        test.assertEqual(degerler[0], degerler[1])
        test.assertEqual(satirlar[k + 4], "")
        test.assertEqual(satirlar[k + 5], son)

    # kullanici mesaji (sozel disinda) ayni denklemi icerir
    if not sozel:
        ue = kullanici_denklemi(user, v)
        test.assertEqual(taraf_formlari(ue, v), taraf_formlari(denk, v), (user, denk))
        test.assertTrue(denk == denk.lower() or True)
        test.assertEqual(denk, denk.replace(v.upper(), v))


class RastgeleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bol, cls.ist = uret_v2.uret_hepsi(7, 2600, 200, 200)
        cls.satirlar = cls.bol["train"] + cls.bol["val"] + cls.bol["test"]

    def test_3000_ornek(self):
        self.assertEqual(len(self.satirlar), 3000)
        for s in self.satirlar:
            denetle(self, s)

    def test_dagilim(self):
        n = len(self.satirlar)
        sayac = {}
        for s in self.satirlar:
            sayac[s["meta"]["tip"]] = sayac.get(s["meta"]["tip"], 0) + 1
        for (tip, w, _), k in zip(uret_v2.TIPLER, uret_v2.kotalar(n)):
            self.assertEqual(sayac[tip], k)
            self.assertAlmostEqual(k / n * 100, float(w), delta=0.5)
        self.assertAlmostEqual(sayac["sozel"] / n, 0.10, delta=0.005)
        self.assertAlmostEqual(sayac["t15"] / n, 0.08, delta=0.005)

    def test_buyuk_harf_ve_yeni_sablonlar(self):
        buyuk = 0
        for s in self.satirlar:
            if s["meta"]["tip"] == "sozel":
                continue
            v = s["meta"]["degisken"]
            user = s["messages"][0]["content"]
            if re.search(r"(?<![A-Za-z])" + v.upper() + r"(?![A-Za-z])", user):
                buyuk += 1
                self.assertIn(f"Denklem: ", s["messages"][1]["content"])
                self.assertNotRegex(s["messages"][1]["content"], r"(?<![A-Za-z])" + v.upper() + r"(?![A-Za-z])")
        oran = buyuk / sum(1 for s in self.satirlar if s["meta"]["tip"] != "sozel")
        self.assertGreater(oran, 0.015)
        self.assertLess(oran, 0.06)
        # yeni sablonlar kullaniliyor
        for on in ("solve ", "Çöz bakalım: ", "ödevim var ", "Merhaba, şu denklemde takıldım: "):
            self.assertTrue(any(s["messages"][0]["content"].startswith(on) for s in self.satirlar), on)

    def test_sozel_kapsam(self):
        alt = self.ist["sozel_alt"]
        beklenen = {"v1_0", "v1_1", "v1_2", "v1_3", "v1_4", "v1_5", "v1_6", "yas1", "yas2", "yas3",
                    "ard2_kucuk", "ard2_buyuk", "ard3_kucuk", "ard3_ortanca", "ard3_buyuk",
                    "cift_kucuk", "cift_buyuk", "para", "yari", "ucte", "yari_fazla", "ucte_eksik"}
        self.assertEqual(set(alt), beklenen)
        for s in self.satirlar:
            if s["meta"]["tip"] == "sozel":
                x = F(s["meta"]["cevap"])
                self.assertEqual(x.denominator, 1)
                self.assertGreater(x, 0)
        yas = [s for s in self.satirlar if "yaşında" in s["messages"][0]["content"]
               or "yaşının" in s["messages"][0]["content"]]
        for s in yas:
            self.assertLessEqual(int(s["meta"]["cevap"]), 90)
        buyuk = [s for s in self.satirlar
                 if s["messages"][0]["content"].startswith("Ardışık iki tam")
                 and s["messages"][0]["content"].endswith("Büyük sayı kaçtır?")]
        self.assertTrue(buyuk)
        for s in buyuk:
            self.assertEqual(int(s["meta"]["aranan"]), int(s["meta"]["cevap"]) + 1)

    def test_yeni_tipler_ve_kesir(self):
        t15 = [s for s in self.satirlar if s["meta"]["tip"] == "t15"]
        self.assertTrue(any(s["messages"][1]["content"].split("\n")[2].startswith("1. adım: Terimleri düzenleyelim.")
                            for s in t15))
        for s in t15:
            sol, sag = s["meta"]["denklem"].split(" = ")
            self.assertTrue(re.search(r"[A-Za-z]", sol) and re.search(r"[A-Za-z]", sag))
        self.assertTrue(any("/" in s["meta"]["cevap"] for s in t15))
        t16 = [s for s in self.satirlar if s["meta"]["tip"] == "t16"]
        for s in t16:
            self.assertIn("Benzer terimleri birleştirelim:", s["messages"][1]["content"])
        self.assertTrue(any("/" in s["meta"]["cevap"] for s in self.satirlar if s["meta"]["tip"] != "sozel"))
        self.assertTrue(any("1. adım: Paydalardan" in s["messages"][1]["content"] for s in self.satirlar))


# --------------------------------------------------------------------------
# Sizinti ve determinizm
# --------------------------------------------------------------------------
def yapi(s):
    return uret_v2.yapi_anahtari(s["meta"]["denklem"], s["meta"]["degisken"], s["meta"]["tip"])


def v1_anahtarlar():
    out = set()
    for ad in ("val", "test"):
        with open(os.path.join(KOK, "data", ad + ".jsonl"), encoding="utf-8") as f:
            for satir in f:
                s = json.loads(satir)
                out.add(yapi(s))
    return out


class SizintiTest(unittest.TestCase):
    def test_v1_ve_bolmeler_arasi(self):
        v1 = v1_anahtarlar()
        self.assertGreater(len(v1), 700)
        bol, ist = uret_v2.uret_hepsi(42, 2500, 150, 250)
        k = {ad: {yapi(s) for s in satir} for ad, satir in bol.items()}
        for ad in k:
            self.assertFalse(k[ad] & v1, ad)
            # ham metin (harfli) kanonik denklem de v1'de yok
            ham = {s["meta"]["denklem"] for s in bol[ad]}
            self.assertFalse(ham & v1, ad)
        self.assertFalse(k["train"] & k["val"])
        self.assertFalse(k["train"] & k["test"])
        self.assertFalse(k["val"] & k["test"])
        # v1'in alttaki sozel denklemleri de yok (siki yasak)
        yasak = uret_v2.v1_yasaklari()
        for ad in k:
            self.assertFalse(k[ad] & yasak, ad)
        self.assertGreater(ist["yasak_elenen"], 0)  # yasak gercekten devreye giriyor

    def test_yasak_devrede(self):
        # v1 test'teki bir denklem bu motorda uretilebilir ama dagitilmaz
        self.assertIn("3(x + 53) = 4(x + 62)", v1_anahtarlar())
        self.assertIn("3(x + 53) = 4(x + 62)", uret_v2.v1_yasaklari())


class TekrarTest(unittest.TestCase):
    def test_determinizm_ve_dosyalar(self):
        with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
            args = ["--seed", "11", "--train", "400", "--val", "40", "--test", "60"]
            uret_v2.main(args + ["--out", t1])
            uret_v2.main(args + ["--out", t2])
            anahtarlar = {}
            for ad, adet in (("train", 400), ("val", 40), ("test", 60)):
                bs = []
                for dosya in (ad + ".jsonl", ad + "_messages.jsonl"):
                    if dosya == "test_messages.jsonl":
                        continue
                    with open(os.path.join(t1, dosya), "rb") as f:
                        b1 = f.read()
                    with open(os.path.join(t2, dosya), "rb") as f:
                        b2 = f.read()
                    self.assertEqual(b1, b2, dosya)
                    self.assertFalse(b1.startswith(b"\xef\xbb\xbf"))
                    self.assertNotIn(b"\r", b1)
                    self.assertTrue(b1.endswith(b"\n"))
                    self.assertNotIn(b"\\u", b1)
                    bs.append(b1.decode("utf-8").split("\n")[:-1])
                tam = [json.loads(x) for x in bs[0]]
                self.assertEqual(len(tam), adet)
                anahtarlar[ad] = [s["meta"]["denklem"] for s in tam]
                self.assertEqual(len(set(anahtarlar[ad])), adet)
                if len(bs) > 1:  # meta'siz kopya
                    kopya = [json.loads(x) for x in bs[1]]
                    self.assertEqual(kopya, [{"messages": s["messages"]} for s in tam])
            self.assertFalse(set(anahtarlar["train"]) & set(anahtarlar["val"]))
            self.assertFalse(set(anahtarlar["train"]) & set(anahtarlar["test"]))
            self.assertFalse(set(anahtarlar["val"]) & set(anahtarlar["test"]))
            self.assertFalse(os.path.exists(os.path.join(t1, "test_messages.jsonl")))

    def test_farkli_seed(self):
        a, _ = uret_v2.uret_hepsi(1, 50, 5, 5)
        b, _ = uret_v2.uret_hepsi(2, 50, 5, 5)
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()

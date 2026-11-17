# -*- coding: utf-8 -*-
import json
import os
import re
import sys
import tempfile
import unittest
from fractions import Fraction as F

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
import uret  # noqa: E402
from uret import T, P, FP  # noqa: E402


# --------------------------------------------------------------------------
# Bagimsiz ayristirici/cozucu: metin -> (A, B) dogrusal form
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
    """'sol = sag' -> 'yok' | 'sonsuz' | Fraction ; ayrica taraf formlari"""
    sol, sag = metin.split(" = ") if " = " in metin else metin.split("=")
    (al, bl), (ar, br) = ayristir(sol, v), ayristir(sag, v)
    a, b = al - ar, br - bl
    if a == 0:
        return "yok" if b != 0 else "sonsuz"
    return F(b) / F(a)


def taraf_formlari(metin, v):
    sol, sag = metin.split(" = ") if " = " in metin else metin.split("=")
    return ayristir(sol, v), ayristir(sag, v)


def metin(sol, sag, v="x"):
    return uret.asistan_metni(sol, sag, v)[0]


class YonelmeEkiTest(unittest.TestCase):
    def test_tablo(self):
        beklenen = {
            1: "e", 2: "ye", 3: "e", 4: "e", 5: "e", 6: "ya", 7: "ye", 8: "e", 9: "a", 10: "a",
            20: "ye", 30: "a", 40: "a", 50: "ye", 60: "a", 70: "e", 80: "e", 90: "a",
            100: "e", 12: "ye", 36: "ya", 45: "e", -3: "e", 200: "e", 1000: "e",
        }
        for n, ek in beklenen.items():
            self.assertEqual(uret.yonelme_eki(n), ek, n)

    def test_isaret_basta(self):
        self.assertEqual(uret.sayi_yonelme(-3), "-3'e")
        self.assertEqual(uret.sayi_yonelme(-6), "-6'ya")
        self.assertEqual(uret.sayi_yonelme(7), "7'ye")
        self.assertEqual(uret.sayi_yonelme(100), "100'e")


SABLON_ORNEGI = """Denklem: 3x + 5 = 20

1. adım: Sabit terimi sağa geçirmek için her iki taraftan 5 çıkaralım.
3x = 20 - 5
3x = 15

2. adım: Her iki tarafı 3'e bölelim.
x = 15/3
x = 5

Sağlama: x = 5 için sol taraf 3·5 + 5 = 20, sağ taraf 20. Eşitlik sağlanıyor.

Sonuç: x = 5"""


class ElleYazilmisTest(unittest.TestCase):
    def kontrol(self, sol, sag, beklenen, v="x"):
        self.assertEqual(metin(sol, sag, v), beklenen)

    def test_sablon(self):
        self.kontrol([T(3), T(5, False)], [T(20, False)], SABLON_ORNEGI)

    def test_5x3_2x9(self):
        self.kontrol(
            [T(5), T(3, False)], [T(2), T(9, False)],
            """Denklem: 5x + 3 = 2x + 9

1. adım: Bilinmeyenli terimleri solda toplamak için her iki taraftan 2x çıkaralım.
5x - 2x + 3 = 9
3x + 3 = 9

2. adım: Sabit terimi sağa geçirmek için her iki taraftan 3 çıkaralım.
3x = 9 - 3
3x = 6

3. adım: Her iki tarafı 3'e bölelim.
x = 6/3
x = 2

Sağlama: x = 2 için sol taraf 5·2 + 3 = 13, sağ taraf 2·2 + 9 = 13. Eşitlik sağlanıyor.

Sonuç: x = 2""")

    def test_parantez(self):
        self.kontrol(
            [P(2, [T(1), T(3, False)])], [T(10, False)],
            """Denklem: 2(x + 3) = 10

1. adım: Parantezleri açalım (dağılma özelliği).
2x + 6 = 10

2. adım: Sabit terimi sağa geçirmek için her iki taraftan 6 çıkaralım.
2x = 10 - 6
2x = 4

3. adım: Her iki tarafı 2'ye bölelim.
x = 4/2
x = 2

Sağlama: x = 2 için sol taraf 2·(2 + 3) = 10, sağ taraf 10. Eşitlik sağlanıyor.

Sonuç: x = 2""")

    def test_taraf_degistir(self):
        self.kontrol(
            [T(20, False)], [T(3), T(5, False)],
            """Denklem: 20 = 3x + 5

1. adım: Bilinmeyen sağ tarafta; tarafların yerini değiştirelim.
3x + 5 = 20

2. adım: Sabit terimi sağa geçirmek için her iki taraftan 5 çıkaralım.
3x = 20 - 5
3x = 15

3. adım: Her iki tarafı 3'e bölelim.
x = 15/3
x = 5

Sağlama: x = 5 için sol taraf 20, sağ taraf 3·5 + 5 = 20. Eşitlik sağlanıyor.

Sonuç: x = 5""")

    def test_kesirli_terim(self):
        self.kontrol(
            [T(F(1, 3)), T(2, False)], [T(5, False)],
            """Denklem: x/3 + 2 = 5

1. adım: Paydalardan kurtulmak için her iki tarafı 3 ile çarpalım.
x + 6 = 15

2. adım: Sabit terimi sağa geçirmek için her iki taraftan 6 çıkaralım.
x = 15 - 6
x = 9

Sağlama: x = 9 için sol taraf 9/3 + 2 = 5, sağ taraf 5. Eşitlik sağlanıyor.

Sonuç: x = 9""")

    def test_kesirli_parantez(self):
        self.kontrol(
            [FP([T(1), T(3, False)], 2)], [T(5, False)],
            """Denklem: (x + 3)/2 = 5

1. adım: Paydalardan kurtulmak için her iki tarafı 2 ile çarpalım.
x + 3 = 10

2. adım: Sabit terimi sağa geçirmek için her iki taraftan 3 çıkaralım.
x = 10 - 3
x = 7

Sağlama: x = 7 için sol taraf (7 + 3)/2 = 5, sağ taraf 5. Eşitlik sağlanıyor.

Sonuç: x = 7""")

    def test_negatif_bas_katsayi(self):
        self.kontrol(
            [T(-2), T(7, False)], [T(1, False)],
            """Denklem: -2x + 7 = 1

1. adım: Sabit terimi sağa geçirmek için her iki taraftan 7 çıkaralım.
-2x = 1 - 7
-2x = -6

2. adım: Her iki tarafı -2'ye bölelim.
x = -6/(-2)
x = 3

Sağlama: x = 3 için sol taraf -2·3 + 7 = 1, sağ taraf 1. Eşitlik sağlanıyor.

Sonuç: x = 3""")

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

1. adım: Parantezleri açalım (dağılma özelliği).
2x + 6 = 2x + 6

2. adım: Bilinmeyenli terimleri solda toplamak için her iki taraftan 2x çıkaralım.
2x - 2x + 6 = 6

Bilinmeyen sadeleşti ve geriye 6 = 6 kaldı. Bu eşitlik her zaman doğrudur.

Sonuç: Denklem her x değeri için sağlanır (sonsuz çözüm vardır).""")

    def test_kesir_cevap(self):
        self.kontrol(
            [T(4), T(1, False)], [T(8, False)],
            """Denklem: 4x + 1 = 8

1. adım: Sabit terimi sağa geçirmek için her iki taraftan 1 çıkaralım.
4x = 8 - 1
4x = 7

2. adım: Her iki tarafı 4'e bölelim.
x = 7/4

Sağlama: x = 7/4 için sol taraf 4·(7/4) + 1 = 8, sağ taraf 8. Eşitlik sağlanıyor.

Sonuç: x = 7/4""")

    def test_2x3_5x_9(self):
        self.kontrol(
            [T(2), T(3, False)], [T(5), T(-9, False)],
            """Denklem: 2x + 3 = 5x - 9

1. adım: Bilinmeyenli terimleri solda toplamak için her iki taraftan 5x çıkaralım.
2x - 5x + 3 = -9
-3x + 3 = -9

2. adım: Sabit terimi sağa geçirmek için her iki taraftan 3 çıkaralım.
-3x = -9 - 3
-3x = -12

3. adım: Her iki tarafı -3'e bölelim.
x = -12/(-3)
x = 4

Sağlama: x = 4 için sol taraf 2·4 + 3 = 11, sağ taraf 5·4 - 9 = 11. Eşitlik sağlanıyor.

Sonuç: x = 4""")

    def test_x2_x3(self):
        self.kontrol(
            [T(F(1, 2)), T(F(1, 3))], [T(5, False)],
            """Denklem: x/2 + x/3 = 5

1. adım: Paydalardan kurtulmak için her iki tarafı 6 ile çarpalım.
3x + 2x = 30

2. adım: Benzer terimleri birleştirelim.
5x = 30

3. adım: Her iki tarafı 5'e bölelim.
x = 30/5
x = 6

Sağlama: x = 6 için sol taraf 6/2 + 6/3 = 5, sağ taraf 5. Eşitlik sağlanıyor.

Sonuç: x = 6""")

    def test_pay_katsayili(self):
        self.kontrol(
            [T(F(3, 4)), T(-2, False)], [T(4, False)],
            """Denklem: 3x/4 - 2 = 4

1. adım: Paydalardan kurtulmak için her iki tarafı 4 ile çarpalım.
3x - 8 = 16

2. adım: Sabit terimi sağa geçirmek için her iki tarafa 8 ekleyelim.
3x = 16 + 8
3x = 24

3. adım: Her iki tarafı 3'e bölelim.
x = 24/3
x = 8

Sağlama: x = 8 için sol taraf 3·8/4 - 2 = 4, sağ taraf 4. Eşitlik sağlanıyor.

Sonuç: x = 8""")

    def test_eksi_parantez(self):
        self.kontrol(
            [P(-1, [T(1), T(-2, False)])], [T(5, False)],
            """Denklem: -(x - 2) = 5

1. adım: Parantezleri açalım (dağılma özelliği).
-x + 2 = 5

2. adım: Sabit terimi sağa geçirmek için her iki taraftan 2 çıkaralım.
-x = 5 - 2
-x = 3

3. adım: Her iki tarafı -1 ile çarpalım.
x = -3

Sağlama: x = -3 için sol taraf -(-3 - 2) = 5, sağ taraf 5. Eşitlik sağlanıyor.

Sonuç: x = -3""")

    def test_sagda_negatif_katsayi(self):
        self.kontrol(
            [T(5), T(3, False)], [T(-2), T(17, False)],
            """Denklem: 5x + 3 = -2x + 17

1. adım: Bilinmeyenli terimleri solda toplamak için her iki tarafa 2x ekleyelim.
5x + 2x + 3 = 17
7x + 3 = 17

2. adım: Sabit terimi sağa geçirmek için her iki taraftan 3 çıkaralım.
7x = 17 - 3
7x = 14

3. adım: Her iki tarafı 7'ye bölelim.
x = 14/7
x = 2

Sağlama: x = 2 için sol taraf 5·2 + 3 = 13, sağ taraf -2·2 + 17 = 13. Eşitlik sağlanıyor.

Sonuç: x = 2""")

    def test_sadelesen_kesir(self):
        self.kontrol(
            [T(6), T(1, False)], [T(10, False)],
            """Denklem: 6x + 1 = 10

1. adım: Sabit terimi sağa geçirmek için her iki taraftan 1 çıkaralım.
6x = 10 - 1
6x = 9

2. adım: Her iki tarafı 6'ya bölelim.
x = 9/6
x = 3/2

Sağlama: x = 3/2 için sol taraf 6·(3/2) + 1 = 10, sağ taraf 10. Eşitlik sağlanıyor.

Sonuç: x = 3/2""")

    def test_negatif_kesir(self):
        self.kontrol(
            [T(-3), T(1, False)], [T(8, False)],
            """Denklem: -3x + 1 = 8

1. adım: Sabit terimi sağa geçirmek için her iki taraftan 1 çıkaralım.
-3x = 8 - 1
-3x = 7

2. adım: Her iki tarafı -3'e bölelim.
x = 7/(-3)
x = -7/3

Sağlama: x = -7/3 için sol taraf -3·(-7/3) + 1 = 8, sağ taraf 8. Eşitlik sağlanıyor.

Sonuç: x = -7/3""")

    def test_sira_duzenle_ve_harf(self):
        self.kontrol(
            [T(5, False), T(2)], [T(9, False)],
            """Denklem: 5 + 2y = 9

1. adım: Terimleri düzenleyelim.
2y + 5 = 9

2. adım: Sabit terimi sağa geçirmek için her iki taraftan 5 çıkaralım.
2y = 9 - 5
2y = 4

3. adım: Her iki tarafı 2'ye bölelim.
y = 4/2
y = 2

Sağlama: y = 2 için sol taraf 5 + 2·2 = 9, sağ taraf 9. Eşitlik sağlanıyor.

Sonuç: y = 2""", v="y")

    def test_sozel(self):
        self.assertEqual(
            uret.asistan_metni([T(3), T(5, False)], [T(20, False)], "x", sozel=True)[0],
            "Bilinmeyen sayıya x diyelim.\n\n" + SABLON_ORNEGI.replace("Sonuç: x = 5", "Sonuç: x = 5 (aranan sayı 5)"),
        )

    def test_ardisik(self):
        self.kontrol(
            [T(1), T(1), T(1, False)], [T(21, False)],
            """Denklem: x + x + 1 = 21

1. adım: Benzer terimleri birleştirelim.
2x + 1 = 21

2. adım: Sabit terimi sağa geçirmek için her iki taraftan 1 çıkaralım.
2x = 21 - 1
2x = 20

3. adım: Her iki tarafı 2'ye bölelim.
x = 20/2
x = 10

Sağlama: x = 10 için sol taraf 10 + 10 + 1 = 21, sağ taraf 21. Eşitlik sağlanıyor.

Sonuç: x = 10""")

    def test_saglama_patlar(self):
        with self.assertRaises(AssertionError):
            uret.saglama([T(2), T(1, False)], [T(8, False)], F(3), "x")


class KotaTest(unittest.TestCase):
    def test_kotalar(self):
        for n in (100, 1000, 8900, 273):
            k = uret.kotalar(n)
            self.assertEqual(sum(k), n)
        k = uret.kotalar(8900)
        self.assertEqual(k[3], 8900 * 14 // 100)  # t4


SONUC_RE = re.compile(r"^Sonuç: (\S+) = (-?\d+(?:/\d+)?)(?: \(aranan sayı (-?\d+(?:/\d+)?)\))?$")
SAGLAMA_RE = re.compile(r"^Sağlama: (\S+) = (-?\d+(?:/\d+)?) için sol taraf (.+), sağ taraf (.+)\. Eşitlik sağlanıyor\.$")


def sablon_regex(sablon, v):
    desen = re.escape(sablon)
    desen = desen.replace(re.escape("{eq}"), "(?P<eq>.+?)")
    desen = desen.replace(re.escape("{v_belirtme}"), re.escape(uret.BELIRTME[v]))
    desen = desen.replace(re.escape("{v}"), re.escape(v))
    return re.compile("^" + desen + "$")


def kullanici_denklemi(mesaj, v):
    # en cok sabit metni olan sablon once (yoksa "{eq}" her seyi yutar)
    for s in sorted(uret.SABLONLAR, key=lambda t: -len(t.replace("{eq}", ""))):
        m = sablon_regex(s, v).match(mesaj)
        if m and "=" in m.group("eq"):
            return m.group("eq")
    raise AssertionError(f"şablon bulunamadı: {mesaj!r}")


def ifade_degeri(metin):
    """Degiskensiz ifade ('3·(-5) + 2') degeri."""
    a, b = ayristir(metin, "\0")
    assert a == 0
    return b


class RastgeleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bol, cls.ist = uret.uret_hepsi(7, 2600, 200, 200)
        cls.satirlar = cls.bol["train"] + cls.bol["val"] + cls.bol["test"]

    def test_3000_ornek(self):
        self.assertEqual(len(self.satirlar), 3000)
        for s in self.satirlar:
            meta = s["meta"]
            v = meta["degisken"]
            user, asst = s["messages"][0]["content"], s["messages"][1]["content"]
            satirlar = asst.split("\n")
            dl = [x for x in satirlar if x.startswith("Denklem: ")]
            self.assertEqual(len(dl), 1, asst)
            denk = dl[0][len("Denklem: "):]
            beklenen = denklem_coz(denk, v)
            # meta
            if beklenen in ("yok", "sonsuz"):
                self.assertEqual(meta["cevap"], beklenen)
            else:
                self.assertEqual(F(meta["cevap"]), beklenen)
                self.assertEqual(meta["cevap"], str(beklenen))
            if meta["tip"] != "sozel":
                self.assertEqual(meta["denklem"], denk)
            else:
                self.assertEqual(meta["denklem"], user)
                self.assertEqual(v, "x")
                self.assertTrue(asst.startswith("Bilinmeyen sayıya x diyelim.\n\nDenklem: "))
            # Sonuc
            son = satirlar[-1]
            if beklenen == "yok":
                self.assertEqual(son, "Sonuç: Denklemin çözümü yoktur (çözüm kümesi boş kümedir).")
            elif beklenen == "sonsuz":
                self.assertEqual(son, f"Sonuç: Denklem her {v} değeri için sağlanır (sonsuz çözüm vardır).")
            else:
                m = SONUC_RE.match(son)
                self.assertIsNotNone(m, son)
                self.assertEqual(m.group(1), v)
                self.assertEqual(F(m.group(2)), beklenen)
                if meta["tip"] == "sozel":
                    self.assertEqual(m.group(3), m.group(2))
                else:
                    self.assertIsNone(m.group(3))
            # ara satirlar
            for x in satirlar:
                if "=" not in x or x.startswith(("Denklem:", "Sağlama", "Sonuç", "Bilinmeyen sadeleşti")):
                    continue
                self.assertEqual(denklem_coz(x, v), beklenen, (x, asst))
            # ozel durum: saglama yok; digerlerinde var
            ozel = beklenen in ("yok", "sonsuz")
            self.assertEqual(any(x.startswith("Sağlama") for x in satirlar), not ozel)
            if ozel:
                self.assertTrue(any(x.startswith("Bilinmeyen sadeleşti") for x in satirlar))
            else:
                self.assertFalse(any(x.startswith("Bilinmeyen sadeleşti") for x in satirlar))
                sg = [x for x in satirlar if x.startswith("Sağlama")]
                self.assertEqual(len(sg), 1)
                m = SAGLAMA_RE.match(sg[0])
                self.assertIsNotNone(m, sg[0])
                self.assertEqual(F(m.group(2)), beklenen)
                for taraf in (m.group(3), m.group(4)):
                    # taraf: "ifade" ya da "ifade = deger"
                    if " = " in taraf:
                        ifade, deger = taraf.rsplit(" = ", 1)
                        self.assertEqual(ifade_degeri(ifade), F(deger))
                    else:
                        ifade, deger = taraf, None
                    self.assertNotIn("\0", ifade)
                v1 = m.group(3).rsplit(" = ", 1)[-1] if " = " in m.group(3) else None
                # her iki tarafin degeri esit
                def deg(t):
                    return F(t.rsplit(" = ", 1)[1]) if " = " in t else ifade_degeri(t)
                self.assertEqual(deg(m.group(3)), deg(m.group(4)))
            # adim numaralari
            nos = [int(re.match(r"(\d+)\. adım:", x).group(1)) for x in satirlar if re.match(r"\d+\. adım:", x)]
            self.assertEqual(nos, list(range(1, len(nos) + 1)))
            self.assertGreaterEqual(len(nos), 1)
            # kullanici mesaji (sozel disinda) ayni denklemi icerir
            if meta["tip"] != "sozel":
                ue = kullanici_denklemi(user, v)
                self.assertEqual(taraf_formlari(ue, v), taraf_formlari(denk, v), (user, denk))
            # sistem mesaji yok, anahtarlar
            self.assertEqual([m["role"] for m in s["messages"]], ["user", "assistant"])
            self.assertEqual(set(meta), {"tip", "denklem", "cevap", "degisken"})

    def test_kullanici_stilleri(self):
        u = uret.Uretec(5)
        n = 0
        for tip, _, gen in uret.TIPLER:
            if tip == "sozel":
                continue
            for _ in range(60):
                res = None
                while res is None:
                    res = gen(u, False, False)
                sol, sag = res
                v = "x"
                kan = taraf_formlari(uret.esit(sol, sag, v), v)
                for stil, _w in uret.STILLER:
                    metin_ = uret.kullanici_denklem(sol, sag, v, stil)
                    self.assertEqual(taraf_formlari(metin_, v), kan, (stil, metin_))
                    n += 1
        self.assertGreater(n, 500)
        # bicim ozellikleri
        sol, sag = [T(3), T(5, False)], [T(20, False)]
        self.assertEqual(uret.kullanici_denklem(sol, sag, "x", "bosluksuz"), "3x+5=20")
        self.assertEqual(uret.kullanici_denklem(sol, sag, "x", "yildiz"), "3*x + 5 = 20")
        self.assertEqual(uret.kullanici_denklem([P(2, [T(1), T(3, False)])], [T(10, False)], "x", "yildiz"), "2*(x + 3) = 10")
        self.assertEqual(uret.kullanici_denklem([T(3), T(-5, False)], [T(20, False)], "x", "unicode_eksi"), "3x − 5 = 20")
        self.assertEqual(uret.kullanici_denklem(sol, sag, "x", "esit_bitisik"), "3x + 5=20")

    def test_dagilim(self):
        n = len(self.satirlar)
        sayac = {}
        for s in self.satirlar:
            sayac[s["meta"]["tip"]] = sayac.get(s["meta"]["tip"], 0) + 1
        for (tip, w, _), k in zip(uret.TIPLER, uret.kotalar(n)):
            self.assertEqual(sayac[tip], k)
            self.assertAlmostEqual(k / n * 100, w, delta=0.5)


class TekrarTest(unittest.TestCase):
    def test_determinizm_ve_sizinti(self):
        with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
            args = ["--seed", "11", "--train", "300", "--val", "40", "--test", "60"]
            uret.main(args + ["--out", t1])
            uret.main(args + ["--out", t2])
            anahtarlar = {}
            for ad, adet in (("train", 300), ("val", 40), ("test", 60)):
                with open(os.path.join(t1, ad + ".jsonl"), "rb") as f:
                    b1 = f.read()
                with open(os.path.join(t2, ad + ".jsonl"), "rb") as f:
                    b2 = f.read()
                self.assertEqual(b1, b2)
                self.assertFalse(b1.startswith(b"\xef\xbb\xbf"))
                self.assertNotIn(b"\r", b1)
                self.assertTrue(b1.endswith(b"\n"))
                self.assertNotIn(b"\\u", b1)  # ensure_ascii=False
                satirlar = b1.decode("utf-8").split("\n")[:-1]
                self.assertEqual(len(satirlar), adet)
                anahtarlar[ad] = [json.loads(x)["meta"]["denklem"] for x in satirlar]
                self.assertEqual(len(set(anahtarlar[ad])), adet)
            self.assertFalse(set(anahtarlar["train"]) & set(anahtarlar["val"]))
            self.assertFalse(set(anahtarlar["train"]) & set(anahtarlar["test"]))
            self.assertFalse(set(anahtarlar["val"]) & set(anahtarlar["test"]))

    def test_farkli_seed(self):
        a, _ = uret.uret_hepsi(1, 50, 5, 5)
        b, _ = uret.uret_hepsi(2, 50, 5, 5)
        self.assertNotEqual(a, b)

    def test_buyuk_bolme_sizinti_yok(self):
        bol, _ = uret.uret_hepsi(42, 1500, 100, 150)
        k = {ad: {s["meta"]["denklem"] for s in satir} for ad, satir in bol.items()}
        self.assertFalse(k["train"] & k["val"])
        self.assertFalse(k["train"] & k["test"])
        self.assertFalse(k["val"] & k["test"])

        # harften bagimsiz da ortak yapi yok
        def norm(s):
            if s["meta"]["tip"] == "sozel":
                return s["meta"]["denklem"]
            return re.sub(r"(?<![A-Za-z])" + s["meta"]["degisken"] + r"(?![A-Za-z])", "x", s["meta"]["denklem"])

        n = {ad: {norm(s) for s in satir} for ad, satir in bol.items()}
        self.assertFalse(n["train"] & n["val"])
        self.assertFalse(n["train"] & n["test"])
        self.assertFalse(n["val"] & n["test"])


if __name__ == "__main__":
    unittest.main()

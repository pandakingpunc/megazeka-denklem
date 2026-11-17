#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Turkce, adim adim, birinci dereceden tek bilinmeyenli denklem cozme
veri ureteci (QLoRA icin sentetik egitim verisi).

Model cagrisi yok; her sey kodla uretilir, fractions.Fraction ile kesin hesaplanir.

Kullanim:
    py -3 src/uret.py --seed 42 --train 8000 --val 400 --test 500 --out data
"""
import argparse
import json
import math
import os
import random
import re
import sys
from fractions import Fraction as F

# --------------------------------------------------------------------------
# Atomlar
#   ('t', katsayi Fraction, degiskenli_mi)         terim
#   ('p', k int, (terimler,))                      k(terimler)
#   ('f', (terimler,), d int)                      (terimler)/d
# --------------------------------------------------------------------------


def T(c, var=True):
    return ("t", F(c), bool(var))


def P(k, terimler):
    return ("p", int(k), tuple(terimler))


def FP(terimler, d):
    return ("f", tuple(terimler), int(d))


# --------------------------------------------------------------------------
# Yazim
# --------------------------------------------------------------------------


def _terim_mutlak(c, var, v, star):
    """c >= 0 olan katsayi icin terimin isaretsiz metni."""
    if not var:
        return str(c)
    p, q = c.numerator, c.denominator
    if q == 1:
        if p == 1:
            return v
        return f"{p}*{v}" if star else f"{p}{v}"
    pay = v if p == 1 else (f"{p}*{v}" if star else f"{p}{v}")
    return f"{pay}/{q}"


def _atom_yaz(atom, v, star):
    """(negatif_mi, isaretsiz_metin)"""
    tur = atom[0]
    if tur == "t":
        c = atom[1]
        return c < 0, _terim_mutlak(abs(c), atom[2], v, star)
    if tur == "p":
        k = atom[1]
        ic = yaz(atom[2], v, star)
        if abs(k) == 1:
            govde = f"({ic})"
        else:
            govde = f"{abs(k)}*({ic})" if star else f"{abs(k)}({ic})"
        return k < 0, govde
    return False, f"({yaz(atom[1], v, star)})/{atom[2]}"


def _birlestir(parcalar):
    if not parcalar:
        return "0"
    out = ""
    for i, (neg, govde) in enumerate(parcalar):
        if i == 0:
            out += ("-" if neg else "") + govde
        else:
            out += (" - " if neg else " + ") + govde
    return out


def yaz(atomlar, v, star=False):
    return _birlestir([_atom_yaz(a, v, star) for a in atomlar])


def esit(sol, sag, v):
    return f"{yaz(sol, v)} = {yaz(sag, v)}"


# --------------------------------------------------------------------------
# Degerlendirme
# --------------------------------------------------------------------------


def ev(atomlar, x):
    s = F(0)
    for a in atomlar:
        if a[0] == "t":
            s += a[1] * (x if a[2] else 1)
        elif a[0] == "p":
            s += a[1] * ev(a[2], x)
        else:
            s += ev(a[1], x) / a[2]
    return s


def lin(atomlar):
    """Atom listesini A*x + B olarak dondurur."""
    b = ev(atomlar, F(0))
    return ev(atomlar, F(1)) - b, b


def kanon(a, b):
    out = []
    if a != 0:
        out.append(T(a))
    if b != 0:
        out.append(T(b, False))
    return out


def denklem_sonucu(sol, sag):
    """('yok'|'sonsuz'|Fraction)"""
    al, bl = lin(sol)
    ar, br = lin(sag)
    a, b = al - ar, br - bl
    if a == 0:
        return "yok" if b != 0 else "sonsuz"
    return b / a


# --------------------------------------------------------------------------
# Yonelme eki
# --------------------------------------------------------------------------

_BIRLER = {1: "e", 2: "ye", 3: "e", 4: "e", 5: "e", 6: "ya", 7: "ye", 8: "e", 9: "a"}
_ONLAR = {1: "a", 2: "ye", 3: "a", 4: "a", 5: "ye", 6: "a", 7: "e", 8: "e", 9: "a"}


def yonelme_eki(n):
    """Sayinin okunusuna gore yonelme eki (kesme isareti olmadan)."""
    n = abs(int(n))
    if n == 0:
        return "a"  # sifira
    if n % 10:
        return _BIRLER[n % 10]
    if n % 100:
        return _ONLAR[(n // 10) % 10]
    if n % 1000:
        return "e"  # yuz
    if n % 1000000:
        return "e"  # bin
    return "a"  # milyon


def sayi_yonelme(n):
    """-3 -> "-3'e" (isaret basta kalir)."""
    return f"{n}'{yonelme_eki(n)}"


# --------------------------------------------------------------------------
# Cozum motoru
# --------------------------------------------------------------------------


def cozum(sol, sag, v):
    """Adim adim cozer.

    Doner: (adimlar, ozel, ozel_cumle, sonuc)
      adimlar: [(aciklama, [satirlar])]
      ozel: None | 'yok' | 'sonsuz'
      sonuc: Fraction | None
    """
    adimlar = []
    L, R = list(sol), list(sag)

    # A. Paydalardan kurtul
    paydalar = []
    for taraf in (L, R):
        for a in taraf:
            if a[0] == "t":
                paydalar.append(a[1].denominator)
            elif a[0] == "f":
                paydalar.append(a[2])
    ekok = math.lcm(*paydalar) if paydalar else 1
    if ekok > 1:

        def carp(taraf):
            out = []
            for a in taraf:
                if a[0] == "t":
                    y = a[1] * ekok
                    assert y.denominator == 1
                    out.append(T(y, a[2]))
                elif a[0] == "p":
                    out.append(P(a[1] * ekok, a[2]))
                else:
                    k = ekok // a[2]
                    if k == 1:
                        out.extend(a[1])
                    else:
                        out.append(P(k, a[1]))
            return out

        L, R = carp(L), carp(R)
        adimlar.append(
            (f"Paydalardan kurtulmak için her iki tarafı {ekok} ile çarpalım.", [esit(L, R, v)])
        )

    # B. Parantezleri ac
    if any(a[0] == "p" for taraf in (L, R) for a in taraf):

        def ac(taraf):
            out = []
            for a in taraf:
                if a[0] == "p":
                    for tt in a[2]:
                        out.append(T(a[1] * tt[1], tt[2]))
                else:
                    out.append(a)
            return out

        L, R = ac(L), ac(R)
        adimlar.append(("Parantezleri açalım (dağılma özelliği).", [esit(L, R, v)]))

    # C. Benzer terimler / duzen
    birlestir = False
    duzenle = False
    for taraf in (L, R):
        vi = [i for i, a in enumerate(taraf) if a[2]]
        ci = [i for i, a in enumerate(taraf) if not a[2]]
        if len(vi) > 1 or len(ci) > 1:
            birlestir = True
        elif vi and ci and ci[0] < vi[0]:
            duzenle = True
    aL, bL = lin(L)
    aR, bR = lin(R)
    if birlestir or duzenle:
        L, R = kanon(aL, bL), kanon(aR, bR)
        aciklama = "Benzer terimleri birleştirelim." if birlestir else "Terimleri düzenleyelim."
        adimlar.append((aciklama, [esit(L, R, v)]))

    def ozel_son(bl, br):
        if bl != br:
            return (
                "yok",
                f"Bilinmeyen sadeleşti ve geriye {bl} = {br} kaldı. "
                "Bu eşitlik hiçbir zaman doğru değildir.",
            )
        return (
            "sonsuz",
            f"Bilinmeyen sadeleşti ve geriye {bl} = {br} kaldı. Bu eşitlik her zaman doğrudur.",
        )

    # Hic degisken kalmadiysa
    if aL == 0 and aR == 0:
        ozel, cumle = ozel_son(bL, bR)
        return adimlar, ozel, cumle, None

    # D. Degisken yalniz sagdaysa takas
    if aL == 0:
        aL, bL, aR, bR = aR, bR, aL, bL
        adimlar.append(
            (
                "Bilinmeyen sağ tarafta; tarafların yerini değiştirelim.",
                [f"{yaz(kanon(aL, bL), v)} = {yaz(kanon(aR, bR), v)}"],
            )
        )

    # E. Sagdaki degiskenli terimi sola topla
    if aR != 0:
        c = aR
        if c > 0:
            aciklama = (
                "Bilinmeyenli terimleri solda toplamak için her iki taraftan "
                f"{yaz([T(c)], v)} çıkaralım."
            )
        else:
            aciklama = (
                "Bilinmeyenli terimleri solda toplamak için her iki tarafa "
                f"{yaz([T(-c)], v)} ekleyelim."
            )
        islem_sol = [T(aL), T(-aR)] + ([T(bL, False)] if bL != 0 else [])
        satir1 = f"{yaz(islem_sol, v)} = {yaz(kanon(0, bR), v)}"
        a2 = aL - aR
        if a2 == 0:
            adimlar.append((aciklama, [satir1]))
            ozel, cumle = ozel_son(bL, bR)
            return adimlar, ozel, cumle, None
        satir2 = f"{yaz(kanon(a2, bL), v)} = {yaz(kanon(0, bR), v)}"
        adimlar.append((aciklama, [satir1, satir2]))
        aL, aR = a2, F(0)

    # F. Sabit terimi saga gecir
    if bL != 0:
        lhs = yaz([T(aL)], v)
        if bL > 0:
            aciklama = f"Sabit terimi sağa geçirmek için her iki taraftan {bL} çıkaralım."
            s1 = f"{lhs} = {bR} - {bL}"
        else:
            aciklama = f"Sabit terimi sağa geçirmek için her iki tarafa {-bL} ekleyelim."
            s1 = f"{lhs} = {bR} + {-bL}"
        bR = bR - bL
        bL = F(0)
        adimlar.append((aciklama, [s1, f"{lhs} = {bR}"]))

    # G. Katsayiya bol
    a = aL
    sonuc = bR / a
    if a == -1:
        adimlar.append(("Her iki tarafı -1 ile çarpalım.", [f"{v} = {sonuc}"]))
    elif a != 1:
        aciklama = f"Her iki tarafı {sayi_yonelme(int(a))} bölelim."
        if a > 0:
            s1 = f"{v} = {bR}/{a}"
            tam = sonuc.denominator == 1
            sade = math.gcd(abs(bR.numerator), int(a)) > 1
            if tam or sade:
                adimlar.append((aciklama, [s1, f"{v} = {sonuc}"]))
            else:
                adimlar.append((aciklama, [s1]))
        else:
            s1 = f"{v} = {bR}/({a})"
            adimlar.append((aciklama, [s1, f"{v} = {sonuc}"]))
    return adimlar, None, None, sonuc


# --------------------------------------------------------------------------
# Saglama
# --------------------------------------------------------------------------


def _par(x):
    return f"({x})" if (x < 0 or x.denominator != 1) else str(x)


def _atom_yerine(atom, x, ilk):
    tur = atom[0]
    if tur == "t":
        c, var = atom[1], atom[2]
        if not var:
            return c < 0, str(abs(c))
        neg = c < 0
        ac = abs(c)
        p, q = ac.numerator, ac.denominator
        if q == 1:
            if p == 1:
                if not neg:
                    govde = str(x) if ilk else (f"({x})" if x < 0 else str(x))
                else:
                    govde = _par(x)
            else:
                govde = f"{p}·{_par(x)}"
        else:
            pay = _par(x) if p == 1 else f"{p}·{_par(x)}"
            govde = f"{pay}/{q}"
        return neg, govde
    if tur == "p":
        k = atom[1]
        ic = yerine(atom[2], x)
        govde = f"({ic})" if abs(k) == 1 else f"{abs(k)}·({ic})"
        return k < 0, govde
    return False, f"({yerine(atom[1], x)})/{atom[2]}"


def yerine(atomlar, x):
    return _birlestir([_atom_yerine(a, x, i == 0) for i, a in enumerate(atomlar)])


def saglama(sol, sag, x, v):
    lv, rv = ev(sol, x), ev(sag, x)
    assert lv == rv, (yaz(sol, v), yaz(sag, v), x, lv, rv)

    def taraf(atomlar, deger):
        metin = yerine(atomlar, x)
        return metin if metin == str(deger) else f"{metin} = {deger}"

    return (
        f"Sağlama: {v} = {x} için sol taraf {taraf(sol, lv)}, "
        f"sağ taraf {taraf(sag, rv)}. Eşitlik sağlanıyor."
    )


# --------------------------------------------------------------------------
# Asistan metni
# --------------------------------------------------------------------------


def asistan_metni(sol, sag, v, sozel=False):
    """(metin, cevap_str)"""
    adimlar, ozel, cumle, sonuc = cozum(sol, sag, v)
    beklenen = denklem_sonucu(sol, sag)
    if ozel is None:
        assert sonuc == beklenen, (yaz(sol, v), yaz(sag, v), sonuc, beklenen)
    else:
        assert ozel == beklenen
    satirlar = []
    if sozel:
        satirlar += ["Bilinmeyen sayıya x diyelim.", ""]
    satirlar += [f"Denklem: {esit(sol, sag, v)}", ""]
    assert adimlar, "adım gerekmeyen denklem üretildi"
    for i, (aciklama, ls) in enumerate(adimlar, 1):
        satirlar.append(f"{i}. adım: {aciklama}")
        satirlar += ls
        satirlar.append("")
    if ozel is not None:
        satirlar += [cumle, ""]
        if ozel == "yok":
            satirlar.append("Sonuç: Denklemin çözümü yoktur (çözüm kümesi boş kümedir).")
        else:
            satirlar.append(f"Sonuç: Denklem her {v} değeri için sağlanır (sonsuz çözüm vardır).")
        return "\n".join(satirlar), ozel
    satirlar += [saglama(sol, sag, sonuc, v), ""]
    if sozel:
        satirlar.append(f"Sonuç: {v} = {sonuc} (aranan sayı {sonuc})")
    else:
        satirlar.append(f"Sonuç: {v} = {sonuc}")
    return "\n".join(satirlar), str(sonuc)


# --------------------------------------------------------------------------
# Kullanici mesaji
# --------------------------------------------------------------------------

BELIRTME = {"x": "x'i", "y": "y'yi", "a": "a'yı", "t": "t'yi", "n": "n'yi", "m": "m'yi", "z": "z'yi", "b": "b'yi"}
DIGER_HARFLER = ["y", "a", "t", "n", "m", "z", "b"]

SABLONLAR = [
    "{eq}",
    "{eq} denklemini çöz.",
    "Denklemi çöz: {eq}",
    "{eq} denkleminde {v} kaçtır?",
    "{eq} ise {v} kaçtır?",
    "{v_belirtme} bul: {eq}",
    "Şu denklemi adım adım çözer misin? {eq}",
    "{eq} denkleminin çözümünü adım adım göster.",
    "{eq} eşitliğini sağlayan {v} değerini bul.",
    "{eq} çöz",
    "bunu çözer misin {eq}",
    "{eq} denkleminin çözüm kümesi nedir?",
    "Adım adım çöz: {eq}",
    "{eq} denklemini çözüp sağlamasını yap.",
]

STILLER = [("kanonik", 55), ("bosluksuz", 30), ("yildiz", 8), ("unicode_eksi", 4), ("esit_bitisik", 3)]


def kullanici_denklem(sol, sag, v, stil):
    kan = esit(sol, sag, v)
    if stil == "kanonik":
        return kan
    if stil == "bosluksuz":
        return kan.replace(" ", "")
    if stil == "yildiz":
        return f"{yaz(sol, v, True)} = {yaz(sag, v, True)}"
    if stil == "unicode_eksi":
        return kan.replace("-", "−")
    if stil == "esit_bitisik":
        return f"{yaz(sol, v)}={yaz(sag, v)}"
    raise ValueError(stil)


def kullanici_mesaji(rng, sol, sag, v):
    r = rng.random() * 100
    acc = 0
    stil = STILLER[0][0]
    for ad, w in STILLER:
        acc += w
        if r < acc:
            stil = ad
            break
    eq = kullanici_denklem(sol, sag, v, stil)
    sablon = SABLONLAR[rng.randrange(len(SABLONLAR))]
    return sablon.format(eq=eq, v=v, v_belirtme=BELIRTME[v])


# --------------------------------------------------------------------------
# Denklem uretimi
# --------------------------------------------------------------------------


class Uretec:
    def __init__(self, seed):
        self.rng = random.Random(seed)

    # -- sayi ornekleyiciler
    def sol(self, big, nonzero=False):
        r = self.rng
        while True:
            if big:
                x = r.randint(-100, 100) if r.random() < 0.2 else r.choice([-1, 1]) * r.randint(21, 100)
            else:
                x = r.randint(-15, 20)
            if x == 0 and (nonzero or r.random() < 0.7):
                continue
            return x

    def cb(self, big):
        return 300 if big else 60

    def const(self, big, mx=None, neg_p=0.4):
        m = mx if mx else self.cb(big)
        v = self.rng.randint(1, m)
        return -v if self.rng.random() < neg_p else v

    def coef(self, signed=False):
        a = self.rng.randint(2, 12)
        if signed and self.rng.random() < 0.2:
            a = -a
        return a

    def pmx(self, big):  # parantez ici sabit buyuklugu
        return 60 if big else 20


def g_t1(u, big, frac):
    x0 = u.sol(big)
    b = u.const(big)
    c = x0 + b
    if abs(c) > u.cb(big):
        return None
    return [T(1), T(b, False)], [T(c, False)]


def g_t2(u, big, frac):
    a = u.coef(True)
    x0 = u.sol(big, True)
    c = a * x0
    if abs(c) > u.cb(big):
        return None
    return [T(a)], [T(c, False)]


def _kat_araligi(big, d):
    lo, hi = (-100, 100) if big else (-15, 20)
    return -((-lo) // d), hi // d


def g_t3(u, big, frac):
    d = u.rng.randint(2, 12)
    lo, hi = _kat_araligi(big, d)
    c = u.rng.randint(lo, hi)
    if c == 0:
        return None
    return [T(F(1, d))], [T(c, False)]


def g_t4(u, big, frac):
    a = u.rng.randint(2, 12)
    b = u.const(big)
    if frac:
        c = u.const(big)
        if (c - b) % a == 0:
            return None
    else:
        c = a * u.sol(big) + b
        if abs(c) > u.cb(big):
            return None
    return [T(a), T(b, False)], [T(c, False)]


def g_t5(u, big, frac):
    a = u.rng.randint(2, 12)
    b = u.const(big)
    c = a * u.sol(big) + b
    if abs(c) > u.cb(big):
        return None
    if u.rng.random() < 0.5:
        return [T(b, False), T(a)], [T(c, False)]
    return [T(c, False)], [T(a), T(b, False)]


def g_t6(u, big, frac):
    a, c = u.coef(True), u.coef(True)
    if a == c:
        return None
    b = u.const(big)
    if frac:
        d = u.const(big)
        if (d - b) % (a - c) == 0:
            return None
    else:
        d = b + (a - c) * u.sol(big)
        if d == 0 or abs(d) > u.cb(big):
            return None
    return [T(a), T(b, False)], [T(c), T(d, False)]


def g_t7(u, big, frac):
    a = u.coef(True)
    b = u.const(big, u.pmx(big))
    if frac:
        c = u.const(big)
        if c % a == 0:
            return None
    else:
        c = a * (u.sol(big) + b)
        if c == 0 or abs(c) > u.cb(big):
            return None
    return [P(a, [T(1), T(b, False)])], [T(c, False)]


def g_t8(u, big, frac):
    if u.rng.random() < 0.5:
        a, c = u.coef(True), u.coef(True)
        if a == c:
            return None
        b = u.const(big, u.pmx(big))
        d = (a - c) * u.sol(big) + a * b
        if d == 0 or abs(d) > u.cb(big):
            return None
        return [P(a, [T(1), T(b, False)])], [T(c), T(d, False)]
    a = u.coef(True)
    b = u.const(big, u.pmx(big))
    e = u.const(big)
    if a * b + e == 0:
        return None
    c = a * (u.sol(big) + b) + e
    if c == 0 or abs(c) > u.cb(big):
        return None
    return [P(a, [T(1), T(b, False)]), T(e, False)], [T(c, False)]


def g_t9(u, big, frac):
    a, c = u.coef(True), u.coef(True)
    if a == c:
        return None
    b = u.const(big, u.pmx(big))
    x0 = u.sol(big)
    num = a * (x0 + b)
    if num % c:
        return None
    d = num // c - x0  # a(x0 + b) = c(x0 + d)
    if d == 0 or abs(d) > u.cb(big):
        return None
    return [P(a, [T(1), T(b, False)])], [P(c, [T(1), T(d, False)])]


def g_t10(u, big, frac):
    r = u.rng
    if r.random() < 0.5:
        n, d = 1, r.randint(2, 12)
    else:
        d = r.randint(3, 12)
        n = r.choice([k for k in range(2, d) if math.gcd(k, d) == 1])
    lo, hi = _kat_araligi(big, d)
    m = r.randint(lo, hi)
    if m == 0:
        return None
    b = u.const(big)
    c = n * m + b
    if abs(c) > u.cb(big):
        return None
    return [T(F(n, d)), T(b, False)], [T(c, False)]


def g_t11(u, big, frac):
    d = u.rng.randint(2, 12)
    b = u.const(big, u.pmx(big))
    s = u.sol(big) + b
    if s % d or s == 0:
        return None
    return [FP([T(1), T(b, False)], d)], [T(s // d, False)]


def g_t12(u, big, frac):
    x0 = u.sol(big)
    if u.rng.random() < 0.5:
        a = u.rng.randint(2, 12)
        c = u.coef(True)
        b = u.const(big)
        if a + c == 0:
            return None
        d = (a + c) * x0 + b
        if abs(d) > u.cb(big):
            return None
        return [T(a), T(b, False), T(c)], [T(d, False)]
    a, c = u.rng.randint(2, 12), u.rng.randint(2, 12)
    if a == c:
        return None
    b, e = u.const(big), u.const(big)
    if b + e == 0:
        return None
    f = (a - c) * x0 + b + e
    if abs(f) > u.cb(big):
        return None
    return [T(a), T(b, False), T(-c), T(e, False)], [T(f, False)]


def g_t13(u, big, frac):
    a = u.rng.randint(2, 12)
    b = u.const(big)
    if frac:
        c = u.const(big)
        if (b - c) % a == 0:
            return None
    else:
        c = -a * u.sol(big) + b
        if abs(c) > u.cb(big):
            return None
    if u.rng.random() < 0.5:
        return [T(-a), T(b, False)], [T(c, False)]
    return [T(b, False), T(-a)], [T(c, False)]


def g_t14(u, big, frac):
    r = u.rng
    d1, d2 = r.randint(2, 12), r.randint(2, 12)
    if d1 == d2:
        return None
    p = d1 * d2
    adim = p // math.gcd(p, d1 + d2)
    lo, hi = (-100, 100) if big else (-15, 20)
    kmin, kmax = -((-lo) // adim), hi // adim
    if kmax < 1 and kmin > -1:
        return None
    k = r.randint(kmin, kmax)
    if k == 0:
        return None
    x0 = k * adim
    c = F(x0, d1) + F(x0, d2)
    assert c.denominator == 1
    return [T(F(1, d1)), T(F(1, d2))], [T(c, False)]


def g_ozel_yok(u, big, frac):
    r = u.rng
    k = r.randrange(3)
    a = u.coef(True)
    b = u.const(big, u.pmx(big))
    d = u.const(big)
    if k == 0:
        if b == d:
            return None
        return [T(a), T(b, False)], [T(a), T(d, False)]
    if k == 1:
        if d == a * b:
            return None
        return [P(a, [T(1), T(b, False)])], [T(a), T(d, False)]
    a = r.randint(2, 12)
    c = r.randint(2, 12)
    b = u.const(big)
    if d == b:
        return None
    return [T(a), T(b, False), T(c)], [T(a + c), T(d, False)]


def g_ozel_sonsuz(u, big, frac):
    r = u.rng
    k = r.randrange(4)
    a = u.coef(True)
    b = u.const(big, max(1, 60 // abs(a)))
    if k == 0:
        return [P(a, [T(1), T(b, False)])], [T(a), T(a * b, False)]
    if k == 1:
        return [T(a), T(a * b, False)], [P(a, [T(1), T(b, False)])]
    if k == 2:
        a, c = r.randint(2, 12), r.randint(2, 12)
        b = u.const(big)
        return [T(a), T(b, False), T(c)], [T(a + c), T(b, False)]
    e = u.const(big)
    if a * b + e == 0:
        return None
    return [P(a, [T(1), T(b, False)]), T(e, False)], [T(a), T(a * b + e, False)]


def g_sozel(u, big, frac):
    res = _g_sozel(u, big)
    if res is None:
        return None
    # normal modda sayilar kucuk kalsin
    if not big and max(int(n) for n in re.findall(r"\d+", res[2])) > 125:
        return None
    return res


def _g_sozel(u, big):
    r = u.rng
    k = r.randrange(8)
    hi = 100 if big else 40
    x0 = r.randint(1, hi)
    if k in (0, 4):
        a, b = r.randint(2, 12), r.randint(1, 60)
        c = a * x0 + b
        if k == 0:
            text = f"Bir sayının {a} katına {b} eklenince sonuç {c} oluyor. Bu sayı kaçtır?"
        else:
            text = f"Hangi sayının {a} katının {b} fazlası {c} eder?"
        return [T(a), T(b, False)], [T(c, False)], text
    if k in (1, 5):
        a, b = r.randint(2, 12), r.randint(1, 60)
        c = a * x0 - b
        if c <= 0:
            return None
        if k == 1:
            text = f"Bir sayının {a} katından {b} çıkarılınca sonuç {c} oluyor. Bu sayı kaçtır?"
        else:
            text = f"Hangi sayının {a} katının {b} eksiği {c} eder?"
        return [T(a), T(-b, False)], [T(c, False)], text
    if k == 2:
        a, b = r.randint(2, 12), r.randint(1, 20)
        c = a * (x0 + b)
        text = f"Bir sayıya {b} eklenip sonuç {a} ile çarpılınca {c} elde ediliyor. Bu sayı kaçtır?"
        return [P(a, [T(1), T(b, False)])], [T(c, False)], text
    if k == 3:
        a = r.randint(3, 12)
        c = r.randint(2, a - 1)
        d = (a - c) * x0
        text = f"Bir sayının {a} katı, aynı sayının {c} katından {d} fazladır. Bu sayı kaçtır?"
        return [T(a)], [T(c), T(d, False)], text
    if k == 6:
        x0 = 2 * r.randint(1, hi)
        b = r.randint(1, 60)
        c = x0 // 2 + b
        text = f"Bir sayının yarısına {b} eklenince sonuç {c} oluyor. Bu sayı kaçtır?"
        return [T(F(1, 2)), T(b, False)], [T(c, False)], text
    x0 = r.randint(1, 2 * hi)
    s = 2 * x0 + 1
    text = f"Ardışık iki tam sayının toplamı {s} ediyor. Küçük sayı kaçtır?"
    return [T(1), T(1), T(1, False)], [T(s, False)], text


TIPLER = [
    ("t1", 6, g_t1),
    ("t2", 6, g_t2),
    ("t3", 4, g_t3),
    ("t4", 14, g_t4),
    ("t5", 7, g_t5),
    ("t6", 13, g_t6),
    ("t7", 8, g_t7),
    ("t8", 7, g_t8),
    ("t9", 5, g_t9),
    ("t10", 5, g_t10),
    ("t11", 3, g_t11),
    ("t12", 6, g_t12),
    ("t13", 5, g_t13),
    ("t14", 2, g_t14),
    ("ozel_yok", 2, g_ozel_yok),
    ("ozel_sonsuz", 2, g_ozel_sonsuz),
    ("sozel", 5, g_sozel),
]
KESIRLI_TIPLER = {"t4", "t6", "t7", "t13"}
KESIR_ORANI = 0.30


def kotalar(toplam):
    """En buyuk kalan yontemiyle tip kotalari."""
    ham = [toplam * w / 100 for _, w, _ in TIPLER]
    taban = [int(h) for h in ham]
    kalan = toplam - sum(taban)
    sira = sorted(range(len(TIPLER)), key=lambda i: (-(ham[i] - taban[i]), i))
    for i in sira[:kalan]:
        taban[i] += 1
    return taban


def _buyuk_mu(sol, sag, sonuc):
    def gez(atomlar):
        for a in atomlar:
            if a[0] == "t":
                if not a[2] and abs(a[1]) > 60:
                    return True
            elif a[0] == "p":
                if abs(a[1]) > 12 or gez(a[2]):
                    return True
            else:
                if gez(a[1]):
                    return True
        return False

    if gez(sol) or gez(sag):
        return True
    return isinstance(sonuc, F) and abs(sonuc) > 20


def uret_hepsi(seed, n_train, n_val, n_test):
    """Doner: ({'train':[...], 'val':[...], 'test':[...]}, istatistik)"""
    u = Uretec(seed)
    rng = u.rng
    toplam = n_train + n_val + n_test
    gorulen = set()
    satirlar = []
    ist = {"tip": {}, "cevap": {"tamsayi": 0, "kesir": 0, "yok": 0, "sonsuz": 0}, "buyuk": 0, "kesirli_tip_kesir": 0, "stil": {}}
    for (tip, _, gen), kota in zip(TIPLER, kotalar(toplam)):
        ist["tip"][tip] = kota
        for _ in range(kota):
            kesir = tip in KESIRLI_TIPLER and rng.random() < KESIR_ORANI
            dup = 0
            toplam_deneme = 0
            while True:
                toplam_deneme += 1
                if toplam_deneme > 200000:
                    raise RuntimeError(f"{tip}: yeterli benzersiz denklem üretilemedi")
                pb = 0.08 if dup < 40 else (0.5 if dup < 300 else 1.0)
                big = rng.random() < pb
                v = "x" if (tip == "sozel" or rng.random() < 0.8) else rng.choice(DIGER_HARFLER)
                res = gen(u, big, kesir)
                if res is None:
                    continue
                if tip == "sozel":
                    sol, sag, metin = res
                    anahtar = metin
                else:
                    sol, sag = res
                    metin = None
                    anahtar = esit(sol, sag, v)
                if anahtar in gorulen:
                    dup += 1
                    continue
                break
            gorulen.add(anahtar)
            # harften bagimsiz yapi anahtari: bolmeler arasi yapi sizintisini onlemek icin
            yapi = metin if tip == "sozel" else esit(sol, sag, "x")
            asistan, cevap = asistan_metni(sol, sag, v, sozel=(tip == "sozel"))
            if tip == "sozel":
                kullanici = metin
            else:
                kullanici = kullanici_mesaji(rng, sol, sag, v)
            sonuc = denklem_sonucu(sol, sag)
            if cevap == "yok":
                ist["cevap"]["yok"] += 1
            elif cevap == "sonsuz":
                ist["cevap"]["sonsuz"] += 1
            elif "/" in cevap:
                ist["cevap"]["kesir"] += 1
            else:
                ist["cevap"]["tamsayi"] += 1
            if _buyuk_mu(sol, sag, sonuc):
                ist["buyuk"] += 1
            if tip in KESIRLI_TIPLER and "/" in cevap:
                ist["kesirli_tip_kesir"] += 1
            satirlar.append(
                (
                    yapi,
                    {
                        "messages": [
                            {"role": "user", "content": kullanici},
                            {"role": "assistant", "content": asistan},
                        ],
                        "meta": {
                            "tip": tip,
                            "denklem": anahtar,
                            "cevap": cevap,
                            "degisken": v,
                        },
                    },
                )
            )
    rng.shuffle(satirlar)
    # Ayni yapidaki (yalniz harfi farkli) denklemler hep ayni bolmeye gider.
    gruplar = {}
    for yapi, satir in satirlar:
        gruplar.setdefault(yapi, []).append(satir)
    havuz = list(gruplar.values())

    def al(hedef, havuz):
        secilen, kalan = [], []
        for g in havuz:
            if len(secilen) + len(g) <= hedef:
                secilen.extend(g)
            else:
                kalan.append(g)
        for g in kalan:  # nadir: tam sayiya grup bolmeden ulasilamadiysa
            while g and len(secilen) < hedef:
                secilen.append(g.pop())
        return secilen, kalan

    test, havuz = al(n_test, havuz)
    val, havuz = al(n_val, havuz)
    train = [s for g in havuz for s in g]
    rng.shuffle(train)
    assert len(train) == n_train and len(val) == n_val and len(test) == n_test
    return {"train": train, "val": val, "test": test}, ist


def yaz_jsonl(yol, satirlar):
    with open(yol, "w", encoding="utf-8", newline="\n") as f:
        for s in satirlar:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Denklem çözme veri üreteci")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--train", type=int, default=8000)
    ap.add_argument("--val", type=int, default=400)
    ap.add_argument("--test", type=int, default=500)
    ap.add_argument("--out", default="data")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    bol, ist = uret_hepsi(args.seed, args.train, args.val, args.test)
    os.makedirs(args.out, exist_ok=True)
    for ad, satirlar in bol.items():
        yaz_jsonl(os.path.join(args.out, f"{ad}.jsonl"), satirlar)
    toplam = args.train + args.val + args.test
    print(f"Toplam: {toplam}  (train {args.train}, val {args.val}, test {args.test})")
    print("Tip dağılımı (tüm bölmeler):")
    sayac = {}
    for satirlar in bol.values():
        for s in satirlar:
            sayac[s["meta"]["tip"]] = sayac.get(s["meta"]["tip"], 0) + 1
    for tip, _, _ in TIPLER:
        n = sayac.get(tip, 0)
        print(f"  {tip:12s} {n:5d}  %{100 * n / toplam:5.2f}")
    print("Cevap türü dağılımı:")
    for k, n in ist["cevap"].items():
        print(f"  {k:8s} {n:5d}  %{100 * n / toplam:5.2f}")
    print(f"Büyük sayılı örnek: {ist['buyuk']} (%{100 * ist['buyuk'] / toplam:.2f})")
    print(f"t4/t6/t7/t13 içinde kesir cevaplı: {ist['kesirli_tip_kesir']} (%{100 * ist['kesirli_tip_kesir'] / toplam:.2f} toplamın)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

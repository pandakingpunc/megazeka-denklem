#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Megazeka-Denklem v2 veri ureteci.

v1 motorunu (src/uret.py: atomlar, yazim, degerlendirme, v1 denklem
ureteclerinin cogu) import eder; v1 dosyasina ve v1 verisine dokunmaz.

v2 farklari:
  1. gorunur aritmetik (dagilma, payda carpimi, benzer terim, bolme ara hesabi)
  2. ara adimli saglama (zincir: yerine koyma -> parantez ici -> carpimlar -> toplam)
  3. yeni tipler t15 (sabit basta, iki tarafta bilinmeyen) ve t16 (3+ terimli karisik)
  4. genislemis sozel problemler (yas, ardisik sayilar, para, yari/ucte bir)
  5. daha cesitli kullanici mesaji sablonlari, %3 buyuk harfli degisken
  6. v1 val/test ile sizinti yasagi

Kullanim:
    py -3 src/uret_v2.py --seed 7 --train 12000 --val 500 --test 600 --out data/v2
"""
import argparse
import json
import math
import os
import random
import re
import sys
from collections import namedtuple
from fractions import Fraction as F

_SRC = os.path.dirname(os.path.abspath(__file__))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import uret  # noqa: E402
from uret import T, P, FP, yaz, esit, ev, lin, kanon, denklem_sonucu  # noqa: E402,F401

VARSAYILAN_V1_DIZIN = os.path.join(_SRC, "..", "data")

# --------------------------------------------------------------------------
# Uretec ici dogrusal ayristirici (yalniz assertion icin)
# --------------------------------------------------------------------------


def dogrusal(metin, v=None):
    """'3·(x + 2) - 4x' -> (A, B) dogrusal form. v=None ise degiskensiz."""
    metin = metin.replace("−", "-").replace("·", "*").replace(" ", "")
    tok = re.findall(r"\d+|[A-Za-z]|[-+*/()]", metin)
    assert "".join(tok) == metin, metin
    pos = [0]

    def bak():
        return tok[pos[0]] if pos[0] < len(tok) else None

    def al():
        t = tok[pos[0]]
        pos[0] += 1
        return t

    def carp(p, q):
        assert p[0] == 0 or q[0] == 0, ("dogrusal degil", metin)
        return (p[0] * q[1] + q[0] * p[1], p[1] * q[1])

    def carpan():
        t = al()
        if t.isdigit():
            return (F(0), F(int(t)))
        if v is not None and t == v:
            return (F(1), F(0))
        if t == "(":
            e = ifade()
            assert al() == ")", metin
            return e
        raise AssertionError(f"beklenmeyen simge {t!r} ({metin})")

    def terim():
        a = carpan()
        while True:
            t = bak()
            if t == "*":
                al()
                a = carp(a, carpan())
            elif t == "/":
                al()
                b = carpan()
                assert b[0] == 0 and b[1] != 0, metin
                a = (a[0] / b[1], a[1] / b[1])
            elif (v is not None and t == v) or t == "(":
                a = carp(a, carpan())
            else:
                return a

    def ifade():
        isaret = 1
        if bak() in ("+", "-"):
            isaret = -1 if al() == "-" else 1
        a = terim()
        a = (a[0] * isaret, a[1] * isaret)
        while bak() in ("+", "-"):
            op = al()
            b = terim()
            if op == "-":
                b = (-b[0], -b[1])
            a = (a[0] + b[0], a[1] + b[1])
        return a

    r = ifade()
    assert bak() is None, metin
    return r


def _hesap(sol, sag, v):
    """'sol = sag' ara hesabini dogrular, metni dondurur."""
    assert dogrusal(sol, v) == dogrusal(sag, v), (sol, sag)
    return f"{sol} = {sag}"


def _sayi_metni(toplam, var, v):
    if toplam == 0:
        return "0"
    return yaz([T(toplam, var)], v)


# --------------------------------------------------------------------------
# Cozum motoru (gorunur aritmetik)
# --------------------------------------------------------------------------


def _sar(atom, v):
    """Carpilan terimin parantezli yazimi (kesirli/negatifse parantez)."""
    m = yaz([atom], v)
    if atom[0] == "f" or m.startswith("-") or (atom[0] == "t" and "/" in m):
        return f"({m})"
    return m


def _par_terim(atom, v):
    m = yaz([atom], v)
    return f"({m})" if m.startswith("-") else m


def cozum(sol, sag, v):
    """Adim adim cozer.

    Doner: (adimlar, ozel, ozel_cumle, sonuc)
      adimlar: [(aciklama, [satirlar])]
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
        hesaplar = []

        def carp(taraf):
            out = []
            for a in taraf:
                if a[0] == "t":
                    y = a[1] * ekok
                    assert y.denominator == 1
                    yeni = T(y, a[2])
                    hesaplar.append(_hesap(f"{ekok}·{_sar(a, v)}", yaz([yeni], v), v))
                    out.append(yeni)
                elif a[0] == "p":
                    yeni = P(a[1] * ekok, a[2])
                    hesaplar.append(_hesap(f"{ekok}·{_sar(a, v)}", yaz([yeni], v), v))
                    out.append(yeni)
                else:
                    k = ekok // a[2]
                    if k == 1:
                        out.extend(a[1])
                        sonuc_m = yaz(a[1], v)
                    else:
                        yeni = P(k, a[1])
                        out.append(yeni)
                        sonuc_m = yaz([yeni], v)
                    hesaplar.append(_hesap(f"{ekok}·{_sar(a, v)}", sonuc_m, v))
            return out

        L, R = carp(L), carp(R)
        adimlar.append(
            (
                f"Paydalardan kurtulmak için her iki tarafı {ekok} ile çarpalım: "
                + ", ".join(hesaplar)
                + ".",
                [esit(L, R, v)],
            )
        )

    # B. Parantezleri ac
    if any(a[0] == "p" for taraf in (L, R) for a in taraf):
        hesaplar = []

        def ac(taraf):
            out = []
            for a in taraf:
                if a[0] == "p":
                    k = a[1]
                    for tt in a[2]:
                        yeni = T(k * tt[1], tt[2])
                        hesaplar.append(_hesap(f"{k}·{_par_terim(tt, v)}", yaz([yeni], v), v))
                        out.append(yeni)
                else:
                    out.append(a)
            return out

        L, R = ac(L), ac(R)
        adimlar.append(
            ("Parantezleri açalım (dağılma özelliği): " + ", ".join(hesaplar) + ".", [esit(L, R, v)])
        )

    # C. Benzer terimler / duzen
    birlestir = False
    duzenle = False
    hesaplar = []
    for taraf in (L, R):
        vi = [i for i, a in enumerate(taraf) if a[2]]
        ci = [i for i, a in enumerate(taraf) if not a[2]]
        if len(vi) > 1 or len(ci) > 1:
            birlestir = True
        elif vi and ci and ci[0] < vi[0]:
            duzenle = True
        for idx, var in ((vi, True), (ci, False)):
            if len(idx) > 1:
                grup = [taraf[i] for i in idx]
                toplam = sum((g[1] for g in grup), F(0))
                hesaplar.append(_hesap(yaz(grup, v), _sayi_metni(toplam, var, v), v))
    aL, bL = lin(L)
    aR, bR = lin(R)
    if birlestir or duzenle:
        L, R = kanon(aL, bL), kanon(aR, bR)
        if birlestir:
            aciklama = "Benzer terimleri birleştirelim: " + ", ".join(hesaplar) + "."
        else:
            aciklama = "Terimleri düzenleyelim."
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
        ai = int(a)
        aciklama = f"Her iki tarafı {uret.sayi_yonelme(ai)} bölelim."
        s1 = f"{v} = {bR}/{ai}" if ai > 0 else f"{v} = {bR}/({ai})"
        g = math.gcd(abs(bR.numerator), abs(ai))
        if sonuc.denominator == 1:
            assert ai * sonuc == bR
            s2 = f"{v} = {sonuc} (çünkü {ai}·{uret._par(sonuc)} = {bR})"
        elif g > 1:
            s2 = f"{v} = {sonuc} (pay ve payda {g} ile sadeleşti)"
        elif ai < 0:
            s2 = f"{v} = {sonuc}"
        else:
            s2 = None
        adimlar.append((aciklama, [s1] + ([s2] if s2 else [])))
    return adimlar, None, None, sonuc


# --------------------------------------------------------------------------
# Ara adimli saglama
# --------------------------------------------------------------------------


def _atom_b(atom, x, ilk):
    """Parantez icleri tek sayiya indirilmis hali: (negatif_mi, govde)."""
    tur = atom[0]
    if tur == "t":
        return uret._atom_yerine(atom, x, ilk)
    if tur == "p":
        k = atom[1]
        ic = ev(atom[2], x)
        govde = uret._par(ic) if abs(k) == 1 else f"{abs(k)}·{uret._par(ic)}"
        return k < 0, govde
    return False, f"{uret._par(ev(atom[1], x))}/{atom[2]}"


def _yerine_b(atomlar, x):
    return uret._birlestir([_atom_b(a, x, i == 0) for i, a in enumerate(atomlar)])


def _toplam_metni(degerler):
    out = ""
    for i, d in enumerate(degerler):
        if i == 0:
            out += str(d)
        else:
            out += f" - {-d}" if d < 0 else f" + {d}"
    return out


def taraf_zinciri(atomlar, x):
    """Bir tarafin sagalama zinciri (asama metinleri listesi)."""
    degerler = [ev([a], x) for a in atomlar]
    toplam = ev(atomlar, x)
    asamalar = [uret.yerine(atomlar, x)]
    if any(a[0] != "t" for a in atomlar):
        asamalar.append(_yerine_b(atomlar, x))
    asamalar.append(_toplam_metni(degerler))
    asamalar.append(str(toplam))
    out = [asamalar[0]]
    for s in asamalar[1:]:
        if s != out[-1]:
            out.append(s)
    for s in out:
        a, b = dogrusal(s)
        assert a == 0 and b == toplam, (s, toplam)
    return out


def saglama(sol, sag, x, v):
    lv, rv = ev(sol, x), ev(sag, x)
    assert lv == rv, (yaz(sol, v), yaz(sag, v), x, lv, rv)
    return "\n".join(
        [
            f"Sağlama: {v} = {x} değerini ilk denklemde yerine koyalım.",
            "Sol taraf: " + " = ".join(taraf_zinciri(sol, x)),
            "Sağ taraf: " + " = ".join(taraf_zinciri(sag, x)),
            "İki taraf eşit, çözüm doğru.",
        ]
    )


# --------------------------------------------------------------------------
# Sozel problem kaydi
# --------------------------------------------------------------------------

Sozel = namedtuple("Sozel", "sol sag metin intro ek aranan x0 alt")

V1_INTRO = "Bilinmeyen sayıya x diyelim."


def v1_sozel(sol, sag, metin, x0, alt="v1"):
    return Sozel(sol, sag, metin, V1_INTRO, f"aranan sayı {x0}", x0, x0, alt)


def asistan_metni(sol, sag, v, sozel=None):
    """(metin, cevap_str)"""
    adimlar, ozel, cumle, sonuc = cozum(sol, sag, v)
    beklenen = denklem_sonucu(sol, sag)
    if ozel is None:
        assert sonuc == beklenen, (yaz(sol, v), yaz(sag, v), sonuc, beklenen)
    else:
        assert ozel == beklenen
    satirlar = []
    if sozel is not None:
        assert v == "x"
        satirlar += [sozel.intro, ""]
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
    if sozel is not None:
        assert sonuc == sozel.x0, (sonuc, sozel)
        satirlar.append(f"Sonuç: {v} = {sonuc} ({sozel.ek})")
    else:
        satirlar.append(f"Sonuç: {v} = {sonuc}")
    return "\n".join(satirlar), str(sonuc)


# --------------------------------------------------------------------------
# Kullanici mesaji
# --------------------------------------------------------------------------

SABLONLAR = list(uret.SABLONLAR) + [
    "{eq} ise {v}?",
    "{v} için çöz: {eq}",
    "{eq} denkleminin kökü nedir?",
    "{eq} için {v} değerini hesapla.",
    "Merhaba, şu denklemde takıldım: {eq}. Yardım eder misin?",
    "ödevim var {eq} bunu çözer misin lütfen",
    "Çöz bakalım: {eq}",
    "{eq} bu denklemin çözümü nedir",
    "solve {eq}",
]
STILLER = uret.STILLER
BELIRTME = uret.BELIRTME
BUYUK_HARF_ORANI = 0.03


def kullanici_mesaji(rng, sol, sag, v):
    r = rng.random() * 100
    acc = 0
    stil = STILLER[0][0]
    for ad, w in STILLER:
        acc += w
        if r < acc:
            stil = ad
            break
    eq = uret.kullanici_denklem(sol, sag, v, stil)
    sablon = SABLONLAR[rng.randrange(len(SABLONLAR))]
    vv = v
    belirtme = BELIRTME[v]
    if rng.random() < BUYUK_HARF_ORANI:
        eq = eq.replace(v, v.upper())
        vv = v.upper()
        belirtme = belirtme[0].upper() + belirtme[1:]
    return sablon.format(eq=eq, v=vv, v_belirtme=belirtme)


# --------------------------------------------------------------------------
# Yeni denklem tipleri
# --------------------------------------------------------------------------


def g_t15(u, big, frac):
    """b - ax = d - cx (sabit basta, iki tarafta bilinmeyen)."""
    r = u.rng
    ca = r.choice([-1, 1]) * r.randint(1, 12)
    cc = r.choice([-1, 1]) * r.randint(1, 12)
    if ca == cc:
        return None
    b = u.const(big)
    if frac:
        d = u.const(big)
        if (d - b) % (ca - cc) == 0:
            return None
    else:
        d = b + (ca - cc) * u.sol(big)
        if d == 0 or abs(d) > u.cb(big):
            return None
    sol = [T(b, False), T(ca)]
    sag = [T(cc), T(d, False)] if r.random() < 0.5 else [T(d, False), T(cc)]
    return sol, sag


def g_t16(u, big, frac):
    """Uc ve daha fazla terimli karisik iki taraf: 2x + 5 - x = 3x - 7 + 4."""
    r = u.rng
    comps = [(1, 1), (2, 1), (1, 2), (2, 2)]
    agir = [1, 3, 3, 1]
    nvL, ncL = r.choices(comps, agir)[0]
    nvR, ncR = r.choices(comps, agir)[0]
    if nvL + ncL < 3 and nvR + ncR < 3:
        return None
    cL = [r.choice([-1, 1]) * r.randint(1, 9) for _ in range(nvL)]
    cR = [r.choice([-1, 1]) * r.randint(1, 9) for _ in range(nvR)]
    aL, aR = sum(cL), sum(cR)
    if aL == aR or aL == 0 or aR == 0:
        return None
    x0 = u.sol(big)
    kL = [u.const(big) for _ in range(ncL)]
    bL = sum(kL)
    bR = bL + (aL - aR) * x0
    cb = u.cb(big)
    if bL == 0 or bR == 0 or abs(bR) > cb:
        return None
    if ncR == 1:
        kR = [bR]
    else:
        ilk = u.const(big)
        kR = [ilk, bR - ilk]
        if kR[1] == 0 or abs(kR[1]) > cb:
            return None
    sol = [T(c) for c in cL] + [T(k, False) for k in kL]
    sag = [T(c) for c in cR] + [T(k, False) for k in kR]
    r.shuffle(sol)
    r.shuffle(sag)
    return sol, sag


# --------------------------------------------------------------------------
# Sozel problemler
# --------------------------------------------------------------------------

AD_TABLOSU = [
    ("Ali", "Ali'nin"),
    ("Ayşe", "Ayşe'nin"),
    ("Mehmet", "Mehmet'in"),
    ("Zeynep", "Zeynep'in"),
    ("Can", "Can'ın"),
    ("Elif", "Elif'in"),
    ("Emre", "Emre'nin"),
    ("Deniz", "Deniz'in"),
    ("Burak", "Burak'ın"),
    ("Selin", "Selin'in"),
]


def s_yas1(ad, a, x0):
    ad_, gen = ad
    c = a * x0
    metin = f"{gen} yaşının {a} katı {c} ise {ad_} kaç yaşındadır?"
    return Sozel([T(a)], [T(c, False)], metin, f"{gen} yaşına x diyelim.",
                 f"{ad_} {x0} yaşındadır", x0, x0, "yas1")


def s_yas2(ad, a, b, x0):
    ad_, gen = ad
    c = a * x0 + b
    metin = f"{gen} yaşının {a} katının {b} fazlası {c} ediyor. {ad_} kaç yaşındadır?"
    return Sozel([T(a), T(b, False)], [T(c, False)], metin, f"{gen} yaşına x diyelim.",
                 f"{ad_} {x0} yaşındadır", x0, x0, "yas2")


def s_yas3(ad, n, x0):
    ad_, gen = ad
    c = x0 + n
    metin = f"{ad_} {n} yıl sonra {c} yaşında olacak. {ad_} şimdi kaç yaşındadır?"
    return Sozel([T(1), T(n, False)], [T(c, False)], metin, f"{gen} yaşına x diyelim.",
                 f"{ad_} {x0} yaşındadır", x0, x0, "yas3")


def s_ard2(soru, x0, ediyor=False):
    s = 2 * x0 + 1
    kb = "Küçük" if soru == "kucuk" else "Büyük"
    deger = x0 if soru == "kucuk" else x0 + 1
    metin = f"Ardışık iki tam sayının toplamı {s}{' ediyor' if ediyor else ''}. {kb} sayı kaçtır?"
    return Sozel([T(1), T(1), T(1, False)], [T(s, False)], metin,
                 "Küçük sayıya x diyelim. Büyük sayı x + 1 olur.",
                 f"{kb.lower()} sayı {deger}", deger, x0, "ard2_" + soru)


def s_ard3(soru, x0):
    s = 3 * x0 + 3
    ad = {"kucuk": "Küçük", "ortanca": "Ortanca", "buyuk": "Büyük"}[soru]
    deger = {"kucuk": x0, "ortanca": x0 + 1, "buyuk": x0 + 2}[soru]
    metin = f"Ardışık üç tam sayının toplamı {s}. {ad} sayı kaçtır?"
    return Sozel([T(1), T(1), T(1, False), T(1), T(2, False)], [T(s, False)], metin,
                 "Küçük sayıya x diyelim. Ortanca sayı x + 1, büyük sayı x + 2 olur.",
                 f"{ad.lower()} sayı {deger}", deger, x0, "ard3_" + soru)


def s_cift(soru, x0):
    assert x0 % 2 == 0
    s = 2 * x0 + 2
    kb = "Küçük" if soru == "kucuk" else "Büyük"
    deger = x0 if soru == "kucuk" else x0 + 2
    metin = f"Ardışık iki çift sayının toplamı {s}. {kb} çift sayı kaçtır?"
    return Sozel([T(1), T(1), T(2, False)], [T(s, False)], metin,
                 "Küçük çift sayıya x diyelim. Büyük çift sayı x + 2 olur.",
                 f"{kb.lower()} çift sayı {deger}", deger, x0, "cift_" + soru)


def s_para(ad, a, b, x0):
    gen = ad[1]
    c = a * x0 + b
    metin = f"{gen} parasının {a} katının {b} TL fazlası {c} TL ediyor. {gen} kaç TL'si vardır?"
    return Sozel([T(a), T(b, False)], [T(c, False)], metin, f"{gen} parasına x TL diyelim.",
                 f"{gen} {x0} TL'si vardır", x0, x0, "para")


def s_yari(x0):
    c = x0 // 2
    return v1_sozel([T(F(1, 2))], [T(c, False)], f"Hangi sayının yarısı {c} eder?", x0, "yari")


def s_ucte(x0):
    c = x0 // 3
    return v1_sozel([T(F(1, 3))], [T(c, False)], f"Hangi sayının üçte biri {c} eder?", x0, "ucte")


def s_yari_fazla(b, x0):
    c = x0 // 2 + b
    return v1_sozel([T(F(1, 2)), T(b, False)], [T(c, False)],
                    f"Hangi sayının yarısının {b} fazlası {c} eder?", x0, "yari_fazla")


def s_ucte_eksik(b, x0):
    c = x0 // 3 - b
    return v1_sozel([T(F(1, 3)), T(-b, False)], [T(c, False)],
                    f"Hangi sayının üçte birinin {b} eksiği {c} eder?", x0, "ucte_eksik")


# v1'in 7 sozel kalibi (ardisik kucuk, yeni ardisik ailesine katildi)
def _a_v1_0(r, hi):
    x0, a, b = r.randint(1, hi), r.randint(2, 12), r.randint(1, 60)
    c = a * x0 + b
    return v1_sozel([T(a), T(b, False)], [T(c, False)],
                    f"Bir sayının {a} katına {b} eklenince sonuç {c} oluyor. Bu sayı kaçtır?", x0, "v1_0")


def _a_v1_4(r, hi):
    x0, a, b = r.randint(1, hi), r.randint(2, 12), r.randint(1, 60)
    c = a * x0 + b
    return v1_sozel([T(a), T(b, False)], [T(c, False)],
                    f"Hangi sayının {a} katının {b} fazlası {c} eder?", x0, "v1_4")


def _a_v1_1(r, hi):
    x0, a, b = r.randint(1, hi), r.randint(2, 12), r.randint(1, 60)
    c = a * x0 - b
    if c <= 0:
        return None
    return v1_sozel([T(a), T(-b, False)], [T(c, False)],
                    f"Bir sayının {a} katından {b} çıkarılınca sonuç {c} oluyor. Bu sayı kaçtır?", x0, "v1_1")


def _a_v1_5(r, hi):
    x0, a, b = r.randint(1, hi), r.randint(2, 12), r.randint(1, 60)
    c = a * x0 - b
    if c <= 0:
        return None
    return v1_sozel([T(a), T(-b, False)], [T(c, False)],
                    f"Hangi sayının {a} katının {b} eksiği {c} eder?", x0, "v1_5")


def _a_v1_2(r, hi):
    x0, a, b = r.randint(1, hi), r.randint(2, 12), r.randint(1, 20)
    c = a * (x0 + b)
    return v1_sozel([P(a, [T(1), T(b, False)])], [T(c, False)],
                    f"Bir sayıya {b} eklenip sonuç {a} ile çarpılınca {c} elde ediliyor. Bu sayı kaçtır?",
                    x0, "v1_2")


def _a_v1_3(r, hi):
    x0 = r.randint(1, hi)
    a = r.randint(3, 12)
    c = r.randint(2, a - 1)
    d = (a - c) * x0
    return v1_sozel([T(a)], [T(c), T(d, False)],
                    f"Bir sayının {a} katı, aynı sayının {c} katından {d} fazladır. Bu sayı kaçtır?",
                    x0, "v1_3")


def _a_v1_6(r, hi):
    x0 = 2 * r.randint(1, hi)
    b = r.randint(1, 60)
    c = x0 // 2 + b
    return v1_sozel([T(F(1, 2)), T(b, False)], [T(c, False)],
                    f"Bir sayının yarısına {b} eklenince sonuç {c} oluyor. Bu sayı kaçtır?", x0, "v1_6")


def _ad(r):
    return AD_TABLOSU[r.randrange(len(AD_TABLOSU))]


def _a_yas1(r, hi):
    return s_yas1(_ad(r), r.randint(2, 12), r.randint(1, min(hi, 90)))


def _a_yas2(r, hi):
    return s_yas2(_ad(r), r.randint(2, 12), r.randint(1, 30), r.randint(1, min(hi, 90)))


def _a_yas3(r, hi):
    return s_yas3(_ad(r), r.randint(1, 30), r.randint(1, min(hi, 90)))


def _a_ard2_k(r, hi):
    return s_ard2("kucuk", r.randint(1, hi), r.random() < 0.5)


def _a_ard2_b(r, hi):
    return s_ard2("buyuk", r.randint(1, hi), r.random() < 0.5)


def _a_ard3(soru):
    return lambda r, hi: s_ard3(soru, r.randint(1, hi))


def _a_cift(soru):
    return lambda r, hi: s_cift(soru, 2 * r.randint(1, hi))


def _a_para(r, hi):
    return s_para(_ad(r), r.randint(2, 12), r.randint(1, 60), r.randint(1, hi))


def _a_yari(r, hi):
    return s_yari(2 * r.randint(1, hi))


def _a_ucte(r, hi):
    return s_ucte(3 * r.randint(1, hi))


def _a_yari_fazla(r, hi):
    return s_yari_fazla(r.randint(1, 60), 2 * r.randint(1, hi))


def _a_ucte_eksik(r, hi):
    x0 = 3 * r.randint(1, hi)
    b = r.randint(1, 60)
    if x0 // 3 - b <= 0:
        return None
    return s_ucte_eksik(b, x0)


ALTLAR = [
    _a_v1_0, _a_v1_4, _a_v1_1, _a_v1_5, _a_v1_2, _a_v1_3, _a_v1_6,
    _a_yas1, _a_yas2, _a_yas3,
    _a_ard2_k, _a_ard2_b,
    _a_ard3("kucuk"), _a_ard3("ortanca"), _a_ard3("buyuk"),
    _a_cift("kucuk"), _a_cift("buyuk"),
    _a_para,
    _a_yari, _a_ucte, _a_yari_fazla, _a_ucte_eksik,
]


def g_sozel(u, big, frac):
    r = u.rng
    hi = 100 if big else 40
    k = r.choice(ALTLAR)(r, hi)
    if k is None:
        return None
    if not big and max(int(n) for n in re.findall(r"\d+", k.metin)) > 125:
        return None
    assert denklem_sonucu(k.sol, k.sag) == k.x0, k
    return k


# --------------------------------------------------------------------------
# Tip tablosu (v1 agirliklari 79/95 ile kucultuldu; t15 %8, t16 %3, sozel %10)
# --------------------------------------------------------------------------

_ESKI = [
    ("t1", 6, uret.g_t1),
    ("t2", 6, uret.g_t2),
    ("t3", 4, uret.g_t3),
    ("t4", 14, uret.g_t4),
    ("t5", 7, uret.g_t5),
    ("t6", 13, uret.g_t6),
    ("t7", 8, uret.g_t7),
    ("t8", 7, uret.g_t8),
    ("t9", 5, uret.g_t9),
    ("t10", 5, uret.g_t10),
    ("t11", 3, uret.g_t11),
    ("t12", 6, uret.g_t12),
    ("t13", 5, uret.g_t13),
    ("t14", 2, uret.g_t14),
    ("ozel_yok", 2, uret.g_ozel_yok),
    ("ozel_sonsuz", 2, uret.g_ozel_sonsuz),
]
assert sum(w for _, w, _ in _ESKI) == 95
_OLCEK = F(79, 95)
TIPLER = [(ad, F(w) * _OLCEK, g) for ad, w, g in _ESKI]
TIPLER[14:14] = [("t15", F(8), g_t15), ("t16", F(3), g_t16)]
TIPLER.append(("sozel", F(10), g_sozel))
assert sum(w for _, w, _ in TIPLER) == 100
KESIRLI_TIPLER = {"t4", "t6", "t7", "t13", "t15"}
KESIR_ORANI = 0.30


def kotalar(toplam):
    """En buyuk kalan yontemiyle tip kotalari."""
    ham = [F(toplam) * w / 100 for _, w, _ in TIPLER]
    taban = [int(h) for h in ham]
    kalan = toplam - sum(taban)
    sira = sorted(range(len(TIPLER)), key=lambda i: (-(ham[i] - taban[i]), i))
    for i in sira[:kalan]:
        taban[i] += 1
    return taban


# --------------------------------------------------------------------------
# Sizinti yasagi
# --------------------------------------------------------------------------


def yapi_anahtari(denklem, v, tip):
    """Harften bagimsiz yapi anahtari."""
    if tip == "sozel":
        return denklem
    return re.sub(r"(?<![A-Za-z])" + re.escape(v) + r"(?![A-Za-z])", "x", denklem)


def v1_yasaklari(dizin=None):
    """v1 val+test'teki kanonik denklemlerin (harften bagimsiz) ve sozel soru
    metinlerinin kumesi. Sozel kayitlarin alttaki 'Denklem:' satiri da dahildir."""
    dizin = dizin or VARSAYILAN_V1_DIZIN
    yasak = set()
    for ad in ("val", "test"):
        yol = os.path.join(dizin, ad + ".jsonl")
        with open(yol, encoding="utf-8") as f:
            for satir in f:
                s = json.loads(satir)
                meta = s["meta"]
                yasak.add(yapi_anahtari(meta["denklem"], meta["degisken"], meta["tip"]))
                if meta["tip"] == "sozel":
                    for ln in s["messages"][1]["content"].split("\n"):
                        if ln.startswith("Denklem: "):
                            yasak.add(ln[len("Denklem: "):])
    return yasak


# --------------------------------------------------------------------------
# Uretim
# --------------------------------------------------------------------------


def uret_hepsi(seed, n_train, n_val, n_test, v1_dizin=None):
    """Doner: ({'train':[...], 'val':[...], 'test':[...]}, istatistik)"""
    yasak = v1_yasaklari(v1_dizin)
    u = uret.Uretec(seed)
    rng = u.rng
    toplam = n_train + n_val + n_test
    gorulen = set()
    satirlar = []
    ist = {
        "tip": {},
        "cevap": {"tamsayi": 0, "kesir": 0, "yok": 0, "sonsuz": 0},
        "isaret": {"negatif": 0, "sifir": 0, "pozitif": 0},
        "buyuk": 0,
        "kesirli_tip_kesir": 0,
        "sozel_alt": {},
        "yasak_sayisi": len(yasak),
        "yasak_elenen": 0,
        "max_uzunluk": 0,
    }
    for (tip, _, gen), kota in zip(TIPLER, kotalar(toplam)):
        ist["tip"][tip] = kota
        for _ in range(kota):
            kesir = tip in KESIRLI_TIPLER and rng.random() < KESIR_ORANI
            dup = 0
            deneme = 0
            while True:
                deneme += 1
                if deneme > 200000:
                    raise RuntimeError(f"{tip}: yeterli benzersiz denklem üretilemedi")
                pb = 0.08 if dup < 40 else (0.5 if dup < 300 else 1.0)
                big = rng.random() < pb
                v = "x" if (tip == "sozel" or rng.random() < 0.8) else rng.choice(uret.DIGER_HARFLER)
                res = gen(u, big, kesir)
                if res is None:
                    continue
                if tip == "sozel":
                    sz = res
                    sol, sag = sz.sol, sz.sag
                    anahtar = sz.metin
                    yapi = sz.metin
                else:
                    sz = None
                    sol, sag = res
                    anahtar = esit(sol, sag, v)
                    yapi = esit(sol, sag, "x")
                if yapi in yasak:
                    ist["yasak_elenen"] += 1
                    dup += 1
                    continue
                if anahtar in gorulen:
                    dup += 1
                    continue
                break
            gorulen.add(anahtar)
            asistan, cevap = asistan_metni(sol, sag, v, sz)
            if sz is not None:
                kullanici = sz.metin
                aranan = str(sz.aranan)
                ist["sozel_alt"][sz.alt] = ist["sozel_alt"].get(sz.alt, 0) + 1
            else:
                kullanici = kullanici_mesaji(rng, sol, sag, v)
                aranan = cevap
            sonuc = denklem_sonucu(sol, sag)
            if cevap == "yok":
                ist["cevap"]["yok"] += 1
            elif cevap == "sonsuz":
                ist["cevap"]["sonsuz"] += 1
            else:
                ist["cevap"]["kesir" if "/" in cevap else "tamsayi"] += 1
                ist["isaret"]["negatif" if sonuc < 0 else ("sifir" if sonuc == 0 else "pozitif")] += 1
            if uret._buyuk_mu(sol, sag, sonuc):
                ist["buyuk"] += 1
            if tip in KESIRLI_TIPLER and "/" in cevap:
                ist["kesirli_tip_kesir"] += 1
            ist["max_uzunluk"] = max(ist["max_uzunluk"], len(asistan))
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
                            "aranan": aranan,
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
        for g in kalan:
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
    uret.yaz_jsonl(yol, satirlar)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Denklem çözme veri üreteci (v2)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--train", type=int, default=12000)
    ap.add_argument("--val", type=int, default=500)
    ap.add_argument("--test", type=int, default=600)
    ap.add_argument("--out", default=os.path.join("data", "v2"))
    ap.add_argument("--v1-data", default=None, help="v1 val/test klasörü (sızıntı yasağı)")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    bol, ist = uret_hepsi(args.seed, args.train, args.val, args.test, args.v1_data)
    os.makedirs(args.out, exist_ok=True)
    for ad, satirlar in bol.items():
        yaz_jsonl(os.path.join(args.out, f"{ad}.jsonl"), satirlar)
    for ad in ("train", "val"):
        yaz_jsonl(
            os.path.join(args.out, f"{ad}_messages.jsonl"),
            [{"messages": s["messages"]} for s in bol[ad]],
        )
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
    print("Cevap işareti (yok/sonsuz hariç):")
    for k, n in ist["isaret"].items():
        print(f"  {k:8s} {n:5d}")
    print(f"Büyük sayılı örnek: {ist['buyuk']} (%{100 * ist['buyuk'] / toplam:.2f})")
    print(f"Sözel alt dağılımı: {dict(sorted(ist['sozel_alt'].items()))}")
    print(f"Asistan metni en uzun: {ist['max_uzunluk']} karakter")
    print(f"v1 val+test yasak anahtar: {ist['yasak_sayisi']}, elenen aday: {ist['yasak_elenen']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

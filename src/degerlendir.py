"""Megazeka-Denklem değerlendirmesi: test.jsonl + elle yazılmış dağılım dışı sorular.

Kullanım (Unsloth Studio ortamının Python'u ile):
  python src/degerlendir.py --adapter <adaptör klasörü> --out reports/degerlendirme.json
"""
import argparse, json, re, time
from fractions import Fraction as F
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


# ---------- bağımsız doğrusal çözücü ----------
def lin(expr, v):
    s = expr.replace('−', '-').replace('*', '·').replace(' ', '')
    toks = re.findall(r'\d+|[a-zA-Z]|[()+\-/·]', s)
    if ''.join(toks) != s:
        raise ValueError('tanınmayan karakter')
    pos = [0]
    peek = lambda: toks[pos[0]] if pos[0] < len(toks) else None
    def take():
        t = toks[pos[0]]; pos[0] += 1; return t
    def mul(p, q):
        if p[0] and q[0]: raise ValueError('doğrusal değil')
        return (p[0] * q[1] + q[0] * p[1], p[1] * q[1])
    def expr_():
        sign = 1
        if peek() == '-': take(); sign = -1
        elif peek() == '+': take()
        r = term(); r = (sign * r[0], sign * r[1])
        while peek() in ('+', '-'):
            op = take(); t = term()
            r = (r[0] + t[0], r[1] + t[1]) if op == '+' else (r[0] - t[0], r[1] - t[1])
        return r
    def term():
        r = factor()
        while peek() is not None and (peek() in '/(·' or peek().isdigit() or peek().isalpha()):
            if peek() == '·':
                take(); r = mul(r, factor())
            elif peek() == '/':
                take(); q = factor()
                if q[0] or q[1] == 0: raise ValueError('bölme')
                r = (r[0] / q[1], r[1] / q[1])
            else:
                r = mul(r, factor())
        return r
    def factor():
        t = take()
        if t == '(':
            r = expr_()
            if take() != ')': raise ValueError('parantez')
            return r
        if t == '-':
            r = factor(); return (-r[0], -r[1])
        if t.isdigit(): return (F(0), F(int(t)))
        if t.lower() != v: raise ValueError('değişken')
        return (F(1), F(0))
    r = expr_()
    if pos[0] != len(toks): raise ValueError('artık')
    return r


def coz(eq, v):
    l, r = eq.split('=')
    a1, b1 = lin(l, v); a2, b2 = lin(r, v)
    a, b = a1 - a2, b2 - b1
    if a == 0: return 'sonsuz' if b == 0 else 'yok'
    x = b / a
    return str(x.numerator) if x.denominator == 1 else f'{x.numerator}/{x.denominator}'


def sonuc_oku(metin, v):
    m = re.search(r'^Sonuç: (.+)$', metin, re.M)
    if not m: return None
    s = m.group(1)
    if 'çözümü yoktur' in s: return 'yok'
    if 'sonsuz çözüm' in s: return 'sonsuz'
    m2 = re.match(rf'{re.escape(v)} = (-?\d+(?:/\d+)?)', s)
    return m2.group(1) if m2 else None


def aranan_oku(metin, v):
    """Sözelde sorunun istediği sayı: Sonuç parantezindeki son sayı, yoksa x değeri."""
    m = re.search(r'^Sonuç: (.+)$', metin, re.M)
    if not m: return None
    p = re.search(r'\(([^()]*)\)\s*$', m.group(1))
    if p:
        sayilar = re.findall(r'-?\d+(?:/\d+)?', p.group(1))
        if sayilar: return sayilar[-1]
    return sonuc_oku(metin, v)


def _sabit(ifade):
    a, b = lin(ifade, '§')
    if a: raise ValueError('değişkenli')
    return b


def saglama_dogru(metin):
    """Sağlama aritmetiği doğru mu. v2: 'Sol taraf: a = b = c' zincirleri; v1: tek satır.
    None = sağlama yok (özel durum ya da model yazmamış)."""
    zincir = re.findall(r'^(Sol|Sağ) taraf: (.+)$', metin, re.M)
    try:
        if zincir:
            son = []
            for _, z in zincir:
                deger = [_sabit(p) for p in z.split('=')]
                if len(set(deger)) != 1: return False
                son.append(deger[-1])
            return len(son) == 2 and son[0] == son[1]
        m = re.search(r'^Sağlama: .*? için sol taraf (.+?), sağ taraf (.+?)\. Eşitlik', metin, re.M)
        if not m: return None
        son = []
        for z in m.groups():
            deger = [_sabit(p) for p in z.split('=')]
            if len(set(deger)) != 1: return False
            son.append(deger[-1])
        return son[0] == son[1]
    except Exception:
        return False


def ara_satirlar_tutarli(metin, v, cevap):
    """Modelin yazdığı her ara denklem satırı aynı çözümü veriyor mu."""
    bozuk = []
    for ln in metin.split('\n'):
        if '=' not in ln or ln.startswith(('Sağlama', 'Sonuç', 'Bilinmeyen sadeleşti', 'Sol taraf', 'Sağ taraf')) or re.match(r'\d+\. adım', ln):
            continue
        ln = re.sub(r' \((?:çünkü|pay ve payda)[^()]*(?:\([^()]*\)[^()]*)*\)$', '', ln)
        satir = ln[len('Denklem: '):] if ln.startswith('Denklem: ') else ln
        try:
            r = coz(satir, v)
        except Exception:
            bozuk.append(ln); continue
        if cevap not in ('yok', 'sonsuz') and r != cevap:
            bozuk.append(ln)
    return bozuk


# ---------- dağılım dışı sorular (elle yazıldı; cevaplar çözücüyle hesaplanır) ----------
OOD = [
    ("2x+3=7 ise x?", "2x + 3 = 7", "x"),
    ("x için çöz: 4(x-1)=2x+6", "4(x - 1) = 2x + 6", "x"),
    ("5 = x - 3 ise x kaç", "5 = x - 3", "x"),
    ("Merhaba, şu denklemde takıldım: 7x - 4 = 3x + 12. Yardım eder misin?", "7x - 4 = 3x + 12", "x"),
    ("3X + 6 = 0", "3X + 6 = 0", "x"),
    ("ödevim var 2(3x+1)=4(x+2) bunu çözer misin lütfen", "2(3x + 1) = 4(x + 2)", "x"),
    ("x/5 - 1 = 3 denkleminin kökü nedir?", "x/5 - 1 = 3", "x"),
    ("10 - 2x = 4x - 8 için x değerini hesapla.", "10 - 2x = 4x - 8", "x"),
    ("Bir sayının 4 katının 7 eksiği 29 ediyor. Sayıyı bul.", "4x - 7 = 29", "x"),
    ("Ali'nin yaşının 3 katı 45 ise Ali kaç yaşındadır?", "3x = 45", "x"),
    ("y - 7 = -2y + 11", "y - 7 = -2y + 11", "y"),
    ("Çöz bakalım: 6t + 2 = 2(3t + 1)", "6t + 2 = 2(3t + 1)", "t"),
    ("5(x-2) = 5x + 1 denkleminin çözüm kümesini bul", "5(x - 2) = 5x + 1", "x"),
    ("(2x - 4)/3 = x - 3", "(2x - 4)/3 = x - 3", "x"),
    ("8x = 6", "8x = 6", "x"),
    ("x + 250 = 1000", "x + 250 = 1000", "x"),
    ("12 = 4(n - 2)", "12 = 4(n - 2)", "n"),
    ("-x - 9 = 3", "-x - 9 = 3", "x"),
    ("3x + 2x - 5 = 20 denklemini adım adım çöz", "3x + 2x - 5 = 20", "x"),
    ("x/2 + x/4 = 9", "x/2 + x/4 = 9", "x"),
    ("Bir sayının üç katına beş eklenince 26 oluyor, sayı kaç?", "3x + 5 = 26", "x"),
    ("2x + 7 = 2x + 7 bu denklemin çözümü nedir", "2x + 7 = 2x + 7", "x"),
    ("İki ardışık sayının toplamı 41 ise büyük sayı kaçtır?", "x + x + 1 = 41", "x", "21"),
    ("solve 3x - 9 = 0", "3x - 9 = 0", "x"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--adapter', required=True, help='yerel adaptör klasörü ya da HF depo adı')
    ap.add_argument('--base', default=None, help='taban model (varsayılan: adapter_config içindeki)')
    ap.add_argument('--test', default=str(KOK / 'data' / 'test.jsonl'))
    ap.add_argument('--out', default=str(KOK / 'reports' / 'degerlendirme.json'))
    ap.add_argument('--batch', type=int, default=32)
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    from peft import PeftModel

    from peft import PeftConfig
    base = args.base or PeftConfig.from_pretrained(args.adapter).base_model_name_or_path
    try:
        tok = AutoTokenizer.from_pretrained(args.adapter)
    except Exception:  # Hub'daki adaptör deposunda tokenizer yok; tabanınki aynıdır
        tok = AutoTokenizer.from_pretrained(base)
    tok.padding_side = 'left'
    model = AutoModelForCausalLM.from_pretrained(base, device_map='cuda', dtype=torch.bfloat16)
    model = PeftModel.from_pretrained(model, args.adapter).eval()

    def uret(prompts):
        out = []
        for i in range(0, len(prompts), args.batch):
            parca = prompts[i:i + args.batch]
            metin = [tok.apply_chat_template([{'role': 'user', 'content': p}], tokenize=False, add_generation_prompt=True) for p in parca]
            enc = tok(metin, return_tensors='pt', padding=True).to('cuda')
            with torch.no_grad():
                g = model.generate(**enc, max_new_tokens=600, do_sample=False, pad_token_id=tok.pad_token_id)
            out += [tok.decode(x[enc['input_ids'].shape[1]:], skip_special_tokens=True).strip() for x in g]
            print(f'  {min(i + args.batch, len(prompts))}/{len(prompts)}', flush=True)
        return out

    rows = [json.loads(l) for l in open(args.test, encoding='utf-8')]
    if args.limit: rows = rows[:args.limit]
    t0 = time.time()
    gen = uret([r['messages'][0]['content'] for r in rows])
    sure = time.time() - t0

    ayrinti, tip = [], {}
    for r, g in zip(rows, gen):
        m = r['meta']; v = m['degisken']; ref = r['messages'][1]['content']
        cev = sonuc_oku(g, v)
        bozuk = ara_satirlar_tutarli(g, v, m['cevap'])
        dogru = cev == m['cevap']
        if 'aranan' in m and m['aranan'] != m['cevap']:
            dogru = dogru and aranan_oku(g, v) == m['aranan']
        k = {'tip': m['tip'], 'soru': r['messages'][0]['content'], 'beklenen': m.get('aranan', m['cevap']), 'model': cev,
             'cevap_dogru': dogru, 'tam_eslesme': g == ref, 'bozuk_satir': bozuk, 'saglama_dogru': saglama_dogru(g)}
        if not k['tam_eslesme']: k['uretilen'] = g
        ayrinti.append(k)
        t = tip.setdefault(m['tip'], [0, 0]); t[0] += 1; t[1] += k['cevap_dogru']

    ood_gen = uret([o[0] for o in OOD])
    ood = []
    for (q, eq, v, *ara), g in zip(OOD, ood_gen):
        bek = ara[0] if ara else coz(eq, v.lower())
        cev = (aranan_oku(g, v.lower()) or aranan_oku(g, v)) if ara else (sonuc_oku(g, v.lower()) or sonuc_oku(g, v))
        ood.append({'soru': q, 'beklenen': bek, 'model': cev, 'cevap_dogru': cev == bek,
                    'saglama_dogru': saglama_dogru(g), 'uretilen': g})

    n = len(ayrinti)
    ozet = {
        'adapter': args.adapter, 'n_test': n, 'sure_sn': round(sure, 1),
        'cevap_dogru': sum(k['cevap_dogru'] for k in ayrinti),
        'tam_eslesme': sum(k['tam_eslesme'] for k in ayrinti),
        'ara_satir_hatasi_olan': sum(bool(k['bozuk_satir']) for k in ayrinti),
        'saglama_aritmetigi_dogru': f"{sum(k['saglama_dogru'] is True for k in ayrinti)}/{sum(k['saglama_dogru'] is not None for k in ayrinti)}",
        'yanlis_cevapta_saglama_tutuyor_diyor': sum((not k['cevap_dogru']) and bool(re.search(r'Eşitlik sağlanıyor|çözüm doğru', k.get('uretilen', ''))) for k in ayrinti),
        'tip_basina': {t: f'{d}/{a}' for t, (a, d) in sorted(tip.items())},
        'ood_dogru': f"{sum(o['cevap_dogru'] for o in ood)}/{len(ood)}",
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump({'ozet': ozet, 'test': ayrinti, 'ood': ood}, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(ozet, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()

# Megazeka-Denklem · Türkçe adım adım denklem çözücü

Birinci dereceden, tek bilinmeyenli denklemleri **Türkçe ve adım adım** çözen küçük bir dil modeli.
Her çözüm aynı düzeni izler: denklem → numaralı adımlar (ara hesaplar görünür) → bilinmeyeni yerine
koyarak **sağlama** → sonuç. [Qwen2.5-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct)
üzerine yerelde (RTX 4060, 8 GB) eğitilmiş bir **LoRA adaptörüdür**; çalışırken ağ bağlantısı ya da ücretli
bir yapay zekâ API'si kullanmaz. Kardeş projeleri: [Megazeka](https://github.com/pandakingpunc/megazeka)
(yazım düzeltici), [Megazeka-Sayı](https://github.com/pandakingpunc/megazeka-sayi) (sayı normalleştirici).

- Model: https://huggingface.co/pandakingpunc/megazeka-denklem-qwen2.5-1.5b-tr
- Veri: https://huggingface.co/datasets/pandakingpunc/megazeka-denklem-tr-steps

**Soru:** `bunu çözer misin 3(x+53)=4(x+62)`

```
Denklem: 3(x + 53) = 4(x + 62)

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

Sonuç: x = -89
```

Kapsam: tamsayı ve kesirli katsayılar, parantez, paydalı terimler, iki tarafta bilinmeyen, kesirli cevap,
"çözüm yok" ve "sonsuz çözüm" durumları, sayı/yaş/para/ardışık sayı sözel problemleri. Kullanıcı
denklemi boşluksuz (`3x+5=20`), yıldızlı (`3*x`), Unicode eksiyle ya da büyük harfli değişkenle yazabilir.
Kapsam dışı: ondalık sayılar, iki bilinmeyen, ikinci derece denklemler, eşitsizlikler.

## Sonuçlar

Değerlendirme: [`src/degerlendir.py`](src/degerlendir.py), açgözlü (greedy) çözümleme. "Doğru cevap" son
satırdaki değerin bağımsız bir kesir çözücüsüyle karşılaştırılmasıdır; sözel sorularda sorulan sayı
(ör. ardışık sayılarda **büyük** sayı) ayrıca denetlenir. "Sağlama hesabı doğru", modelin yazdığı sağlama
zincirindeki her eşitliğin gerçekten doğru olduğu çözümlerin oranıdır. Test denklemlerinin hiçbiri
eğitim verisinde yoktur (değişken harfi değiştirilmiş eşdeğerleri dahil).

| Küme | İlk deneme (iç ad v1) | **v1.0** |
|---|---:|---:|
| Test A: 500 denklem, 14 tip + sözel | 497/500 | **498/500** |
| Test A: sağlama hesabı doğru | %90,4 | **%97,3** |
| Test B: 600 denklem, yeni tipler ve sözel dahil | — | **600/600** |
| Test B: sağlama hesabı doğru | — | %94,6 |
| Elle yazılmış 24 dağılım dışı soru | 22/24 | **24/24** |

İlk denemede sağlama tek satırdı ve model değerleri hesaplamadan kopyalıyordu: yanlış cevaplarda bile
"Eşitlik sağlanıyor" yazıyordu. v1.0'da sağlama ve ara hesaplar adım adım yazıldı; sağlama hatası %9,6'dan
%2,7'ye indi. Ayrıntı: [`reports/degerlendirme-v2.md`](reports/degerlendirme-v2.md),
[`reports/degerlendirme-v1.md`](reports/degerlendirme-v1.md).

### Bilinen sınırlar

- **Sağlamaya körü körüne güvenmeyin.** Model zor bir hesapta yanılırsa (`1452/22 = 69`) sağlamayı yine
  "çözüm doğru" diye bitirebilir; kendi yazdığı kontrol tutmasa da durmaz. Test A'daki 2 yanlıştan biri böyle.
- Sağlama hatalarının çoğu (31'den 28'i) kesirli cevaplarda: tamsayı ile kesir tek hamlede toplanıyor
  (`31 + 108/7`). Cevabın kendisi bu örneklerde doğru.
- Test A'daki diğer yanlış bir okuma hatası: soru `11b/12 + 12 = 1`, model `11b/12 + 1 = 1` diye yazdı.
- Veri sentetik ve tek bir anlatım kalıbından; çok farklı sorulmuş sorularda, uzun metin problemlerinde ve
  kapsam dışı denklemlerde davranışı ölçülmedi.

## Kullanım

Adaptör, eğitimde kullanılan 4-bit tabanla ([unsloth/Qwen2.5-1.5B-Instruct-unsloth-bnb-4bit](https://huggingface.co/unsloth/Qwen2.5-1.5B-Instruct-unsloth-bnb-4bit),
yaklaşık 1,6 GB) en iyi sonucu verir. Bu taban NVIDIA ekran kartı ve `bitsandbytes` ister.

```bash
pip install torch transformers peft accelerate bitsandbytes
```

```python
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

taban = "unsloth/Qwen2.5-1.5B-Instruct-unsloth-bnb-4bit"
tok = AutoTokenizer.from_pretrained(taban)
model = AutoModelForCausalLM.from_pretrained(taban, dtype=torch.bfloat16, device_map="cuda")
model = PeftModel.from_pretrained(model, "pandakingpunc/megazeka-denklem-qwen2.5-1.5b-tr")

soru = "2(3x + 1) = 4(x + 2) denklemini çöz."
metin = tok.apply_chat_template([{"role": "user", "content": soru}], tokenize=False, add_generation_prompt=True)
girdi = tok(metin, return_tensors="pt").to(model.device)
cikti = model.generate(**girdi, max_new_tokens=600, do_sample=False)
print(tok.decode(cikti[0][girdi["input_ids"].shape[1]:], skip_special_tokens=True))
```

Sistem mesajı vermeyin (eğitimde yoktu; Qwen şablonu kendi varsayılanını ekler). Açgözlü çözümleme
(`do_sample=False`) önerilir.

**Ekran kartı yoksa** taban olarak orijinal `Qwen/Qwen2.5-1.5B-Instruct` verilebilir (`device_map="cpu"`,
`dtype=torch.float32`; yavaştır). Adaptör 4-bit taban üzerinde eğitildiği için doğruluk biraz düşer: Test B'nin
ilk 200 sorusunda 4-bit taban 200/200, orijinal bf16 taban 196/200 (hataların ikisi Unicode eksi `−` ile
yazılmış sorularda).

## Yeniden üretme

```bash
# Veri (yalnız standart kütüphane; aynı tohum aynı baytları üretir)
python src/uret.py --seed 42 --train 8000 --val 400 --test 500 --out data          # Test A ve ilk deneme verisi
python src/uret_v2.py --seed 7 --train 12000 --val 500 --test 600 --out data/v2    # v1.0 verisi, Test B
python -m unittest tests.test_uret tests.test_uret_v2                               # 56 test

# Eğitim (Unsloth kurulu bir ortamda; ~65 dk, RTX 4060)
python -X utf8 training/train.py --config configs/v2.json --ad v2

# Değerlendirme (eğitim sonunda kendiliğinden de çalışır)
python -X utf8 src/degerlendir.py --adapter models/v2 --test data/test.jsonl --out reports/degerlendirme-v2-v1test.json
```

Eğitim: 4-bit QLoRA, LoRA r 16 / alfa 32, tüm doğrusal katmanlar, LR 2e-4 (doğrusal, 50 adım ısınma),
3 epoch, toplu iş 8 × birikim 2, bağlam 1024, yalnız asistan yanıtında kayıp. 12.000 eğitim örneği,
2.250 adım; doğrulama kaybı 0,0015 → 0,0007. Kayıp geçmişi: [`reports/gecmis-v2.jsonl`](reports/gecmis-v2.jsonl).

**Sürüm adları:** depo içindeki dosyalar iç adları taşır. İlk deneme (`src/uret.py`, Unsloth Studio ile
eğitildi) "v1", yayımlanan model "v2" diye geçer (`src/uret_v2.py`, `configs/v2.json`,
`reports/degerlendirme-v2*.`). Yayın etiketi **v1.0**, iç adı v2 olan modeldir.

## Lisans

- Kod: [MIT](LICENSE)
- Model adaptörü: Apache-2.0 (taban model Qwen2.5-1.5B-Instruct'ın lisansı)
- Veri: CC0-1.0

Yazar: Mustafa Karatüm ([ORCID 0009-0006-7053-2872](https://orcid.org/0009-0006-7053-2872))

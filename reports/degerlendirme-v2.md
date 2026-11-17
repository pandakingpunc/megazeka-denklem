# Megazeka-Denklem v2 değerlendirmesi (2026-11-17)

**Eğitim:** kendi betiğimiz, `training/train.py --config configs/v2.json --ad v2`, Unsloth 2026.11.5 / TRL 0.23.1.
- Model: Qwen2.5-1.5B-Instruct 4-bit + LoRA r16/α32, LR 2e-4, 3 epoch, 8×2, 2.250 adım, yalnız asistan yanıtı eğitildi.
- Veri: `src/uret_v2.py --seed 7`, 12.000 eğitim / 500 doğrulama / 600 test. Bu üç bölmede v1'in test/val denklemleri yok.
- Değerlendirme kaybı 0,0015 (adım 250) → 0,0007 (adım 2250), monoton düştü. En iyi kontrol noktası son adım; `models/v2` ile `models/v2-best` aynı adım.
- Eğitim log'u: `reports/gecmis-v2.jsonl`, `reports/egitim-v2.log`.

## v1 ile karşılaştırma

| Ölçüt | v1 | v2 |
|---|---|---|
| v1 testi (500), doğru cevap | 497 | **498** |
| v1 testi, sağlama hesabı doğru | 443/490 (%90,4) | **477/490 (%97,3)** |
| v1 testi, yanlış cevapta "sağlanıyor" diyen | 3 | 2 |
| v2 testi (600, yeni tipler dahil), doğru cevap | — | **600/600** |
| v2 testi, sağlama hesabı doğru | — | 543/574 (%94,6) |
| Elle yazılmış 24 dağılım dışı soru | 22/24 | **24/24** |

Tam metin eşleşmesi v1 testinde anlamsız, çünkü biçim değişti. v2 testinde 569/600.

## Kalan hatalar
- **v1 testindeki 2 yanlış:**
  - `11b/12 + 12 = 1` sorusunu `11b/12 + 1 = 1` diye kopyaladı. Kendi denklemini doğru çözdü; hata soruyu okumada.
  - `11(x + 36) = -11(x - 168)`: 11·36 artık doğru, ama 1452/22'yi 69 buldu (doğrusu 66). Kendi yazdığı "çünkü 22·69 = 1498" kontrolü tutmuyor, yine de devam etti. Sağlamada sağ tarafı kopyaladı.
- **Sağlama hatalarının 28/31'i kesirli cevapta.** v2 testindeki 74 kesirli cevabın 28'inde sağlama hesabı yanlış. Tamsayı cevaplarda bu oran 3/500.
  - Hata hep tamsayı + kesir toplamında: `31 + 108/7 = 359/7` (doğrusu 325/7).
  - Model bu adımı ortak paydaya çevirmeden tek hamlede yapıyor, sonra sağ tarafa aynı sonucu kopyalıyor.
- Model kendi "çünkü" ve sağlama kontrolü tutmadığında durup düzeltmeyi bilmiyor. Veride hiç tutmayan kontrol örneği yok.

## v3 için öneriler
1. Kesirli sağlamada ortak payda adımını yaz: `31 + 108/7 = 217/7 + 108/7 = 325/7`.
2. "Kontrol tutmadı → geri dön" örnekleri: kasıtlı bir aritmetik kayması, ardından `çünkü 22·69 = 1518, 1452 değil; yeniden bölelim: x = 66`. Bu, modele tutarsızlığı fark edip düzeltmeyi öğretebilir. Riski: model gereksiz yere geri dönmeyi de öğrenebilir; az oranda (%5) eklenmeli.
3. Kopyalama hatası için "Denklem:" satırının kullanıcı yazımıyla birebir aynı olduğunu ölçen ayrı bir metrik.

# Megazeka-Denklem v1 değerlendirmesi (2026-11-17)

Model: Qwen2.5-1.5B-Instruct + QLoRA (r16, α32, LR 2e-4, 3 epoch, 8×2, 1.500 adım, bağlam 1024), Unsloth Studio.
Adaptör: `Unsloth Studio çıktısı, yerelde models/v1`
Eğitim kaybı 0,0001; değerlendirme kaybı 0,0034 → 0,0015, sonra düz (ezber belirtisi yok).
Komut: `src/degerlendir.py` (greedy, batch 32, bf16). Ham çıktı: `reports/degerlendirme-v1.json`.

## Sonuçlar

| Ölçüt | Sonuç |
|---|---|
| Test (500 görülmemiş denklem), son cevap doğru | **497/500 (%99,4)** |
| Test, metin referansla birebir aynı | 452/500 (%90,4) |
| Doğru cevaplı ama Sağlama satırındaki ara değer yanlış | 44/497 (%8,9) |
| Ara denklem satırı tutarsız | 3/500 |
| Elle yazılmış 24 dağılım dışı soru | **22/24** (betik 23 dedi; ardışık sayı sorusunu elle düzelttim) |

Tip başına: t4 60/61, t9 23/24, t12 22/23; diğer tüm tipler, özel durumlar ve sözel %100.

## Hatalar

**Yanlış cevaplar (3/500), üçü de tek adımlı aritmetik kayması:**
- `4x + 188 - 7x - 127 = 181`: 4x - 7x'i `-x` yazdı (doğrusu -3x). Model -120 buldu, doğrusu -40.
- `11(x + 36) = -11(x - 168)`: 11·36'yı 404 yazdı (doğrusu 396).
- `6x - 29 = 34`: 63/6'yı 7 yazdı (doğrusu 21/2).

**Sağlama güvenilmez.** Üç yanlış cevapta da "Eşitlik sağlanıyor" yazdı. 44 doğru cevapta ise Sağlama değerleri yanlış (ör. 3·(-36) = -132), ama iki tarafa hep aynı sayıyı yazıyor. Model sağlamayı hesaplamıyor, kalıbı kopyalıyor. Bunun iki sebebi olabilir:
- Veride hiç başarısız sağlama örneği yok.
- Sağlama tek satırda, ara adımsız çok basamaklı bir hesap istiyor.

**Dağılım dışı (2/24):**
- "Ali'nin yaşının 3 katı 45": 15'i doğru buldu ama Sonuç satırını bozdu ("Ali 15 ile ilgili"). Yaş problemi şablonu veride yok.
- "İki ardışık sayının toplamı 41 ise **büyük** sayı": 20 dedi, doğrusu 21. Veride hep küçük sayı soruluyor.

**Not:** Kısa denemede (batch 8) `10 - 2x = 4x - 8` yanlıştı, uydurma sağlamayla -5/3 çıktı. Tam koşuda (batch 32) aynı soru doğru çıktı. Greedy çıktı batch dolgusuna göre değişebiliyor. Bu tipteki denklemler (sabit başta, iki tarafta bilinmeyen) eğitim verisinde yok.

## v2 için öneriler
1. Sağlamayı ara adımlı yaz: `3·(-89 + 53) = 3·(-36) = -108`.
2. Aritmetiği görünür yap: benzer terimde `4x - 7x = -3x`, çarpımda `11·36 = 396`.
3. Eksik kalıpları ekle: `b - ax = cx + d`, yaş/para/ardışık sayı problemleri ("büyük sayı" soruları dahil).
4. İstersen: model yanlış bulduğunda sağlamanın tutmadığını gösteren düzeltme örnekleri (riskli; önce 1-3).

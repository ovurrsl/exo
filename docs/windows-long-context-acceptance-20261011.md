# Windows RAM offload: uzun bağlam kabulü — 11 Ekim 2026

Kaynak düzeltmesi: `1df687aa`, ayrı dal: `work/windows-long-context-acceptance`.
Hedef RTX 5070, 12 GiB VRAM ve 48 GB RAM. Model:
`mlx-community/Qwen3-32B-4bit`, snapshot
`bcaaf7f538adf166c1080a2befdb4f6019f66639`.

Kısa sohbetlerin geçmesi 8K bağlamın çalıştığını kanıtlamadı. Gerçek uzun
girdide aşama öncesi boş VRAM kontrolü hata verdi. CUDA havuzunda kullanılan
baytlar, kalıcı ağırlıklar + materyalize KV + geçerli hidden tensoruyla tam
eşleşiyordu. Kullanılmayan fakat havuzdan geri alınamayan fiziksel alan vardı.
Bu ölçüm tensor sızıntısı yerine havuz parçalanmasını destekliyor; sistemdeki
havuz dışı GPU kullanımının tamamının kaynağı bu deneyle belirlenmedi.

| Kontrollü kaynak deneyi | Sonuç |
| --- | --- |
| Önceki dinamik KV + 256 MiB fiziksel pay | 8K hata; yaklaşık 268 MiB kullanılmayan havuz rezervi |
| Sabit KV tek başına | 8K hata; yaklaşık 93 MiB kullanılmayan havuz rezervi |
| 512 MiB fiziksel pay tek başına | 8K hata; yaklaşık 471 MiB kullanılmayan havuz rezervi |
| Sabit KV + 512 MiB fiziksel pay | 8K doğru yanıt, üretim, iptal ve normal kapanış |

Yeni Windows offload yolu isteğin başında context sınırına yuvarlanmış KV
alanını GPU üzerinde ayırıyor. Tahsis/evaluation başarısızsa yeni sahipler ve
bellek kredileri temizleniyor; aynı cache yeniden kaydedilince tekrar tahsis
yapılmıyor. Fiziksel pay katalog ve yükleyici tarafından aynı sabitten
alınıyor. Gerçek boş NVML belleği her aşamada kontrol edilmeye devam ediyor;
2,5 GiB runtime rezervi azaltılmadı. Mac kaynakları ve Mac çalışma yolu bu
değişiklikte düzenlenmedi.

Deney kancaları olmayan gerçek kaynak kabulünde:

- Altı kısa Türkçe isteğin altısı da `Kırmızı`, `stop` yanıtı verdi. Bu altı
  yanıt ayrıca bağımsız olarak elle incelendi.
- 8.122 giriş tokenı, 11 çıktı tokenı: `The color of the apple is **red**.`,
  `stop`; toplam 8.133 token.
- İki SSE üretimi: ayrı ayrı 64 çıktı tokenı, `length`, `[DONE]`; sunucunun
  üretim tokenı sayısı API çıktı sayısıyla eşleşti. Decode hızları
  **0,97503 ve 0,96418 token/s**. Giriş tokenı sayaçlarında API 30/sunucu 31
  farkı bulunduğundan bütün sayaçların aynı olduğu iddia edilmiyor.
- İptal sonrası `Hello!`, `stop`; runner ve node çıkış kodları 0.
- Son dört kısa istek ölçümünde süreç ağacı RSS aralığı 479.232 bayt, private
  aralığı 235.388.928 bayt. Bu sınırlı gözlem bellek sızıntısı olmadığının
  kanıtı değildir. NVML ölçümü sistem genelidir; MLX peak bellek toplamı
  doğrudan adanmış VRAM olarak yorumlanmamalıdır.
- 906 test geçti; 8 atlandı, 195 yavaş test varsayılan seçim dışında kaldı.
  Gerçek CUDA referans/logit/KV karşılaştırmalarında ayrıca 2 test geçti.
  Windows ve Darwin tip kontrolleri 0 hata; Ruff ve biçim kontrolü geçti.

Yerel kaynak kanıtları:
`build/acceptance/qwen3-32b-long-context-production/inference.json` ve
`node.log`; tam test, tip ve GPU parity kayıtları aynı `build/acceptance`
dizinindedir. Bunlar kaynak kabulüdür. Yeni frozen runtime, masaüstü runtime
dağıtımı ve yükleyici için kabul ayrı kaydedilmelidir. İmzalı yükleyici ve
Mac küme testi bu raporun kabul kapsamına dahil değildir.

32B RAM offload hâlâ yaklaşık 1 token/s sınıfındadır. Bu sonuç VRAM'e tamamen
sığan model hızına eşdeğer değildir; 8K doğrulaması da tüm Qwen boyutları veya
başka mimariler için genel destek kanıtı değildir.

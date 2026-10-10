# Windows CUDA vision ve görüntü kabulü — 10 Ekim 2026

Güncel review kurucusuna paketlenen frozen runtime, **tek RTX 5070 üzerinde gerçek HTTP vision, FLUX üretim/düzenleme ve iptal sonrası toparlanma testlerini geçti**. Runtime kaynak commit'i **`7d11c690b321169fde843d90bc1884780731cd1a`**, MLX **`0.32.3.dev20261009+win.3`**. Engine ve runtime manifest hash'leri, `f99234db` GUI ile derlenen kurucunun yerel kimlik kaydıyla aynı bulundu. Eski paketin kabulü bu yeni runtime'a taşınmadı.

## Gerçek test sonuçları

| Kontrol                         | Sonuç ve sınır                                                                                                                                           |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Qwen3-VL-4B-Instruct-4bit       | İki ayrı görüntülü `/v1/chat/completions` isteği, sentetik 112×112 kırmızı görüntüyü **“Red”** olarak tanıdı. İki yanıt da `stop` ile sonlandı.          |
| FLUX.1-schnell-4bit yerleştirme | `/instance/previews` ve `/instance` yolu gerçekten kullanıldı; tek CUDA rank'ı için **6.693.214.336 bayt** ağırlık bütçesi doğrulandı.                   |
| Üretim ve iptal/toparlanma      | İlk üretim, gerçek partial PNG sonrası client disconnect ve sonraki üretim geçti.                                                                        |
| Düzenleme ve girdi etkisi       | Sentetik kırmızı/mavi 512×512 girdiler farklı final PNG hash'leri üretti; input conditioning devredeydi.                                                 |
| Düzenleme iptali/toparlanması   | Gerçek partial PNG sonrası iptal ve aynı seed/girdiyle tekrar geçti; yeniden üretilen final PNG, iptal öncesi eş koşullu düzenlemeyle aynı hash'i verdi. |
| Görüntü sayısı                  | Yedi görev: beş tamamlanmış final PNG ve iki iptal edilmiş görev. PNG'ler 512×512, çözümlenebilir ve düz renk olmayan çıktılardı.                        |
| Süreç kapanışı                  | İki deneyde de node ve spawned worker normal çıkış **0**; zorla temizleme veya shutdown hatası yok.                                                      |

Testler ayrı namespace, rastgele portlar ve workspace veri dizinleri kullandı. Model snapshot'ları mevcut salt okunur kabul dizininden yüklendi; kullanıcının modeli, çalışan uygulaması veya API varsayılanı **52415** değiştirilmedi. Normal chat şemasının tanımadığı `use_prefix_cache` alanı, bu vision deneyinin açık prefix-cache seçeneği kabulü sayılmaz; [LAN raporundaki](windows-lan-acceptance-20261010.md) benchmark testi bu seçeneği ayrıca doğrular.

## Kanıt ve kalan kapsam

Yerel `build/acceptance/` kayıtları:

- `vision-upstream-integrated-20261010/inference.json`, `node.log`: iki vision yanıtı ve normal worker kapanışı;
- `image-upstream-integrated-20261010/inference.json`, `node.log` ve 12 partial/final PNG: görev sonuçları, input etkisi, iptal ve tekrar;
- `windows-upstream-integrated-media-identity-20261010.json`: engine/manifest/wheel, helper ve iki raporun SHA-256 kimlikleri;
- `windows-panel-controls-installer-artifact-20261010.json`: aynı runtime'ı içeren imzasız kurucu kimliği.

Bu kabul tek CUDA düğümü, mevcut iki model snapshot'ı ve sentetik girdilerle sınırlıdır. Karma Mac–Windows vision/image pipeline, mask/inpaint, başka model ailesi, maksimum context/VRAM basıncı, geliştirme araçları olmayan temiz Windows kurulumu ve imzalı yayın kabulü açık kalır. `release_ready=false` korunur. Mac Swift/Metal/JACCL kaynakları bu testlerde değiştirilmedi.
